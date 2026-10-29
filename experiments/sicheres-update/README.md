# Isolierter Versuch: sichere Plattform-Updates

Stand: lokaler Stand von `origin/develop` zum Erstellungszeitpunkt. Dies ist
ein **Prototyp**, nicht die bestehende App und nicht mit Staging verbunden.
Der Test startet einen eindeutig benannten Docker-Compose-Stack mit zwei
lokalen Containern und einem simulierten Dienst. Die Ports sind nur auf
`127.0.0.1` gebunden. Es werden weder OpenStack noch GitHub noch die echte
Staging-Konfiguration angesprochen.

```powershell
python experiments/sicheres-update/test_experiment.py
```

Getestet werden ein Update zwischen lokal gebauten Container-Images, eine atomare Auftragssperre mit
Auslaufen bereits angenommener simulierten Aufträge, der Abbruch bei Timeout,
ein Rückwechsel bei bewusst fehlerhaftem Healthcheck und eine Diagnose mit
erlaubten Statuswerten ohne Rohlogs. Auch konkurrierende Updates und der Ausfall
des Sperrdienstes werden geprüft. Der Test räumt ausschließlich seinen eigenen,
zufällig benannten Compose-Stack wieder auf.

## Stand des echten Umbaus in den isolierten Arbeitskopien

Neben diesem ursprünglichen Mini-Stack existieren jetzt experimentelle
Änderungen in `backend-deploy-experiment` und `deployment-deploy-experiment`:

- Backend: transaktionssichere, persistente Auftragssperre mit Migration,
  503 bei Wartung, Wartungssteuerung und PostgreSQL-Integrationstests.
- Deployment: opt-in Runner-Schutz, Prüfung nicht destruktiver OpenTofu-Pläne
  und ein neuer geschützter Auto-Updater mit Image-Pinning, begrenztem
  Rückwechsel und bereinigtem Containerstatus.
- Vor einem Neustart werden auch Celery-Worker sowie die wartenden und
  unbestätigten RabbitMQ-Nachrichten geprüft. Ungültige oder fehlende Antworten
  blockieren den Update-Versuch.
- Der Updater lehnt automatische Backend-Updates ab, wenn die aktuelle
  Datenbankrevision nicht zu den Migration-Heads des Zielimages passt.
- `GUARDED_STAGING_UPDATES` ist standardmäßig nicht aktiviert. Die Änderungen
  sind weder gemerged noch ausgerollt. Der beschriebene Teststack arbeitet
  weiterhin unabhängig vom echten Staging.

Automatisierte Backend-Tests gegen eine separate Datenbank:

```powershell
python experiments/sicheres-update/run_backend_tests.py tests/test_platform_maintenance.py tests/test_maintenance_operator.py
```

Der Test nutzt die bereits existierende lokale Backend-Entwicklungsumgebung
für ihre Python-Abhängigkeiten **nur lesend** und startet eine neue PostgreSQL-
Instanz mit zufälligem Compose-Projektnamen. Keine vorhandene Datenbank wird
für die Tests verwendet.

Weitere Tests:

```powershell
python experiments/sicheres-update/test_guarded_autoupdate.py
python experiments/sicheres-update/test_inplace_plan.py
python experiments/sicheres-update/test_broker_queues.py
python experiments/sicheres-update/test_real_broker.py
```

## Was vor einer Übernahme noch fehlt

Hier werden **keine Images, Datenbankmigrationen oder Aufträge des echten
App-Stores** verarbeitet. `v1` und `v2` sind lokal gebaute Test-Images mit
simuliertem Dienst, keine Images des App-Stores. Für den tatsächlichen Einsatz fehlen:

- Die echte Auftragsannahme nutzt die Sperre. Ein isolierter RabbitMQ-/Celery-
  Test prüft außerdem wartende und aktive simulierte Tasks; echter Worker,
  laufendes OpenTofu sowie Abstürze und Wiederanlauf müssen separat geprüft
  werden. Eine reine einmalige Datenbank-Statusabfrage hätte ein Race.
- Beide Wege sind vorbereitet, benötigen aber einen koordinierten Bootstrap:
  Backend/Migration zuerst, alter Timer ausgeschaltet oder geschützt, erst
  danach das Flag aktivieren. Ein ungeschützter alter Backend-Prozess oder
  Timer kann die Sperre umgehen.
- Der Timer nutzt lokale Image-IDs zum Rückwechsel. Diese Images müssen auch
  im Fehlerfall verfügbar bleiben; für dauerhaften Rückwechsel sind Registry-
  Digests nötig. Datenbankmigrationen brauchen ein geeignetes
  Kompatibilitäts- und Wiederherstellungskonzept; ein altes Image allein ist
  kein vollständiger Datenbank-Rollback.
- Backend-, Worker- und Frontend-Versionen und ihr Zusammenspiel müssen mit
  echter Compose-Konfiguration, Testdatenbank und einem simulierten Worker-Job
  getestet werden. Neustart eines Containers verursacht kurzzeitige
  Unterbrechung; der Versuch beweist keine unterbrechungsfreie Bereitstellung.
- Ein für Ausfälle robuster Wartungszustand mit gesichertem Recovery,
  Zugriffsschutz und sauberem Aufräumen ist nötig. Der Versuch hält die Sperre
  bei unbekanntem Zustand bewusst fest und braucht dann manuelle Hilfe.
- Vor jeder Übernahme: ADR 0003 sowie DNS, Migrationen, Datensicherung,
  Zertifikate, Security, beobachtbare Fehlerfälle und Durchlauf auf einer
  getrennten Testumgebung prüfen. Kein automatisches Staging-Deployment
  aufgrund dieses Prototyps auslösen.

Hinweis: Anders als ältere Dokumentation nahelegt, liegen die Anwendungs- und
Keycloak-Datenbanken laut ADR 0006 bereits auf dem Runner außerhalb der
Staging-VM. Das ersetzt keine unabhängig getestete Datensicherung.
