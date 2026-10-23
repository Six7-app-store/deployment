# 0017 — Vor jedem Agenten-Commit laufen Doku-Zuordnung und die Tests der CI

**Status:** Vorschlag
**Datum:** 23.10.2026
**Beteiligt:** Projektteam

## Kontext

`docs/harness.md` hielt bis heute zwei Grundsätze fest:

- „Schnelle Gates laufen lokal, teure Gates laufen in der Pipeline." Das
  Stop-Gate prüft deshalb nur Lint und Typecheck. Ein voller Backend-Lauf
  dauert rund 3,5 Minuten.
- Die Hooks laufen fail-open: kein Docker, Container aus, kaputtes JSON →
  stilles Exit 0.

`harness/git-workflow.md` verlangt seit Oktober 2026, Commits je
abgeschlossenem Arbeitspaket zu bündeln, nicht je Datei. Ein Agent committet
damit selten.

Beim Bau dieses Gates gefunden:

- Das Stop-Gate für `deployment` rief `tofu`/`terraform` am Host auf. Lag
  keins davon im `PATH`, lief es still nicht. Auf dem Rechner, an dem gebaut
  wurde, war keins installiert.
- ADR 0014 lag im Repo, stand aber nicht im Verzeichnis `docs/adr/README.md`.
- `docs/deploy-runbook.md` verlinkte zweimal eine Datei, die es nicht mehr
  gibt; `docs/dev-setup.md` verlinkte das Makefile unter falschem Pfad.
- `docs/pipeline.md` sagte noch „Ein Merge nach `main` genügt" — Stand vor
  ADR 0013.

Alle vier Stellen sind im selben Commit wie dieses ADR korrigiert.

Doku und Diagramme liegen in `deployment`, der Code, den sie beschreiben,
in vier Repos. Ob eine Codeänderung eine Beschreibung falsch macht, hat bisher
niemand maschinell gefragt.

Am 23.10.2026 entschied das Team: Vor einem Commit sollen die Tests laufen,
und ist der Container aus, wird der Commit blockiert.

## Entscheidung

Wir prüfen jeden `git commit` eines Agenten vor der Ausführung, und das Gate
schließt, wenn es nicht prüfen kann.

Der Bash-Hook erkennt `git commit` im zerlegten Kommando (auch nach `cd` oder
mit `git -C`) und prüft das zuständige Repo in dieser Reihenfolge:

1. **Doku-Zuordnung.** `harness/doc-map.json` ordnet Pfaden die Doku zu, die
   sie beschreibt. Ist eine Datei mit Zuordnung geändert, aber keine der
   zugeordneten Dokus — weder im Arbeitsbaum von `deployment` noch auf dessen
   Branch seit `origin/develop` —, wird blockiert. Ausweg mit Spur in der
   Historie: die Zeile `Doku-geprueft: <Grund>` in der Commit-Nachricht.
2. **Gates der CI**, ohne Coverage-Schwelle (die bleibt in der Pipeline):
   - backend: ruff, pytest gegen `postgres-test`
   - worker: ruff, black, isort, pytest
   - frontend: vue-tsc, vitest
   - deployment: `docs_check.py`, `fmt -check` der IaC-Bäume (am Host, sonst
     über Docker), Harness-Tests, wenn `harness/` betroffen ist

   Sind nur `.md`-Dateien oder `.claude/`-Kopien betroffen, laufen keine
   Tests.
3. **Schließen statt schweigen.** Läuft Docker oder der Container nicht,
   testet der Container einen anderen Checkout als den, in dem committet wird,
   oder scheitert das Gate selbst, wird der Commit blockiert.

Der Bash-Hook bekommt dafür ein Zeitlimit von 900 Sekunden. Bei einem
kürzeren würde Claude Code den Hook abbrechen und das Kommando trotzdem
ausführen.

Dazu kommt `scripts/docs_check.py` (`make docs-check`) und in der CI
`.github/workflows/docs-check.yml`:

- ADR-Nummern lückenlos, Kopfzeile, Status gültig und gleich im Verzeichnis
- relative Links und Anker
- `doc-map.json` zeigt auf existierende Doku und Pfade
- Mermaid-Diagramme rendern (mermaid-cli in Docker)
- jede offene Story hat ein Issue (ADR 0016)

Das Stop-Gate für `deployment` nutzt denselben fmt-Weg mit Docker-Fallback
und den schnellen Teil des Doku-Checks; dort bleibt es fail-open.

## Konsequenzen

Leichter:

- Ein Commit des Agenten ist ein Beleg, dass Lint und Tests der CI auf genau
  diesem Stand gelaufen sind.
- Die Frage „stimmt die Doku noch?" kommt in dem Moment, in dem der Agent die
  Änderung im Kopf hat, nicht erst im Review.
- Toter Link, fehlendes ADR im Verzeichnis, Diagramm mit Syntaxfehler fallen
  in der CI auf.

Schwerer:

- Ein Backend-Commit dauert spürbar länger — am 23.10.2026 gemessen 351 s
  für die Suite (frontend 31 s, worker 6 s) —, und der Stack muss laufen.
- `doc-map.json` ist Pflege. Eine zu grobe Zuordnung erzeugt Rauschen, eine zu
  feine wird nicht gepflegt. `docs-check` meldet immerhin Muster, die keine
  Datei mehr treffen.
- `Doku-geprueft:` lässt sich missbrauchen. `/pr-review` prüft, ob der Grund
  trägt; der Hook kann das nicht.
- Das Gate gilt nur für Claude-Sitzungen. Ein Mensch am eigenen Terminal
  committet ohne Hook. Das ist der Ausweg, wenn das Gate selbst kaputt ist.
- Tests laufen im Container gegen den gemounteten Checkout. Ein Commit aus
  einem Worktree wird deshalb abgewiesen, statt mit fremden Tests grün
  durchzugehen.
- Die Doku-Prüfung erkennt, *ob* eine Doku angefasst wurde, nicht ob sie
  danach stimmt.

## Verworfene Alternativen

**Tests im Stop-Hook.** Jede Antwort des Agenten würde Minuten kosten.
`docs/harness.md` hat das schon einmal verworfen. Daran ändert sich nichts:
der Commit ist der seltene Moment, das Turn-Ende der häufige.

**Git-`pre-commit`-Hook im Repo.** Würde auch Menschen bremsen und braucht ein
zusätzliches Werkzeug, um versioniert verteilt zu werden — eines, das die CI
nicht kennt. Der Claude-Hook ist schon verteilt (`make harness-sync`).

**Fail-open beibehalten.** Ein Commit ohne gelaufene Tests ist genau der Fall,
den das Gate verhindern soll. Ein Gate, das bei abgeschaltetem Docker
schweigt, sieht aus wie ein grünes.

**Doku nur im Review prüfen.** Dann ist der PR schon offen, und der Reviewer
findet die Lücke nur, wenn er die Doku kennt. Die Zuordnung macht dieses
Wissen maschinenlesbar.
