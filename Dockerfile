# maluS v1 — application image.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MALUS_DB_URL=sqlite:////data/malus.db

WORKDIR /app

# Install the package (wheels cover argon2-cffi/pydantic-core/cryptography on slim).
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install ".[mcp]"

# Migrations + entrypoint.
COPY alembic.ini ./
COPY alembic ./alembic
COPY docker-entrypoint.sh /usr/local/bin/malus-entrypoint

RUN chmod +x /usr/local/bin/malus-entrypoint \
    && useradd --create-home --uid 10001 malus \
    && mkdir -p /data && chown malus /data
USER malus

EXPOSE 8000
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"

ENTRYPOINT ["malus-entrypoint"]
