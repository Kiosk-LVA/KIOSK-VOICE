import hashlib
import logging
from typing import Optional
from app.config import settings

logger = logging.getLogger("kiosk-tts.cache")

class AudioCacheManager:
    def __init__(self):
        self.redis_client = None
        self._is_connected = False

    def connect(self):
        if not settings.CACHE_ENABLED or not settings.REDIS_HOST:
            logger.info("Redis cache is disabled or REDIS_HOST is not set.")
            return

        try:
            import redis
            self.redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD or None,
                db=settings.REDIS_DB,
                socket_timeout=2.0,
                socket_connect_timeout=2.0,
            )
            # Test ping connection
            self.redis_client.ping()
            self._is_connected = True
            logger.info(f"Connected to Redis cache at {settings.REDIS_HOST}:{settings.REDIS_PORT}")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis ({e}). Running without audio cache.")
            self.redis_client = None
            self._is_connected = False

    def _generate_key(self, text: str, speaker: str, speed: float) -> str:
        payload = f"{text.strip()}:{speaker}:{speed:.2f}"
        hash_digest = hashlib.md5(payload.encode("utf-8")).hexdigest()
        return f"kiosk:tts:{hash_digest}"

    def get_audio(self, text: str, speaker: str, speed: float) -> Optional[bytes]:
        if not self._is_connected or self.redis_client is None:
            return None
        try:
            key = self._generate_key(text, speaker, speed)
            cached_data = self.redis_client.get(key)
            if cached_data:
                logger.debug(f"Cache HIT for key: {key}")
                return cached_data
        except Exception as e:
            logger.warning(f"Redis GET error: {e}")
        return None

    def set_audio(self, text: str, speaker: str, speed: float, audio_bytes: bytes) -> bool:
        if not self._is_connected or self.redis_client is None:
            return False
        try:
            key = self._generate_key(text, speaker, speed)
            self.redis_client.setex(key, settings.REDIS_TTL, audio_bytes)
            logger.debug(f"Cache SET for key: {key}")
            return True
        except Exception as e:
            logger.warning(f"Redis SET error: {e}")
            return False

    def set_audio_with_ttl(self, text: str, speaker: str, speed: float, audio_bytes: bytes, ttl: int) -> bool:
        """Lưu audio với TTL tùy chỉnh. ttl=0 nghĩa là không bao giờ hết hạn (persist)."""
        if not self._is_connected or self.redis_client is None:
            return False
        try:
            key = self._generate_key(text, speaker, speed)
            if ttl == 0:
                self.redis_client.set(key, audio_bytes)  # Không TTL — tồn tại vĩnh viễn
            else:
                self.redis_client.setex(key, ttl, audio_bytes)
            logger.debug(f"Cache SET (TTL={'∞' if ttl == 0 else ttl}s) for key: {key}")
            return True
        except Exception as e:
            logger.warning(f"Redis SET error: {e}")
            return False

cache_manager = AudioCacheManager()
