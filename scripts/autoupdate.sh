#!/usr/bin/env bash
#
# Holt neue Images aus GHCR und startet die betroffenen Dienste neu.
#
# Laeuft auf der Staging-VM, angestossen von appstore-autoupdate.timer. Damit
# aktualisiert sich Staging nach einem Merge auf main von selbst, ohne dass
# jemand einen Deploy ausloest.
#
# WARUM DIE VM ZIEHT, STATT DASS JEMAND SCHIEBT
# Ein GitHub-Runner erreicht von diesem Projekt aus weder die OpenStack-API
# (Firewall) noch den SSH-Port dieser VM (Security Group, nur Campusnetz). Was
# er erreicht, ist GHCR - und GHCR erreicht diese VM auch. Also dreht der
# Ablauf sich um: Niemand kommt herein, die Maschine schaut selbst nach.
#
# WAS DAS NICHT KANN
# Nur Container werden getauscht. Aenderungen an Terraform, Ansible oder der
# Compose-Datei erfasst dieses Skript NICHT - dafuer bleibt der Deploy ueber
# deploy.cmd bzw. das Runbook zustaendig. Der Grund ist Absicht: Ein Skript,
# das sich seine eigene Ausfuehrungsgrundlage nachlaedt, ist nicht mehr
# nachvollziehbar zu machen.
#
# Aufruf ohne Argumente. Rueckgabe 0 auch dann, wenn es nichts zu tun gab.

set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/home/ubuntu/app}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.staging.yml}"
# Nur diese Dienste werden automatisch getauscht. Postgres, RabbitMQ, Redis und
# Keycloak stehen bewusst nicht in der Liste: Sie haengen an gepinnten
# Upstream-Tags, und ein unbeaufsichtigter Neustart einer Datenbank ist etwas,
# das man sich nicht nebenbei einhandelt.
SERVICES="${SERVICES:-backend worker frontend}"

cd "$PROJECT_ROOT"

log() { echo "[$(date -Is)] $*"; }

# Das Playbook entfernt die GHCR-Zugangsdaten am Ende jedes Deploys wieder aus
# dem Root-Store. Fuer private Packages muss dieses Skript sich deshalb selbst
# anmelden - aus derselben .env, aus der auch das Playbook liest, und mit
# --password-stdin, damit das Token nicht in der Prozessliste steht.
set -a
# shellcheck disable=SC1091
. ./.env
set +a

if [ -z "${GIT_ACCESS_TOKEN:-}" ]; then
  log "FEHLER: GIT_ACCESS_TOKEN fehlt in $PROJECT_ROOT/.env - private Images sind nicht ziehbar."
  exit 1
fi

cleanup() {
  docker logout ghcr.io >/dev/null 2>&1 || true
}
trap cleanup EXIT

printf '%s' "$GIT_ACCESS_TOKEN" \
  | docker login ghcr.io --username "${GIT_USER:-x-access-token}" --password-stdin >/dev/null

# Der Vergleich laeuft ueber die Image-ID vor und nach dem Pull, nicht ueber die
# Ausgabe von `compose pull`. Deren Text ist nicht stabil genug, um darauf eine
# Entscheidung zu gruenden, und `latest` behaelt beim Ueberschreiben denselben
# Namen - nur die ID wechselt.
changed=""
for svc in $SERVICES; do
  image=$(docker compose -f "$COMPOSE_FILE" config --images "$svc" 2>/dev/null | head -n1)
  if [ -z "$image" ]; then
    log "WARNUNG: kein Image fuer Dienst '$svc' in $COMPOSE_FILE - uebersprungen."
    continue
  fi

  before=$(docker image inspect --format '{{.Id}}' "$image" 2>/dev/null || echo "none")
  docker pull --quiet "$image" >/dev/null
  after=$(docker image inspect --format '{{.Id}}' "$image" 2>/dev/null || echo "none")

  if [ "$before" != "$after" ]; then
    log "neu: $svc ($image)"
    changed="$changed $svc"
  fi
done

if [ -z "$changed" ]; then
  log "Keine neuen Images."
  exit 0
fi

# --no-deps: Nur die getauschten Dienste werden angefasst. Ohne das zieht
# Compose die Abhaengigkeiten mit und startet im Zweifel die Datenbank neu.
log "Starte neu:$changed"
# shellcheck disable=SC2086
docker compose -f "$COMPOSE_FILE" up -d --no-deps $changed

# Migrationen nur, wenn das Backend selbst neu ist. Ein neues Frontend bringt
# keine Schemaaenderung mit, und ein alembic-Lauf gegen eine unveraenderte
# Datenbank ist zwar folgenlos, aber er verschleiert im Log, wann wirklich
# migriert wurde.
if echo "$changed" | grep -qw backend; then
  log "Warte auf den Backend-Container."
  for _ in $(seq 1 30); do
    [ "$(docker inspect -f '{{.State.Running}}' backend-prod 2>/dev/null || echo false)" = "true" ] && break
    sleep 2
  done

  log "Wende Migrationen an."
  docker exec backend-prod python -m alembic upgrade head
fi

# Aufraeumen, sonst fuellt sich die Platte mit jedem Merge um eine
# Image-Generation. Nur verwaiste Images, keine Volumes, keine Netzwerke.
docker image prune -f >/dev/null 2>&1 || true

log "Fertig."
