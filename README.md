# Deployment

Dieses Repository hält alles zusammen, was die Plattform zum Laufen braucht: die
Compose-Stacks für die drei Umgebungen, den zentralen Makefile, den
Keycloak-Realm, die Seed-Daten und die Terraform- und Ansible-Definitionen der
Infrastruktur.

Die Anwendung selbst liegt in eigenen Repositories (`backend`, `frontend`,
`worker`). Hier wird nichts gebaut, was dort entsteht — hier wird es
zusammengesetzt, konfiguriert und ausgerollt.

## Setup-Anleitungen

- [Lokales Dev Setup](docs/dev-setup.md)
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
| `make dev-restart-worker` | Neustart, wenn der Hot-Reload nicht greift — etwa bei Celery-Tasks |
| `make migrate-dev` | Alembic-Migrationen anwenden |
| `make migration-create MSG="..."` | Neue Migration erzeugen |
| `make seed-data` | Seed-Daten laden; idempotent, gefahrlos wiederholbar |
| `make health` | Backend, Frontend und Keycloak anpingen |

## Die drei Umgebungen

| Umgebung | Compose-Datei | Reverse Proxy | Wie sie ausgerollt wird |
|---|---|---|---|
| dev | `docker-compose.dev.yml` | keiner, Dienste direkt auf Ports | `make dev-up` auf dem eigenen Rechner |
| staging | `docker-compose.staging.yml` | Caddy, Zertifikat über dns-01 | Workflow im eigenen Forgejo, siehe [Staging Setup](docs/staging-setup.md) |
| prod | `docker-compose.prod.yml` | nginx, Zertifikat selbst hinterlegt | `make prod-up` auf der Zielmaschine |

Staging und Produktion unterscheiden sich nicht nur in der Größe: Staging
entsteht vollständig aus Terraform und Ansible, Produktion wird bislang von Hand
aufgesetzt. Die Compose-Datei für Staging hat deshalb bewusst keine Make-Targets
— sie soll nur über die Pipeline laufen, damit kein Arbeitsplatz von dem
abweicht, was dort erzeugt wird.

## Aufbau

```text
deployment/
├── Makefile                  # Einstiegspunkt für alles Lokale
├── docker-compose.*.yml      # ein Stack je Umgebung
├── caddy/                    # Reverse Proxy für Staging, mit rfc2136-Modul
├── nginx/                    # Reverse Proxy für Produktion
├── keycloak/                 # Realm-Export und dessen Template
├── seed/                     # Seed-Skript, Kurse, App-Beschreibungen
├── forgejo/                  # der Forge-Host: Compose-Stack und Setup-Skripte
├── infrastructure/           # Terraform und Ansible
│   ├── terraform/            # Modul und Umgebungen
│   └── ansible/              # Playbooks für Staging und den Forge-Host
├── docs/                     # die drei Setup-Anleitungen
├── .forgejo/workflows/       # der Deploy-Workflow, der tatsächlich läuft
└── .github/workflows/        # das Gegenstück für GitHub, hier ohne Wirkung
```

Warum der Deploy in Forgejo liegt und nicht auf GitHub, steht in
[Staging Setup](docs/staging-setup.md) unter „Warum ein eigenes Forgejo".

## Weiterführend

- [`infrastructure/README.md`](infrastructure/README.md) — Terraform-Modul, die
  beiden Umgebungen, Adressierung, State-Backend und die CI/CD-Workflows
- [`forgejo/SCRIPTS.md`](forgejo/SCRIPTS.md) — die Skripte, mit denen der
  Forge-Host aufgesetzt wurde, Schritt für Schritt
