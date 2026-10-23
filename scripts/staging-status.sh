#!/usr/bin/env bash
# Lesender Blick auf beide Staging-Staende. Aendert nichts.
#
#   make staging-status
#
# Warum ein Skript und nicht ein paar curl-Zeilen im Skill: die
# Berechtigungen erlauben genau dieses Target ohne Rueckfrage. Einzelne
# curl-Aufrufe gegen beliebige Hosts freizugeben hiesse, jede Adresse
# freizugeben.
#
# Staging hat sonst bewusst keine Make-Targets: nichts hier baut, startet
# oder veraendert etwas. Ausgerollt wird nur ueber die Pipeline (ADR 0015).
#
# Drei Fragen, in der Reihenfolge, die am schnellsten zur Ursache fuehrt:
#   1. Zeigt der DNS auf die aktuelle VM? Jeder Neubau vergibt eine neue
#      IPv6-Adresse; ein lokaler Resolver haelt die alte noch eine Weile
#      und meldet einen Timeout, obwohl die Pipeline gruen ist.
#   2. Antworten Frontend, Backend und Keycloak?
#   3. Was hat die Pipeline zuletzt getan, und laeuft gerade ein Deploy?

set -u

ZONE="${STAGING_ZONE:-s241699-at-student-dhbw-mannheim-de.users.dhbw.site}"
# develop: Staging (ADR 0013). main: Produktionsstand unter der alten
# Staging-Adresse (ADR 0014) — wird hier nur gelesen.
STAENDE="develop=staging.$ZONE main=appstore.$ZONE"
REPO="Six7-app-store/deployment"
REALM="dhbw"

PY=$(command -v python || command -v python3)

code() {
  # -w schreibt auch bei einem Verbindungsfehler "000".
  curl -sS -o /dev/null -m 15 -w '%{http_code}' "$@" 2>/dev/null || true
}

a_oeffentlich() {
  curl -sS -m 10 "https://dns.google/resolve?name=$1&type=A" 2>/dev/null | "$PY" -c '
import json, sys
try:
    print(len([a for a in json.load(sys.stdin).get("Answer", []) if a.get("type") == 1]))
except Exception:
    print(0)
'
}

aaaa_lokal() {
  "$PY" - "$1" <<'PY'
import socket, sys
try:
    infos = socket.getaddrinfo(sys.argv[1], 443, socket.AF_INET6, socket.SOCK_STREAM)
    print(" ".join(sorted({i[4][0] for i in infos})) or "-")
except Exception:
    print("-")
PY
}

aaaa_oeffentlich() {
  curl -sS -m 10 "https://dns.google/resolve?name=$1&type=AAAA" 2>/dev/null | "$PY" -c '
import json, sys
try:
    data = json.load(sys.stdin)
    print(" ".join(sorted(a["data"] for a in data.get("Answer", []) if a.get("type") == 28)) or "-")
except Exception:
    print("-")
'
}

for eintrag in $STAENDE; do
  stand=${eintrag%%=*}
  host=${eintrag#*=}
  echo "== Stand $stand: https://$host"

  lokal=$(aaaa_lokal "$host")
  oeffentlich=$(aaaa_oeffentlich "$host")
  if [ "$lokal" = "$oeffentlich" ]; then
    echo "   DNS        AAAA $oeffentlich"
  else
    echo "   DNS        AAAA lokal $lokal, oeffentlich $oeffentlich  <- veraltet? ipconfig /flushdns"
  fi

  echo "   Frontend   $(code "https://$host/")"
  if [ "$(a_oeffentlich "$host")" = "0" ]; then
    echo "   IPv4       kein A-Eintrag (die VM ist nur ueber IPv6 erreichbar)"
  else
    echo "   IPv4       $(code -4 "https://$host/")"
  fi
  echo "   IPv6       $(code -6 "https://$host/")"
  echo "   Backend    $(code "https://$host/api/health")  $(curl -sS -m 15 "https://$host/api/health" 2>/dev/null | head -c 200)"
  echo "   Keycloak   $(code "https://$host/realms/$REALM/.well-known/openid-configuration")"
done

echo
echo "== Pipeline (staging.yml, letzte 6 Laeufe)"
if command -v gh >/dev/null 2>&1; then
  gh run list -R "$REPO" --workflow staging.yml --limit 6 \
    --json databaseId,status,conclusion,displayTitle,event,headBranch,createdAt \
    --template '{{range .}}   #{{printf "%.0f" .databaseId}}  {{.status}}/{{.conclusion}}  {{.event}}@{{.headBranch}}  {{timeago .createdAt}}  {{.displayTitle}}{{"\n"}}{{end}}'
else
  echo "   gh fehlt — Pipeline-Stand nicht lesbar."
fi
