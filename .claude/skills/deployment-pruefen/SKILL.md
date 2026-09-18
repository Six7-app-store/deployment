---
name: deployment-pruefen
description: Nachweisen, ob ein Deployment durchgelaufen ist und die Instanz wirklich antwortet. Aufruf mit dem Hostnamen als Argument.
---

# Deployment prüfen

Weist nach, ob eine Umgebung läuft — mit Belegen, nicht mit Behauptungen.

Aufruf: `/deployment-pruefen <hostname>` — ohne Argument wird die lokale
Dev-Umgebung geprüft.

## Die Grenze

| Erlaubt | Verboten |
|---|---|
| Staging-Workflow anstoßen (`mode: plan`, dann `apply`) | Produktions-Deployment |
| Health-Endpunkt abfragen | `terraform apply` / `destroy` von Hand |
| Erreichbarkeit über IPv4 und IPv6 prüfen | Rollback, `deploy.cmd`, `scripts/deploy.sh` |
| Containerstatus und Logs lesen | Secrets lesen oder schreiben |
| Pipeline-Ergebnis lesen | |

Die Grenze läuft zwischen **dem Knopf, den die Pipeline anbietet** und **der
Infrastruktur darunter**. Den Workflow starten: ja. Terraform von Hand gegen
OpenStack: nein. Dieselbe Regel, die auch für Menschen im Team gilt.

**Immer zuerst `mode: plan`.** Der Lauf prüft Runner, Image, Checkout, alle
sechs Secrets und eine echte OpenStack-Anmeldung, ändert aber nichts. Erwartet
wird `0 to add, 0 to change, 0 to destroy` und **keine** Zeile mit
`must be replaced`. Steht dort etwas anderes, ist das ein Befund für einen
Menschen — nicht der Anlass, trotzdem `apply` zu fahren.

## Lokal (dev)

```bash
# Antwortet das Backend?
curl -sS http://localhost:8000/health
# erwartet: {"status":"healthy","service":"backend-api","version":"1.0.0"}

# Welche Container laufen, und sind sie gesund?
make dev-ps

# Frontend erreichbar?
curl -sS -o /dev/null -w '%{http_code}\n' http://localhost:5173/
```

Ein Dienst ohne `healthy` in `make dev-ps` ist die erste Spur. Dann die Logs:
`make dev-logs-backend`, `-worker`, `-frontend`, `-keycloak`.

## Staging

```bash
curl -4 -sS -o /dev/null -w '%{http_code}\n' https://<APP_HOSTNAME>/
curl -6 -sS -o /dev/null -w '%{http_code}\n' https://<APP_HOSTNAME>/
curl -sS https://<APP_HOSTNAME>/api/health
```

Beide der ersten beiden sollten `200` liefern — IPv4 und IPv6 getrennt prüfen,
weil der DNS beide Einträge hat und einer davon fehlen kann.

Eine Anfrage an die nackte IP schlägt über HTTPS **erwartungsgemäß** fehl:
Caddy wählt den Site-Block über den Namen im SNI, den eine IP nicht mitbringt.
Über HTTP antwortet sie mit `308` — das genügt als Erreichbarkeitsnachweis und
ist kein Fehler.

## Pipeline-Ergebnis

Der Staging-Deploy läuft in **Forgejo**, nicht in GitHub Actions. Der Workflow
gibt am Ende `docker compose ps` aus; dort sollten alle Dienste mit Healthcheck
`healthy` sein. Das Log ist die verlässlichste Quelle dafür, *warum* etwas
schiefging.

Der CI-Status der Pull Requests liegt dagegen auf GitHub:

```bash
gh run list --limit 5
gh pr checks
```

**Voraussetzung:** `gh` muss installiert und angemeldet sein. Ist es das nicht,
schlagen diese Befehle mit `command not found` fehl — dann ist das die
Antwort, nicht ein rotes Deployment.

## Wenn etwas rot ist

Reihenfolge, die am schnellsten zur Ursache führt:

1. **Antwortet der Host überhaupt?** Nein → Infrastruktur oder DNS, nicht der
   Code.
2. **Antwortet er, aber mit 502/503?** → Container läuft nicht oder ist nicht
   healthy. Compose-Status und Logs ansehen.
3. **200, aber die Anwendung verhält sich falsch?** → Deployment war
   erfolgreich, das Problem liegt im Code. Ab hier gilt der normale Weg:
   reproduzieren, Test schreiben, beheben.

Ein häufiger Fall, der wie ein kaputtes Deployment aussieht und keiner ist:
eine geänderte `.env` wurde mit `restart` statt `up -d --force-recreate`
übernommen. Die Umgebung wird beim **Erzeugen** des Containers festgeschrieben —
ein Neustart liest sie nicht neu.

## Ergebnis melden

Nicht „Deployment ok" behaupten, sondern zeigen: das Kommando, den Statuscode,
die Antwort des Health-Endpunkts. Ein Beleg ist schneller zu prüfen als eine
Behauptung nachzustellen.
