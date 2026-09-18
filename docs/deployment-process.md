# Deploymentprozess des App-Stores

Dieses Dokument beschreibt, was nach einer Codeänderung passiert, bis die
Änderung im laufenden App-Store sichtbar ist — also das Ausrollen **des Stores
selbst**, nicht das Ausrollen der Apps, die der Store anbietet.

Es benennt für jeden Schritt, ob er **automatisch** abläuft oder **von Hand**
erfolgt, und begründet bei den manuellen Schritten, ob sie es bleiben müssen
oder bloß noch sollen.

Die drei Umgebungen im Einzelnen stehen in [dev-setup.md](dev-setup.md),
[staging-setup.md](staging-setup.md) und [prod-setup.md](prod-setup.md); hier
geht es um den Ablauf, der sie verbindet.

---

## 1. Die Kette auf einen Blick

```
 Entwicklung          Prüfung              Artefakt            Ausrollen
 ───────────          ───────              ────────            ─────────

 Code ändern          CI auf dem PR        Image bauen         Deploy
 Branch, Commit   →   Lint, Tests,     →   und nach GHCR   →   Terraform
 Push                 Scans, Build         pushen              + Ansible
   ⬤ manuell            ○ automatisch        ○ automatisch       ⬤ manuell
                             │                     ▲                  │
                             ▼                     │                  ▼
                       Code Review            Merge auf main         DNS
                        ⬤ manuell              ⬤ manuell          ⬤ manuell
                                                                      │
                                                                      ▼
                                                                  Abnahme
                                                                 ◑ teils autom.
```

`○` automatisch · `⬤` manuell · `◑` gemischt

**Die Kette ist an genau einer Stelle unterbrochen**: zwischen Image-Push und
Ausrollen. Das Image entsteht ohne Zutun, auf die VM bringt es ein Mensch.
Warum das so ist und nicht anders sein kann, steht in Abschnitt 6; wie es geht,
im [Deploy-Runbook](deploy-runbook.md).

Beteiligt sind vier Repositories: `backend`, `frontend` und `worker` liefern je
ein Container-Image; dieses `deployment`-Repository hält die Compose-Stacks,
Terraform und Ansible und ist der Ort, an dem ausgerollt wird.

---

## 2. Phase 1 — Entwicklung ⬤ manuell

Entwickelt wird auf einem Feature-Branch gegen den lokalen Stack:

```bash
cd deployment
make dev-up        # Stack starten
make migrate-dev   # Migrationen
make health        # Backend, Frontend, Keycloak anpingen
```

**Keine Pre-commit-Hooks.** In keinem der vier Repositories liegt eine
`.pre-commit-config.yaml`. Formatierung und Linting werden ausschließlich in der
CI geprüft — lokal ist nichts erzwungen. Wer vor dem Push sicher gehen will,
ruft die Prüfungen selbst auf (`poetry run ruff check .` bzw. `npm run test`).

> Das ist der eine Schritt, der ohne Weiteres automatisierbar wäre und es
> **sollte**: Pre-commit-Hooks würden dieselben Prüfungen vorziehen und CI-Läufe
> sparen, die heute an Formatierungsfehlern scheitern. Sie sind schlicht noch
> nicht eingerichtet.

---

## 3. Phase 2 — Pull Request ○ automatisch

Ein Pull Request gegen `main` startet die GitHub-Actions-Pipeline des jeweiligen
Repositories. Die Jobs laufen parallel, `Build` wartet auf die Prüfjobs.

### backend und worker (Python)

| Job | Inhalt | Blockiert? |
|---|---|---|
| 🔍 Lint | `ruff check` — im **worker** zusätzlich `black --check`, `isort --check-only`, `mypy` | ja |
| 🧪 Test (unit) | pytest gegen einen Postgres-Service-Container | ja |
| 🧪 Test (integration) | pytest mit den externen Abhängigkeiten | ja |
| 📊 Coverage | Coverage-Report als Artefakt | nein |
| 🔒 Security | Trivy `fs` — Abhängigkeiten, Secrets, Misconfigs | ja, ab HIGH |
| 🐳 Build | Docker-Build `linux/amd64,linux/arm64`, **ohne** Push | ja |
| 🔒 Image Scan | Trivy gegen das gebaute Image | ja, ab HIGH |

### frontend (Vue/Vite)

| Job | Inhalt | Blockiert? |
|---|---|---|
| 📐 Type Check | `vue-tsc -b --noEmit` | ja |
| 🧪 Test | `vitest` mit Coverage, Badge-Erzeugung | ja |
| 📊 Coverage | Report; auf `main` zusätzlich Deploy auf GitHub Pages | nein |
| 🔒 Security | `npm audit --audit-level=high` **und** Trivy `fs` | ja, ab HIGH |
| 🐳 Build | Docker-Build **nur `linux/amd64`** | ja |
| 🔒 Image Scan | Trivy gegen das gebaute Image | ja, ab HIGH |

> Der Frontend-Build ist bewusst auf amd64 beschränkt. Das Ziel ist eine
> amd64-VM, und der emulierte arm64-Build blieb unter QEMU in `npm install`
> hängen, bis das 6-Stunden-Limit griff. Backend und Worker bauen weiterhin
> beide Architekturen.

### deployment

| Job | Inhalt | Blockiert? |
|---|---|---|
| 🔒 Gitleaks | Secret-Scan über die volle Historie | ja |
| QA | `terraform fmt`/`validate` über alle Umgebungen, Ansible-Syntaxcheck | ja |
| QA | `ansible-lint` | nein |
| QA | Trivy-Scan der Terraform-Definitionen | nein, aber SARIF |

> Der Workflow heißt `CI - Infrastructure QA`. Er prüft die Definitionen, die
> beim Deploy von Hand ausgeführt werden — ein kaputtes Playbook fällt damit
> auf, bevor es jemand auf die VM trägt.

Alle Sicherheitsbefunde werden zusätzlich als SARIF in den Security-Tab
hochgeladen — auch die per `.trivyignore` unterdrückten, damit sie sichtbar
bleiben.

---

## 4. Phase 3 — Code Review ⬤ manuell

Ein Mensch liest den Code und gibt ihn frei. Gemerged wird erst, wenn Review und
alle blockierenden Checks grün sind.

> **Muss manuell bleiben.** Kein Scan ersetzt das Urteil darüber, ob eine
> Änderung fachlich richtig ist.

---

## 5. Phase 4 — Merge auf main ⬤ manuell, danach ○ automatisch

Der Merge selbst ist eine menschliche Entscheidung. Was danach kommt, nicht:
Bei `push` auf `main` laufen dieselben Prüfjobs erneut, und der Job **📦 Push**
lädt das Image nach GHCR hoch.

Gepusht wird nach `ghcr.io/<org>/<repo>`, benannt aus `${{ github.repository }}`.
Getaggt wird:

| Tag | Wann |
|---|---|
| `latest` | auf dem Default-Branch |
| `sha-<commit>` | immer |
| `<major>.<minor>.<patch>` | bei Git-Tags `v*.*.*` |

**Hier endet die Automatik.** Ein neues Image liegt in der Registry — auf der
VM läuft weiterhin das alte, bis jemand den Deploy ausführt.

---

## 6. Phase 5 — Deploy ⬤ manuell

### Warum das nicht automatisiert ist

Das ist kein Sicherheitsargument, sondern schlicht Netzwerk. Gemessen am
2026-09-18 von einem GitHub-gehosteten Runner (öffentliche IP
`145.132.101.182`) aus:

| Ziel | Ergebnis |
|---|---|
| DNS `newstack.dhbw.cloud` | löst öffentlich auf → `141.72.5.140` |
| `https://…:5000/v3` (Keystone) | **`000 TIMEOUT`** |
| `https://…:443/` (Horizon) | **`000 TIMEOUT`** |

Der Name ist öffentlich, das Netz ist es nicht. Ein gehosteter Runner kann also
grundsätzlich nicht nach OpenStack ausrollen — unabhängig davon, welche
Zugangsdaten er hätte. **Das ist eine Firewall, kein Konfigurationsproblem.**

Automatisieren ließe sich der Deploy deshalb nur mit einem **self-hosted
Runner** im Campusnetz. Und damit kommt das zweite Argument:

### Die Sicherheitsfrage

Ein self-hosted Runner an einem **öffentlichen** Repository ist genau das,
wovor GitHub warnt:

> Self-hosted runners should almost never be used for public repositories on
> GitHub, because any user can open pull requests against the repository and
> compromise the environment.
>
> — GitHub, *Secure use reference*, „Hardening for self-hosted runners"

Ein Runner mit Produktionszugang, der an einem Repository hängt, bei dem jeder
Fremde einen Pull Request öffnen kann — das ist eine Kombination, die man für
einen gesparten Klick nicht eingeht.

**Beides zusammen** — das Netz lässt GitHub nicht durch, und der Ausweg über
einen eigenen Runner schafft ein größeres Problem als er löst — führt zu der
Entscheidung: Der Deploy bleibt ein Schritt, den ein Mensch im VPN ausführt.

> Dieses Projekt hat den Ausweg früher anders gelöst: ein eigener
> **Forgejo-Host**, Code öffentlich auf GitHub, Runner und Secrets in einer
> selbst kontrollierten Instanz. Das ist die sauberere Trennung und bleibt als
> Weg bestehen, siehe [staging-setup.md](staging-setup.md). Auch dort wurde der
> Deploy allerdings von Hand gestartet — an dieser Stelle der Kette ändert der
> Umweg nichts.

### Auslösen

Ein Mensch im Campusnetz oder VPN führt Terraform und Ansible aus. Die Schritte
im Einzelnen stehen im **[Deploy-Runbook](deploy-runbook.md)**.

Zwei Sicherungen sind dabei bewusst eingebaut:

> **Erst `plan` lesen, dann `apply`.** Zwei Dinge im Plan sind ein Stoppsignal:
> `must be replaced` an der VM und `destroy` an einem Volume — beides würde
> Daten vernichten.
>
> **Seed-Daten nur auf ausdrückliche Anforderung** (`-e seed_data=true`). Ein
> Deploy fasst sonst keine Anwendungsdaten an.

### Was dabei abläuft

1. **Umgebung setzen** — `OS_CLOUD`, der State-Backend-Zugang, und der
   öffentliche SSH-Schlüssel aus dem privaten abgeleitet, damit das
   OpenStack-Keypair zu dem Schlüssel passt, mit dem Ansible sich verbindet.
2. **Terraform** — `init`, `validate`, `plan`, dann nach Prüfung `apply`. Er
   gleicht die VM, ihre Security-Group und das zweite IPv4-Interface ab. Der
   State liegt in einem Postgres-Backend, nicht lokal.
3. **Inventory** aus den Terraform-Outputs erzeugen. Ist die Adresse leer, hier
   abbrechen — sonst liefe Ansible mit „no hosts matched" grün durch, ohne
   etwas zu tun.
4. **Ansible** — Netzwerk einrichten, Docker installieren, Stack und `.env`
   kopieren, Keycloak-Realm rendern, an GHCR anmelden, Images ziehen,
   `docker compose up -d`, Caddy bei Bedarf neu bauen.
5. **Migrationen** anwenden, bei `seed_data=true` zusätzlich das Seed-Skript.
6. **Aufräumen** — Inventory löschen, Secrets aus der Shell entfernen.

Ein vollständiger Durchlauf dauert etwa fünf bis zehn Minuten.

> Die Schritte 2 bis 5 laufen nach dem Start ohne weiteres Zutun. Manuell ist
> der *Anstoß*, nicht die Ausführung — Terraform und Ansible machen dieselbe
> Arbeit, die eine Pipeline machen würde.

---

## 7. Phase 6 — DNS ⬤ manuell

Die VM ist über beide Adressfamilien erreichbar, also gehören zwei Einträge
unter denselben Hostnamen (TTL 300):

```
A      <APP_HOSTNAME>   <vm_ipv4>
AAAA   <APP_HOSTNAME>   <vm_ip>
```

Beide Werte liefert `terraform output`. Das Zertifikat braucht keine
Aufmerksamkeit — Caddy weist die Kontrolle über dns-01 nach.

> **Nur beim ersten Mal und nach einem Neuaufbau nötig.** Bleibt die VM
> bestehen, bleiben die Adressen. Automatisierbar wäre es über die DNS-API der
> Zone; das ist bislang nicht eingerichtet.

---

## 8. Phase 7 — Abnahme ◑ teils automatisch

Das Playbook prüft am Ende selbst: es wartet auf die Backend-Gesundheit, wendet
die Migrationen an und gibt `docker compose ps` aus. Ein fehlgeschlagener Health
Check bricht den Lauf ab.

Von Hand bleibt der fachliche Blick: Anmeldung über Keycloak, eine App
ausrollen, die Oberfläche durchklicken.

> **Sollte weiter automatisiert werden.** Ein Smoke-Test gegen die laufende
> Umgebung wäre der nächste sinnvolle Ausbauschritt.

---

## 9. Produktion ⬤ vollständig manuell

Staging entsteht vollständig aus Terraform und Ansible. **Produktion wird von
Hand aufgesetzt**, beschrieben in [prod-setup.md](prod-setup.md): VM vorbereiten,
Repository klonen, `.env` befüllen, Zertifikat hinterlegen, `make prod-up`.

Die Images zieht auch Prod aus GHCR — gebaut wird auf der VM nichts.

> Der Unterschied ist bewusst: die Staging-Compose-Datei hat absichtlich keine
> Make-Targets, damit kein Arbeitsplatz von dem abweicht, was die Pipeline
> erzeugt. Für Prod fehlt die Entsprechung noch — hier **sollte** automatisiert
> werden, sobald eine dauerhafte Prod-Umgebung existiert.

---

## 10. Zusammenfassung: automatisch vs. manuell

| # | Schritt | Wie | Bewertung |
|---|---|---|---|
| 1 | Code ändern, committen, pushen | ⬤ manuell | muss |
| 2 | Lint, Format, Typen | ○ automatisch (CI) | — |
| 3 | Unit- und Integrationstests | ○ automatisch (CI) | — |
| 4 | Coverage-Report | ○ automatisch (CI) | — |
| 5 | Dependency-, Secret- und IaC-Scans | ○ automatisch (CI) | — |
| 6 | Image bauen und scannen | ○ automatisch (CI) | — |
| 7 | Code Review und Freigabe | ⬤ manuell | **muss** manuell bleiben |
| 8 | Merge auf `main` | ⬤ manuell | **muss** manuell bleiben |
| 9 | Image nach GHCR pushen | ○ automatisch (CI) | — |
| 10 | Deploy auslösen | ⬤ manuell (Mensch im VPN) | **muss**, siehe Abschnitt 6 |
| 11 | Terraform: Infrastruktur abgleichen | ○ automatisch | — |
| 12 | Ansible: VM konfigurieren, Stack starten | ○ automatisch | — |
| 13 | Migrationen | ○ automatisch | — |
| 14 | Seed-Daten | ⬤ manuell (Schalter) | **soll** manuell bleiben |
| 15 | DNS-Einträge | ⬤ manuell | könnte automatisiert werden |
| 16 | Health Checks | ○ automatisch | — |
| 17 | Fachliche Abnahme | ⬤ manuell | **soll** automatisiert *ergänzt* werden |
| 18 | Prod-Deployment | ⬤ manuell | **soll** automatisiert werden |
| 19 | Pre-commit-Hooks | — nicht vorhanden | **soll** eingerichtet werden |

**Die Schritte 2 bis 9 laufen vollautomatisch** — von der ersten Prüfung bis zum
fertigen, auf Sicherheitslücken gescannten Image in der Registry greift niemand
ein.

**Die Kette ist an genau einer Stelle unterbrochen:** zwischen Schritt 9 und
Schritt 10. Diese Unterbrechung ist der interessante Teil der Antwort, denn sie
hat zwei voneinander unabhängige Gründe, von denen schon jeder für sich reicht:

1. **Sie *muss* dort sein.** Die OpenStack-API ist von außen nicht erreichbar.
   Kein GitHub-Runner kommt hin — das ist eine Firewall, keine
   Konfigurationsfrage.
2. **Sie *soll* dort sein.** Der einzige Ausweg wäre ein self-hosted Runner an
   einem öffentlichen Repository, und der gäbe jedem, der einen Pull Request
   öffnen kann, eine Ausführungsumgebung mit Produktionszugang.

Danach läuft wieder alles von selbst: Terraform und Ansible erledigen die
Schritte 11 bis 13 und 16 ohne weiteres Zutun. **Manuell ist der Anstoß, nicht
die Arbeit.**

Der übrige manuelle Rest ist entweder einmalig (DNS), eine bewusste Sperre
(Seed-Daten) oder schlicht noch nicht gebaut (Prod, Pre-commit, Smoke-Test).

---

## 11. Stand der Umsetzung

Die Repositories der Organisation `Six7-app-store` sind **Forks**. Bis zum
2026-09-18 gab es dort keinen einzigen Workflow-Lauf, was zunächst nach einer
Fork-Sperre aussah. Ein Testlauf hat das widerlegt: Actions funktioniert, es
hatte nur nie jemand gepusht, der einen Trigger traf. Seitdem laufen die
Pipelines.

**Erledigt:**

- CI läuft in allen vier Repositories, `workflow_dispatch` ergänzt.
- `CI - Infrastructure QA` prüft Terraform und Ansible bei jedem Push und Pull
  Request. Sie ersetzt die alte `staging.yml`, die einen nie registrierten
  Runner nannte und jeden Push auf `main` rot gefärbt hätte.
- Der manuelle Deploy ist als [Runbook](deploy-runbook.md) beschrieben.

**Noch offen:**

| Was | Wann nötig |
|---|---|
| **`IMAGE_NAMESPACE` umstellen** | Erst wenn unter `ghcr.io/six7-app-store/` Images liegen — also nach dem ersten Merge auf `main` und dem Öffentlich-Stellen der Packages unter `github.com/orgs/Six7-app-store/packages`. Siehe [`.env.staging.example`](../.env.staging.example) |
| **Smoke-Test nach dem Deploy** | Wäre der nächste sinnvolle Ausbauschritt, siehe Abschnitt 8 |
| **Pre-commit-Hooks** | Siehe Abschnitt 2 |

---

## 12. Weiterführend

- [deploy-runbook.md](deploy-runbook.md) — der Deploy Schritt für Schritt, mit
  den Stolperstellen, die tatsächlich Zeit gekostet haben
- [staging-setup.md](staging-setup.md) — Staging im Detail, Secrets, Verifikation
- [prod-setup.md](prod-setup.md) — der manuelle Prod-Weg, Schritt für Schritt
- [`infrastructure/README.md`](../infrastructure/README.md) — Terraform-Modul,
  Adressierung, State-Backend
- [`forgejo/SCRIPTS.md`](../forgejo/SCRIPTS.md) — wie der Forge-Host aufgesetzt
  wurde
