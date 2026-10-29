# 0013 — `develop` ist Staging, `main` ist Produktion

**Status:** Angenommen
**Datum:** 22.10.2026
**Beteiligt:** Projektteam
**Korrigiert:** 29.10.2026 — Die erste Fassung ließ den Produktionsdeploy bei einer Person auf der
Zielmaschine und schloss einen Deploy nach einem Merge auf `main` aus. Seit
ADR 0014 rollt die Pipeline `main` automatisch unter `appstore.<zone>` aus,
und das Team betreibt genau diesen Stand als Produktion.

## Kontext

Bis Oktober 2026 hatte `main` zwei Rollen. Jeder Merge darauf baute Staging
neu (ADR 0003), und derselbe Stand war der, den eine Person in Produktion
ausrollt. `develop` gab es in allen vier Stack-Repos, aber ohne Aufgabe: Die
CI lief nur für `main`, der Standardbranch war `main`, also zielten die
meisten Feature-PRs direkt dorthin. Einiges landete trotzdem nur auf
`develop` — der Backend-Refactor (#18), der neue Deployment-Wizard im
Frontend —, ohne dass die CI je darüber lief.

Am 22.10.2026 lagen die beiden Branches überall auseinander. Im deployment-
und im worker-Repo stand `develop` seit dem 20. bzw. 19.09., im Frontend lag
`main` hinter `develop`, im Backend hatten beide Seiten eigene Commits: fünf
Dateien mit Konflikten und zwei Alembic-Heads, die `alembic upgrade head`
blockiert hätten.

Folgenlos war das alte `develop` nicht. Der Harness-Check in backend,
frontend und worker holt seine Quelle vom gleichnamigen Branch im
deployment-Repo, sonst von `develop`. Das veraltete `develop` dort machte
jeden Feature-PR ohne Gegenstück rot, und mehrere wurden trotzdem gemergt.

## Entscheidung

`develop` ist Staging, `main` ist Produktion.

- Neue Arbeit zweigt von `develop` ab und kommt per Pull Request nach
  `develop` zurück. Die CI läuft für Pull Requests und Pushes auf beide
  Branches.
- Ein Merge auf `develop` baut Staging neu: backend, frontend und worker
  pushen ihr Image als `:develop` und stoßen danach `staging.yml` an, ein
  Push auf `develop` im deployment-Repo tut das direkt.
  `docker-compose.staging.yml` zieht standardmäßig `:develop`.
- `main` bekommt nur Release-PRs `develop` → `main`, gemergt mit
  Merge-Commit. Daraus entstehen die Images `:latest`. Den Release-Merge gibt
  eine Person frei; ausgerollt wird danach automatisch (ADR 0014).
- Nach einem Release wird `develop` per Fast-Forward auf `main` gezogen.
  Hotfixes zweigen von `main` ab und werden danach in `develop` gemergt.
- Standardbranch ist in allen vier Repos `develop`. Das Tag `latest` hängt
  deshalb nicht mehr an `{{is_default_branch}}`, sondern ausdrücklich an
  `refs/heads/main`.

ADR 0003, 0005 und 0006 sprechen vom „Merge auf `main`", der Staging neu
baut. Seit diesem ADR ist damit der Merge auf `develop` gemeint; sonst gilt
dort alles weiter.

## Konsequenzen

- Auf Staging läuft genau `develop`, in Produktion genau `main`. Dazwischen
  liegt ein Release-PR, den man ansehen und prüfen kann.
- `develop` hat dieselbe CI wie `main`. Ein Merge ohne grüne Prüfung ist dort
  nicht mehr der Normalfall.
- Welche Images Staging zieht, entscheidet am Ende das Secret
  `STAGING_ENV_FILE`. Steht dort `*_VERSION=latest` — so stand es bis hierher
  in `.env.staging.example` —, läuft auf Staging der Produktionsstand.
  `staging.yml` warnt in dem Fall.
- `repository_dispatch` und `workflow_dispatch` laufen mit dem Workflow vom
  Standardbranch. Steht der im deployment-Repo nicht auf `develop`, baut ein
  angestoßener Staging-Deploy mit der Konfiguration von `main`.
- Ein Release ist ein zusätzlicher Schritt, und danach muss `develop`
  nachgezogen werden. Bleibt das aus, steht `develop` um den Merge-Commit
  „hinter" `main` — harmlos im Inhalt, aber genau das Bild, das diese
  Entscheidung ausgelöst hat.

## Verworfene Alternativen

**Nur `main`, `develop` als Spiegel oder gar nicht.** Entsprach dem, was bis
dahin tatsächlich geschah, und wäre am einfachsten gewesen. Verworfen, weil
dann jeder Merge zugleich Staging und den Stand für die Produktion ändert: Es
gäbe keinen Ort, an dem etwas auf Staging läuft, bevor es Produktion wird.

**Release per Squash- oder Rebase-Merge.** Hielte `main` linear, schreibt aber
jeden Release neu. `develop` und `main` trügen danach dauerhaft verschiedene
Commits für denselben Inhalt, und jede weitere Zusammenführung brächte
Scheinkonflikte. Deshalb Merge-Commit.

**Staging aus `main`, Produktion über Versions-Tags.** Hätte die Pipeline
unverändert gelassen. Verworfen, weil das Team bereits mit `develop` und
`main` arbeitet und „Branch = Umgebung" ohne Zusatzwissen lesbar ist.
