FROM python:3.11-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml .
COPY src/ ./src/

# Install dependencies with uv
RUN uv sync --frozen --no-dev

# Create data dir
RUN mkdir -p /data/pdfs

EXPOSE 8000

CMD ["uv", "run", "python", "src/server.py"]