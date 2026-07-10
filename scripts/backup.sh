#!/bin/sh
# maluS backup — SQLite (consistent .backup) or Postgres (pg_dump).
# Usage: MALUS_DB_URL=... scripts/backup.sh [out-dir]
set -e
: "${MALUS_DB_URL:?set MALUS_DB_URL}"
OUT="${1:-backups}"
mkdir -p "$OUT"
TS=$(date +%Y%m%d-%H%M%S)

case "$MALUS_DB_URL" in
  sqlite:////*) DB="/${MALUS_DB_URL#sqlite:////}" ;;   # absolute (four slashes)
  sqlite:///*)  DB="${MALUS_DB_URL#sqlite:///}" ;;      # relative (three slashes)
  postgres*|postgresql*) DB="" ;;
  *) echo "unsupported MALUS_DB_URL: $MALUS_DB_URL" >&2; exit 1 ;;
esac

if [ -n "$DB" ]; then
  DEST="$OUT/malus-$TS.db"
  sqlite3 "$DB" ".backup '$DEST'"
else
  DEST="$OUT/malus-$TS.sql"
  pg_dump "$MALUS_DB_URL" > "$DEST"
fi
echo "backup written: $DEST"
