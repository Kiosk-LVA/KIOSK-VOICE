import io
import os
import re
import time
import struct
import logging
from pathlib import Path
from typing import Tuple, List, Optional
import numpy as np
import soundfile as sf
from v_tts import TTS
from app.config import settings
from app.cache import cache_manager

logger = logging.getLogger("kiosk-tts.engine")

def create_wav_header(
    sample_rate: int = 24000,
    num_channels: int = 1,
    bits_per_sample: int = 16,
    data_size: int = 0x7FFFFFFF
) -> bytes:
    """
    Generates a 44-byte WAV header configured for continuous PCM audio streaming.
    """
    byte_rate = sample_rate * num_channels * (bits_per_sample // 8)
    block_align = num_channels * (bits_per_sample // 8)
    file_size = 36 + data_size if data_size < 0x7FFFFFFF else 0x7FFFFFFF

    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF',
        file_size,
        b'WAVE',
        b'fmt ',
        16,                # Subchunk1Size (16 for PCM)
        1,                 # AudioFormat (1 for PCM)
        num_channels,      # NumChannels (1 = Mono)
        sample_rate,       # SampleRate (24000)
        byte_rate,         # ByteRate
        block_align,       # BlockAlign
        bits_per_sample,   # BitsPerSample (16)
        b'data',
        data_size          # Subchunk2Size
    )
    return header

def split_text_into_chunks(text: str, max_chunk_len: int = 35) -> List[str]:
    """
    Splits normalized Vietnamese text into short clauses/chunks for low-latency streaming TTS.
    """
    clean_text = text.strip()
    if not clean_text:
        return []

    # 1. Split by punctuation (, . ; ! ? \n -)
    raw_parts = [p.strip() for p in re.split(r'[,.;!?\n\-]+', clean_text) if p.strip()]

    final_chunks = []
    for part in raw_parts:
        if len(part) <= max_chunk_len:
            final_chunks.append(part)
        else:
            # Sub-split long clause if > max_chunk_len
            words = part.split()
            current_words = []
            current_len = 0
            for w in words:
                w_len = len(w) + 1
                if current_len + w_len > max_chunk_len and current_words:
                    final_chunks.append(" ".join(current_words))
                    current_words = [w]
                    current_len = len(w)
                else:
                    current_words.append(w)
                    current_len += w_len
            if current_words:
                final_chunks.append(" ".join(current_words))

    return [c for c in final_chunks if c]

class TTSEngineManager:
    def __init__(self):
        self.tts: Optional[TTS] = None
        self._is_ready = False

    def load_model(self):
        logger.info("Initializing V-TTS engine...")
        start_time = time.time()
        
        # 1. Determine model path
        model_path = None
        if settings.MODEL_PATH:
            model_path = settings.MODEL_PATH
        else:
            # Auto-check if local models directory exists
            local_model_dir = Path("./models/vits-vietnamese")
            if local_model_dir.exists() and (local_model_dir / "config.json").exists():
                model_path = str(local_model_dir)
                logger.info(f"Detected pre-downloaded local model at: '{model_path}'")

        # 2. Initialize TTS
        self.tts = TTS(
            model_path=model_path,
            device=settings.DEVICE
        )
        self._is_ready = True
        elapsed = time.time() - start_time
        logger.info(f"V-TTS engine loaded successfully in {elapsed:.2f}s! Available speakers: {self.get_speakers()}")

        # 3. Warmup TTS engine to pre-allocate memory and initialize PyTorch computational graph
        logger.info("Warming up V-TTS engine with a dummy inference...")
        try:
            warmup_speaker = self.get_speakers()[0] if self.get_speakers() else "NF"
            _ = self.tts.synthesize("Khởi động", speaker=warmup_speaker)
            logger.info("V-TTS engine warmup completed successfully!")
        except Exception as e:
            logger.error(f"V-TTS engine warmup failed: {e}")

    def is_ready(self) -> bool:
        return self._is_ready and self.tts is not None

    def get_speakers(self) -> List[str]:
        if not self.tts:
            return []
        return self.tts.list_speakers()

    def synthesize_stream_generator(
        self,
        text: str,
        speaker: Optional[str] = None,
        speed: Optional[float] = None
    ):
        """
        Synthesizes text in low-latency chunks and yields continuous WAV PCM audio bytes.
        First chunk arrives in ~350-400ms. Subsequent chunks stream seamlessly.
        Saves full combined WAV file to Redis cache when complete.
        """
        if not self.tts:
            raise RuntimeError("TTS Engine is not initialized")

        target_speaker = speaker or settings.DEFAULT_SPEAKER
        target_speed = speed if speed is not None else settings.DEFAULT_SPEED
        speakers_list = self.get_speakers()
        if target_speaker not in speakers_list and speakers_list:
            target_speaker = speakers_list[0]

        start_time = time.time()

        from src.vietnamese.text_processor import process_vietnamese_text
        norm_text = process_vietnamese_text(text)
        chunks = split_text_into_chunks(norm_text)

        logger.info(f"Chunk Streaming TTS start for '{text[:30]}...' -> {len(chunks)} chunks: {chunks}")

        sample_rate = 24000
        header_sent = False
        all_audio_segments = []

        for idx, chunk_text in enumerate(chunks):
            chunk_start = time.time()

            # Kiểm tra chunk-level cache trước (pre-warm hoặc từ lần synthesis trước)
            cached_chunk_wav = cache_manager.get_audio(chunk_text, target_speaker, target_speed)
            if cached_chunk_wav:
                # Đọc PCM từ WAV bytes (bỏ qua 44-byte WAV header)
                pcm_bytes = cached_chunk_wav[44:]
                audio_array = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32767.0
                sample_rate = 24000
                logger.debug(f"Chunk {idx+1}/{len(chunks)} cache HIT: '{chunk_text[:20]}' (~1ms)")
            else:
                audio_array, sr = self.tts.synthesize(
                    text=chunk_text,
                    speaker=target_speaker,
                    speed=target_speed,
                )
                sample_rate = sr

                if len(audio_array) > 0:
                    # Peak normalization to 0.98
                    max_val = np.max(np.abs(audio_array))
                    if max_val > 0:
                        audio_array = (audio_array / max_val) * 0.98

                # Lưu chunk vào cache để pre-warm hoặc lần sau dùng lại
                if len(audio_array) > 0:
                    chunk_byte_io = io.BytesIO()
                    sf.write(chunk_byte_io, audio_array, sample_rate, format='WAV', subtype='PCM_16')
                    cache_manager.set_audio_with_ttl(
                        chunk_text, target_speaker, target_speed,
                        chunk_byte_io.getvalue(), settings.KIOSK_CACHE_TTL
                    )

            if len(audio_array) > 0:
                # 5ms crossfade on edges to prevent pop/click artifacts (120 samples @ 24kHz)
                fade_len = min(120, len(audio_array) // 2)
                if fade_len > 0:
                    fade_in = np.linspace(0.0, 1.0, fade_len)
                    fade_out = np.linspace(1.0, 0.0, fade_len)
                    audio_array[:fade_len] *= fade_in
                    audio_array[-fade_len:] *= fade_out

                all_audio_segments.append(audio_array)

                # Float32 [-1, 1] to Int16 PCM bytes
                pcm_bytes = (audio_array * 32767).astype(np.int16).tobytes()

                if not header_sent:
                    yield create_wav_header(sample_rate=sample_rate)
                    header_sent = True
                    first_chunk_latency = time.time() - start_time
                    logger.info(f"⚡ First audio chunk sent in {first_chunk_latency*1000:.1f}ms! (Chunk 1/{len(chunks)})")

                yield pcm_bytes
                chunk_time = time.time() - chunk_start
                logger.debug(f"Chunk {idx+1}/{len(chunks)} done in {chunk_time*1000:.1f}ms")

                # Chèn silence giữa các chunk (trừ chunk cuối)
                if idx < len(chunks) - 1 and settings.CHUNK_PAUSE_MS > 0:
                    silence_samples = int(sample_rate * settings.CHUNK_PAUSE_MS / 1000)
                    all_audio_segments.append(np.zeros(silence_samples, dtype=np.float32))
                    yield bytes(silence_samples * 2)  # Int16 = 2 bytes/sample, toàn số 0

        total_process_time = time.time() - start_time

        # Save full audio to Redis cache
        if all_audio_segments:
            full_audio = np.concatenate(all_audio_segments)
            audio_duration = len(full_audio) / float(sample_rate)
            rtf = total_process_time / audio_duration if audio_duration > 0 else 0.0

            logger.info(
                f"✅ Chunk Streaming completed '{text[:30]}...' -> Audio: {audio_duration:.2f}s | Total: {total_process_time:.2f}s (RTF: {rtf:.2f})"
            )

            byte_io = io.BytesIO()
            sf.write(byte_io, full_audio, sample_rate, format='WAV', subtype='PCM_16')
            full_wav_bytes = byte_io.getvalue()
            cache_manager.set_audio(text, target_speaker, target_speed, full_wav_bytes)

    def synthesize_wav(
        self,
        text: str,
        speaker: Optional[str] = None,
        speed: Optional[float] = None
    ) -> Tuple[bytes, float, float]:
        """
        Synthesizes text into audio and encodes it directly as WAV bytes in memory.
        Returns: Tuple[wav_bytes, duration_in_seconds, process_time_in_seconds]
        """
        if not self.tts:
            raise RuntimeError("TTS Engine is not initialized")

        target_speaker = speaker or settings.DEFAULT_SPEAKER
        target_speed = speed if speed is not None else settings.DEFAULT_SPEED
        speakers_list = self.get_speakers()
        if target_speaker not in speakers_list and speakers_list:
            logger.warning(f"Speaker '{target_speaker}' not found. Fallback to '{speakers_list[0]}'")
            target_speaker = speakers_list[0]

        start_time = time.time()

        # Normalize text (auto-insert commas for kiosk announcements, number expansion, etc.)
        from src.vietnamese.text_processor import process_vietnamese_text
        norm_text = process_vietnamese_text(text)

        # Single model inference — fastest path (~2.7s on CPU)
        audio_array, sample_rate = self.tts.synthesize(
            text=norm_text,
            speaker=target_speaker,
            speed=target_speed,
        )

        # Peak normalization to 0.98 — maximize loudness without clipping
        max_val = np.max(np.abs(audio_array))
        if max_val > 0:
            audio_array = (audio_array / max_val) * 0.98

        process_time = time.time() - start_time
        audio_duration = len(audio_array) / float(sample_rate)
        rtf = process_time / audio_duration if audio_duration > 0 else 0.0

        logger.info(
            f"Synthesized '{text[:30]}...' -> Audio: {audio_duration:.2f}s | Processed in: {process_time:.2f}s (RTF: {rtf:.2f})"
        )

        # Encode to WAV bytes in-memory (stateless, no disk I/O)
        byte_io = io.BytesIO()
        sf.write(byte_io, audio_array, sample_rate, format='WAV', subtype='PCM_16')
        byte_io.seek(0)
        wav_bytes = byte_io.read()

        return wav_bytes, audio_duration, process_time

    def _synthesize_chunk_wav(self, text: str, speaker: str) -> bytes:
        """
        Tổng hợp một đoạn text ngắn thành WAV bytes trong bộ nhớ.
        Dùng nội bộ cho pre-warm và kiosk streaming.
        """
        from src.vietnamese.text_processor import process_vietnamese_text
        norm_text = process_vietnamese_text(text)
        audio_array, sample_rate = self.tts.synthesize(
            text=norm_text,
            speaker=speaker,
            speed=settings.DEFAULT_SPEED,
        )
        if len(audio_array) > 0:
            max_val = np.max(np.abs(audio_array))
            if max_val > 0:
                audio_array = (audio_array / max_val) * 0.98
        byte_io = io.BytesIO()
        sf.write(byte_io, audio_array, sample_rate, format='WAV', subtype='PCM_16')
        return byte_io.getvalue()

    def prewarm_kiosk_cache(self, speaker: Optional[str] = None) -> None:
        """
        Pre-warm Redis cache cho tất cả các chunk Kiosk cố định:
        - "Mời bệnh nhân số 1" → "Mời bệnh nhân số N" (N = KIOSK_MAX_STT)
        - "vào quầy lễ tân số 1" → "vào quầy lễ tân số N" (N = KIOSK_MAX_COUNTER)
        Bỏ qua chunk nào đã tồn tại trong cache (safe to call on restart).
        """
        if not self.tts:
            logger.warning("Kiosk pre-warm skipped: TTS engine not ready")
            return

        target_speaker = speaker or settings.DEFAULT_SPEAKER
        speed = settings.DEFAULT_SPEED
        ttl = settings.KIOSK_CACHE_TTL  # 0 = không TTL (vĩnh viễn)

        logger.info(
            f"🔥 Kiosk pre-warm bắt đầu: STT 1→{settings.KIOSK_MAX_STT}, "
            f"Quầy 1→{settings.KIOSK_MAX_COUNTER}, speaker={target_speaker}, TTL={'∞' if ttl == 0 else f'{ttl}s'}"
        )
        total_start = time.time()
        skipped = 0
        synthesized = 0

        # --- Phase 1: Pre-warm số quầy (ưu tiên cao, số lượng ít) ---
        for counter in range(1, settings.KIOSK_MAX_COUNTER + 1):
            chunk_text = f"vào quầy lễ tân số {counter}"
            cached = cache_manager.get_audio(chunk_text, target_speaker, speed)
            if cached:
                skipped += 1
                continue
            try:
                wav_bytes = self._synthesize_chunk_wav(chunk_text, target_speaker)
                cache_manager.set_audio_with_ttl(chunk_text, target_speaker, speed, wav_bytes, ttl)
                synthesized += 1
            except Exception as e:
                logger.warning(f"Pre-warm quầy {counter} thất bại: {e}")

        logger.info(f"✅ Pre-warm số quầy xong: {synthesized} tổng hợp mới, {skipped} đã có trong cache")

        # --- Phase 2: Pre-warm STT bệnh nhân (chạy background, số lượng nhiều hơn) ---
        skipped_stt = 0
        synthesized_stt = 0
        for stt in range(1, settings.KIOSK_MAX_STT + 1):
            chunk_text = f"Mời bệnh nhân số {stt}"
            cached = cache_manager.get_audio(chunk_text, target_speaker, speed)
            if cached:
                skipped_stt += 1
                continue
            try:
                wav_bytes = self._synthesize_chunk_wav(chunk_text, target_speaker)
                cache_manager.set_audio_with_ttl(chunk_text, target_speaker, speed, wav_bytes, ttl)
                synthesized_stt += 1
            except Exception as e:
                logger.warning(f"Pre-warm STT {stt} thất bại: {e}")

        elapsed = time.time() - total_start
        logger.info(
            f"🎉 Kiosk pre-warm hoàn tất trong {elapsed:.1f}s | "
            f"STT: {synthesized_stt} mới / {skipped_stt} đã có | "
            f"Quầy: đã xong ở Phase 1"
        )

    def synthesize_kiosk_stream_generator(
        self,
        stt: int,
        counter: int,
        speaker: Optional[str] = None,
    ):
        """
        Stream âm thanh cho câu Kiosk: "Mời bệnh nhân số {stt}, vào quầy lễ tân số {counter}"
        Lấy từng phần từ Redis cache (nếu có) để đạt độ trễ ~5ms.
        Fallback về synthesis bình thường nếu cache miss.
        """
        if not self.tts:
            raise RuntimeError("TTS Engine is not initialized")

        target_speaker = speaker or settings.DEFAULT_SPEAKER
        speed = settings.DEFAULT_SPEED
        sample_rate = 24000

        chunk_stt     = f"Mời bệnh nhân số {stt}"
        chunk_counter = f"vào quầy lễ tân số {counter}"

        logger.info(f"Kiosk stream: STT={stt}, quầy={counter}, speaker={target_speaker}")

        header_sent = False
        all_segments = []

        for chunk_text in [chunk_stt, chunk_counter]:
            # Thử lấy từ cache trước
            cached_wav = cache_manager.get_audio(chunk_text, target_speaker, speed)
            if cached_wav:
                logger.debug(f"Cache HIT kiosk chunk: '{chunk_text}'")
                # Đọc PCM data từ WAV bytes (bỏ qua 44-byte WAV header)
                pcm_bytes = cached_wav[44:]
                audio_array = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32767.0
            else:
                logger.debug(f"Cache MISS kiosk chunk: '{chunk_text}' → synthesis")
                from src.vietnamese.text_processor import process_vietnamese_text
                norm_text = process_vietnamese_text(chunk_text)
                audio_array, sample_rate = self.tts.synthesize(
                    text=norm_text,
                    speaker=target_speaker,
                    speed=speed,
                )
                if len(audio_array) > 0:
                    max_val = np.max(np.abs(audio_array))
                    if max_val > 0:
                        audio_array = (audio_array / max_val) * 0.98
                # Lưu vào cache để lần sau dùng lại
                wav_bytes = self._synthesize_chunk_wav(chunk_text, target_speaker)
                cache_manager.set_audio_with_ttl(
                    chunk_text, target_speaker, speed, wav_bytes,
                    settings.KIOSK_CACHE_TTL
                )

            if len(audio_array) > 0:
                # Crossfade 5ms để chống pop/click khi ghép chunk
                fade_len = min(120, len(audio_array) // 2)
                if fade_len > 0:
                    audio_array[:fade_len]  *= np.linspace(0.0, 1.0, fade_len)
                    audio_array[-fade_len:] *= np.linspace(1.0, 0.0, fade_len)
                all_segments.append(audio_array)
                pcm_bytes = (audio_array * 32767).astype(np.int16).tobytes()
                if not header_sent:
                    yield create_wav_header(sample_rate=sample_rate)
                    header_sent = True
                yield pcm_bytes

engine_manager = TTSEngineManager()
