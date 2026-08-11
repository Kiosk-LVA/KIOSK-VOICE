from typing import Any, Optional, Dict
from fastapi.responses import JSONResponse
from fastapi import status

def success_response(
    message: str = "Thành công",
    data: Optional[Any] = None,
    extra: Optional[Dict[str, Any]] = None,
    status_code: int = status.HTTP_200_OK
) -> JSONResponse:
    """
    Standard Kiosk Ecosystem JSON Success Response Wrapper.
    Output: { "success": true, "message": "...", "data": ..., ...extra }
    """
    content = {
        "success": True,
        "message": message
    }
    if data is not None:
        content["data"] = data
    if extra:
        content.update(extra)
    return JSONResponse(status_code=status_code, content=content)

def error_response(
    message: str = "Đã xảy ra lỗi",
    status_code: int = status.HTTP_400_BAD_REQUEST,
    extra: Optional[Dict[str, Any]] = None
) -> JSONResponse:
    """
    Standard Kiosk Ecosystem JSON Error Response Wrapper.
    Output: { "success": false, "message": "..." }
    """
    content = {
        "success": False,
        "message": message
    }
    if extra:
        content.update(extra)
    return JSONResponse(status_code=status_code, content=content)
