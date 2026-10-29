# 0014 — Die Pipeline baut zwei Stände: `develop` als Staging, `main` als Produktion

**Status:** Vorschlag
**Datum:** 22.10.2026
**Beteiligt:** Projektteam
**Korrigiert:** 29.10.2026 — Die erste Fassung nannte die Instanz aus `docker-compose.prod.yml`
„Produktion“ und verwarf, den main-Stand dazu zu machen. Das Team betreibt
aber den main-Stand unter `appstore.<zone>` als Produktion, und eine Instanz
aus `docker-compose.prod.yml` hat es nie gegeben. Titel, Entscheidung,
Konsequenzen und die verworfene Alternative sind darauf umgestellt.

## Kontext

ADR 0013 hat `develop` zu Staging gemacht. Die eine Staging-VM unter
`appstore.<zone>` zieht seitdem `:develop`, eine `main`-Seite gab es danach
nicht mehr. `docker-compose.prod.yml` beschreibt eine eigenständige
Installation, die eine Person auf einer eigenen VM von Hand aufsetzt. Eine
laufende Instanz davon gibt es nicht.

Bis zum 22.10.2026 lief auf genau dieser VM der Stand von `main`. Für das Team
war sie deshalb die Produktion. Gewünscht sind zwei Stände nebeneinander:
Staging mit `develop` und die Produktion mit `main`, beide automatisch nach
jedem Merge.

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

Der main-Stand ist die Produktion. Eine Person gibt sie mit dem Release-PR
`develop` → `main` frei, ausgerollt wird automatisch. `docker-compose.prod.yml`
bleibt eine Anleitung für eine eigenständige Installation außerhalb der
Pipeline.

## Konsequenzen

**Leichter:**

- Was in Produktion geht, steht vorher als `develop` auf Staging. Danach
  läuft es unter der gewohnten Adresse.
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
- Beide Stände benutzen dieselben Passwörter, Client-Secrets, Tokens und
  OpenStack-Zugangsdaten. Staging und Produktion sind damit nicht getrennt:
  Wer an die Zugangsdaten von Staging kommt, hat die der Produktion. Ein
  eigenes Secret `DEVELOP_ENV_FILE` ist vorgesehen, aber nicht angelegt.
- Ein Merge auf `main` reißt die Produktion ab und baut sie neu. Seit
  ADR 0006 überstehen die Daten das, die Produktion ist dabei aber einige
  Minuten weg, und laufende App-Aufträge brechen ab, solange der Schutz aus
  ADR 0024 für `main` nicht eingeschaltet ist.
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

**`docker-compose.prod.yml` als Produktion automatisch ausrollen**, neben
dem main-Stand. Hätte eine zweite Infrastruktur (nginx statt Caddy, kein
OpenTofu) in die Pipeline geholt, für eine Instanz, die es nicht gibt. Der
Mensch bleibt trotzdem im Ablauf: Er gibt den Release-PR frei, nicht den
Rollout.

**Gemeinsame Datenbanken für beide Stände.** Dann migrierte `develop` die
Daten von `main`, und der develop-Worker sähe die OpenTofu-States der
Deployments von `main` und könnte sie abreißen.
