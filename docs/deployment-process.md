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

**Die Kette läuft durch.** Von der ersten Prüfung im Pull Request bis zum
aktualisierten Staging greift niemand ein; manuell sind nur noch Review und
Merge am Anfang — und der Sprung nach Produktion, absichtlich.

Der Deploy selbst läuft dabei nicht auf GitHub, sondern auf einem Runner im
Campusnetz, den eine eigene Forgejo-Instanz betreibt. Warum das so sein muss,
steht in Abschnitt 6; wie der Merge dort ankommt, in Abschnitt 11.

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
| 🧪 Test (integration) | pytest über alles, was nicht `unit` markiert ist | ja |
| 📊 Coverage | führt die Daten beider Test-Jobs zusammen, HTML-Report + Badge; auf `main` zusätzlich Deploy auf GitHub Pages | nein |
| 🔒 Security | `pip-audit --strict` **und** Trivy `fs` (Abhängigkeiten, Secrets, Misconfigs) | ja, ab HIGH |
| 🐳 Build | Docker-Build `linux/amd64,linux/arm64`, **ohne** Push | ja |
| 🔒 Image Scan | Trivy gegen das gebaute Image (amd64, `--load`) | ja, ab HIGH |

### frontend (Vue/Vite)

| Job | Inhalt | Blockiert? |
|---|---|---|
| 📐 Type Check | `vue-tsc -b --noEmit` | ja |
| 🧪 Test | `vitest` mit Coverage, Badge-Erzeugung | ja |
| 📊 Coverage | Report; auf `main` zusätzlich Deploy auf GitHub Pages | nein |
| 🔒 Security | `npm audit --audit-level=high --omit=dev` **und** Trivy `fs` | ja, ab HIGH |
| 🐳 Build | Docker-Build **nur `linux/amd64`** | ja |
| 🔒 Image Scan | Trivy gegen das gebaute Image | ja, ab HIGH |

> Der Frontend-Build ist bewusst auf amd64 beschränkt. Das Ziel ist eine
> amd64-VM, und der emulierte arm64-Build blieb unter QEMU in `npm install`
> hängen, bis das 6-Stunden-Limit griff. Backend und Worker bauen weiterhin
> beide Architekturen.

### deployment

| Workflow | Inhalt | Blockiert? |
|---|---|---|
| 🔒 Secret Scan | `gitleaks detect` über die volle Historie | ja |
| CI - Infrastructure QA | `terraform fmt -check`, `validate` über **alle** Umgebungen unter `envs/` | ja |
| CI - Infrastructure QA | Ansible-Syntaxcheck gegen `staging.yml`, nach `ansible-galaxy`-Install | ja |
| CI - Infrastructure QA | `ansible-lint` | nein |
| CI - Infrastructure QA | Trivy-Scan der Terraform-Definitionen | nein, aber SARIF |

> `validate` läuft mit `-backend=false`: der echte State liegt in Postgres, das
> ohne Zugangsdaten und ohne DHBW-Netz nicht erreichbar ist. Für eine Syntax-
> und Typprüfung braucht es ihn nicht.

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

Gepusht wird nach `ghcr.io/<org>/<repo>`, benannt aus `${{ github.repository }}`
— in einem Fork also in dessen Namespace, nicht in den des Upstreams. Getaggt
wird:

| Tag | Wann |
|---|---|
| `latest` | auf dem Default-Branch |
| `sha-<commit>` | immer |
| `<major>.<minor>.<patch>` | bei Git-Tags `v*.*.*` |

> Welchen Namespace der Deploy später **zieht**, steht unabhängig davon in
> `IMAGE_NAMESPACE` in der `.env` der VM (Vorlage:
> [`.env.staging.example`](../.env.staging.example)). Zeigt der auf eine andere
> Organisation als die, in der gebaut wurde, rollt der Deploy fremde Images aus
> — ohne Fehlermeldung, weil `latest` dort ja existiert.

Ist der Lauf grün, stößt **CD - Staging-Deploy anstossen** den Deploy auf dem
Forgejo-Runner an — siehe Abschnitt 11. Bis dahin läuft auf der VM weiterhin das
alte Image.

---

## 6. Phase 5 — Deploy ○ automatisch, auf einem Runner im Campusnetz

### Warum GitHub Actions hier nicht ausrollt

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

Automatisieren ließe sich der Deploy deshalb nur mit einem Runner **im
Campusnetz**. Und damit kommt die zweite Frage:

### Warum der Runner nicht an GitHub hängt

Ein self-hosted Runner an einem **öffentlichen** Repository ist genau das,
wovor GitHub warnt:

> Self-hosted runners should almost never be used for public repositories on
> GitHub, because any user can open pull requests against the repository and
> compromise the environment.
>
> — GitHub, *Secure use reference*, „Hardening for self-hosted runners"

Ein Runner mit Produktionszugang an einem Repository, bei dem jeder Fremde einen
Pull Request öffnen kann — das ist eine Kombination, die man für einen
gesparten Klick nicht eingeht.

**Der Ausweg, den dieses Projekt gewählt hat**, löst beides auf einmal: Der
Runner hängt an einer eigenen **Forgejo**-Instanz im Campusnetz. GitHub bleibt
primär und öffentlich; Forgejo spiegelt das `deployment`-Repository als
Pull-Mirror und steuert nur Runner und Secrets bei. Fremde können dort keinen
Pull Request öffnen, weil sie keinen Zugang haben.

Weil ein Pull-Mirror in Forgejo **read-only** ist, muss jede Datei, die er
ausführt, über den Mirror ankommen — die Deploy-Definition liegt deshalb im
GitHub-Repository unter
[`.forgejo/workflows/staging.yml`](../.forgejo/workflows/staging.yml) und bleibt
damit öffentlich einsehbar.

### Auslösen

Im Regelfall gar nicht von Hand: Ein grüner CI-Lauf auf `main` startet den
Deploy selbst, Abschnitt 11 beschreibt den Weg. Der Knopf bleibt trotzdem, für
Wiederholungen und für den Fall, dass man den Plan erst sehen will — im Forgejo
unter **Actions → CD - Staging Deployment (Forgejo) → Run workflow**. Zwei
Eingaben:

| Eingabe | Default | Wirkung |
|---|---|---|
| `mode` | `plan` | `plan` hält vor jeder Änderung an; `apply` rollt durch |
| `seed` | `false` | legt zusätzlich Seed-Benutzer, -Kurse und -Apps an |

`plan` als Default ist Absicht: Ein Fehlklick kann nichts verändern. Der
Plan-Lauf prüft trotzdem alles, worauf es ankommt — Job-Zustellung, Job-Image,
Checkout, alle sechs Secrets und eine echte Keystone-Anmeldung. Der automatische
Auslöser übergibt dagegen ausdrücklich `mode=apply`; er soll ja durchlaufen.

Daneben besteht der Weg von Hand fort, für den Fall, dass der Forge-Host steht
oder etwas klemmt: **[deploy.cmd](../deploy.cmd)** auf einem Windows-Rechner mit
Docker Desktop, oder die Einzelschritte aus dem
**[Deploy-Runbook](deploy-runbook.md)**. Beide führen dieselben Befehle aus wie
der Workflow.

> **Erst `plan` lesen, dann `apply`.** Zwei Dinge im Plan sind ein Stoppsignal:
> `must be replaced` an der VM und `destroy` an einem Volume — beides würde
> Daten vernichten. `deploy.cmd` bricht in dem Fall von sich aus ab.
>
> **Seed-Daten nur auf ausdrückliche Anforderung.** Ein Deploy fasst sonst keine
> Anwendungsdaten an.

### Was dabei abläuft

1. **Werkzeugprüfung** — `terraform`, `ansible`, `trivy` melden ihre Version.
   Fehlt etwas im Job-Image, scheitert der Lauf hier statt zwanzig Minuten
   später mitten im `apply`.
2. **`terraform fmt -check`** und ein Trivy-Scan der Terraform-Dateien. Der Scan
   ist für Staging bewusst nicht blockierend; sein SARIF wird als Artefakt
   abgelegt, weil Forgejo keinen Security-Tab hat.
3. **SSH-Schlüssel** aus dem Secret schreiben und den öffentlichen Teil daraus
   ableiten, damit das OpenStack-Keypair immer zu dem Schlüssel passt, mit dem
   Ansible sich gleich verbindet.
4. **Terraform** — `init`, `validate`, `plan`; bei `mode=apply` dann `apply`. Er
   gleicht VM, Security-Group und das zweite IPv4-Interface ab. Der State liegt
   im Postgres-Backend, nicht auf dem Runner: Job-Container werden nach jedem
   Lauf gelöscht.
5. **Inventory** aus den Terraform-Outputs erzeugen. Ist die Adresse leer, bricht
   der Schritt ab — sonst liefe Ansible mit „no hosts matched" grün durch, ohne
   etwas zu tun.
6. **Ansible** — Netzwerk einrichten, Datenvolume einhängen, Stack und `.env`
   kopieren, Keycloak-Realm rendern, an GHCR anmelden, Images ziehen,
   `docker compose up -d`, Caddy bei Bedarf neu bauen.
7. **Migrationen** anwenden (`alembic upgrade head` als eigener Playbook-Schritt,
   nicht als Init-Container — so landen Exit-Code und stderr sichtbar im Log),
   bei `seed=true` zusätzlich das Seed-Skript.
8. **Aufräumen** — Schlüssel und Inventory löschen, Zugangsdaten aus dem
   Docker-Root-Store entfernen.

Ein vollständiger Durchlauf dauert etwa fünf bis zehn Minuten.

---

## 7. Phase 6 — DNS ⬤ manuell

Die VM ist über beide Adressfamilien erreichbar, also gehören zwei Einträge
unter denselben Hostnamen (TTL 300):

```
A      <APP_HOSTNAME>   <vm_ipv4>
AAAA   <APP_HOSTNAME>   <vm_ip>
```

Beide Werte liefert `terraform output`. Das Zertifikat braucht keine
Aufmerksamkeit — Caddy weist die Kontrolle über **dns-01** nach (rfc2136), weil
http-01 und tls-alpn-01 an diesem Host beide scheiterten.

> **Nur beim ersten Mal und nach einem Neuaufbau nötig.** Bleibt die VM
> bestehen, bleiben die Adressen. Automatisierbar wäre es über die DNS-API der
> Zone; das ist bislang nicht eingerichtet.

---

## 8. Phase 7 — Abnahme ◑ teils automatisch

Das Playbook prüft am Ende selbst: es wartet auf den Backend-Container, wendet
die Migrationen an, wartet auf Keycloak, lädt die Caddy-Konfiguration neu und
gibt `docker compose ps` aus. Ein fehlgeschlagener Health Check bricht den Lauf
ab.

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

Prod unterscheidet sich außerdem technisch von Staging: TLS terminiert dort
`nginx` mit einem selbst ausgestellten Zertifikat, nicht Caddy mit ACME. Für
Prod gibt es weder eine Terraform-Umgebung noch ein Playbook.

> Der Unterschied ist teils bewusst: die Staging-Compose-Datei hat absichtlich
> keine Make-Targets, damit kein Arbeitsplatz von dem abweicht, was die Pipeline
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
| 10 | Deploy auslösen | ○ automatisch nach grüner CI | Knopf bleibt für Wiederholungen |
| 11 | Terraform: Infrastruktur abgleichen | ○ automatisch (Runner) | — |
| 12 | Ansible: VM konfigurieren, Stack starten | ○ automatisch (Runner) | — |
| 13 | Migrationen | ○ automatisch (Runner) | — |
| 14 | Seed-Daten | ⬤ manuell (Schalter) | **soll** manuell bleiben |
| 15 | DNS-Einträge | ⬤ manuell | könnte automatisiert werden |
| 16 | Health Checks | ○ automatisch | — |
| 17 | Fachliche Abnahme | ⬤ manuell | **soll** automatisiert *ergänzt* werden |
| 18 | Prod-Deployment | ⬤ manuell | **soll** automatisiert werden |
| 19 | Pre-commit-Hooks | — nicht vorhanden | **soll** eingerichtet werden |

**Die Schritte 2 bis 13 und 16 laufen vollautomatisch** — vom Merge bis zum
aktualisierten Staging greift niemand ein.

Was manuell bleibt, ist es entweder mit Absicht (Review, Merge, Prod,
Seed-Daten), nur einmalig nötig (DNS) oder schlicht noch nicht gebaut
(Pre-commit, Smoke-Test).

---

## 11. Der Auslöser: wie der Merge den Deploy startet

Bis dahin war die Kette an dieser Stelle unterbrochen: Der Runner stand im
richtigen Netz, hatte alle Secrets — nur drücken musste den Knopf ein Mensch.
Diese Lücke ist geschlossen.

### Der Weg eines Merges

```
  Merge auf main (GitHub)
        │
        ▼
  CI läuft durch, Image nach GHCR
        │
        │  workflow_run: erst wenn die CI grün ist
        ▼
  .github/workflows/trigger-staging-deploy.yml
        │
        │  HTTPS auf Port 8443, zwei Token im Header
        ▼
  Caddy auf dem Forge-Host  ──► alles außer 3 Endpunkten: 404
        │
        ▼
  Forgejo startet CD - Staging Deployment (mode=apply)
        │
        ▼
  Terraform → Ansible → Compose → Staging
```

Der auslösende Job trägt **keine** Zugangsdaten zu OpenStack, keinen
SSH-Schlüssel und keine `.env`. Er kennt die Adresse des Forge-Hosts und zwei
Token, mehr nicht. Alles, womit man Schaden anrichten könnte, liegt weiterhin
ausschließlich in Forgejo.

### Warum `workflow_run` und nicht `push`

Ein `push`-Trigger würde feuern, während die CI noch baut — der Deploy liefe
dann gegen das **alte** Image, das noch in GHCR liegt. `workflow_run` wartet auf
das Ende des CI-Laufs und prüft zusätzlich `conclusion == 'success'`, denn
ausgelöst wird es auch nach einem Fehlschlag.

### Der Umweg über den Mirror

Forgejo bekommt dieses Repository als Pull-Mirror und holt sich neue Commits in
einem eigenen Takt — nicht beim Push. Ein Dispatch unmittelbar nach dem Merge
träfe also womöglich noch den Stand von davor: Der Deploy liefe mit den alten
Playbooks und meldete trotzdem grün.

Deshalb macht der Auslöser im `deployment`-Repository drei Schritte statt einem:

1. `POST …/mirror-sync` — Forgejo anstoßen, jetzt zu holen
2. `GET …/branches/main` in Schleife, bis der Commit-SHA dem entspricht, auf dem
   die QA grün war (bis zu 5 Minuten)
3. erst dann `POST …/actions/workflows/staging.yml/dispatches`

Bleibt der Mirror zurück, bricht der Job ab, statt einen Deploy mit altem Stand
zu starten. In `backend`, `frontend` und `worker` entfallen die Schritte 1 und
2: Ein neues Image ändert nichts an den Dateien, die der Runner ausführt.

### Der Spalt in der Firewall

Der Forge-Host ist campus-only, und das bleibt er — mit einer Ausnahme:
`dispatch_port` (Standard **8443**) ist aus dem Internet erreichbar. Was dort
antwortet, ist aber nicht Forgejo, sondern ein eigener Caddy-Block, der genau
drei Endpunkte an genau einem Repository durchlässt und auf alles andere `404`
antwortet — auch auf die Anmeldeseite und auf git-over-HTTPS.

Zwei Hürden liegen davor:

| Hürde | Wozu |
|---|---|
| `X-Deploy-Auth` | gemeinsames Geheimnis; hält Scanner fern, bevor überhaupt jemand Forgejo erreicht |
| `Authorization: token …` | die eigentliche Authentifizierung, von Forgejo geprüft |

> **Die beiden Dateien gehören zusammen.**
> [`security_group.tf`](../infrastructure/terraform/envs/forgejo/security_group.tf)
> öffnet den Port, [`caddy/Caddyfile`](../forgejo/caddy/Caddyfile) verengt ihn.
> Den Port zu öffnen, ohne dass der Caddy-Block steht, stellt die ganze
> Forgejo-Instanz ins Internet. Ändert sich eine der beiden Dateien, gehört ein
> Blick in die andere.
>
> Genauso gefährlich: ein **leerer** Wert. `header X-Deploy-Auth {$…}` mit
> leerem Geheimnis trifft auch ohne Header, und ein leeres
> `FORGEJO_DEPLOY_REPO` weitet den Pfad-Matcher auf jedes Repository der
> Instanz aus. [`forgejo.yml`](../infrastructure/ansible/forgejo.yml) bricht
> deshalb ab, wenn eines der beiden fehlt.

Wieder zumachen geht in einem Schritt: `dispatch_port_enabled = false` in
`envs/forgejo`, `terraform apply`. Der Auslöser scheitert danach mit einer
klaren Meldung, und Deploys laufen wieder per Knopfdruck.

### Einrichten

**1. Auf dem Forge-Host** — in die `.env` neben den TLS-Werten (Vorlage:
[`forgejo/.env.example`](../forgejo/.env.example)):

```bash
FORGEJO_DEPLOY_REPO=<org>/deployment      # so wie es in der Forgejo-URL steht
FORGEJO_DISPATCH_AUTH=$(openssl rand -hex 32)
```

**2. Einen Forgejo-Token anlegen** — als Benutzer, der das gespiegelte
Repository sehen darf: *Einstellungen → Anwendungen → Zugriffstoken*. Nötig sind
`write:repository` (für `mirror-sync` und den Dispatch) und `read:repository`.

**3. Terraform und Ansible laufen lassen**, damit Port und Caddy-Block
entstehen:

```bash
cd infrastructure/terraform/envs/forgejo && terraform apply
cd ../../../ansible && ansible-playbook -i inventory-forgejo.sh forgejo.yml
```

**4. In jedem der vier GitHub-Repositories** vier Secrets hinterlegen
(*Settings → Secrets and variables → Actions*):

| Secret | Wert |
|---|---|
| `FORGEJO_BASE_URL` | `https://<forge-hostname>:8443` — mit Port, ohne Schrägstrich am Ende |
| `FORGEJO_DEPLOY_REPO` | `<org>/deployment`, derselbe Wert wie in der `.env` |
| `FORGEJO_TOKEN` | der Token aus Schritt 2 |
| `FORGEJO_DISPATCH_AUTH` | dasselbe Geheimnis wie in der `.env` |

Fehlt eines, bricht der Auslöser im ersten Schritt mit einer Liste der fehlenden
Namen ab, statt in einen unklaren Netzwerkfehler zu laufen.

> **Zum Einspielen der Workflow-Dateien:** Ein Push, der etwas unter
> `.github/workflows/` anfasst, verlangt einen Token mit `workflow`-Scope.
> Fehlt der, weist GitHub den Push ab — das sieht wie ein Rechteproblem am
> Branch aus, ist aber keines. Entweder den Scope ergänzen oder die Datei über
> die GitHub-Weboberfläche anlegen.

### Prüfen, ob es wirkt

```bash
# Erreichbarkeit — von irgendwo außerhalb des Campusnetzes:
curl -s -o /dev/null -w '%{http_code}
' https://<forge-hostname>:8443/
# 404 ist das richtige Ergebnis: der Port antwortet, gibt aber nichts preis.
# 000 heißt: Port zu oder Host nicht erreichbar.
```

Danach eine Kleinigkeit auf `main` mergen und zusehen: In GitHub erscheint
*CD - Staging-Deploy anstossen*, in Forgejo kurz darauf der Lauf.

### Was bewusst manuell bleibt

Review und Merge bleiben menschliche Entscheidungen, und der Sprung nach
**Produktion** bleibt es auch. Ein Tor, an dem jemand zustimmt, ist zwischen
Staging und Prod kein Mangel, sondern der Zweck der Trennung.

Auch der Knopf im Forgejo bleibt: Der Workflow ist weiterhin
`workflow_dispatch`, mit `plan` als Standard. Der Auslöser ist ein zweiter Weg
zu demselben Lauf, kein Ersatz.

---

## 12. Stand der Umsetzung

Die Repositories der Organisation `Six7-app-store` sind **Forks**. Bis zum
2026-09-18 gab es dort keinen einzigen Workflow-Lauf, was zunächst nach einer
Fork-Sperre aussah. Ein Testlauf hat das widerlegt: Actions funktioniert, es
hatte nur nie jemand gepusht, der einen Trigger traf. Seitdem laufen die
Pipelines.

**Erledigt:**

- CI läuft in allen vier Repositories, `workflow_dispatch` ergänzt.
- `CI - Infrastructure QA` prüft Terraform und Ansible bei jedem Push und Pull
  Request. Sie ersetzt die alte `staging.yml` auf GitHub, die einen nie
  registrierten Runner nannte und jeden Push auf `main` rot gefärbt hätte.
- Der Forgejo-Deploy ist gebaut: Workflow, Job-Image mit vorinstalliertem
  Terraform/Ansible/Trivy, Runner-Konfiguration mit persistentem
  tfstate-Volume, und eine eigene Terraform-Umgebung für den Forge-Host
  (`envs/forgejo`, bewusst mit lokalem State — sie ist der Bootstrap).
- Der Weg von Hand ist als [Runbook](deploy-runbook.md) beschrieben und als
  [`deploy.cmd`](../deploy.cmd) verpackt.
- Der Deploy wird nach einem Merge automatisch angestoßen: ein
  `trigger-staging-deploy.yml` in allen vier Repositories, ein eng gefasster
  Port am Forge-Host, siehe Abschnitt 11.

### Die Staging-Umgebung läuft

Nachgeprüft am 2026-09-18 gegen die laufende Instanz:

| Prüfung | Ergebnis |
|---|---|
| VM `staging-dhbw-appstore` | `ACTIVE`, seit 2026-09-09 |
| Frontend | HTTP 200 |
| Backend `/api/health` | `{"status":"healthy","service":"backend-api","version":"1.0.0"}` |
| Keycloak `/realms/dhbw` | HTTP 200, Public Key vorhanden |
| TLS-Zertifikat | gültig bis 2027-03-27, ausgestellt über die GEANT-CA |

> Die VM hat inzwischen ein zweites IPv4-Interface; davor war sie nur über IPv6
> erreichbar, was ohne IPv6 im VPN-Tunnel wie ein Ausfall aussah. Wer eine
> Vorführung plant, prüft die Erreichbarkeit trotzdem vorher.

**Noch offen:**

| Was | Wann nötig |
|---|---|
| **`IMAGE_NAMESPACE` setzen** | Sobald unter `ghcr.io/six7-app-store/` Images liegen — sonst zieht der Deploy die Images des Upstreams. Siehe [`.env.staging.example`](../.env.staging.example) |
| **Secrets für den Auslöser** | Vier Stück je Repository, plus zwei Werte in der `.env` des Forge-Hosts. Ohne sie bricht der Auslöser mit einer Liste der fehlenden Namen ab — Einrichtung in Abschnitt 11 |
| **Smoke-Test nach dem Deploy** | Wäre der nächste sinnvolle Ausbauschritt, siehe Abschnitt 8 |
| **Prod automatisieren** | Siehe Abschnitt 9 |
| **Pre-commit-Hooks** | Siehe Abschnitt 2 |

---

## 13. Weiterführend

- [deploy-runbook.md](deploy-runbook.md) — der Deploy Schritt für Schritt, mit
  den Stolperstellen, die tatsächlich Zeit gekostet haben
- [staging-setup.md](staging-setup.md) — Staging im Detail, Secrets, Verifikation
- [prod-setup.md](prod-setup.md) — der manuelle Prod-Weg, Schritt für Schritt
- [`infrastructure/README.md`](../infrastructure/README.md) — Terraform-Modul,
  Adressierung, State-Backend
- [`forgejo/README.md`](../forgejo/README.md) und
  [`forgejo/SCRIPTS.md`](../forgejo/SCRIPTS.md) — wie der Forge-Host aufgesetzt
  wird
