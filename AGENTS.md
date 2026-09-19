# Deployment — Click-n-Deploy App Store

Einstiegspunkt für alles Lokale. Hier liegen die Compose-Stacks der drei
Umgebungen, Keycloak-Realm, Seed-Daten, Terraform und Ansible. Backend,
Frontend und Worker laufen nur über die Stacks hier.

## Befehle

- Alles hochziehen: `make quickstart` (env + dev-up + migrate-dev + seed-data)
- Start / Stopp: `make dev-up`, `make dev-down`, `make dev-ps`, `make urls`
- Logs: `make dev-logs-backend`, `-frontend`, `-worker`, `-keycloak`
- Shell: `make shell-backend`, `shell-worker`, `shell-db`, `shell-redis`
- Nur einen Dienst neu starten: `make dev-restart-backend` (und -frontend, -worker)
- Moodle-Testinstanz: siehe `docs/moodle-lti-dev.md`
- Claude-Harness verteilen: `make harness-sync` (nach jedem `git pull`),
  prüfen: `make harness-check`. Quelle: `harness/`, siehe `harness/README.md`.
- `make help` listet alle Targets.

## Umgebungen

| Umgebung | Compose-Datei | Ausrollen |
|---|---|---|
| dev | `docker-compose.dev.yml` | `make dev-up` am eigenen Rechner |
| staging | `docker-compose.staging.yml` | **nur** über die Pipeline, nie von Hand |
| prod | `docker-compose.prod.yml` | `make prod-*` auf der Zielmaschine, manuell |

Der Staging-Deploy läuft in **GitHub Actions** auf dem self-hosted Runner im
Campusnetz (`.github/workflows/staging.yml`, ADR 0002) — von außen ist die
OpenStack-API der DHBW nicht erreichbar. Ausgelöst von Push auf `main`, von
`repository_dispatch` aus den drei anderen Repos, oder von Hand. Jeder Lauf
reißt die VM ab und baut sie neu (ADR 0003); einen Trockenlauf gibt es nicht.

**Bewusst kein `pull_request`-Trigger.** Das Repository ist öffentlich, und ein
self-hosted Runner an einem Fork-PR gäbe Fremden eine Ausführungsumgebung mit
OpenStack-Zugang. Nicht nachrüsten.

Staging hat bewusst keine Make-Targets, damit kein Arbeitsplatz von dem
abweicht, was die Pipeline erzeugt.

## Env-Fallen

- `docker compose restart <dienst>` übernimmt **keine** geänderte `.env` —
  die Umgebung wird beim Erzeugen des Containers festgeschrieben. Nach
  einer `.env`-Änderung: `up -d --force-recreate <dienst>`. Das
  `dev-restart-*`-Target reicht dafür nicht.
- Port 5432 kann auf einem Entwicklungsrechner belegt sein. Dann
  `DB_PORT` in der `.env` umbiegen — der interne DSN bleibt `@postgres:5432`.
- Git Bash verbiegt Containerpfade. `docker compose exec`-Aufrufe, die
  `/tmp/...` übergeben, mit `MSYS_NO_PATHCONV=1` prefixen.

## Konventionen

- Jede neue Env-Variable gehört in `.env.example` **und** in den Service
  in `docker-compose.dev.yml` — mit Default, damit ein frischer Checkout
  ohne Konfiguration startet.
- Optionale Features bekommen einen Kill-Switch mit Default `false`
  (Vorbild: `LTI_ENABLED`).
- Redis: DB 0 gehört Celery, DB 1 der LTI-Sitzungsablage. Nicht mischen.
- Terraform-Änderungen mit `terraform fmt -recursive` formatieren — die
  Pipeline prüft das mit `-check` und bricht sonst ab.

## Definition of Done

- `.env.example` und Compose-Datei zusammen aktualisiert
- Terraform formatiert
- Harness geändert? `make harness-sync` gefahren, `make harness-test` grün,
  die erzeugten Kopien mitcommittet
- Architekturentscheidung getroffen? ADR unter `docs/adr/` (Format: `docs/adr/README.md`)

## Nicht anfassen

- `.env` — nur `.env.example` wird gepflegt
- Alles auf `*.pem` (Tool-Schlüssel, gehört nie ins Repo)
- Kein Prod-Deploy und kein `terraform apply` gegen Staging von Hand
- Kein `git push --force`
- `.claude/` — erzeugt aus `harness/`. Änderungen gehören in die Quelle, sonst
  sind sie beim nächsten `make harness-sync` weg.

Geheimnisse, Produktions-Deploys, `terraform apply` und Pushes auf `main` sind
zusätzlich als deny-Regel in `.claude/settings.json` gesperrt. So ein Kommando
scheitert ohne Nachfrage — das ist Absicht und kein Werkzeugfehler.
