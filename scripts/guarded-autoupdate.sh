#!/usr/bin/env bash
# Installed only if guarded updates are explicitly enabled after bootstrap.
set -euo pipefail
PROJECT_ROOT=${PROJECT_ROOT:-/home/ubuntu/app}
cd "$PROJECT_ROOT"
set -a
# shellcheck disable=SC1091
. ./.env
set +a
export PROJECT_ROOT
exec python3 /usr/local/bin/appstore-guarded-autoupdate.py
