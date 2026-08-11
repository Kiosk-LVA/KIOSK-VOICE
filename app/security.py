import hmac
import hashlib
import time
import logging
from fastapi import HTTPException, status
from app.config import settings

logger = logging.getLogger("kiosk-tts.security")

def verify_hmac(payload_str: str, timestamp: str, signature: str) -> bool:
    """
    Verifies HMAC SHA-256 signature for API request security.
    If API_HMAC_SECRET is not set (empty), security check is bypassed.
    
    Formula: signature = HMAC-SHA256(secret, f"{timestamp}:{payload_str}")
    """
    if not settings.API_HMAC_SECRET:
        return True  # HMAC check is optional/disabled when secret is empty

    if not timestamp or not signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing HMAC authentication parameters (timestamp / signature)"
        )

    # 1. Anti-replay attack check: Timestamp must be within 300s window
    try:
        ts_int = int(timestamp)
        now_int = int(time.time())
        if abs(now_int - ts_int) > 300:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Request timestamp expired (must be within 300s window)"
            )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid timestamp format (must be UNIX integer timestamp)"
        )

    # 2. Compute expected HMAC-SHA256 digest
    message = f"{timestamp}:{payload_str}"
    expected_signature = hmac.new(
        settings.API_HMAC_SECRET.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    # 3. Constant-time comparison to prevent timing side-channel attacks
    if not hmac.compare_digest(expected_signature, signature.lower()):
        logger.warning(f"HMAC Signature mismatch! Expected: {expected_signature}, Got: {signature}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid HMAC signature"
        )

    return True
