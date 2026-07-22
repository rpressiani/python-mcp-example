FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

WORKDIR /app

COPY pyproject.toml ./
RUN uv sync --no-cache

COPY main.py .

EXPOSE 8001

CMD ["uv", "run", "python", "main.py"]
