"""API middleware for error handling and request logging."""

import logging
import time
from collections.abc import MutableMapping
from typing import Any

from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)


class RequestLoggingAndErrorMiddleware:
    """ASGI middleware that logs requests and catches unhandled exceptions.

    Uses pure ASGI (not BaseHTTPMiddleware) to avoid issues with
    streaming responses and graceful shutdown.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.time()
        state: dict[str, object] = {}

        async def send_wrapper(message: MutableMapping[str, Any]) -> None:
            if message["type"] == "http.response.start":
                state["status_code"] = message.get("status", 0)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as e:
            logger.error("Unhandled exception: %s", type(e).__name__)
            status = 500
            body = b'{"detail":"Internal server error"}'
            headers = [[b"content-type", b"application/json"]]
            await send({"type": "http.response.start", "status": status, "headers": headers})
            await send({"type": "http.response.body", "body": body})
            state["status_code"] = status

        duration = time.time() - start
        path = scope.get("path", "?")
        method = scope.get("method", "?")
        headers_list = scope.get("headers", [])
        tenant_id = "anonymous"
        for name, value in headers_list:
            if name == b"x-api-key":
                tenant_id = value.decode() if isinstance(value, bytes) else str(value)
                break
        status_code = state.get("status_code", "?")
        logger.info("%s %s %s %s %ss", method, path, tenant_id, status_code, f"{duration:.3f}")
