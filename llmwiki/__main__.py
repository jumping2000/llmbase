"""Allow running MCP server as: python -m llmwiki"""
from .mcp_server import main
import asyncio

asyncio.run(main())
