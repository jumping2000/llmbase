from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Optional
from urllib.parse import urlparse

from .llm import _load_env


@dataclass(frozen=True)
class McpSettings:
    transport: str
    http_port: int
    http_url: Optional[str]
    api_key: Optional[str]


def _validate_transport(value: str) -> str:
    allowed = {"stdio", "streamable-http"}
    if value not in allowed:
        raise ValueError(f"Invalid MCP_TRANSPORT: {value!r}; expected one of {sorted(allowed)}")
    return value


def _validate_port(value: int) -> int:
    if not isinstance(value, int) or value <= 0:
        raise ValueError("MCP_HTTP_PORT must be a positive integer")
    return value


def _validate_http_url(value: Optional[str]) -> Optional[str]:
    if value is None or value == "":
        return None
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"Invalid MCP_HTTP_URL: {value!r}")
    return value


def resolve_mcp_settings(
    *,
    transport: Optional[str] = None,
    http_port: Optional[int] = None,
    http_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> McpSettings:
    """Resolve MCP runtime settings.

    Precedence: CLI args (explicit params) > environment variables > defaults.
    """
    # Ensure any .env is loaded like other modules do.
    try:
        _load_env()
    except Exception:
        # Best-effort: if loading .env fails, fall back to current env.
        pass

    # Transport
    if transport is None:
        transport = os.environ.get("MCP_TRANSPORT", "stdio")
    transport = str(transport)
    _validate_transport(transport)

    api_key = api_key if api_key is not None else os.environ.get("MCP_API_KEY")

    if transport == "stdio":
        return McpSettings(
            transport=transport,
            http_port=8100 if http_port is None else http_port,
            http_url=http_url,
            api_key=api_key,
        )

    # HTTP port
    if http_port is None:
        port_val = os.environ.get("MCP_HTTP_PORT")
        if port_val is None or port_val == "":
            http_port = 8100
        else:
            try:
                http_port = int(port_val)
            except Exception:
                raise ValueError("MCP_HTTP_PORT must be an integer")
    _validate_port(http_port)

    # HTTP URL
    if http_url is None:
        http_url = os.environ.get("MCP_HTTP_URL")
    http_url = _validate_http_url(http_url)

    return McpSettings(
        transport=transport,
        http_port=http_port,
        http_url=http_url,
        api_key=api_key,
    )
