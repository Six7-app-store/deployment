# Harness für die agentenzentrierte Entwicklung

Ziel: Nach der Spezifikation einer Anforderung läuft der Agent eigenständig
los, setzt sie qualitätsgesichert um und bringt sie in den Einsatz — ohne
dass die Codebasis dabei degradiert.

Dieses Dokument beschreibt, wie das bei uns aufgebaut ist: wo was
dokumentiert wird, welche Werkzeuge der Agent bekommt, und welche
Anforderungen an ihn gestellt werden.

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
