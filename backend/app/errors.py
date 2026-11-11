from fastapi import Request
from fastapi.responses import JSONResponse


class APIError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict | None = None):
        self.status, self.code, self.message = status, code, message
        self.details = details or {}


def envelope(code: str, message: str, request_id: str, details: dict | None = None) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "request_id": request_id,
        }
    }


async def api_error(request: Request, exc: APIError):
    return JSONResponse(
        envelope(exc.code, exc.message, request.state.request_id, exc.details),
        status_code=exc.status,
    )
