"""ASGI entry point for production web + MCP deployment.

Usage::

    uvicorn asgi:app --host 0.0.0.0 --port 5555 --workers 2

This replaces ``gunicorn wsgi:app`` when MCP streamable HTTP is needed.
For deployments that only need the web UI without MCP, ``wsgi.py`` is
still available.
"""

import logging
from pathlib import Path

from llmwiki.web import create_asgi_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
)

base = Path(__file__).resolve().parent
app = create_asgi_app(base)
