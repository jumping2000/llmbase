"""MCP Server — expose LLMBase as a Model Context Protocol server.

Tools are generated from ``llmwiki.operations`` so this surface never drifts
from the CLI / HTTP definitions. Register a custom operation via
``llmwiki.operations.register`` and it appears here automatically.

Usage:
    python -m llmwiki [--base-dir .]

Or register in a Claude Code / Cursor / Claude Desktop config::

    {
      "mcpServers": {
        "llmbase": {
          "command": "python",
          "args": ["-m", "llmwiki.mcp_server", "--base-dir", "/path/to/kb"]
        }
      }
    }
"""

import argparse
import asyncio
import json
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import anyio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.server.streamable_http import StreamableHTTPServerTransport
from mcp.types import Tool, TextContent
import uvicorn
from starlette.applications import Starlette
from starlette.routing import Mount
from .mcp_config import McpSettings

from . import operations as ops

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("llmbase.mcp")


def _tools() -> list[Tool]:
    return [
        Tool(name=op.name, description=op.description, inputSchema=op.params)
        for op in ops.all_operations()
    ]


def handle_tool(name: str, arguments: dict, base_dir: Path) -> str:
    """Back-compat shim: synchronously dispatch a tool and return text.

    Kept for callers that pre-date the operations-contract refactor
    (tests, older integration scripts). New code should import
    ``llmwiki.operations.dispatch`` directly.
    """
    if ops.get(name) is None:
        return f"Unknown tool: {name}"
    try:
        result = ops.dispatch(name, base_dir, arguments or {})
    except RuntimeError as e:
        # Match legacy message for lock contention
        return f"Another write operation is running. {e}"
    return _format(result)


def _format(result) -> str:
    """Render an operation's return value for MCP text output."""
    if isinstance(result, str):
        return result
    try:
        return json.dumps(result, ensure_ascii=False, indent=2, default=str)
    except (TypeError, ValueError):
        return str(result)


def create_server(base_dir: Path) -> Server:
    server = Server("llmbase")

    @server.list_tools()
    async def list_tools():
        return _tools()

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        if ops.get(name) is None:
            raise ValueError(f"Unknown tool: {name}")
        try:
            result = await asyncio.to_thread(ops.dispatch, name, base_dir, arguments or {})
            return [TextContent(type="text", text=_format(result))]
        except RuntimeError as e:
            # Lock contention — render as normal text instead of surfacing as error
            return [TextContent(type="text", text=f"Busy: {e}")]
        except Exception as e:
            logger.error(f"Tool {name} failed: {e}")
            raise

    return server


def create_streamable_http_app(base_dir: Path) -> Starlette:
    """Create a Starlette app that serves the MCP streamable HTTP transport at /mcp."""
    server = create_server(base_dir)
    transport = StreamableHTTPServerTransport(mcp_session_id=None)

    @asynccontextmanager
    async def lifespan(app: Starlette):
        async with transport.connect() as (read_stream, write_stream):
            async with anyio.create_task_group() as task_group:
                task_group.start_soon(
                    server.run,
                    read_stream,
                    write_stream,
                    server.create_initialization_options(),
                )
                yield
                task_group.cancel_scope.cancel()

    async def asgi_app(scope, receive, send):
        await transport.handle_request(scope, receive, send)

    return Starlette(routes=[Mount("/mcp", app=asgi_app)], lifespan=lifespan)


def main():
    parser = argparse.ArgumentParser(description="LLMBase MCP Server")
    parser.add_argument("--base-dir", type=str, default=".", help="Knowledge base directory")
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default=None)
    parser.add_argument("--http-port", type=int, default=None)
    parser.add_argument("--http-url", type=str, default=None)
    args = parser.parse_args()

    base_dir = Path(args.base_dir).resolve()
    logger.info(f"Starting LLMBase MCP server (base: {base_dir})")

    from .mcp_config import resolve_mcp_settings

    settings = resolve_mcp_settings(
        transport=args.transport,
        http_port=args.http_port,
        http_url=args.http_url,
    )
    run_mcp(base_dir, settings)


if __name__ == "__main__":
    main()


def run_streamable_http_server(base_dir: Path, port: int = 8100) -> None:
    """Run the streamable-http ASGI app using uvicorn on localhost."""
    app = create_streamable_http_app(base_dir)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


async def _stdio_run(base_dir: Path) -> None:
    """Coroutine to run the stdio MCP server for a given base_dir."""
    server = create_server(base_dir)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def run_mcp(base_dir: Path, settings: McpSettings | None = None) -> None:
    """Run the MCP transport selected by `settings` (or env/defaults if None).

    If `settings.transport == 'stdio'` the stdio server is started. If
    `streamable-http` the ASGI app is served via uvicorn on localhost.
    """
    if settings is None:
        # Lazy import to avoid circular imports in CLI tests.
        from .mcp_config import resolve_mcp_settings

        settings = resolve_mcp_settings()

    if settings.transport == "stdio":
        asyncio.run(_stdio_run(base_dir))
    elif settings.transport == "streamable-http":
        run_streamable_http_server(base_dir, settings.http_port)
    else:
        raise ValueError(f"Unsupported MCP transport: {settings.transport}")
