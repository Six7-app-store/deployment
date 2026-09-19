# Click-n-Deploy App Store — Arbeitsordner

<!-- Erzeugt von deployment/harness/sync.py. Nicht hier bearbeiten,
     sondern in deployment/harness/root/CLAUDE.md. -->

Dieser Ordner ist kein Repository. Er hält die **vier getrennten Git-Repos**
des Projekts nebeneinander, weil sie nur zusammen laufen:

| Ordner | Rolle |
|---|---|
| `deployment/` | Einstiegspunkt. Compose-Stacks aller Umgebungen, Keycloak-Realm, Seed-Daten, Terraform, Ansible, ADRs |
| `backend/` | FastAPI + SQLAlchemy + Alembic + Celery |
| `frontend/` | Vue 3 + TypeScript + Pinia + Vite |
| `worker/` | Celery-Worker: klont App-Repos, baut Packer-Images, fährt Terraform gegen OpenStack |

Backend, Frontend und Worker laufen **nicht standalone**, sondern nur als
Dienste im Stack aus `deployment/docker-compose.dev.yml`.

## Vor der Arbeit in einem Repo

**Die `AGENTS.md` des betroffenen Repos lesen.** Dort stehen die Befehle, die
Konventionen, die Definition of Done und die Fallen — je Repo verschieden und
verbindlich. Diese Datei hier ersetzt sie nicht, sie ordnet nur ein.

Ein Commit gehört in genau ein Repo. Eine Änderung, die zwei Repos betrifft
(z. B. neuer Endpunkt + Frontend-Aufruf), sind zwei Commits in zwei Repos.

## Gilt überall

- **Alles im Container.** Die venvs liegen unter `/app/.venv` und sind nicht
  im `PATH`; `node_modules` am Host sind unvollständig. Ein blankes `pytest`
  oder `npm test` am Host scheitert und sieht aus, als gäbe es keine Tests.
- **`.env`, `*.pem`, `*.key` sind tabu** — lesen wie schreiben. Gepflegt wird
  `.env.example`. Die deny-Regeln in `.claude/settings.json` setzen das hart
  durch, ein Hook erklärt den Grund.
- **Kein Produktions-Deploy, kein `terraform apply` von Hand.** Staging läuft
  über die Forgejo-Pipeline, Produktion über einen Menschen auf der
  Zielmaschine.
- **Kein Push auf `main`, kein Force-Push.** Jeder Push fragt nach; auf `main`
  pusht eine Person.
- **Architekturentscheidung getroffen?** ADR nach `deployment/docs/adr/`, im
  selben Commit. Format: `deployment/docs/adr/README.md`.

## Harness

Hooks, Berechtigungen und geteilte Skills liegen kanonisch in
`deployment/harness/` und werden von dort in die vier Repos und in diesen
Ordner verteilt:

```bash
cd deployment && make harness-sync     # verteilen
cd deployment && make harness-check    # nur prüfen, ändert nichts
```

Änderungen am Harness gehören nach `deployment/harness/`, nie in eine der
erzeugten Kopien. Nach `git pull` im `deployment`-Repo einmal `make
harness-sync` fahren.
