#!/usr/bin/env bash
# Stdin script executed on the staging VM *only by the deployment workflow*.
# Stop new timer triggers and wait for an already running legacy update.
# Never kill the running update: it might be part way through a container swap.
set -euo pipefail
timeout=${1:-900}
[[ "$timeout" =~ ^[0-9]+$ ]] || { echo 'Invalid timeout' >&2; exit 1; }
systemctl stop appstore-autoupdate.timer
deadline=$((SECONDS + timeout))
while :; do
  state=$(systemctl show appstore-autoupdate.service --property=ActiveState --value)
  job=$(systemctl show appstore-autoupdate.service --property=Job --value)
  case "$state" in
    inactive)
      if [[ -z "$job" ]]; then
        echo 'Legacy timer stopped; no update service is running or queued.'
        exit 0
      fi
      ;;
    active|activating|deactivating|reloading) ;;
    *) echo 'Legacy updater is in an unknown or failed state; investigate.' >&2; exit 1 ;;
  esac
  if (( SECONDS >= deadline )); then
    echo 'Legacy updater did not become idle; bootstrap stopped.' >&2
    exit 2
  fi
  sleep 2
done
