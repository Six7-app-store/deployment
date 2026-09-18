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
- `make help` listet alle Targets.

## Umgebungen

| Umgebung | Compose-Datei | Ausrollen |
|---|---|---|
| dev | `docker-compose.dev.yml` | `make dev-up` am eigenen Rechner |
| staging | `docker-compose.staging.yml` | **nur** über die Pipeline, nie von Hand |
| prod | `docker-compose.prod.yml` | `make prod-*` auf der Zielmaschine, manuell |

Der Staging-Deploy läuft in **Forgejo**, nicht in GitHub Actions:
`.forgejo/workflows/staging.yml` ist der Workflow, der tatsächlich läuft.
`.github/workflows/staging.yml` ist das Gegenstück ohne Wirkung — beide
müssen zusammen geändert werden, sonst driften sie. Warum überhaupt
Forgejo: `docs/staging-setup.md`, Abschnitt „Warum ein eigenes Forgejo".

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
- Staging-Workflow in **beiden** Kopien geändert, falls betroffen
- Architekturentscheidung getroffen? ADR unter `docs/adr/` (Format: `docs/adr/README.md`)

## Nicht anfassen

- `.env` — nur `.env.example` wird gepflegt
- Alles auf `*.pem` (Tool-Schlüssel, gehört nie ins Repo)
- Kein Prod-Deploy und kein `terraform apply` gegen Staging von Hand
- Kein `git push --force`
