#!/bin/sh
# maluS restore — inverse of backup.sh. STOP the app before restoring.
# Usage: MALUS_DB_URL=... scripts/restore.sh <backup-file>
set -e
: "${MALUS_DB_URL:?set MALUS_DB_URL}"
SRC="${1:?usage: restore.sh <backup-file>}"
[ -f "$SRC" ] || { echo "no such file: $SRC" >&2; exit 1; }

case "$MALUS_DB_URL" in
  sqlite:////*) DB="/${MALUS_DB_URL#sqlite:////}" ;;
  sqlite:///*)  DB="${MALUS_DB_URL#sqlite:///}" ;;
  postgres*|postgresql*) DB="" ;;
  *) echo "unsupported MALUS_DB_URL: $MALUS_DB_URL" >&2; exit 1 ;;
esac

if [ -n "$DB" ]; then
  cp "$SRC" "$DB"
  rm -f "$DB-wal" "$DB-shm"   # drop stale WAL sidecars
  echo "restored SQLite database: $DB"
else
  psql "$MALUS_DB_URL" < "$SRC"
  echo "restored Postgres database from: $SRC"
fi
