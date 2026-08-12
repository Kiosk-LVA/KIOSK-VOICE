import os
from pathlib import Path

class Settings:
    # Server Settings
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "1106"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "info")

    # TTS Model Settings
    MODEL_PATH: str = os.getenv("MODEL_PATH", "")  # Path to local model dir (e.g. ./models/vits-vietnamese)
    DEVICE: str = os.getenv("DEVICE", "cpu")        # "cpu" or "cuda"
    DEFAULT_SPEAKER: str = os.getenv("DEFAULT_SPEAKER", "female_north")
    DEFAULT_SPEED: float = float(os.getenv("DEFAULT_SPEED", "0.88"))  # 0.88x speed: slightly slower for hospital patients
    MAX_TEXT_LENGTH: int = int(os.getenv("MAX_TEXT_LENGTH", "500"))  # Limit text length per request to prevent high latency/OOM

    # Redis Cache Settings
    REDIS_HOST: str = os.getenv("REDIS_HOST", "")  # e.g. "redis.infrastructure.svc.cluster.local"
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    REDIS_TTL: int = int(os.getenv("REDIS_TTL", str(5 * 60)))  # Default 5 minutes — hospital announcements are short-lived
    CACHE_ENABLED: bool = os.getenv("CACHE_ENABLED", "true").lower() in ("true", "1", "yes")

    # Security Settings (HMAC signature secret, optional)
    API_HMAC_SECRET: str = os.getenv("API_HMAC_SECRET", "")

    # CPU Optimization Settings
    TORCH_THREADS: int = int(os.getenv("TORCH_THREADS", "4"))
    TORCH_COMPILE: bool = os.getenv("TORCH_COMPILE", "false").lower() in ("true", "1", "yes")
    PURE_PYTHON_PHONEMIZER: bool = os.getenv("PURE_PYTHON_PHONEMIZER", "true").lower() in ("true", "1", "yes")

settings = Settings()
