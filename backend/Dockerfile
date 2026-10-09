ARG PYTHON_VERSION=3.14.7
FROM python:${PYTHON_VERSION}-slim AS builder
WORKDIR /app
ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy
RUN python -m pip install --no-cache-dir uv==0.12.15
COPY pyproject.toml uv.lock .python-version ./
COPY app ./app
COPY scripts ./scripts
RUN uv sync --frozen --no-dev --no-editable --compile-bytecode

FROM python:${PYTHON_VERSION}-slim AS runtime
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY --from=builder /app/.venv ./.venv
COPY --from=builder /app/app ./app
COPY --from=builder /app/scripts ./scripts
USER 10001:10001
EXPOSE 9000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9000/api/v2/health', timeout=2)"
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9000"]
