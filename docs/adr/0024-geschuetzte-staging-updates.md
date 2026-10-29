# 0024 — Geschützte und teilweise inkrementelle Staging-Updates

**Status:** Vorschlag
**Datum:** 28.10.2026
**Beteiligt:** Projektteam (Entscheidung ausstehend)
**Korrigiert:** 29.10.2026 — Die erste Fassung sagte, der Schutz werde vor Tests und Teamentscheidung
nicht im Live-Staging aktiviert. Er ist für `develop` seit dem 29.10.2026
aktiv; für `main` ist er vorbereitet, aber aus. Abschnitt „Stand“ ergänzt.

## Kontext

ADR 0003 legt für jeden Merge einen vollständigen Neuaufbau fest. Das prüft
die Reproduzierbarkeit, unterbricht jedoch die Plattform und kann laufende
App-Aufträge stören. Zusätzlich existiert ein unabhängiger Auto-Update-Timer.
Ein Schutz nur im GitHub-Workflow würde diesen zweiten Weg nicht abdecken.

## Vorgeschlagene Entscheidung

Für `develop` soll ein explizit aktivierter Schutz beide Wege koordinieren.
Das Backend verwaltet eine persistente Wartungssperre in der Anwendungsdatenbank:
Auftragsannahme und Setzen der Sperre verriegeln dieselbe Datenbankzeile.
Nach Setzen der Sperre werden bestehende `PENDING`- und `RUNNING`-Tasks
abgewartet. Vor dem Neustart müssen Celery-Worker erreichbar und ohne aktive,
reservierte oder geplante Tasks sein; RabbitMQ muss außerdem null wartende und
null unbestätigte Nachrichten melden. Unklare Antworten blockieren das Update.
Die Sperre wird nur vom Besitzer freigegeben; nach einem nicht
eindeutig erfolgreich abgeschlossenen Update bleibt sie geschlossen.

Für einen Image-Dispatch aus Frontend, Backend oder Worker soll der Workflow
die bestehende VM beibehalten. Ein OpenTofu-Plan mit Löschung oder Ersetzung
wird abgelehnt. Andere Auslöser und ausdrücklich verlangte Neubauten behalten
den vollständigen Neuaufbau bei. Damit würde diese Entscheidung ADR 0003 für
den genannten Teilfall einschränken, falls das Team sie annimmt.

Der alternative Timer setzt dieselbe Sperre, speichert laufende Image-IDs und
rollt diese bei fehlerhaftem Healthcheck zurück. Automatische Backend-Updates
werden verweigert, sobald die Zielversion eine Datenbankmigration benötigt.
Diagnosen enthalten ausschließlich ausgewählte Containerzustände und keine
Rohlogs.

## Grenzen und Voraussetzungen

- Der neue Backend-Code und seine Migration müssen vor der Aktivierung
  bereits laufen. Während der Umstellung darf kein alter, ungeschützter Timer
  aktiv sein. Bis zum Bootstrap ist der Schalter des Stands nicht gesetzt.
  Ein ausdrücklich manueller Bootstrap-Lauf kann den alten Timer anhalten,
  einen bereits laufenden Timer-Job fertig werden lassen, die gemeinsame
  Sperre setzen und anschließend die geschützte Timer-Variante installieren.
  Der Lauf ist auf `develop`, `recreate=false` und `seed=false` beschränkt und muss vor
  dem Setzen der Flag erfolgreich auf einem Teststack erprobt werden.
- Der Workflow ändert bei einem Image-Dispatch auch Ansible- und
  Compose-Konfiguration. Ob diese Aktualisierung unabhängig von weiteren
  Infrastrukturänderungen akzeptabel ist, muss auf einem getrennten Stack
  geprüft werden. Sie ist nicht unterbrechungsfrei.
- Der Timer-Rollback ist auf Container-Images ohne erforderliche Migration
  begrenzt. Für den Plattform-Workflow existiert noch kein automatischer
  Rollback. Images müssen verfügbar bleiben; Backups ersetzen dies nicht.
- Datenbankstatus allein ist kein zuverlässiger Nachweis: Der Reconciler kann
  ein länger in Celery `PENDING` stehendes Task als fehlgeschlagen markieren,
  obwohl der Broker es noch hält. Deshalb werden Broker und Worker separat
  geprüft. Der Test mit lokalem RabbitMQ und simuliertem Celery-Task deckt
  Grundfälle ab; Tests mit dem echten Worker, laufendem OpenTofu-Prozess,
  Absturz und Wiederanlauf stehen noch aus.
- Nach unbekanntem Fehler ist ein kontrollierter, manueller Recovery-Ablauf
  nötig. Der Besitzer der Wartungssperre wird im Workflow protokolliert. Eine
  Wiederaufnahme kann diesen exakten Besitzer angeben und setzt dessen Sperre
  fort; bei einem Fehler im Wiederaufnahmelauf bleibt die Sperre bestehen.
- Tests gegen einen unabhängigen OpenStack-Teststack und die Teamentscheidung
  stehen aus.

## Stand

| Stand | Schalter (Repository-Variable) | Zustand |
|---|---|---|
| `develop` (Staging) | `GUARDED_STAGING_UPDATES` | `true` seit 29.10.2026, nach Bootstrap-Lauf |
| `main` (Produktion) | `GUARDED_MAIN_UPDATES` | nicht gesetzt, Schutz aus |

Der Ablauf bis zur Aktivierung für `main` steht in
[docs/geschuetzte-main-updates-vorbereitung.md](../geschuetzte-main-updates-vorbereitung.md).
Bis dahin reißt jeder Release-Merge die Produktion ab und baut sie neu
(ADR 0003), auch während App-Aufträge laufen.
