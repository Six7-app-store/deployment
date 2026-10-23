# 0016 — Offene User Stories leben als Issues in Six7-app-store/deployment

**Status:** Vorschlag
**Datum:** 23.10.2026
**Beteiligt:** Projektteam

## Kontext

Die Anforderungen stehen als 40 User Stories in der Projektkonzeption
(`Projektkonzeption_2026-10-01_17-40-49.pdf`). Am 01.10.2026 wurden sie in
`docs/user-story-audit-2026-10-01.md` gegen den Code geprüft:

| Status | Anzahl |
|---|---|
| U – umgesetzt | 8 |
| T – teilweise | 26 |
| O – offen | 3 |
| D – dokumentiert | 3 |

Zu den 29 T/O-Stories gibt es Arbeitspakete P01–P16 in
`docs/user-story-umsetzungsplan-2026-10-01.md`. Das Audit beschreibt sich
selbst als Momentaufnahme: Es „bewahrt den Prüfstand vom 01.10.2026".

Die Belege der Stories verteilen sich auf mehrere Repos: im Audit 28 Links
nach backend, 20 nach Ubuntu-App, 15 nach self-service-ui, 13 nach frontend.
Die meisten Stories betreffen mehr als ein Repo.

In allen vier Stack-Repos sind Issues abgeschaltet, wie bei GitHub-Forks
üblich. Einen Ort, an dem der Stand einer Story fortgeschrieben wird, gab es
nicht.

`docs/harness.md` nennt als Ziel: Der Agent erzeugt die Spezifikation aus der
User Story, ein Mensch bestätigt sie.

Seit dem 21.10.2026 ist Six7-app-store das einzige Ziel für Pushes, PRs und
Links. DHBW-AppStore dient nur als Quelle zum Abgleichen.

## Entscheidung

Wir führen jede offene Story als genau ein Issue in `Six7-app-store/deployment`.
Ihr Stand lebt dort, nicht in einem Markdown-Dokument.

- Issues in `deployment` sind eingeschaltet. Die anderen Repos bleiben ohne
  Issues.
- `scripts/story_issues.py` (`make story-issues`) legt aus der neuesten
  Story-Matrix ein Issue je T/O-Story an. Titel `US-NN: …`, Labels
  `user-story`, `plan:PNN`, `repo:<name>`. Bestehende Issues fasst es nicht
  an.
- Der Plan entsteht je Issue mit `/issue-planen`. Er wird gegen den Code von
  heute geprüft und als Kommentar ins Issue geschrieben. Gebaut wird erst,
  wenn eine Person ihn bestätigt hat.
- PRs in allen Repos verweisen mit `Teil von Six7-app-store/deployment#N` auf
  das Issue, nicht mit `Closes`. Geschlossen wird nach dem Nachweis auf
  Staging, und das bestätigt eine Person.
- Das Audit wird nicht fortgeschrieben. Eine neue Projektkonzeption ergibt
  ein neues, datiertes Audit, und die Story-IDs bleiben dabei stabil.
- Die CI (`docs-check.yml`) prüft: Jede T/O-Story hat genau ein Issue, und
  kein Issue nennt eine Story, die es nicht gibt.

## Konsequenzen

Leichter:

- Eine Story hat einen Ort, den PRs aus jedem Repo verlinken können.
- Plan, fachliche Rückfragen, PRs und der Nachweis auf Staging stehen an
  einer Stelle und tragen ein Datum.
- Der Agent kann Issues anlegen und kommentieren, ohne nachzufragen.
  Schließen und Löschen fragen nach.

Schwerer:

- Das Repository ist öffentlich, also sind es auch die Issues. Was in einen
  Plan oder Kommentar geschrieben wird, ist öffentlich — keine Zugangsdaten,
  keine internen Adressen über das hinaus, was im Repo schon steht.
- Audit und Issues sind zwei Quellen. Das trägt nur, solange das Audit
  unverändert bleibt und der lebende Stand ausschließlich im Issue steht.
- Schreibende `gh`-Aufrufe ohne `-R` würden bei einem Fork auf das Original
  zielen. Der Bash-Hook blockt sie.
- Die beim Anlegen übernommenen Befunde sind Stand 01.10.2026. Einige Stories
  sind inzwischen weiter (etwa P15 durch ADR 0010). `/issue-planen` prüft den
  Ist-Stand deshalb zuerst.

## Verworfene Alternativen

**Issues je Repo.** Eine Story, die backend, frontend und ein App-Template
betrifft, würde in drei Teil-Issues zerfallen, die jemand verlinkt halten
muss. Den Stand der Story gäbe es dann nirgends als Ganzes.

**Zusätzlich ein GitHub-Project-Board.** Braucht weitere Token-Scopes
(`project`), und für den Anfang reichen Issues mit Labels. Ein Board lässt
sich später über dieselben Issues legen, ohne etwas umzubauen.

**`SPEC.md` im Repo**, wie in `docs/harness.md` bisher vorgesehen. Eine Datei
je Feature-Branch verwaist nach dem Merge und ist aus den anderen Repos
schlecht verlinkbar. Diskutiert wird im Issue, also gehört der Plan dorthin.

**Status in der Story-Matrix fortschreiben.** Die Matrix ist erklärtermaßen
eine Momentaufnahme. Nachträglich geändert, erzählt sie nicht mehr, was am
01.10. geprüft wurde, und mit jedem Merge entstünde ein Konflikt in einer
Datei.
