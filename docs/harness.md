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

Die Kette steht. Seit dem 23.10.2026 beginnt sie beim Issue statt bei einer
`SPEC.md`, und der Commit ist ein Gate (ADR 0015 bis 0017).

| Schritt | Heute | Ziel bis Projektende |
|---|---|---|
| Anforderung → Issue | Agent legt je offener Story ein Issue an (`/stories-zu-issues`, ADR 0016) | unverändert |
| Issue → Plan | Agent prüft gegen den Code, schreibt den Plan ins Issue (`/issue-planen`), Mensch bestätigt | unverändert |
| Umsetzung | Agent; Hooks halten Lint und Typecheck grün | unverändert |
| Verifikation | Stop-Hook lokal; Commit-Gate mit Doku-Zuordnung und Tests (ADR 0017); Pipeline im Pull Request | unverändert |
| Gegenprüfung | `/code-review` im frischen Kontext, `pr-review` gegen die DoD | unverändert |
| Pull Request öffnen | Agent; Push und PR fragen nach | unverändert |
| **Merge** | **Mensch** | **Mensch — bleibt so** |
| Staging-Deploy anstoßen | läuft bei jedem Merge auf `develop` von selbst; den develop-Stand darf der Agent zusätzlich neu bauen (ADR 0015) | unverändert |
| Nachweis, dass es läuft | Agent prüft (`deployment-pruefen`, `make staging-status`) und schreibt den Beleg ins Issue | unverändert |
| **Produktion freigeben** (Release-PR `develop` → `main`) | **Mensch**; ausgerollt wird danach automatisch | **Mensch — bleibt so** |

### Was dafür noch fehlt

| Lücke | Aufwand |
|---|---|
| Smoke-Test als letzter Schritt in `staging.yml` (Login, App-Liste, ein API-Aufruf), damit „grün" mehr heißt als „Container laufen" | ein Workflow-Schritt |
| Diagnose-Workflow für den develop-Stand: Containerstatus und Fehlerzähler von der VM, **ohne Rohlogs** — das Repository ist öffentlich, Job-Logs und Artefakte sind es auch | ein Workflow |
| Laufende App-Deployments vor einem Neubau erkennen; heute warnt nur der Skill | Endpunkt im Backend |

### Warum das im Projektrahmen umsetzbar ist

Weil nichts davon neue Infrastruktur braucht. Die Pipeline läuft, der Runner
läuft, die Secrets liegen, die Hooks greifen. Die offenen Punkte sind
Workflow-Schritte auf dem vorhandenen Runner.

Den Punkt „Staging-Deploy anstoßen" hat der Umbau vom 19.09.2026 erledigt,
bevor er eine Lücke werden konnte: Staging baut sich seit `52d931f` bei jedem
Merge selbst neu auf (ADR 0003), seit ADR 0013 bei jedem Merge auf `develop`. Angestoßen werden muss nichts mehr.

### Was bewusst außerhalb bleibt

- **Die Freigabe der Produktion.** Den Release-PR `develop` → `main` mergt
  ein Mensch, über die gesamte Projektlaufzeit. Danach rollt die Pipeline
  aus; einen Lauf gegen den main-Stand stößt der Agent nie an.
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
| Deterministische Regeln | `deployment/harness/`, verteilt nach `.claude/` je Repo | Was garantiert passieren muss, gehört nicht in Prosa |
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
| Qualitätssicherung (IaC) | tofu fmt, Trivy | in der Pipeline |
| Gegenprüfung | `/code-review` | Subagent in frischem Kontext, sieht nur den Diff |
| Deployment | GitHub Actions, self-hosted Runner | Staging automatisch bei Merge auf `develop`; von Hand `gh workflow run staging.yml` |

Die vollständige, jeweils gültige Liste steht in der `AGENTS.md` des
betreffenden Repositories — nicht hier, damit es nur eine Quelle gibt.

### Welchem Agenten? Die Werkzeugschichten

Claude Code lädt Konfiguration aus mehreren Ebenen, spätere überschreiben
frühere. Daraus ergibt sich die Trennung, nach der wir sortieren:

| Schicht | Ort | Im Repo | Gilt für |
|---|---|---|---|
| Baseline | `AGENTS.md`, `CLAUDE.md` | ✅ | alle |
| | `.claude/settings.json` (Hooks, Berechtigungen, Plugins) | ✅ erzeugt | alle |
| | `.claude/skills/<name>/SKILL.md` | ✅ | alle |
| | `.claude/hooks/agent_guard.py` | ✅ erzeugt | alle |
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
| `adr-schreiben` | alle (geteilt) | Wann fällig, Format, Nummernvergabe, Doku danach |
| `deployment-pruefen` | alle (geteilt) | Ob eine Umgebung läuft; develop-Stand neu bauen |
| `pr-review` | alle (geteilt) | Diff gegen die Definition of Done des betroffenen Repos |
| `stories-zu-issues` | alle (geteilt) | Offene User Stories als Issues in `deployment` |
| `issue-planen` | alle (geteilt) | Plan gegen den heutigen Code, als Kommentar ins Issue; die Kette bis Staging |
| `doku-nachziehen` | alle (geteilt) | Doku und Diagramme finden und anpassen, die eine Änderung falsch macht |

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

Wichtig beim Einrichten: In `.mcp.json` steht `npx -y chrome-devtools-mcp@1.9.0`,
nicht der absolute Pfad einer Maschine. Genau daran wäre es gescheitert — die
persönliche Konfiguration, aus der wir es übernommen haben, zeigte auf ein
`node_modules`-Verzeichnis unter einem bestimmten Benutzerprofil.

Die Version ist festgenagelt und nicht `@latest`. `npx` löst bei **jedem**
Serverstart neu auf, nicht erst nach einem Release über Nacht — zwei Leute
können am selben Tag unterschiedliche Versionen fahren. Das verstößt gegen
die Regel eine Ebene höher: ein Werkzeug darf nie nötig sein, um ein
korrektes Ergebnis zu erzeugen, und erst recht nicht in wechselnder
Fassung. Aktualisiert wird bewusst, in einem Commit.

**Geprüft und abgelehnt**, mit Begründung:

| Server | Warum nicht |
|---|---|
| `postgres` | Der offizielle Server ist eingestellt und archiviert, mit einer SQL-Injection, die den Read-only-Schutz umgeht; die AWS-Variante hat CVE-2026-85787 mit demselben Effekt. Wir haben `make shell-db` — der Agent kommt über Bash an die Datenbank. Falls doch: nur mit eigener Datenbankrolle ohne Schreibrechte, denn der Query-Filter im Server ist eine Hürde, keine Grenze. |
| `github` | Benchmarks zeigen den 4- bis 32-fachen Token-Verbrauch gegenüber der CLI, weil die Werkzeugschemata in jeder Anfrage mitfahren. Erst `gh` einrichten, das ist billiger und wird offiziell empfohlen. |
| `playwright` | Überschneidet sich mit `chrome-devtools`. Zwei Browser-Werkzeuge nebeneinander heißen nur, dass der Agent bei jeder Aufgabe wählen muss. |
| `filesystem`, `docker` | Doppelt. Claude Code hat Datei-Werkzeuge eingebaut, und die Container-Befehle stehen als `make`-Targets in `AGENTS.md`. |

Keine Server mit Schreibrechten auf Keycloak, Redis, RabbitMQ oder OpenStack,
und keine, die `.env`, `*.pem`, Tokens oder OpenTofu-State an einen externen
Dienst übertragen könnten.

### Deployment: anstoßen und nachweisen

Der Agent darf **den develop-Stand ausrollen und prüfen, ob es funktioniert
hat**. Der main-Stand, also die Produktion, bleibt beim Menschen (ADR 0015).

| Erlaubt | Verboten |
|---|---|
| `gh workflow run staging.yml … --ref develop -f stand=develop` | jeder Lauf für den Stand `main` (Produktion), Arbeiten an einer eigenständigen Installation |
| `/health` abfragen, Erreichbarkeit über IPv4 und IPv6 prüfen | `tofu apply` / `destroy` von Hand |
| Containerstatus und Logs lesen | `deploy.cmd` / `scripts/deploy.sh` von Hand |
| Pipeline-Ergebnis lesen | Secrets lesen oder schreiben |

Die Grenze läuft nicht zwischen *lesen* und *schreiben*, sondern zwischen
**dem Knopf, den die Pipeline anbietet** und **der Infrastruktur darunter**.
Der Agent darf den Workflow starten; OpenTofu von Hand gegen OpenStack
laufen zu lassen bleibt ihm verwehrt. Damit gilt für ihn genau dieselbe
Regel wie für uns.

Daneben gibt es `deploy.cmd` bzw. `scripts/deploy.sh`, die von einem
Entwicklerrechner im VPN ausrollen. Dieser Weg ist für den Agenten
**verschlossen** — er ist genau die Infrastruktur unter dem Knopf. Was der
Agent darf, ist der GitHub-Workflow.

**Achtung, seit dem 19.09.2026 anders:** Die frühere Eingabe `mode` mit
Default `plan` gibt es nicht mehr. Der heutige Workflow kennt `recreate`
(Default **true**, fährt `tofu destroy` und baut neu) und `seed`. Einen
Trockenlauf gibt es nicht — jeder Lauf verändert etwas.

Vertretbar bleibt es aus zwei anderen Gründen. Erstens ist Staging bewusst
wegwerfbar: es wird ohnehin bei jedem Merge neu gebaut (ADR 0003), ein
zusätzlicher Lauf zerstört also nichts, was nicht ohnehin verginge. Zweitens
deployt Staging nur, was schon in `develop` steht, und dorthin kommt nichts
ohne menschlichen Merge. Dazu kommt das Gate im Harness: der Bash-Hook lässt
nur den develop-Stand durch, und nur, wenn kein anderer Deploy läuft; eine
deny-Regel sperrt `stand=main` zusätzlich.

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

Seit der Vereinheitlichung ist es **ein** Skript für alle vier Repos; es
leitet die geltende Regel aus dem Pfad der bearbeiteten Datei ab.

| Ereignis | Wirkung |
|---|---|
| `PreToolUse` auf Edit/Write | Blockt Schreibzugriffe auf `.env`, `*.pem`, `*.key` — in **allen** Repos, nicht nur in deployment. `.env.example` bleibt erlaubt |
| `PreToolUse` auf Edit/Write | Blockt Änderungen an **bestehenden** Alembic-Migrationen; neue bleiben erlaubt |
| `PreToolUse` auf Bash | Blockt Kommandos, die eine Geheimnisdatei lesen würden. Die deny-Regeln greifen am Read-Werkzeug, eine Shell geht daran vorbei |
| `PreToolUse` auf Bash | Schreibende `gh`-Aufrufe nur mit `-R Six7-app-store/…` |
| `PreToolUse` auf Bash | `gh workflow run staging.yml` nur für den Stand `develop` und nur ohne laufenden Deploy (ADR 0015) |
| `PreToolUse` auf Bash | Commit-Gate vor `git commit`: Doku-Zuordnung aus `harness/doc-map.json`, dann Lint und Tests der CI im Container (ADR 0017) |
| `PostToolUse` auf Edit/Write | backend: `ruff --fix`. worker: ruff, black, isort. `*.tofu`: `tofu fmt`. frontend: bewusst nichts |
| `Stop` | Turn-Ende blockiert, solange das Gate des Repos rot ist: ruff (backend), ruff/black/isort (worker), `vue-tsc` (frontend), `tofu fmt -check` auf `infrastructure/tofu` — am Host, sonst über Docker — und der schnelle Teil von `make docs-check` (deployment) |

Die Skripte liegen als lesbare Python-Dateien unter `.claude/hooks/`, nicht
als Einzeiler im JSON. Sie sind damit im Pull Request review-fähig und
einzeln testbar. `jq` wird bewusst nicht verwendet: es ist nicht auf jedem
Entwicklungsrechner installiert, `python` bei diesem Projekt zwangsläufig.

### Zwei bewusste Entscheidungen zu den Hooks

**Die Hooks laufen fail-open — mit zwei Ausnahmen.** Kein Docker,
Container aus, kaputtes JSON — jeder Fehler endet still mit Exit 0. Ein Hook,
der die Arbeit blockiert, weil er selbst defekt ist, kostet mehr, als er
schützt. Das harte Gate ist die Pipeline; die Hooks fangen Fehler nur früher
ab.

Die Ausnahmen sind der Staging-Deploy und das Commit-Gate. Beide schließen,
wenn sie nicht prüfen können: ein Deploy reißt eine VM ab, und ein Commit
ohne gelaufene Tests ist genau der Fall, den das Gate verhindern soll
(ADR 0015, ADR 0017). Ein Mensch am eigenen Terminal committet weiterhin
ohne Hook — das ist der Ausweg, falls das Gate selbst kaputt ist.

**Das Stop-Gate prüft Lint, nicht die Testsuite.** Ein voller Backend-Lauf
dauert rund 3,5 Minuten. Ein Stop-Hook, der ihn bei jedem Turn-Ende fährt,
wäre nach einer halben Stunde abgeschaltet. Deshalb die Aufteilung:

> **Schnelle Gates laufen lokal, teure Gates laufen in der Pipeline.**

Lint und Formatierung kosten Sekunden und gehören an den Turn. Tests
kosten Minuten und gehören an den **Commit** — der ist seltener als das
Turn-Ende, weil Commits je Arbeitspaket gebündelt werden (ADR 0017).
Coverage und Security-Scan bleiben im Pull Request, wo Wartezeit nichts
blockiert.

### Die harte Ebene: Berechtigungen

Hooks sind deterministisch, aber sie sind Code, den wir selbst schreiben —
und sie laufen fail-open. Für die Dinge, die unter keinen Umständen passieren
dürfen, ist das zu weich. Deshalb liegt darunter noch eine Ebene, die Claude
Code selbst durchsetzt: der `permissions`-Block in `.claude/settings.json`.

| Ebene | Wirkung | Wenn sie ausfällt |
|---|---|---|
| `AGENTS.md` | beratend | Der Agent macht es trotzdem |
| Hook | deterministisch, aber fail-open | Kein Docker → Hook schweigt |
| `permissions.deny` | hart, vor jedem Werkzeugaufruf | Der Aufruf findet nicht statt |

Was hart gesperrt ist: Lesen **und** Schreiben von `.env`, `*.pem`, `*.key`
und `clouds.yaml`; `git push --force`, jeder Push auf `main` und jeder Push an das Remote `dhbw` (E6, DHBW-AppStore);
`gh pr merge`; `make prod*` und Compose gegen die Prod- und Staging-Stacks;
`deploy.cmd` und `scripts/deploy.sh`; `tofu apply|destroy|state|import` und dasselbe für `terraform`;
`docker system prune`, `docker volume rm`, `rm -rf`. Dazu `docker exec
<container> env`, weil die Secret-Sperre sonst über den Container zu umgehen
wäre.

Was nachfragt statt zu sperren: jeder `git push`, `git reset --hard`,
`git rebase`, `tofu plan`, `gh issue close|delete`,
`docker compose down`, die zurücksetzenden `make`-Targets — und das
Bearbeiten von `.github/workflows/**` und `harness/**`. Wer sein eigenes
Prüfsystem umschreiben darf, hat keines.

Was ohne Nachfrage geht, weil der Hook es prüft: `gh workflow run
staging.yml` (nur develop-Stand), `gh issue create|edit|comment` (nur
Six7-app-store), `git commit` (nur durch das Commit-Gate).

Das **Lesen** der Secrets mitzusperren ist der Punkt, der vorher fehlte. Ein
Hook auf `Edit|Write` verhindert nur das Schreiben; gelesen wandert der
Inhalt in den Kontext und damit an die API. `.claudeignore` ist dafür nicht
geeignet — es hat dokumentierte Umgehungen, `permissions.deny` nicht.

**Und die Shell geht auch daran vorbei.** Eine `Read`-Regel gilt für das
Lese-Werkzeug, nicht für ein Kommando in Bash. Das schließt kein Muster über
Programmnamen: wer `cat` sperrt, hat `head`, `sed`, `awk`, `base64` und einen
Dreizeiler in python nicht gesperrt. Deshalb prüft ein PreToolUse-Hook auf
Bash das **Argument** statt des Programms und blockt jedes Kommando, in dem
ein Geheimnispfad vorkommt. Aufrufe, die die aufgelösten Werte ohne
Dateinamen ausgeben, fängt stattdessen eine deny-Regel: eine Suche im
Kommandostring könnte ein Kommando nicht von seiner Erwähnung in einer
Commit-Nachricht unterscheiden, und genau daran ist der erste Versuch
gescheitert.

Zwei Kosten, beide bewusst. Der Hook blockt auch Kommandos, die den Namen
nur erwähnen, ohne zu lesen; beim Bau hat er prompt den eigenen Patch
aufgehalten. Und er findet keinen Pfad, der erst zur Laufzeit entsteht.
Beides steht als Test in `harness/test_agent_guard.py` — die Lücke ist
festgehalten, nicht weggeschwiegen. Was dort trägt, ist die Ebene darunter:
Bash-Kommandos sind nicht auto-approved, alles Unbekannte fragt nach.

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
- Kein `tofu apply` gegen Staging von Hand — nur über die Pipeline
- Kein Schreiben in `.env` oder `*.pem`
- Kein Bearbeiten bestehender Alembic-Migrationen
- Kein `git push --force`
- Kein Merge ohne grüne CI
- Kein Lauf gegen den main-Stand, kein `gh`-Aufruf gegen DHBW-AppStore

Die Grenzen sind die Hälfte der Antwort. Ein Agent, der alles darf,
braucht bei jedem Schritt einen Menschen — und war damit nie autonom.

## Die Kette von der Anforderung bis in den Einsatz

```
User Story (Story-Matrix im Audit)
   │
   ├─ /stories-zu-issues            ──►  Issue in Six7-app-store/deployment
   │
   ├─ /issue-planen                 Ist gegen heutigen Code belegt,
   │     fachliche Fragen an Menschen    Abnahme, Doku, ADR, Nachweis
   │     (AskUserQuestion)          ──►  Plan als Kommentar im Issue
   │
   ├─ Mensch bestätigt den Plan
   │
   ├─ Implementierung               PostToolUse-Hook: Lint nach jedem Edit
   │                                PreToolUse-Hook: Tabu-Zonen blockiert
   │
   ├─ Doku, Diagramme, ADR          doku-nachziehen, adr-schreiben
   │
   ├─ Verifikation                  Stop-Hook: Turn endet nicht rot
   │
   ├─ Commit je Repo                Commit-Gate: Doku-Zuordnung, Lint, Tests
   │
   ├─ Gegenprüfung                  /code-review, /pr-review
   │
   ├─ Pull Request                  „Teil von Six7-app-store/deployment#N"
   │
   ├─ Pipeline                      lint → test → coverage → security
   │                                → build → image-scan, Doku-Check
   │
   ├─ Merge (Mensch) ──► develop ──► Staging-Deploy
   │
   └─ Nachweis auf Staging          make staging-status, Abnahme → Kommentar
                                    im Issue; Schließen bestätigt ein Mensch
```

Ein brauchbarer Plan ist selbsttragend: er benennt die beteiligten
Dateien und Schnittstellen, sagt explizit, was **nicht** dazugehört, und
endet mit einem Verifikationsschritt, der beweist, dass die Sache
funktioniert. Er steht im Issue, nicht in einer `SPEC.md` im Repo
(ADR 0016). Zeit, die in die Präzision der Spezifikation fließt, zahlt
sich stärker aus als Zeit, die man mit dem Zusehen bei der Umsetzung
verbringt.

## Schutz gegen Degradation

Dass die Codebasis nicht schleichend schlechter wird, ist eine eigene
Anforderung — und sie lässt sich nur maschinell halten.

| Mechanismus | Wirkung |
|---|---|
| Coverage-Ratsche | `fail_under` bzw. `thresholds` in allen Repos; der Lauf schlägt fehl, wenn die Abdeckung darunter fällt. Der Wert wird nur erhöht, nie gesenkt. |
| Lint-Gate am Turn-Ende | Formatierungs- und Stilverfall wird nicht angesammelt |
| Commit-Gate | Kein Agenten-Commit ohne gelaufene Tests; geänderter Code fragt nach der Doku, die ihn beschreibt |
| Doku-Check in der CI | Tote Links, fehlende ADR-Einträge, kaputte Diagramme, Stories ohne Issue fallen im PR auf |
| Tabu-Zonen als Hook | Migrationen und Secrets sind nicht vom Wohlwollen abhängig |
| ADR-Pflicht | Architekturentscheidungen bleiben nachvollziehbar statt implizit |
| Gegenprüfung im frischen Kontext | Fängt das, was der Schreibende nicht sieht |

**Zum Stand der Ratsche:** Die Schwellen für Frontend und Worker sind
bewusst unter dem vermuteten Ist-Wert angesetzt, damit das Gate beim
Einbau nicht sofort rot steht. Nach dem ersten vollständigen
Coverage-Lauf gehören sie auf knapp unter den tatsächlichen Wert gezogen.
Ab da gilt: nur hoch, nie runter.

## Wo die Hooks greifen

`.claude/settings.json` wird aus dem Verzeichnis geladen, in dem die Sitzung
startet — plus `~/.claude`. Unterverzeichnisse werden **nicht** gescannt.

Bis zur Vereinheitlichung war das die ganze Wahrheit, mit der Begründung: wer
am Backend arbeitet, startet im Backend. In der Praxis stimmte das nicht. Alle
vier Repos liegen bei jedem von uns in einem gemeinsamen Arbeitsordner, weil
sie nur zusammen laufen, und eine Sitzung, die dort startet, lief ohne Hooks
und ohne deny-Regeln — ohne dass etwas darauf hingewiesen hätte.

Deshalb liegt der Harness jetzt kanonisch in `deployment/harness/` und wird
von dort verteilt: in die vier Repos **und** in den Arbeitsordner darüber.

```bash
make harness-sync     # verteilen, nach jedem git pull
make harness-check    # nur prüfen, Exit 1 bei Drift
make harness-test     # Tests des Hook-Helfers
```

Der Hook leitet das zuständige Repo aus dem Pfad der bearbeiteten Datei ab,
nicht aus dem Arbeitsverzeichnis. Dieselbe Regel gilt damit aus beiden
Startpunkten. Startet die Sitzung im Arbeitsordner, prüft das Stop-Gate nur
die Repos mit uncommitteten Änderungen — sonst kostet jedes Turn-Ende einen
Durchlauf über alle vier.

Der zweite Grund für die eine Quelle: vorher lag in drei Repos eine eigene
Kopie von `agent_guard.py`, und die drei waren bereits auseinandergedriftet.
Getrennte Repositories können einander nichts mitgeben — ein Skript kann es.
Details in `harness/README.md`.
