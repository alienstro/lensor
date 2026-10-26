FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev
# Download the tokenizer files at build time, not on the first upload.
RUN python -c "from lensor.ingest.chunker import chunk_text; chunk_text('Warm the cache.')"

EXPOSE 8000
# Read the client address from X-Forwarded-For only when a proxy on a private network sent it.
# The rate limit on /api/chat uses that address.
CMD ["sh", "-c", "alembic upgrade head && uvicorn lensor.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips=10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,127.0.0.1"]
