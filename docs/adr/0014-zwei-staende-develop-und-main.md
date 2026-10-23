# 0014 — Die Pipeline baut zwei Stände: `develop` und `main`

**Status:** Vorschlag
**Datum:** 22.10.2026
**Beteiligt:** Projektteam

## Kontext

ADR 0013 hat `develop` zu Staging gemacht. Die eine Staging-VM unter
`appstore.<zone>` zieht seitdem `:develop`, eine `main`-Seite gab es danach
nicht mehr. Die Produktion aus `docker-compose.prod.yml` existiert nur als
Anleitung, die eine Person auf einer eigenen VM von Hand ausrollt. Eine
laufende Instanz davon gibt es nicht.

Bis zum 22.10.2026 lief auf genau dieser VM der Stand von `main`. Für das Team
war sie deshalb die Seite des Projekts. Gewünscht sind zwei Stände
nebeneinander: Staging mit `develop` und eine Seite mit `main`, beide
automatisch nach jedem Merge.

Anwendungs-, Keycloak- und OpenTofu-State-Datenbank liegen seit ADR 0005 und
0006 in der Postgres-Instanz auf der Runner-VM, außerhalb des Stacks.

## Entscheidung

`staging.yml` baut je Branch einen eigenen Stand, aus demselben
`envs/staging`, demselben Playbook und derselben Compose-Datei.

| | `main` | `develop` |
|---|---|---|
| VM, Keypair, Security Group | `staging-dhbw-appstore*` (unverändert) | `develop-dhbw-appstore*` |
| OpenTofu-State | `/var/lib/tofu-state/staging/` (unverändert) | `/var/lib/tofu-state/develop/` |
| Hostname | `APP_HOSTNAME` aus `STAGING_ENV_FILE` (unverändert) | `staging.<zone>`, abweichend über die Variable `DEVELOP_APP_HOSTNAME` |
| Datenbanken | wie bisher | dieselben Namen mit `_develop` |
| Images | `:latest` | `:develop` |
| Caddy-Sicherung | `/var/lib/caddy-backup/caddy_data.tgz` | `/var/lib/caddy-backup/develop/caddy_data.tgz` |

- Der Branch des Auslösers bestimmt den Stand: bei `push` der Branch selbst,
  bei `repository_dispatch` `client_payload.ref`, bei `workflow_dispatch` die
  Auswahl im Formular. Fehlt die Angabe, gilt `develop`.
- Die `.env` von `develop` wird zur Laufzeit aus `STAGING_ENV_FILE`
  abgeleitet. Ein Secret `DEVELOP_ENV_FILE` ersetzt die Ableitung, falls
  develop doch anders konfiguriert werden soll.
- Die develop-Datenbanken legt der Workflow auf dem Runner an, wenn es sie
  nicht gibt. Eigentümer sind dieselben Rollen wie bei `main`.
- Der main-Stand behält Namen, State und Adresse. Dadurch bleibt beim
  Umstieg nichts zurück, was erst von Hand aufgeräumt werden müsste.
- Die CI von backend, frontend und worker stößt den Neuaufbau nach grünen
  Läufen auf `develop` und auf `main` an.

Die Produktion aus `docker-compose.prod.yml` bleibt davon unberührt und wird
weiterhin von einer Person ausgerollt.

## Konsequenzen

**Leichter:**

- Was nach `main` geht, steht vorher als `develop` auf einer eigenen Seite.
  Danach läuft es unter der gewohnten Adresse.
- Die Stände teilen nichts, was sie gegenseitig beschädigen könnte: Ein
  Neuaufbau von `develop` reißt nur die develop-VM ab, und die Migrationen von
  `develop` laufen nur gegen die develop-Datenbanken. Auch die
  Deployment-States der beiden Worker bleiben getrennt.
- Ein zweites Secret muss niemand pflegen.

**Schwerer:**

- Doppelt so viel Kontingent: zweimal `k8s.node` (4 vCPU, 8 GB, 50 GB),
  dazu die App-Deployments, die beide Worker anlegen.
- Die Runner-VM (1 vCPU, 2 GB) trägt jetzt sechs Datenbanken statt drei.
  Deploys der beiden Stände laufen nacheinander, weil es einen Runner gibt.
  Ein Release mit Nachziehen von `develop` kostet so zwei Neuaufbauten
  hintereinander.
- Beide Stände benutzen dieselben Passwörter, Client-Secrets und Tokens.
  Für zwei Testinstanzen ist das hinnehmbar, getrennt sind sie damit aber
  nicht.
- Ein Merge auf `main` reißt jetzt eine Seite ab und baut sie neu. Seit
  ADR 0006 überstehen die Daten das, die Seite ist dabei aber einige Minuten
  weg.
- Ob der TSIG-Schlüssel auch für `staging.<zone>` schreiben darf, ist erst
  nach dem ersten develop-Lauf belegt. Bisher ist das nur für `appstore.<zone>`
  nachgewiesen.

## Verworfene Alternativen

**Ein eigenes OpenTofu-Env je Stand** (`envs/develop` neben `envs/staging`).
Wäre näher am Gewohnten gewesen, hätte aber zwei Kopien desselben Codes
bedeutet, die auseinanderlaufen. Was sich unterscheidet, sind ein Präfix und
ein State-Pfad.

**Ein zweites Secret `DEVELOP_ENV_FILE` als Pflicht.** Hätte dreißig Werte
doppelt gepflegt, von denen sich drei unterscheiden. Bleibt als Option für
den Fall, dass develop eigene Zugangsdaten bekommen soll.

**Den main-Stand zur Produktion machen**, also `docker-compose.prod.yml`
automatisch ausrollen. Hätte die Regel gebrochen, dass ein Mensch die
Produktion ausrollt, und eine zweite Infrastruktur (nginx statt Caddy, kein
OpenTofu) in die Pipeline geholt.

**Gemeinsame Datenbanken für beide Stände.** Dann migrierte `develop` die
Daten von `main`, und der develop-Worker sähe die OpenTofu-States der
Deployments von `main` und könnte sie abreißen.
