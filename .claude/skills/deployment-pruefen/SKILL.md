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
| Staging-Workflow anstoßen — **nur nach Rückfrage bei einem Menschen** | Produktions-Deployment |
| Health-Endpunkt abfragen | `terraform apply` / `destroy` von Hand |
| Erreichbarkeit über IPv4 und IPv6 prüfen | Rollback, `deploy.cmd`, `scripts/deploy.sh` |
| Containerstatus und Logs lesen | Secrets lesen oder schreiben |
| Pipeline-Ergebnis lesen | |

Die Grenze läuft zwischen **dem Knopf, den die Pipeline anbietet** und **der
Infrastruktur darunter**. Den Workflow starten: ja. Terraform von Hand gegen
OpenStack: nein. Dieselbe Regel, die auch für Menschen im Team gilt.

**Es gibt keinen Trockenlauf mehr.** Bis zum Umbau am 19.09.2026 kannte der
Workflow eine Eingabe `mode` mit Default `plan`, die nichts veränderte. Die
gibt es nicht mehr. `.github/workflows/staging.yml` kennt heute zwei Eingaben:

| Eingabe | Default | Wirkung |
|---|---|---|
| `recreate` | **true** | `terraform destroy -auto-approve`, dann Neuaufbau. Die Staging-VM ist danach eine andere Maschine |
| `seed` | false | legt Benutzer, Kurse und Apps an |

**Jeder Lauf verändert also etwas.** Der schonendste ist
`workflow_dispatch` mit `recreate: false` — der überspringt das `destroy` und
wendet nur Änderungen an. Ein reines „erst mal schauen" ist nicht vorgesehen.

Dass Staging bei jedem Merge ohnehin neu gebaut wird, ist eine bewusste
Entscheidung (`docs/adr/0003-staging-wird-bei-jedem-merge-neu-gebaut.md`) — das
macht einen versehentlichen Lauf nicht harmlos, nur nicht katastrophal. Ein
Deploy anzustoßen ist deshalb kein Schritt, den dieser Skill allein geht:
`gh workflow run` steht in `permissions.ask`, ein Mensch bestätigt ihn.

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

Der Staging-Deploy läuft seit `52d931f` in **GitHub Actions**, auf dem
self-hosted Runner im Campusnetz (VM `github-runner`). Der frühere
Forgejo-Workflow ist gelöscht. Warum ein eigener Runner nötig ist: die
OpenStack-API der DHBW ist von außen nicht erreichbar —
`docs/adr/0002-self-hosted-runner-auf-eigener-vm.md`.

Ausgelöst wird er von einem Push auf `main`, von einem `repository_dispatch`
aus der CI von frontend, backend oder worker, oder von Hand. Der Workflow gibt
am Ende `docker compose ps` aus; dort sollten alle Dienste mit Healthcheck
`healthy` sein. Das Log ist die verlässlichste Quelle dafür, *warum* etwas
schiefging.

Sowohl das Deployment als auch der CI-Status der Pull Requests liegen damit
auf GitHub:

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
