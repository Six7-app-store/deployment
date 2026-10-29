#!/usr/bin/env bash
# Experimental runner-side companion to the backend maintenance gate.
# Default: local PostgreSQL as OS user postgres. Tests may select direct mode.
set -euo pipefail
action=${1:-}
db=${2:-}
owner=${3:-}
timeout=${4:-600}
[[ "$db" =~ ^[a-zA-Z0-9_]+$ ]] || { echo 'Invalid database name' >&2; exit 1; }
[[ "$owner" =~ ^[a-zA-Z0-9_-]{1,64}$ ]] || { echo 'Invalid maintenance owner' >&2; exit 1; }
[[ "$timeout" =~ ^[0-9]+$ ]] || { echo 'Invalid timeout' >&2; exit 1; }

if [[ ${MAINTENANCE_PSQL_MODE:-local} == direct ]]; then
  command=(psql)
elif [[ ${MAINTENANCE_PSQL_MODE:-local} == local ]]; then
  command=(sudo -n -u postgres psql)
else
  echo 'Invalid PostgreSQL access mode' >&2; exit 1
fi

query() {
  # Inputs were validated above. Errors are suppressed: DB errors may contain
  # credentials. The non-zero status still prevents continuing the deployment.
  printf '%s\n' "$1" | "${command[@]}" -X -q -A -t -v ON_ERROR_STOP=1 -d "$db" 2>/dev/null
}

case "$action" in
  begin)
    # UPDATE takes the same row lock as task admission's FOR SHARE. Once the
    # transaction commits, new tasks cannot be admitted; older ones may drain.
    acquired=$(query "UPDATE platform_maintenance SET owner='$owner' WHERE id=1 AND owner IS NULL RETURNING 1;")
    [[ "$acquired" == 1 ]] || { echo 'Maintenance gate unavailable' >&2; exit 2; }
    deadline=$((SECONDS + timeout))
    while :; do
      state=$(query "SELECT CASE WHEN owner='$owner' THEN 1 ELSE 0 END FROM platform_maintenance WHERE id=1;")
      [[ "$state" == 1 ]] || { echo 'Maintenance ownership lost' >&2; exit 1; }
      active=$(query "SELECT count(*) FROM tasks WHERE status IN ('PENDING','RUNNING');")
      [[ "$active" =~ ^[0-9]+$ ]] || { echo 'Invalid active task count' >&2; exit 1; }
      if [[ "$active" == 0 ]]; then
        echo 'Maintenance acquired; tasks drained.'
        exit 0
      fi
      if (( SECONDS >= deadline )); then
        released=$(query "UPDATE platform_maintenance SET owner=NULL WHERE id=1 AND owner='$owner' RETURNING 1;")
        [[ "$released" == 1 ]] || { echo 'Maintenance release failed' >&2; exit 1; }
        echo 'Active tasks remain; deployment was not started.' >&2
        exit 2
      fi
      sleep 2
    done
    ;;
  end)
    released=$(query "UPDATE platform_maintenance SET owner=NULL WHERE id=1 AND owner='$owner' RETURNING 1;")
    [[ "$released" == 1 ]] || { echo 'Maintenance release failed' >&2; exit 1; }
    echo 'Maintenance released.'
    ;;
  *) echo 'Usage: maintenance-operator.sh begin|end DATABASE OWNER [TIMEOUT_SECONDS]' >&2; exit 1 ;;
esac
