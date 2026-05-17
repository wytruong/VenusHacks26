import os

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

DEFAULT_MAX_REQUEST_BYTES = 25 * 1024 * 1024
ECG_ROUTE_PATH = "/api/ecg/apple-watch/infer"


class RequestEntityTooLarge(Exception):
    pass


class RequestSizeLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") != "POST" or scope.get("path") != ECG_ROUTE_PATH:
            await self.app(scope, receive, send)
            return

        max_bytes = _max_request_bytes()
        content_length = _content_length(scope)
        if content_length is not None and content_length > max_bytes:
            await _too_large_response(scope, receive, send)
            return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > max_bytes:
                    raise RequestEntityTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except RequestEntityTooLarge:
            await _too_large_response(scope, receive, send)


def _max_request_bytes() -> int:
    raw_value = os.getenv("ECG_MAX_REQUEST_BYTES")
    if raw_value is None:
        return DEFAULT_MAX_REQUEST_BYTES
    try:
        parsed = int(raw_value)
    except ValueError:
        return DEFAULT_MAX_REQUEST_BYTES
    return parsed if parsed > 0 else DEFAULT_MAX_REQUEST_BYTES


def _content_length(scope: Scope) -> int | None:
    for name, value in scope.get("headers", []):
        if name.lower() == b"content-length":
            try:
                return int(value.decode("ascii"))
            except ValueError:
                return None
    return None


async def _too_large_response(scope: Scope, receive: Receive, send: Send) -> None:
    response = JSONResponse({"detail": "Request body is too large."}, status_code=413)
    await response(scope, receive, send)
