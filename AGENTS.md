# Deployment — Click-n-Deploy App Store

Einstiegspunkt für alles Lokale. Hier liegen die Compose-Stacks der drei
Umgebungen, Keycloak-Realm, Seed-Daten, OpenTofu und Ansible. Backend,
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

| Umgebung | Branch | Compose-Datei | Ausrollen |
|---|---|---|---|
| dev | beliebig | `docker-compose.dev.yml` | `make dev-up` am eigenen Rechner |
| staging | `develop` | `docker-compose.staging.yml` | **nur** über die Pipeline, nie von Hand |
| prod | `main` | `docker-compose.prod.yml` | `make prod-*` auf der Zielmaschine, manuell |

Der Staging-Deploy läuft in **GitHub Actions** auf dem self-hosted Runner im
Campusnetz (`.github/workflows/staging.yml`, ADR 0002) — von außen ist die
OpenStack-API der DHBW nicht erreichbar. Ausgelöst von Push auf `develop`, von
`repository_dispatch` aus der CI der drei anderen Repos auf `develop`, oder
von Hand. Ein Merge auf `main` löst nichts aus: `main` ist Produktion
(ADR 0013). Jeder Lauf
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
- OpenTofu-Änderungen mit `tofu fmt -recursive infrastructure/tofu`
  formatieren — die Pipeline prüft das mit `-check` und bricht sonst ab.
- Alle Umgebungen und das Modul `openstack_vm` liegen unter
  `infrastructure/tofu/` (ADR 0010, ADR 0015). Neue Infrastruktur gehört dorthin.

## Definition of Done

- `.env.example` und Compose-Datei zusammen aktualisiert
- OpenTofu formatiert
- Harness geändert? `make harness-sync` gefahren, `make harness-test` grün,
  die erzeugten Kopien mitcommittet
- Architekturentscheidung getroffen? ADR unter `docs/adr/` (Format: `docs/adr/README.md`)

## Nicht anfassen

- `.env` — nur `.env.example` wird gepflegt
- Alles auf `*.pem` (Tool-Schlüssel, gehört nie ins Repo)
- Kein Prod-Deploy und kein `tofu apply` von Hand
- Kein `git push --force`
- `.claude/` — erzeugt aus `harness/`. Änderungen gehören in die Quelle, sonst
  sind sie beim nächsten `make harness-sync` weg.

Geheimnisse, Produktions-Deploys, `tofu apply` und Pushes auf `main` sind
zusätzlich als deny-Regel in `.claude/settings.json` gesperrt. So ein Kommando
scheitert ohne Nachfrage — das ist Absicht und kein Werkzeugfehler.

<!-- BEGIN HARNESS GIT WORKFLOW -->
<!-- Quelle: deployment/harness/git-workflow.md; mit harness-sync verteilen. -->
## Branches: develop ist Staging, main ist Produktion

Gilt in den vier Stack-Repos (deployment, backend, frontend, worker); die
App-Repos haben nur `main`. Begründung: `deployment/docs/adr/0013-*.md`.

- Neue Arbeit zweigt von `develop` ab (`feat/…`, `fix/…`, `chore/…`, `docs/…`)
  und kommt per Pull Request nach `develop` zurück. Jeder Merge dort baut
  Staging neu.
- `main` bekommt nur Release-PRs `develop` → `main`, gemergt mit
  **Merge-Commit** — kein Squash, kein Rebase, sonst laufen die Branches
  auseinander. Danach `develop` per Fast-Forward nachziehen:
  `git push origin origin/main:develop`. Ist `develop` inzwischen weiter, statt
  dessen ein PR `main` → `develop`.
- Hotfix: Branch von `main`, PR nach `main`, danach `main` in `develop` mergen.
- Ein Feature über mehrere Repos geht in allen betroffenen Repos zusammen nach
  `develop` und mit demselben Release nach `main`.
- Agenten mergen keine Pull Requests und pushen nicht auf `main`; das tut eine
  Person.

## Commits und Pushes bündeln

- Änderungen zuerst als zusammenhängendes Arbeitspaket fertigstellen und die
  passenden Prüfungen abschließen. Nicht nach jeder Datei, kleinen Korrektur
  oder jedem Zwischenschritt committen.
- Pro abgeschlossenem Arbeitspaket und betroffenem Repository möglichst einen
  nachvollziehbaren Commit erstellen. Mehrere Commits sind sinnvoll, wenn sie
  unabhängig prüfbare Änderungen trennen; fremde Änderungen nicht mit aufnehmen.
- Commits erst gesammelt nach Abschluss des Arbeitspakets pushen, nicht nach
  jedem einzelnen Commit. Kein automatischer Commit-/Push-Zyklus während der
  Umsetzung. Pushes nur im bereits autorisierten Umfang ausführen.
- Repoübergreifende Arbeiten bleiben getrennte Commits je Repository; vor einem
  gebündelten Push die erforderlichen Prüfungen der betroffenen Repos abschließen.
- Bestehende Commit-Historie nicht zum Zusammenfassen umschreiben, sofern das
  nicht ausdrücklich beauftragt wurde. Kein Force-Push und kein Agenten-Push
  auf `main`. Explizite Nutzerwünsche zu Zwischenständen haben Vorrang.
<!-- END HARNESS GIT WORKFLOW -->
