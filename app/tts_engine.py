import io
import os
import time
import logging
from pathlib import Path
from typing import Tuple, List, Optional
import numpy as np
import soundfile as sf
from v_tts import TTS
from app.config import settings

logger = logging.getLogger("kiosk-tts.engine")

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

    def is_ready(self) -> bool:
        return self._is_ready and self.tts is not None

    def get_speakers(self) -> List[str]:
        if not self.tts:
            return []
        return self.tts.list_speakers()

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
        # Commas in norm_text produce natural micro-pauses from the VITS duration predictor
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

engine_manager = TTSEngineManager()
