import io
import os
import sys
import types
# Windows PyTorch DLL path polyfill for Python 3.8+
if sys.platform == "win32":
    import site
    for sp in site.getsitepackages():
        t_lib = os.path.join(sp, "torch", "lib")
        if os.path.isdir(t_lib):
            try:
                os.add_dll_directory(t_lib)
            except Exception:
                pass

# Python 3.12 compatibility polyfill for legacy 'vinorm' package
try:
    import imp
except ImportError:
    import importlib
    import importlib.util
    imp = types.ModuleType('imp')
    def _find_module(name, path=None):
        spec = importlib.util.find_spec(name, path)
        if spec and spec.origin:
            return (None, os.path.dirname(spec.origin), ('', '', 1))
        raise ImportError(f"No module named '{name}'")
    imp.find_module = _find_module
    imp.reload = importlib.reload
    sys.modules['imp'] = imp

# Polyfill pkg_resources for legacy 'librosa' package compatibility
try:
    import pkg_resources
except ImportError:
    import importlib.resources
    pkg_resources = types.ModuleType('pkg_resources')
    def _resource_filename(package_or_requirement, resource_name):
        try:
            return str(importlib.resources.files(package_or_requirement) / resource_name)
        except Exception:
            return resource_name
    pkg_resources.resource_filename = _resource_filename
    sys.modules['pkg_resources'] = pkg_resources

# Force UTF-8 default encoding for open() calls on Windows
import builtins
_orig_open = builtins.open
def _utf8_open(file, mode='r', buffering=-1, encoding=None, errors=None, newline=None, closefd=True, opener=None):
    if encoding is None and 'b' not in mode:
        encoding = 'utf-8'
    return _orig_open(file, mode, buffering=buffering, encoding=encoding, errors=errors, newline=newline, closefd=closefd, opener=opener)
builtins.open = _utf8_open

import logging
from contextlib import asynccontextmanager
from typing import Optional, List
from fastapi import FastAPI, Query, HTTPException, status
from fastapi.responses import StreamingResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from enum import Enum

from app.config import settings
from app.cache import cache_manager
from app.tts_engine import engine_manager

# Configure Logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("kiosk-tts.server")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Kiosk TTS Service...")
    cache_manager.connect()
    engine_manager.load_model()
    yield
    # Shutdown
    logger.info("Shutting down Kiosk TTS Service...")

app = FastAPI(
    title="Kiosk Text-to-Speech API",
    description="High-performance Vietnamese TTS Audio Streaming Service for Kiosk Systems",
    version="1.0.0",
    docs_url="/api-docs",
    redoc_url=None,
    openapi_url="/api-docs/openapi.json",
    lifespan=lifespan,
    servers=[
        {"url": "http://localhost:1106", "description": "Local Development"},
        {"url": "https://kioskvoice.bvdk333.work", "description": "Production"},
    ]
)

# CORS setup for Web Browser & Kiosk Frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Cache", "X-Audio-Duration", "X-Process-Time"]
)

# Speaker Enum — 5 available voices
class SpeakerID(str, Enum):
    NF  = "NF"   # Nữ miền Bắc (Female - Northern accent)
    SF  = "SF"   # Nữ miền Nam  (Female - Southern accent)
    NM1 = "NM1"  # Nam miền Bắc giọng 1 (Male - Northern accent, voice 1)
    NM2 = "NM2"  # Nam miền Bắc giọng 2 (Male - Northern accent, voice 2)
    SM  = "SM"   # Nam miền Nam  (Male - Southern accent)

# Pydantic Schemas
class TTSRequest(BaseModel):
    text: str = Field(
        ...,
        description="Văn bản tiếng Việt cần phát âm",
        example="Mời bệnh nhân Nguyễn Văn A vào phòng khám số 3"
    )
    speaker: Optional[SpeakerID] = Field(
        default=None,
        description=(
            "Giọng đọc. Các giá trị hợp lệ:\n"
            "- **NF** — Nữ miền Bắc (Female, Northern accent) \n"
            "- **SF** — Nữ miền Nam (Female, Southern accent) \n"
            "- **NM1** — Nam miền Bắc, giọng 1 (Male, Northern accent, voice 1) \n"
            "- **NM2** — Nam miền Bắc, giọng 2 (Male, Northern accent, voice 2) \n"
            "- **SM** — Nam miền Nam (Male, Southern accent) \n\n"
            "Mặc định server dùng **NF** nếu không truyền."
        ),
        example=SpeakerID.NF
    )

class SpeakersResponse(BaseModel):
    default_speaker: str
    available_speakers: List[str]

from app.response import success_response, error_response
from fastapi import Request

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    return error_response(
        message=str(exc.detail),
        status_code=exc.status_code
    )

# System & Probe Endpoints
@app.get("/api/health", status_code=status.HTTP_200_OK, tags=["System"])
def health_check():
    """Liveness probe - used by K8s livenessProbe"""
    return success_response(
        message="Hệ thống Kiosk TTS hoạt động bình thường",
        data={
            "status": "healthy",
            "service": "KIOSK-TTS",
            "version": "1.0.0"
        }
    )

@app.get("/api/health/ready", tags=["System"])
def readiness_check():
    """Readiness probe - used by K8s readinessProbe"""
    if not engine_manager.is_ready():
        return error_response(
            message="Kiosk TTS chưa sẵn sàng (V-TTS Engine chưa load xong)",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            extra={
                "data": {
                    "status": "not_ready",
                    "service": "KIOSK-TTS",
                    "version": "1.0.0"
                }
            }
        )
    return success_response(
        message="Kiosk TTS sẵn sàng xử lý yêu cầu",
        data={
            "status": "ready",
            "service": "KIOSK-TTS",
            "version": "1.0.0",
            "cacheConnected": cache_manager._is_connected,
            "speakers": engine_manager.get_speakers()
        }
    )

# Core API Endpoints
@app.get("/api/speakers", tags=["TTS"])
def list_speakers():
    speakers = engine_manager.get_speakers()
    return success_response(
        message="Danh sách giọng đọc sẵn có",
        data={
            "defaultSpeaker": settings.DEFAULT_SPEAKER,
            "availableSpeakers": speakers
        }
    )

def _process_tts_request(text: str, speaker: Optional[str]):
    # Text validation
    clean_text = text.strip() if text else ""
    if not clean_text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Text parameter cannot be empty")

    if len(clean_text) > settings.MAX_TEXT_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Text length ({len(clean_text)}) exceeds maximum allowed limit of {settings.MAX_TEXT_LENGTH} characters"
        )

    selected_speaker = speaker or settings.DEFAULT_SPEAKER
    
    # 1. Check Redis Cache
    cached_wav = cache_manager.get_audio(clean_text, selected_speaker, settings.DEFAULT_SPEED)
    if cached_wav:
        logger.info(f"Cache HIT for text: '{clean_text[:25]}...' [speaker={selected_speaker}]")
        return StreamingResponse(
            io.BytesIO(cached_wav),
            media_type="audio/wav",
            headers={
                "X-Cache": "HIT",
                "Content-Disposition": 'inline; filename="speech.wav"'
            }
        )

    # 2. Cache MISS: Low-latency Chunk Streaming (~400ms first audio byte)
    logger.info(f"Cache MISS for text: '{clean_text[:25]}...' [speaker={selected_speaker}] -> Initiating Chunk Streaming")
    return StreamingResponse(
        engine_manager.synthesize_stream_generator(
            text=clean_text,
            speaker=selected_speaker,
        ),
        media_type="audio/wav",
        headers={
            "X-Cache": "MISS",
            "X-Streaming": "chunked",
            "Content-Disposition": 'inline; filename="speech.wav"'
        }
    )

AUDIO_RESPONSES = {
    200: {
        "content": {"audio/wav": {}},
        "description": "Stream âm thanh WAV (PCM 16-bit) - Có trình phát Audio trực tiếp trên Swagger UI"
    }
}

@app.get("/api/stream", tags=["TTS"], responses=AUDIO_RESPONSES, response_class=StreamingResponse)
def stream_audio_get(
    text: str = Query(..., description="Văn bản tiếng Việt cần phát âm", example="Mời bệnh nhân Nguyễn Văn A vào phòng khám số 3"),
    speaker: Optional[SpeakerID] = Query(default=None, description="Giọng đọc: NF (Nữ Bắc), SF (Nữ Nam), NM1 (Nam Bắc 1), NM2 (Nam Bắc 2), SM (Nam Nam)"),
):
    return _process_tts_request(text=text, speaker=speaker)

@app.post("/api/stream", tags=["TTS"], responses=AUDIO_RESPONSES, response_class=StreamingResponse)
def stream_audio_post(body: TTSRequest):
    return _process_tts_request(text=body.text, speaker=body.speaker)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=False)
