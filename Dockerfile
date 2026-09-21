FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    FATHOMARK_FRAMEWORK_DIR=/app/frameworks \
    FATHOMARK_DATA_DIR=/data \
    PYTHONDONTWRITEBYTECODE=1

COPY pyproject.toml uv.lock ./
COPY packages ./packages
COPY frameworks ./frameworks
COPY examples ./examples

RUN uv sync --frozen --no-dev --extra postgres
RUN mkdir -p /data

VOLUME ["/data"]
EXPOSE 8000

CMD ["uv", "run", "--no-dev", "uvicorn", "fathomark_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
