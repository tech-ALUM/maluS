#!/bin/sh
# maluS container entrypoint: apply migrations, then serve.
set -e

echo "maluS: applying database migrations (alembic upgrade head)..."
alembic upgrade head

echo "maluS: starting server on 0.0.0.0:8000 ..."
exec malus serve --host 0.0.0.0 --port 8000 --db "${MALUS_DB_URL}"
