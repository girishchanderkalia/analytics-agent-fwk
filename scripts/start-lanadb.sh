#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="postgres:17.11"
CONTAINER="lanadb-local"
VOLUME="lanadb-local-data"
DATABASE="lanadb"
DUMP=""

usage() {
  printf '%s\n' \
    'Usage: bash scripts/start-lanadb.sh [--dump <archive>]' \
    '' \
    'Starts PostgreSQL 17.11 on 127.0.0.1:5433 using the persistent lanadb-local-data volume.' \
    'Reads LANADB_USERNAME and LANADB_PASSWORD from the repository-root .env.' \
    'Exported environment variables take precedence.' \
    '' \
    '--dump restores a pg_dump archive into lanadb, replacing objects included in the archive.' \
    'This removes existing rows (including seeded mocks) from those tables.' \
    'Restore is transactional; a failed restore rolls back its database changes.' \
    '' \
    'Examples (Git Bash):' \
    '  bash scripts/start-lanadb.sh' \
    '  bash scripts/start-lanadb.sh --dump "C:/code/data/lanadb.dump"' \
    '' \
    'If the image is missing, download it with: docker pull postgres:17.11'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dump)
      if [[ $# -lt 2 || -z "$2" || "$2" == --* ]]; then
        echo 'ERROR: --dump requires an archive path.' >&2
        exit 1
      fi
      DUMP="$2"
      shift 2
      ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR: Unknown argument: $1" >&2; usage >&2; exit 1 ;;
  esac
done

if [[ -n "$DUMP" ]]; then
  if command -v cygpath >/dev/null 2>&1; then
    DUMP="$(cygpath -u "$DUMP")"
  fi
  if [[ ! -f "$DUMP" || ! -s "$DUMP" ]]; then
    echo "ERROR: Dump file does not exist or is empty: $DUMP" >&2
    exit 1
  fi
  DUMP="$(cd "$(dirname "$DUMP")" && pwd)/$(basename "$DUMP")"
fi

if ! command -v docker >/dev/null 2>&1; then
  echo 'ERROR: Docker CLI not found. Install Docker Desktop and reopen the terminal.' >&2
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo 'ERROR: Docker engine is unavailable. Start Docker Desktop and try again.' >&2
  exit 1
fi
if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  printf '%s\n' "ERROR: Docker Hub image $IMAGE is not available locally." \
    "Download it with: docker pull $IMAGE" \
    'Then rerun this script.' >&2
  exit 1
fi

source "$ROOT_DIR/scripts/load-env.sh" "$ROOT_DIR/.env"
if [[ -z "${LANADB_USERNAME:-}" || -z "${LANADB_PASSWORD:-}" ]]; then
  echo 'ERROR: Set LANADB_USERNAME and LANADB_PASSWORD in .env (or the environment).' >&2
  exit 1
fi

if docker container inspect "$CONTAINER" >/dev/null 2>&1; then
  actual_image="$(docker inspect --format '{{.Config.Image}}' "$CONTAINER")"
  if [[ "$actual_image" != "$IMAGE" ]]; then
    echo "ERROR: $CONTAINER uses $actual_image, not $IMAGE. No container was changed." >&2
    exit 1
  fi
  echo "Starting existing container $CONTAINER."
  docker start "$CONTAINER" >/dev/null
else
  echo "Creating $CONTAINER from $IMAGE."
  export POSTGRES_USER="$LANADB_USERNAME"
  export POSTGRES_PASSWORD="$LANADB_PASSWORD"
  MSYS_NO_PATHCONV=1 docker run --detach --name "$CONTAINER" \
    --env POSTGRES_USER --env POSTGRES_PASSWORD --env "POSTGRES_DB=$DATABASE" \
    --publish 127.0.0.1:5433:5432 \
    --mount "type=volume,source=$VOLUME,target=/var/lib/postgresql/data" \
    "$IMAGE" >/dev/null
  unset POSTGRES_USER POSTGRES_PASSWORD
fi

MSYS_NO_PATHCONV=1 docker exec "$CONTAINER" bash -c '
  for attempt in {1..60}; do
    if pg_isready --username="$1" --dbname="$2" >/dev/null 2>&1; then
      exit 0
    fi
    sleep 1
  done
  echo "ERROR: PostgreSQL did not become ready within 60 seconds." >&2
  exit 1
' -- "$LANADB_USERNAME" "$DATABASE"
docker exec "$CONTAINER" psql --username="$LANADB_USERNAME" --dbname="$DATABASE" \
  --no-psqlrc --set=ON_ERROR_STOP=1 --command='SELECT 1;' >/dev/null

if [[ -n "$DUMP" ]]; then
  archive="/tmp/lanadb-restore-$$.dump"
  cleanup() {
    MSYS_NO_PATHCONV=1 docker exec "$CONTAINER" rm -f "$archive" >/dev/null 2>&1 || true
  }
  trap cleanup EXIT
  source_path="$DUMP"
  if command -v cygpath >/dev/null 2>&1; then
    source_path="$(cygpath -w "$DUMP")"
  fi
  MSYS_NO_PATHCONV=1 docker cp "$source_path" "$CONTAINER:$archive" >/dev/null
  MSYS_NO_PATHCONV=1 docker exec "$CONTAINER" pg_restore --list "$archive" >/dev/null
  echo "Restoring $DUMP; existing objects included in the archive will be replaced."
  MSYS_NO_PATHCONV=1 docker exec "$CONTAINER" pg_restore \
    --username="$LANADB_USERNAME" --dbname="$DATABASE" \
    --clean --if-exists --no-owner --no-acl --no-tablespaces \
    --single-transaction --exit-on-error "$archive"
  docker exec "$CONTAINER" psql --username="$LANADB_USERNAME" --dbname="$DATABASE" \
    --no-psqlrc --set=ON_ERROR_STOP=1 --command='ANALYZE;' >/dev/null
  echo 'Restore completed.'
fi

echo "PostgreSQL is ready: $CONTAINER, database $DATABASE, user $LANADB_USERNAME."
echo 'JDBC URL: jdbc:postgresql://127.0.0.1:5433/lanadb'