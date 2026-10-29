# 0015 — Der Agent baut den develop-Stand selbst neu, die Produktion nie

**Status:** Vorschlag
**Datum:** 23.10.2026
**Beteiligt:** Projektteam
**Korrigiert:** 29.10.2026 — Die erste Fassung trennte den main-Stand von „der Produktion“ aus
`docker-compose.prod.yml`. Der main-Stand ist die Produktion (ADR 0014).
Die Sperren selbst sind unverändert.

## Kontext

Seit ADR 0013 ist `develop` Staging und `main` Produktion. Seit ADR 0014 baut
`.github/workflows/staging.yml` zwei Stände: `develop` auf eigener VM unter
`staging.<zone>`, `main` als Produktion auf der bisherigen VM unter
`appstore.<zone>`. Daneben beschreibt `docker-compose.prod.yml` eine
eigenständige Installation, die eine Person von Hand aufsetzt.

Bis heute stand `gh workflow run` in `permissions.ask`: Jeder Lauf, den ein
Agent anstoßen wollte, wartete auf einen Klick. `docs/harness.md` begründete
das damit, dass jeder Lauf etwas verändert — `recreate` steht auf `true`, einen
Trockenlauf gibt es nicht.

Staging wird ohnehin bei jedem Merge abgerissen und neu gebaut (ADR 0003).

Von einem Entwicklerrechner aus erreicht ein Agent Staging nur über HTTPS und
über die GitHub-API. Port 22 der VMs ist nur aus dem Campusnetz offen
(`infrastructure/tofu/envs/staging/security_group.tf`); an die Container-Logs
kommt er nicht.

Am 22.10.2026 ersetzte ein Neubau des develop-Stands den Worker, während ein
App-Deployment im Store auf cloud-init wartete. Das Deployment blieb danach
dauerhaft auf „läuft". Ein Mechanismus, der solche Tasks aufräumt, fehlt.

Am 23.10.2026 entschied das Team: Der Agent soll Staging bedienen dürfen, die
Produktion nicht.

## Entscheidung

Wir erlauben dem Agenten, den Stand `develop` ohne Rückfrage neu zu bauen, und
sperren für ihn jeden Lauf gegen den Stand `main`, also die Produktion, sowie
jede Aktion gegen eine eigenständige Installation.

Umgesetzt in drei Reihen:

1. `permissions.allow` enthält `gh workflow run staging.yml *`; die allgemeine
   ask-Regel für `gh workflow run` entfällt.
2. Der Bash-Hook (`harness/agent_guard.py`) lässt den Aufruf nur durch, wenn
   `--ref develop` und `-f stand=develop` ausdrücklich dastehen und kein
   Staging-Deploy läuft oder wartet. Lässt sich das nicht feststellen, blockt
   er. Für Eingaben per `--json` blockt er immer.
3. `permissions.deny` sperrt `gh workflow run *stand=main*` zusätzlich, falls
   der Hook ausfällt. Wie bisher gesperrt bleiben `make prod*`, Compose gegen
   die Prod- und Staging-Datei, `deploy.cmd` und `tofu apply`.

Lesend kommt `make staging-status` dazu: DNS beider Stände (lokal gegen
öffentlich), Frontend, IPv4/IPv6, `/api/health`, Keycloak, letzte Läufe.

Das Bearbeiten von `.github/workflows/**` und `harness/**` fragt nach. Ein
Agent, der Staging bedienen darf, soll nicht nebenbei die Regeln umschreiben,
die das begrenzen.

## Konsequenzen

Leichter:

- Der Agent kann eine gemergte Änderung auf Staging nachweisen und einen
  kaputten develop-Stand neu bauen, ohne dass jemand daneben sitzt.
- Zwei Läufe überholen sich nicht: Der Hook lehnt ab, solange einer läuft.
- `make staging-status` erkennt den häufigsten Fehlalarm nach einem Neubau —
  einen lokalen DNS-Cache mit der alten IPv6-Adresse.

Schwerer:

- Ein Neubau mit `recreate=true` beendet laufende App-Deployments im
  develop-Stand; der Hook sieht sie nicht. Der Skill `deployment-pruefen`
  empfiehlt `recreate=false` und eine Nachfrage vor Vorführungen — das ist
  Beratung, keine Sperre.
- Jeder Neubau vergibt der VM eine neue IPv6-Adresse.
- Der Hook ist eigener Code. Fällt er aus, bleibt nur die deny-Regel auf
  `stand=main`; die Prüfung auf laufende Deploys entfällt dann.
- Der Agent bleibt für Container-Logs auf das angewiesen, was der Workflow
  ausgibt.

## Verworfene Alternativen

**Bei `ask` bleiben.** Jede Verifikation wartet auf einen Klick, für etwas,
das ADR 0003 ausdrücklich als wegwerfbar behandelt. Der Agent kann dann nicht
selbst merken, dass ein Stand rot ist, und weiterarbeiten.

**SSH-Zugang des Agenten zur VM.** Port 22 ist nur aus dem Campusnetz offen.
Ihn zu öffnen oder einen Tunnel zu bauen hieße, einen Schlüssel mit
VM-Zugriff in die Agentensitzung zu bringen. Das ist genau die Infrastruktur
unter dem Knopf, die nach `docs/harness.md` bei der Pipeline bleibt.

**Beide Stände freigeben.** Der main-Stand ist die Produktion. Ihn neu zu
bauen, nimmt sie für einige Minuten vom Netz und bricht laufende
App-Aufträge ab.

**Nur Berechtigungsmuster, kein Hook.** Muster vergleichen Wörter in fester
Reihenfolge. Die Reihenfolge der `-f`-Felder ist frei, und ob gerade ein
Deploy läuft, kann ein Muster nicht wissen.
