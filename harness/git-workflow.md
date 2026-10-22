## Branches: develop ist Staging, main ist Produktion

Gilt in den vier Stack-Repos (deployment, backend, frontend, worker); die
App-Repos haben nur `main`. Begründung: `deployment/docs/adr/0013-*.md`.

- Neue Arbeit zweigt von `develop` ab (`feat/…`, `fix/…`, `chore/…`, `docs/…`)
  und kommt per Pull Request nach `develop` zurück. Jeder Merge dort baut
  Staging neu.
- `main` bekommt nur Release-PRs `develop` → `main`, gemergt mit
  **Merge-Commit** — kein Squash, kein Rebase, sonst laufen die Branches
  auseinander. Danach `develop` per Fast-Forward nachziehen:
  `git push origin origin/main:develop`. Ist `develop` inzwischen weiter, statt
  dessen ein PR `main` → `develop`.
- Hotfix: Branch von `main`, PR nach `main`, danach `main` in `develop` mergen.
- Ein Feature über mehrere Repos geht in allen betroffenen Repos zusammen nach
  `develop` und mit demselben Release nach `main`.
- Agenten mergen keine Pull Requests und pushen nicht auf `main`; das tut eine
  Person.

## Commits und Pushes bündeln

- Änderungen zuerst als zusammenhängendes Arbeitspaket fertigstellen und die
  passenden Prüfungen abschließen. Nicht nach jeder Datei, kleinen Korrektur
  oder jedem Zwischenschritt committen.
- Pro abgeschlossenem Arbeitspaket und betroffenem Repository möglichst einen
  nachvollziehbaren Commit erstellen. Mehrere Commits sind sinnvoll, wenn sie
  unabhängig prüfbare Änderungen trennen; fremde Änderungen nicht mit aufnehmen.
- Commits erst gesammelt nach Abschluss des Arbeitspakets pushen, nicht nach
  jedem einzelnen Commit. Kein automatischer Commit-/Push-Zyklus während der
  Umsetzung. Pushes nur im bereits autorisierten Umfang ausführen.
- Repoübergreifende Arbeiten bleiben getrennte Commits je Repository; vor einem
  gebündelten Push die erforderlichen Prüfungen der betroffenen Repos abschließen.
- Bestehende Commit-Historie nicht zum Zusammenfassen umschreiben, sofern das
  nicht ausdrücklich beauftragt wurde. Kein Force-Push und kein Agenten-Push
  auf `main`. Explizite Nutzerwünsche zu Zwischenständen haben Vorrang.
