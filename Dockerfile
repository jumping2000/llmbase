FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npx vite build

FROM python:3.12-slim

# Force UTF-8 regardless of the base image's locale. Today the container
# gets UTF-8 only because python:3.12-slim happens to set LANG=C.UTF-8 —
# by accident, not by contract. A base-image bump or a LANG override at
# deploy time would silently send every text read back to the platform
# default, and the healthcheck (`llmbase stats`) reads the whole wiki.
ENV PYTHONUTF8=1

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend
COPY llmwiki/ ./llmwiki/
COPY pyproject.toml llmbase.py wsgi.py asgi.py ./
RUN pip install --no-cache-dir -e .

# Copy built frontend
COPY --from=frontend-build /app/static/dist ./static/dist

# Create data directories
RUN mkdir -p raw wiki/_meta wiki/concepts wiki/outputs

# Expose port
EXPOSE 5555

# Use uvicorn for unified ASGI (Flask + MCP). Single worker required
# because MCP sessions are in-memory (StreamableHTTPSessionManager).
CMD ["uvicorn", "--host", "0.0.0.0", "--port", "5555", "--workers", "1", "--timeout-keep-alive", "300", "asgi:app"]
