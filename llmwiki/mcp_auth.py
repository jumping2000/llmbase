"""ASGI middleware that validates X-API-Key on /mcp requests."""

import hmac

from starlette.responses import Response


class MCPAuthMiddleware:
    """Wraps an ASGI callable with X-API-Key validation for /mcp routes.

    When *api_key* is empty/None the middleware is a no-op pass-through
    (local dev mode). Otherwise every request whose path starts with
    ``/mcp`` must carry a matching ``X-API-Key`` header.

    Usage::

        handler = MCPAuthMiddleware(session_manager.handle_request, os.getenv("MCP_API_KEY"))
        Mount("/mcp", app=handler)
    """

    def __init__(self, app, api_key: str | None = None):
        self.app = app
        self.api_key = api_key.strip() if api_key else ""

    async def __call__(self, scope, receive, send):
        if not self.api_key:
            await self.app(scope, receive, send)
            return

        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Only gate /mcp — Starlette Mount strips the prefix, so
        # scope["path"] inside the mount may already be "/" or "/...".
        # We check the raw path instead.
        raw_path = scope.get("raw_path", scope.get("path", b"/")).decode()
        if not raw_path.startswith("/mcp"):
            await self.app(scope, receive, send)
            return

        headers = {k.decode(): v.decode() for k, v in scope.get("headers", [])}
        key = headers.get("x-api-key", "")

        if not key or not hmac.compare_digest(key, self.api_key):
            response = Response(
                content='{"jsonrpc":"2.0","error":{"code":-32001,"message":"Unauthorized: invalid X-API-Key"},"id":null}',
                status_code=401,
                media_type="application/json",
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
