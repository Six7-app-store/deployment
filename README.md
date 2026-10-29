# Deployment

Dieses Repository hält alles zusammen, was die Plattform zum Laufen braucht: die
Compose-Stacks für die drei Umgebungen, den zentralen Makefile, den
Keycloak-Realm, die Seed-Daten und die OpenTofu- und Ansible-Definitionen der
Infrastruktur.

Die Anwendung selbst liegt in eigenen Repositories (`backend`, `frontend`,
`worker`). Hier wird nichts gebaut, was dort entsteht — hier wird es
zusammengesetzt, konfiguriert und ausgerollt.

## Dokumentation

- [Architektur: Self-Service-Portal und Moodle/LTI](docs/architektur.md)
- [Harness für die agentenzentrierte Entwicklung](docs/harness.md)
- [Lokales Dev Setup](docs/dev-setup.md)
- [Moodle-Testinstanz für LTI](docs/moodle-lti-dev.md)
- [Moodle für die Staging-Vorführung herrichten](docs/moodle-staging-demo.md)
- [Staging Setup](docs/staging-setup.md)
- [Produktives Setup](docs/prod-setup.md)

## Schnellstart

Kein Dienst wird einzeln gestartet. Alles läuft über den Makefile in diesem
Verzeichnis:

```bash
cd deployment
make init      # .env anlegen, Stack starten, migrieren, Seed-Daten laden
make urls      # alle Dev-URLs auf einen Blick
make help      # sämtliche Targets mit Beschreibung
```

Die wichtigsten im Alltag:

| Befehl | Wirkung |
|---|---|
| `make dev-up` / `make dev-down` | Stack starten und stoppen (Volumes bleiben) |
| `make dev-logs-backend` | Logs verfolgen; auch `-frontend`, `-worker`, `-keycloak` |
| `make shell-backend` | Shell im Container; auch `shell-worker`, `shell-frontend`, `shell-db` |
| `make harness-sync` | Claude-Harness in alle vier Repos verteilen — nach jedem `git pull` hier |
| `make dev-restart-worker` | Neustart, wenn der Hot-Reload nicht greift — etwa bei Celery-Tasks |
| `make migrate-dev` | Alembic-Migrationen anwenden |
| `make migration-create MSG="..."` | Neue Migration erzeugen |
| `make seed-data` | Seed-Daten laden; idempotent, gefahrlos wiederholbar |
| `make health` | Backend, Frontend und Keycloak anpingen |

## Die Umgebungen

| Umgebung | Compose-Datei | Reverse Proxy | Wie sie ausgerollt wird |
|---|---|---|---|
| dev | `docker-compose.dev.yml` | keiner, Dienste direkt auf Ports | `make dev-up` auf dem eigenen Rechner |
| staging (`develop`, `staging.<zone>`) | `docker-compose.staging.yml` | Caddy, Zertifikat über dns-01 | GitHub-Workflow auf dem self-hosted Runner nach jedem Merge auf `develop`, siehe [Staging Setup](docs/staging-setup.md) |
| Produktion (`main`, `appstore.<zone>`) | `docker-compose.staging.yml` | Caddy, Zertifikat über dns-01 | derselbe Workflow nach dem Release-Merge `develop` → `main`, den eine Person freigibt (ADR 0014) |
| eigenständige Installation | `docker-compose.prod.yml` | nginx, Zertifikat selbst hinterlegt | `make prod-up` auf einer eigenen VM, von Hand ([Anleitung](docs/prod-setup.md)); läuft derzeit nirgends |

Staging und Produktion entstehen beide vollständig aus OpenTofu und Ansible,
aus demselben Code; sie unterscheiden sich nur im Branch, in VM, Hostname und
Datenbanken. Die eigenständige Installation wird dagegen von Hand aufgesetzt.
Die Compose-Datei für Staging und Produktion hat deshalb bewusst keine
Make-Targets — sie soll nur über die Pipeline laufen, damit kein Arbeitsplatz
von dem abweicht, was dort erzeugt wird.

## Aufbau

```text
deployment/
├── Makefile                  # Einstiegspunkt für alles Lokale
├── docker-compose.*.yml      # ein Stack je Umgebung
├── caddy/                    # Reverse Proxy für Staging, mit rfc2136-Modul
├── nginx/                    # Reverse Proxy für Produktion
├── keycloak/                 # Realm-Export und dessen Template
├── seed/                     # Seed-Skript, Kurse, App-Beschreibungen
├── deploy-image/             # Image für `deploy.cmd`: OpenTofu, Ansible, Trivy
├── infrastructure/           # OpenTofu und Ansible
│   ├── tofu/                 # Modul, Staging- und Moodle-Umgebung
│   └── ansible/              # Playbooks für Staging und Moodle
├── docs/                     # Architektur, Harness, Setup-Anleitungen, ADRs
└── .github/workflows/        # Staging-Deploy (self-hosted Runner) und CI
```

Warum der Deploy auf einem self-hosted Runner läuft, steht in
[ADR 0002](docs/adr/0002-self-hosted-runner-auf-eigener-vm.md).

## Weiterführend

- [`infrastructure/README.md`](infrastructure/README.md) — OpenTofu-Modul, die
  beiden Umgebungen, Adressierung, State-Backend und die CI/CD-Workflows
