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

 Code ändern          CI auf dem PR        Image bauen         Deploy auslösen
 Branch, Commit   →   Lint, Tests,     →   und nach GHCR   →   im Forgejo
 Push                 Scans, Build         pushen              (Terraform+Ansible)
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
VM läuft weiterhin das alte.

---

## 6. Phase 5 — Deploy ⬤ manuell ausgelöst, dann ○ automatisch

### Warum der Auslöser manuell ist

Dies ist die zentrale Entwurfsentscheidung des Prozesses, und sie ist bewusst so
getroffen.

Ausgerollt wird von einem **self-hosted Runner**, denn nur ein solcher erreicht
die OpenStack-VM und darf die Zugangsdaten halten. GitHub rät davon an
öffentlichen Repositories ausdrücklich ab:

> Self-hosted runners should almost never be used for public repositories on
> GitHub, because any user can open pull requests against the repository and
> compromise the environment.
>
> — GitHub, *Secure use reference*, „Hardening for self-hosted runners"

Deshalb liegt der Runner samt Secrets in einer **eigenen Forgejo-Instanz**, die
das Team selbst kontrolliert; der Code bleibt öffentlich auf GitHub. Forgejo
erhält das Repository als Pull-Mirror, weshalb der Workflow unter
`.forgejo/workflows/staging.yml` **im GitHub-Repo** liegen muss — ein Mirror ist
schreibgeschützt.

Den Deploy von GitHub aus anzustoßen hieße, ein Forgejo-Token als GitHub-Secret
zu hinterlegen — also genau die Kopplung herzustellen, die diese Trennung
vermeiden soll. Der Preis ist der verlorene Automatismus.

> **Muss manuell bleiben**, solange der Code öffentlich liegt und der Runner
> Produktionszugang hat. Ein Auto-Deploy ließe sich nur *innerhalb* von Forgejo
> bauen, nicht von GitHub aus.

Ausführlich steht das in [staging-setup.md](staging-setup.md) unter
„Warum ein eigenes Forgejo".

### Auslösen

Im Forgejo unter **Actions → CD - Staging Deployment (Forgejo) → Run workflow**:

| Eingabe | Bedeutung | Default |
|---|---|---|
| `mode` | `plan` hält vor jeder Änderung an, `apply` rollt aus | `plan` |
| `seed` | legt Seed-Nutzer, Kurse und Apps an | `false` |
| `forget_volume` | Notausgang für ein in `creating` hängendes Cinder-Volume | `false` |

> `plan` als Default ist Absicht: ein Fehlklick kann keine Infrastruktur
> verändern. Ein Plan-Lauf prüft trotzdem alles Wesentliche — Runner, Job-Image,
> Checkout, alle sechs Secrets und eine echte Keystone-Anmeldung.
>
> `seed: false` als Default ebenfalls: ein Deploy fasst keine Anwendungsdaten an,
> solange es nicht ausdrücklich verlangt wird.

Üblich sind **zwei** Läufe: erst `plan` lesen, dann `apply`. Erwartet wird
`0 to add, 0 to change, 0 to destroy` und keine Zeile `must be replaced`.

### Was der Lauf dann selbst erledigt ○

1. **Vorprüfungen** — Werkzeugversionen, `terraform fmt -check`, Trivy-Scan der
   IaC (in Staging bewusst nicht blockierend, Befunde als SARIF-Artefakt).
2. **SSH-Schlüssel** aus dem Secret schreiben, den öffentlichen Teil ableiten
   und an Terraform übergeben.
3. **Terraform** — `init`, `validate`, `plan`; bei `apply` die VM, ihre
   Security-Group und das zweite IPv4-Interface abgleichen. State liegt in einem
   Postgres-Backend.
4. **Inventory** aus den Terraform-Outputs erzeugen (bricht ab, wenn leer —
   sonst liefe Ansible mit „no hosts matched" grün durch, ohne etwas zu tun).
5. **Ansible** — Netzwerk einrichten, Docker installieren, Stack und `.env`
   kopieren, Keycloak-Realm rendern, an GHCR anmelden, Images ziehen,
   `docker compose up -d`, Caddy bei Bedarf neu bauen.
6. **Migrationen** anwenden, bei `seed: true` das Seed-Skript.
7. **Aufräumen** — Schlüssel und Inventory werden in jedem Fall gelöscht.

Ein vollständiger Lauf dauert etwa fünf Minuten.

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
| 10 | Deploy auslösen | ⬤ manuell (Forgejo) | **muss**, siehe Abschnitt 6 |
| 11 | Terraform: Infrastruktur abgleichen | ○ automatisch | — |
| 12 | Ansible: VM konfigurieren, Stack starten | ○ automatisch | — |
| 13 | Migrationen | ○ automatisch | — |
| 14 | Seed-Daten | ⬤ manuell (Schalter) | **soll** manuell bleiben |
| 15 | DNS-Einträge | ⬤ manuell | könnte automatisiert werden |
| 16 | Health Checks | ○ automatisch | — |
| 17 | Fachliche Abnahme | ⬤ manuell | **soll** automatisiert *ergänzt* werden |
| 18 | Prod-Deployment | ⬤ manuell | **soll** automatisiert werden |
| 19 | Pre-commit-Hooks | — nicht vorhanden | **soll** eingerichtet werden |

**Die Kette ist an genau einer Stelle bewusst unterbrochen**: zwischen Schritt 9
und Schritt 10. Alles davor ist vollautomatisch, alles danach ebenfalls — nur
der Übergang ist eine menschliche Entscheidung, und zwar aus einem
Sicherheitsgrund, nicht aus Bequemlichkeit.

---

## 11. Stand der Umsetzung

Der beschriebene Prozess ist im Ursprungsprojekt vollständig in Betrieb. In der
Organisation `Six7-app-store` sind die Repositories **Forks**, und für Forks
aktiviert GitHub Actions nicht von selbst:

- In allen vier Repositories dieser Organisation gibt es **bislang null
  Workflow-Läufe**, obwohl die Workflow-Dateien vorhanden sind.
- Folglich existieren unter `ghcr.io/six7-app-store/` noch **keine Images**. Die
  Compose-Stacks ziehen deshalb weiterhin aus dem Namespace des
  Ursprungsprojekts; steuerbar über `IMAGE_NAMESPACE`, siehe
  [`.env.staging.example`](../.env.staging.example).

Zum Aktivieren genügt je Repository ein Klick im **Actions**-Tab
(„I understand my workflows, go ahead and enable them"). Danach gilt die
Reihenfolge: erst ein grüner Lauf auf `main`, dann die Packages unter
`github.com/orgs/<org>/packages` auf öffentlich stellen, dann `IMAGE_NAMESPACE`
umtragen.

> Zu beachten: [`.github/workflows/staging.yml`](../.github/workflows/staging.yml)
> löst bei jedem Push auf `main` aus, findet aber weder `self-hosted`-Runner noch
> Secrets. Sobald Actions aktiviert ist, erzeugt dieser Workflow dauerhaft rote
> Läufe. Der wirksame Deploy ist der Forgejo-Workflow daneben.

---

## 12. Weiterführend

- [staging-setup.md](staging-setup.md) — Staging im Detail, Secrets, Verifikation
- [prod-setup.md](prod-setup.md) — der manuelle Prod-Weg, Schritt für Schritt
- [`infrastructure/README.md`](../infrastructure/README.md) — Terraform-Modul,
  Adressierung, State-Backend
- [`forgejo/SCRIPTS.md`](../forgejo/SCRIPTS.md) — wie der Forge-Host aufgesetzt
  wurde
