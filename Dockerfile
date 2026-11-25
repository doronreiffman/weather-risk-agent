# The public site's image (docs/DEPLOY_DESIGN.md 5.6). Koyeb builds it from the repository on every push.
# The database is built here, from the committed raw responses with no network, so start-up does not rebuild it.
# The key and the access code are never in the image: the host passes them as environment variables, and
# without WRA_ACCESS_CODE the server refuses to start.
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.0 /uv /usr/local/bin/uv
WORKDIR /app
# byte-compile at build time, so a start after an idle hour skips that work (0.1 of a CPU on the free host)
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never

# dependencies first, so a change to our own code does not reinstall them
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev && .venv/bin/wra ingest

EXPOSE 8000
# the venv's script directly, so start-up skips uv; PORT if the host sets one
CMD ["sh", "-c", "exec /app/.venv/bin/wra serve --host 0.0.0.0 --port ${PORT:-8000}"]
