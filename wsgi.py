"""WSGI entry point for production web deployment."""
import logging
from pathlib import Path
from llmwiki.web import create_web_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

base = Path(__file__).resolve().parent
app = create_web_app(base)
