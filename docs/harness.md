# Harness für die agentenzentrierte Entwicklung

Ziel: Nach der Spezifikation einer Anforderung läuft der Agent eigenständig
los, setzt sie qualitätsgesichert um und bringt sie in den Einsatz — ohne
dass die Codebasis dabei degradiert.

Dieses Dokument beschreibt, wie das bei uns aufgebaut ist: wo was
dokumentiert wird, welche Werkzeuge der Agent bekommt, und welche
Anforderungen an ihn gestellt werden. Das System, an dem er arbeitet,
steht in [`architektur.md`](architektur.md).

## Ist-Stand und Ziel

Das Ziel ist nicht „der Agent macht alles", sondern: **der Mensch entscheidet
noch über Merge und Produktion, alles davor läuft ohne ihn.** Aus einer
Anforderung wird ein Feature, und wir sehen es uns am Ende an.

Die Kette steht schon. Was fehlt, sind drei Handgriffe, nicht drei Bausteine.

| Schritt | Heute | Ziel bis Projektende |
|---|---|---|
| Anforderung → `SPEC.md` | Mensch schreibt sie im Interview mit dem Agenten | Agent erzeugt sie aus der User Story, Mensch bestätigt |
| Umsetzung | Agent; Hooks halten Lint und Typecheck grün | unverändert |
| Verifikation | Stop-Hook lokal, Pipeline im Pull Request | unverändert |
| Gegenprüfung | `/code-review` im frischen Kontext | unverändert |
| Pull Request öffnen | Mensch | Agent |
| **Merge** | **Mensch** | **Mensch — bleibt so** |
| Staging-Deploy anstoßen | Mensch klickt in Forgejo | Agent stößt den Workflow an |
| Nachweis, dass es läuft | Agent prüft lesend (`deployment-pruefen`) | unverändert |
| **Produktion** | **Mensch** | **Mensch — bleibt so** |

### Was dafür noch fehlt

| Lücke | Aufwand |
|---|---|
| Forgejo-API-Token mit Recht auf `workflow_dispatch`, abgelegt außerhalb des Repositories | ein Handgriff in den Forgejo-Einstellungen |
| `gh` installiert und angemeldet, damit der Agent den CI-Stand der Pull Requests lesen kann | eine Installation |
| Ein Skill, der aus einer User Story eine `SPEC.md` erzeugt — nach demselben Muster wie die sieben vorhandenen | ein Arbeitstag |

### Warum das im Projektrahmen umsetzbar ist

Weil nichts davon neue Infrastruktur braucht. Die Pipeline läuft, der Runner
läuft, die Secrets liegen, die Hooks greifen, sieben Skills sind im Einsatz.
Die drei offenen Punkte sind ein Token, eine Installation und ein weiterer
Skill desselben Formats.

Der Staging-Workflow trägt die Absicherung bereits in sich: seine Eingabe
`mode` steht standardmäßig auf `plan`, und ein `plan`-Lauf prüft Runner,
Image, Checkout, alle sechs Secrets und eine echte Anmeldung an OpenStack —
ohne irgendetwas zu ändern. Der Agent kann also erst prüfen und dann
ausrollen, und ein Fehlgriff bleibt folgenlos.

### Was bewusst außerhalb bleibt

- **Produktions-Deployments.** Bleiben manuell, über die gesamte Projektlaufzeit.
- **Merge ohne Menschen.** Der Pull Request ist der Punkt, an dem wir hinsehen.
  Fällt er weg, fällt die Kontrolle weg.
- **Der Agent ändert die Pipeline selbst.** Wer sein eigenes Prüfsystem
  umschreiben darf, hat keines.

## Der Grundsatz: die CI ist das Rückgrat

Das Harness ist nicht neben der Qualitätssicherung entstanden, sondern auf
ihr. Alle vier Repositories fahren bereits eine Pipeline aus Lint, Unit-
und Integrationstests, Coverage, Security-Scan, Image-Build und Image-Scan.
Genau diese Prüfungen sind die Rückmeldung, die ein Agent braucht, um zu
merken, dass er fertig ist.

Daraus folgt eine Regel, die den ganzen Aufbau bestimmt:

> **Der Agent bekommt exakt die Kommandos, die auch die CI fährt.
> Ein Werkzeug, das die CI nicht kennt, gehört nicht ins Harness.**

Sonst entstehen zwei Wahrheiten — eine, die lokal grün ist, und eine, die
im Pull Request rot wird.

## Wo wird was dokumentiert

| Was | Wo | Warum dort |
|---|---|---|
| Befehle, Konventionen, Tabu-Zonen je Repo | `AGENTS.md` im Repo-Wurzelverzeichnis | Agenten lesen die nächstgelegene Datei im Verzeichnisbaum. Vier Repos, vier Dateien. |
| Claude-spezifischer Einstieg | `CLAUDE.md` mit `@AGENTS.md` | Einzeiler, der die eine Wahrheit importiert |
| Architekturentscheidungen | `deployment/docs/adr/` | Eine Entscheidung je Datei, unveränderlich, fortlaufend nummeriert |
| Deterministische Regeln | `.claude/settings.json` + `.claude/hooks/` je Repo | Was garantiert passieren muss, gehört nicht in Prosa |
| Setup, Betrieb, Troubleshooting | `deployment/docs/*.md` | Für Menschen wie für Agenten dieselbe Quelle |

### Warum AGENTS.md und nicht nur CLAUDE.md

`AGENTS.md` ist ein offenes Format für Agenten-Anweisungen — im August 2025
als Spezifikation veröffentlicht, seit Dezember 2025 bei der Agentic AI
Foundation der Linux Foundation, in der Größenordnung von 60.000
Repositories im Einsatz. Es wird von mehreren Werkzeugen gelesen, nicht nur
von einem.

Wir arbeiten heute ausschließlich mit Claude Code, das `CLAUDE.md` liest.
Trotzdem liegt die Substanz in `AGENTS.md`, und `CLAUDE.md` besteht aus
einer Zeile:

```markdown
@AGENTS.md
```

Der Grund ist nicht der heutige Werkzeugkasten, sondern der nächste: ein
Wechsel oder eine Ergänzung des Werkzeugs darf keine Dokumentationsmigration
auslösen. Die Kosten dieser Entscheidung sind eine Zeile je Repository.

### Wie eine AGENTS.md geschrieben wird

Die wichtigste Regel ist die Länge. Eine überladene Datei führt dazu, dass
der Agent die Hälfte davon ignoriert — die entscheidenden Regeln gehen im
Rauschen unter. Faustregel: unter 60 Zeilen.

Prüffrage für jede einzelne Zeile:

> **Würde der Agent ohne diese Zeile einen Fehler machen?**

Wenn nein, streichen.

| Gehört hinein | Gehört nicht hinein |
|---|---|
| Befehle, die man nicht erraten kann | Was aus dem Code selbst hervorgeht |
| Umgebungs-Eigenheiten (Ports, Container, Pfade) | Datei-für-Datei-Beschreibungen |
| Konventionen, die von der Norm abweichen | Standardpraktiken der Sprache |
| Tabu-Zonen | API-Dokumentation |
| Definition of Done | „Schreib sauberen Code" |

Ein Beispiel für eine Zeile, die sich verdient hat, dort zu stehen:

```markdown
**Immer `poetry run` im Container.** Das venv liegt unter /app/.venv und ist
nicht im PATH — ein blankes `pytest` scheitert mit `No module named pytest`.
```

Diese Falle ist real und steht sonst nur in einem Makefile-Kommentar. Ein
Agent liest keine Makefile-Kommentare. Er probiert das naheliegende
Kommando, bekommt einen Fehler und schließt daraus, dass es keine Tests
gibt — und meldet die Arbeit als fertig, ohne sie geprüft zu haben.
Das ist genau die Art Fehler, gegen die eine `AGENTS.md` hilft.

Wissen, das nur gelegentlich gebraucht wird, gehört nicht in die immer
geladene Datei, sondern in eine Skill unter `.claude/skills/<name>/SKILL.md`.

## Welche Werkzeuge der Agent bekommt

| Zweck | Werkzeug | Aufruf |
|---|---|---|
| Entwickeln | Docker Compose | `make dev-up`, `make dev-restart-<dienst>` |
| Debuggen | Container-Logs, Shells | `make dev-logs-backend`, `make shell-db` |
| Qualitätssicherung (Python) | pytest, ruff, black, isort | `make test-backend-isolated`, `docker exec … poetry run …` |
| Qualitätssicherung (Frontend) | vitest, vue-tsc | `docker exec frontend-dev sh -lc 'cd /app && npx vitest --run'` |
| Qualitätssicherung (IaC) | terraform fmt, Trivy | in der Pipeline |
| Gegenprüfung | `/code-review` | Subagent in frischem Kontext, sieht nur den Diff |
| Deployment | Forgejo-Workflow | `workflow_dispatch` auf Staging |

Die vollständige, jeweils gültige Liste steht in der `AGENTS.md` des
betreffenden Repositories — nicht hier, damit es nur eine Quelle gibt.

### Welchem Agenten? Die Werkzeugschichten

Claude Code lädt Konfiguration aus mehreren Ebenen, spätere überschreiben
frühere. Daraus ergibt sich die Trennung, nach der wir sortieren:

| Schicht | Ort | Im Repo | Gilt für |
|---|---|---|---|
| Baseline | `AGENTS.md`, `CLAUDE.md` | ✅ | alle |
| | `.claude/settings.json` (Hooks, Plugins) | ✅ | alle |
| | `.claude/skills/<name>/SKILL.md` | ✅ | alle |
| | `.mcp.json` | ✅ | alle |
| Persönlich, projektbezogen | `.claude/settings.local.json` | ❌ gitignored | einer |
| Persönlich, global | `~/.claude/` — Skills, Plugins, Modellwahl | ❌ | einer |

Die Regel, die darüber entscheidet, wo etwas hingehört:

> **Ein persönliches Werkzeug darf einen Entwickler schneller machen. Es darf
> nie nötig sein, um ein korrektes Ergebnis zu erzeugen.**

Sobald ein Ergebnis von einem Werkzeug abhängt, das nicht jeder hat, ist der
Pull Request von jemand anderem nicht mehr gleichwertig prüfbar — und die CI,
die für alle gleich ist, wäre nicht mehr die Wahrheit. Alles, was ein
Arbeitsergebnis beeinflusst, gehört deshalb in die Baseline.

Das gilt auch für scheinbar Harmloses: Modellwahl und Effort-Stufe stehen in
`~/.claude/settings.json`. Zwei Personen mit demselben Prompt bekommen
unterschiedliche Ergebnisse. Das ist hinnehmbar, solange die Gates entscheiden
und nicht das Modell.

### Skills

Wissen, das **nur manchmal** zählt, gehört nicht in die immer geladene
`AGENTS.md`. Die wird sonst zu lang, und der Agent ignoriert die Hälfte davon.
Skills lädt er bei Bedarf.

| Skill | Repo | Wofür |
|---|---|---|
| `neue-migration` | backend | Modelländerung → Migration → anwenden → rückwärts testen |
| `neuer-endpoint` | backend | Router, Schema, CRUD, Berechtigung, Test, Frontend-Aufruf |
| `lti-flow` | backend | Launch-Ablauf, Sitzungsmodell, Rollen, lokale Testfallen |
| `neue-view` | frontend | View/Store/API-Tripel, Route, Container-Neustart |
| `packer-template` | worker | Welches Layout ein App-Repo haben muss |
| `adr-schreiben` | deployment | Wann fällig, Format, Nummernvergabe |
| `deployment-pruefen` | deployment | Lesende Prüfung, ob eine Umgebung läuft |

`neue-migration` zeigt das Prinzip am deutlichsten: Der Hook **verbietet**,
bestehende Migrationen zu bearbeiten. Der Skill sagt, was man **stattdessen**
tut. Ein Verbot ohne Alternative ist nur halb geholfen — der Agent weiß dann,
dass er nicht darf, aber nicht, wie es richtig geht.

**Skills schreiben wir selbst, für unseren Code.** Fertige Sammlungen aus dem
Netz übernehmen wir nicht. Der Anlass war konkret: Auf einem unserer Rechner
lag ein heruntergeladener Skill namens `backend-patterns`, der von Express,
Next.js und TypeScript handelt. Unser Backend ist FastAPI mit SQLAlchemy. Er
wäre nicht nutzlos gewesen, sondern hätte aktiv in die falsche Richtung
gezogen. Bei allem aus fremder Quelle gilt: die `SKILL.md` ganz lesen und jedes
mitgelieferte Skript prüfen, bevor es installiert wird.

### MCP-Server

Genommen, als `.mcp.json` im jeweiligen Repo:

| Server | Repo | Wofür |
|---|---|---|
| `chrome-devtools` | frontend | Der Agent öffnet die App, klickt sich durch, liest die Konsole |
| `context7` (als Plugin) | alle | Aktuelle Bibliotheksdoku statt Trainingswissen |

`chrome-devtools` ist für den LTI-Launch der einzige Weg, das Ergebnis wirklich
zu prüfen: ein Redirect über `host.docker.internal` lässt sich mit einem
Unit-Test nicht nachstellen. `context7` zahlt sich vor allem bei `pylti1p3`
aus — einer Nischenbibliothek, bei der ohne aktuelle Doku geraten wird.

Wichtig beim Einrichten: In `.mcp.json` steht `npx -y chrome-devtools-mcp@latest`,
nicht der absolute Pfad einer Maschine. Genau daran wäre es gescheitert — die
persönliche Konfiguration, aus der wir es übernommen haben, zeigte auf ein
`node_modules`-Verzeichnis unter einem bestimmten Benutzerprofil.

**Geprüft und abgelehnt**, mit Begründung:

| Server | Warum nicht |
|---|---|
| `postgres` | Der offizielle Server ist eingestellt und archiviert, mit einer SQL-Injection, die den Read-only-Schutz umgeht; die AWS-Variante hat CVE-2026-85787 mit demselben Effekt. Wir haben `make shell-db` — der Agent kommt über Bash an die Datenbank. Falls doch: nur mit eigener Datenbankrolle ohne Schreibrechte, denn der Query-Filter im Server ist eine Hürde, keine Grenze. |
| `github` | Benchmarks zeigen den 4- bis 32-fachen Token-Verbrauch gegenüber der CLI, weil die Werkzeugschemata in jeder Anfrage mitfahren. Erst `gh` einrichten, das ist billiger und wird offiziell empfohlen. |
| `playwright` | Überschneidet sich mit `chrome-devtools`. Zwei Browser-Werkzeuge nebeneinander heißen nur, dass der Agent bei jeder Aufgabe wählen muss. |
| `filesystem`, `docker` | Doppelt. Claude Code hat Datei-Werkzeuge eingebaut, und die Container-Befehle stehen als `make`-Targets in `AGENTS.md`. |

Keine Server mit Schreibrechten auf Keycloak, Redis, RabbitMQ oder OpenStack,
und keine, die `.env`, `*.pem`, Tokens oder Terraform-State an einen externen
Dienst übertragen könnten.

### Deployment: anstoßen und nachweisen

Der Agent darf **Staging ausrollen und prüfen, ob es funktioniert hat**.
Produktion bleibt beim Menschen.

| Erlaubt | Verboten |
|---|---|
| Staging-Workflow anstoßen (`mode: plan`, dann `apply`) | Produktions-Deployment |
| `/health` abfragen, Erreichbarkeit über IPv4 und IPv6 prüfen | `terraform apply` / `destroy` von Hand |
| Containerstatus und Logs lesen | `deploy.cmd` / `scripts/deploy.sh` von Hand |
| Pipeline-Ergebnis lesen | Secrets lesen oder schreiben |

Die Grenze läuft nicht zwischen *lesen* und *schreiben*, sondern zwischen
**dem Knopf, den die Pipeline anbietet** und **der Infrastruktur darunter**.
Der Agent darf den Workflow starten; Terraform von Hand gegen OpenStack
laufen zu lassen bleibt ihm verwehrt. Damit gilt für ihn genau dieselbe
Regel wie für uns.

Seit dem 18.09.2026 gibt es dafür einen zweiten Weg: `deploy.cmd` bzw.
`scripts/deploy.sh` rollen von einem Entwicklerrechner aus aus, weil ein
GitHub-gehosteter Runner die OpenStack-API der DHBW nicht erreicht. Dieser
Weg ist für den Agenten **verschlossen** — er ist genau die Infrastruktur
unter dem Knopf. Was der Agent darf, ist der Forgejo-Workflow.

Zwei Dinge machen das vertretbar. Erstens steht die Workflow-Eingabe `mode`
standardmäßig auf `plan` — ein `plan`-Lauf prüft Runner, Image, Checkout,
alle sechs Secrets und eine echte OpenStack-Anmeldung, ändert aber nichts.
Der Agent prüft also erst und rollt dann aus. Zweitens deployt Staging nur,
was schon in `main` steht, und dorthin kommt nichts ohne menschlichen Merge.

Ein Agent, der auf das Ergebnis seiner eigenen Arbeit schauen kann, arbeitet
eine Stufe eigenständiger: Er merkt selbst, dass ein Deployment rot ist,
statt darauf zu warten, dass es jemand meldet.

Konkret macht das der Skill `deployment-pruefen`: Health-Endpunkt,
Statuscodes über IPv4 und IPv6 getrennt, Containerstatus, und für den
CI-Stand `gh run list`. Das Ergebnis wird als Beleg gemeldet — Kommando,
Statuscode, Antwort — nicht als Behauptung „läuft".

## Deterministische Regeln: die Hooks

Anweisungen in Markdown sind **beratend**. Ein Agent kann sie übersehen,
besonders in einer langen Sitzung. Hooks sind **deterministisch**: sie
laufen, ob der Agent daran denkt oder nicht.

Deshalb gilt: Was garantiert passieren muss, wird ein Hook. Was Kontext
ist, bleibt Prosa.

| Repo | Ereignis | Wirkung |
|---|---|---|
| backend | `PreToolUse` auf Edit/Write | Blockt Änderungen an **bestehenden** Alembic-Migrationen; neue bleiben erlaubt |
| backend | `PostToolUse` auf Edit/Write | `ruff --fix` auf die geänderte Datei |
| backend | `Stop` | Turn-Ende blockiert, solange `ruff check` rot ist |
| worker | `PostToolUse` / `Stop` | dasselbe mit ruff, black und isort |
| frontend | `Stop` | Turn-Ende blockiert, solange `vue-tsc` rot ist |
| deployment | `PreToolUse` auf Edit/Write | Blockt Schreibzugriffe auf `.env` und `*.pem`; `.env.example` bleibt erlaubt |
| deployment | `Stop` | Turn-Ende blockiert, solange Terraform unformatiert ist |

Die Skripte liegen als lesbare Python-Dateien unter `.claude/hooks/`, nicht
als Einzeiler im JSON. Sie sind damit im Pull Request review-fähig und
einzeln testbar. `jq` wird bewusst nicht verwendet: es ist nicht auf jedem
Entwicklungsrechner installiert, `python` bei diesem Projekt zwangsläufig.

### Zwei bewusste Entscheidungen zu den Hooks

**Die Hooks laufen fail-open.** Kein Docker, Container aus, kaputtes
JSON — jeder Fehler endet still mit Exit 0. Ein Hook, der die Arbeit
blockiert, weil er selbst defekt ist, kostet mehr, als er schützt. Das
harte Gate ist die Pipeline; die Hooks fangen Fehler nur früher ab.

**Das Stop-Gate prüft Lint, nicht die Testsuite.** Ein voller Backend-Lauf
dauert rund 3,5 Minuten. Ein Stop-Hook, der ihn bei jedem Turn-Ende fährt,
wäre nach einer halben Stunde abgeschaltet. Deshalb die Aufteilung:

> **Schnelle Gates laufen lokal, teure Gates laufen in der Pipeline.**

Lint und Formatierung kosten Sekunden und gehören an den Turn. Tests,
Coverage und Security-Scan kosten Minuten und gehören in den Pull Request,
wo Wartezeit nichts blockiert.

## Anforderungen an den Agenten

### Was er tun muss

1. **Verifizieren, nicht behaupten.** Ein Ergebnis gilt erst als fertig,
   wenn ein Kommando mit Pass/Fail es bestätigt hat. Der Agent legt den
   Beleg vor — Testausgabe, Exit-Code, Screenshot —, statt „passt" zu melden.
2. **Erst erkunden, dann planen, dann bauen.** Bei allem, was mehrere
   Dateien berührt oder unvertrauten Code ändert, zuerst der Plan Mode
   (`Shift+Tab`), der nur liest. Bei einem Einzeiler entfällt das.
3. **Migration im selben Commit.** Modelländerung ohne Alembic-Migration
   ist unvollständig.
4. **ADR bei Architekturentscheidungen.** Im selben Commit, nach dem
   Format in `docs/adr/README.md`.
5. **Gegenprüfung vor „fertig".** `/code-review` läuft in frischem Kontext
   und sieht nur den Diff, nicht die Begründung, die ihn erzeugt hat. Wer
   schreibt, bewertet nicht.

### Was er nicht darf

- Kein Produktions-Deployment
- Kein `terraform apply` gegen Staging von Hand — nur über die Pipeline
- Kein Schreiben in `.env` oder `*.pem`
- Kein Bearbeiten bestehender Alembic-Migrationen
- Kein `git push --force`
- Kein Merge ohne grüne CI

Die Grenzen sind die Hälfte der Antwort. Ein Agent, der alles darf,
braucht bei jedem Schritt einen Menschen — und war damit nie autonom.

## Die Kette von der Anforderung bis in den Einsatz

```
User Story
   │
   ├─ Interview (AskUserQuestion)  ──►  SPEC.md
   │     Scope, betroffene Dateien, Out-of-Scope,
   │     End-to-End-Verifikation
   │
   ├─ Plan Mode                    read-only, bis der Plan steht
   │
   ├─ Implementierung              PostToolUse-Hook: Lint nach jedem Edit
   │                               PreToolUse-Hook: Tabu-Zonen blockiert
   │
   ├─ Verifikation                 Stop-Hook: Turn endet nicht rot
   │
   ├─ Gegenprüfung                 /code-review im frischen Kontext
   │
   ├─ Commit + Pull Request
   │
   └─ Pipeline                     lint → test → coverage → security
            │                              → build → image-scan
            │
            └─ main  ──►  Staging-Deploy (Terraform + Ansible, Forgejo-Runner)
```

Eine brauchbare `SPEC.md` ist selbsttragend: sie benennt die beteiligten
Dateien und Schnittstellen, sagt explizit, was **nicht** dazugehört, und
endet mit einem Verifikationsschritt, der beweist, dass die Sache
funktioniert. Zeit, die in die Präzision der Spezifikation fließt, zahlt
sich stärker aus als Zeit, die man mit dem Zusehen bei der Umsetzung
verbringt.

## Schutz gegen Degradation

Dass die Codebasis nicht schleichend schlechter wird, ist eine eigene
Anforderung — und sie lässt sich nur maschinell halten.

| Mechanismus | Wirkung |
|---|---|
| Coverage-Ratsche | `fail_under` bzw. `thresholds` in allen Repos; der Lauf schlägt fehl, wenn die Abdeckung darunter fällt. Der Wert wird nur erhöht, nie gesenkt. |
| Lint-Gate am Turn-Ende | Formatierungs- und Stilverfall wird nicht angesammelt |
| Tabu-Zonen als Hook | Migrationen und Secrets sind nicht vom Wohlwollen abhängig |
| ADR-Pflicht | Architekturentscheidungen bleiben nachvollziehbar statt implizit |
| Gegenprüfung im frischen Kontext | Fängt das, was der Schreibende nicht sieht |

**Zum Stand der Ratsche:** Die Schwellen für Frontend und Worker sind
bewusst unter dem vermuteten Ist-Wert angesetzt, damit das Gate beim
Einbau nicht sofort rot steht. Nach dem ersten vollständigen
Coverage-Lauf gehören sie auf knapp unter den tatsächlichen Wert gezogen.
Ab da gilt: nur hoch, nie runter.

## Einschränkung: wo die Hooks greifen

`.claude/settings.json` wird aus dem Verzeichnis geladen, in dem die
Sitzung startet. Die Hooks greifen also nur, wenn Claude Code **im
jeweiligen Repository** gestartet wird — nicht im übergeordneten
Arbeitsverzeichnis, das alle vier enthält.

Das ist kein Nachteil, sondern passt zur Struktur: dieselbe Regel sorgt
dafür, dass die nächstgelegene `AGENTS.md` gilt. Wer am Backend arbeitet,
startet im Backend.
