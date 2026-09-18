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
   ⬤ manuell            ○ automatisch        ○ automatisch       ○ automatisch
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

Zwischen Image-Push und Deploy liegt ein `repository_dispatch`: `backend`,
`frontend` und `worker` melden dem `deployment`-Repository, dass ein neues
Image bereitsteht, und dessen Workflow rollt es aus. Ein Merge auf `main`
erreicht OpenStack damit ohne weiteres Zutun.

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

> Der QA-Job gehört zum Deploy-Workflow, läuft aber auf `ubuntu-latest` und
> braucht deshalb weder OpenStack noch den self-hosted Runner. Er prüft damit
> auch dann, wenn gar nicht ausgerollt werden kann — siehe Abschnitt 6.

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

Danach meldet der Job **🚀 Deploy anstoßen** dem `deployment`-Repository per
`repository_dispatch` (`event_type: service-image-published`), dass ein neues
Image bereitsteht. Das ist das Bindeglied, das einen Merge bis auf die VM
durchreicht.

> Der Job läuft ausschließlich bei `push` auf `main`, nie aus einem Pull
> Request. Fehlt das Secret `DEPLOY_DISPATCH_TOKEN`, endet er mit einer Warnung
> statt mit einem Fehler — eine noch nicht eingerichtete Automatik soll keinen
> grünen Build rot färben.

---

## 6. Phase 5 — Deploy ○ automatisch

### Warum ein self-hosted Runner nicht verhandelbar ist

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
Zugangsdaten er hätte. Der Runner muss im DHBW-Netz stehen (Campus oder VPN).

Daraus folgt der Zuschnitt des Workflows `CD - Deploy to OpenStack`:

| Job | Runner | Inhalt |
|---|---|---|
| `qa` | `ubuntu-latest` | `terraform fmt`/`validate`, Ansible-Syntaxcheck und -Lint, Trivy-IaC-Scan mit SARIF |
| `deploy` | `[self-hosted, openstack]` | Terraform + Ansible gegen OpenStack |

> Alles, was ohne OpenStack auskommt, läuft damit auf GitHubs Infrastruktur —
> auch dann, wenn der self-hosted Runner gerade aus ist. Nur der Deploy selbst
> braucht das Universitätsnetz.

### Die Sicherheitsfrage, die dabei bleibt

Ein self-hosted Runner an einem **öffentlichen** Repository ist genau das,
wovor GitHub warnt:

> Self-hosted runners should almost never be used for public repositories on
> GitHub, because any user can open pull requests against the repository and
> compromise the environment.
>
> — GitHub, *Secure use reference*, „Hardening for self-hosted runners"

Diese Warnung entfällt nicht dadurch, dass der Prozess so verlangt ist. Drei
Maßnahmen halten das Risiko klein:

1. **`deploy` ist aus einem Pull Request nicht erreichbar.** Der Job nimmt nur
   `push` auf `main`, `workflow_dispatch` und `repository_dispatch` an. Wer
   einen Fork anlegt und einen PR öffnet, erreicht den Runner nicht — und
   Secrets bekommt ein Fork-PR ohnehin keine.
2. **Die Credentials hängen an der Environment `openstack`**, nicht am
   Repository. Nur ein Job, der diese Environment anfordert, sieht sie; dort
   lässt sich zusätzlich ein Reviewer als Freigabe erzwingen.
3. In *Settings → Actions → General* gehört **„Require approval for all
   external contributors"** aktiviert.

> Die Alternative, die dieses Projekt früher verfolgt hat, war ein eigener
> Forgejo-Host: Code öffentlich auf GitHub, Runner und Secrets in einer selbst
> kontrollierten Instanz. Das ist sicherheitstechnisch die sauberere Trennung,
> kostet aber den durchgehenden Automatismus, weil der Deploy dort von Hand
> gestartet wurde. Der Aufbau ist in [staging-setup.md](staging-setup.md)
> beschrieben und bleibt als Rückfallweg bestehen.

### Auslösen

Drei Wege:

| Auslöser | Modus | Wann |
|---|---|---|
| `push` auf `main` (deployment-Repo) | `apply` | Änderung an Compose, Terraform oder Ansible |
| `repository_dispatch` | `apply` | `backend`, `frontend` oder `worker` hat ein Image gepusht |
| `workflow_dispatch` | `plan` (Default) oder `apply` | von Hand, etwa zur Vorführung |

> Der manuelle Lauf steht absichtlich auf `plan`: ein Fehlklick darf keine
> Infrastruktur verändern. Ein Plan-Lauf prüft trotzdem alles Wesentliche —
> Runner, Checkout, alle Secrets und eine echte Keystone-Anmeldung.
>
> `seed` bleibt ebenfalls auf `false`: ein Deploy fasst keine Anwendungsdaten
> an, solange es nicht ausdrücklich verlangt wird.

### Was der Lauf dann selbst erledigt ○

1. **Vorprüfungen** — sind alle Secrets da, sind die Werkzeuge da, und
   antwortet Keystone überhaupt? Fehlt etwas, bricht der Lauf hier ab statt
   zwanzig Minuten später mitten in einem `terraform apply`.
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
| 10 | Deploy auslösen | ○ automatisch (`repository_dispatch`) | — |
| 11 | Terraform: Infrastruktur abgleichen | ○ automatisch | — |
| 12 | Ansible: VM konfigurieren, Stack starten | ○ automatisch | — |
| 13 | Migrationen | ○ automatisch | — |
| 14 | Seed-Daten | ⬤ manuell (Schalter) | **soll** manuell bleiben |
| 15 | DNS-Einträge | ⬤ manuell | könnte automatisiert werden |
| 16 | Health Checks | ○ automatisch | — |
| 17 | Fachliche Abnahme | ⬤ manuell | **soll** automatisiert *ergänzt* werden |
| 18 | Prod-Deployment | ⬤ manuell | **soll** automatisiert werden |
| 19 | Pre-commit-Hooks | — nicht vorhanden | **soll** eingerichtet werden |

**Die Kette läuft von Schritt 2 bis Schritt 16 ohne menschliches Zutun durch.**
Menschlich bleiben genau die beiden Entscheidungen, die es auch bleiben sollen:
ob der Code taugt (Review) und ob er nach `main` darf (Merge). Danach greift
niemand mehr ein, bis die Umgebung steht.

Der verbleibende manuelle Rest ist entweder einmalig (DNS), eine bewusste
Sperre (Seed-Daten) oder schlicht noch nicht gebaut (Prod, Pre-commit,
Smoke-Test).

> **Die eigentliche Grenze ist nicht organisatorisch, sondern physisch:** Der
> Deploy kann nur aus dem DHBW-Netz heraus laufen. Ist der self-hosted Runner
> aus, bleibt Schritt 10 in der Warteschlange stehen — die Automatik ist dann
> nicht falsch, sondern wartet. Die Schritte 2 bis 9 laufen davon unberührt auf
> GitHubs Runnern weiter.

---

## 11. Stand der Umsetzung

Die Repositories der Organisation `Six7-app-store` sind **Forks**. Bis zum
2026-09-18 gab es dort keinen einzigen Workflow-Lauf, was zunächst nach einer
Fork-Sperre aussah. Ein Testlauf hat das widerlegt: Actions funktioniert, es
hatte nur nie jemand gepusht, der einen Trigger traf. Seitdem laufen die
Pipelines.

**Erledigt:**

- CI läuft in allen vier Repositories, `workflow_dispatch` ergänzt.
- `CD - Deploy to OpenStack` ersetzt die alte `staging.yml`, die einen nie
  registrierten Runner nannte und jeden Push auf `main` rot gefärbt hätte.
- Die vier OpenStack-Secrets liegen in der Environment `openstack`.

**Noch offen — ohne diese Punkte bleibt der Deploy stehen:**

| Was | Warum es nicht automatisch geht |
|---|---|
| **Self-hosted Runner registrieren**, Labels `self-hosted` + `openstack` | Er muss im DHBW-Netz stehen; einen Dienst auf einem Rechner einzurichten ist eine bewusste Entscheidung des Betreibers |
| **`DEPLOY_DISPATCH_TOKEN`** in `backend`, `frontend`, `worker` | GitHub kann sich kein Token für sich selbst ausstellen. Fine-grained PAT mit `Contents:write` auf `Six7-app-store/deployment` |
| **`SSH_PRIVATE_KEY`**, **`STAGING_ENV_FILE`**, **`PG_CONN_STR`** | Liegen beim Team, nicht ableitbar. Ohne sie läuft der Deploy bis zum Terraform-Plan und hält dann an |
| **`IMAGE_NAMESPACE` umstellen** | Erst wenn unter `ghcr.io/six7-app-store/` Images liegen — also nach dem ersten grünen Lauf auf `main` und dem Öffentlich-Stellen der Packages |

---

## 12. Weiterführend

- [staging-setup.md](staging-setup.md) — Staging im Detail, Secrets, Verifikation
- [prod-setup.md](prod-setup.md) — der manuelle Prod-Weg, Schritt für Schritt
- [`infrastructure/README.md`](../infrastructure/README.md) — Terraform-Modul,
  Adressierung, State-Backend
- [`forgejo/SCRIPTS.md`](../forgejo/SCRIPTS.md) — wie der Forge-Host aufgesetzt
  wurde
