# Vorbereitung: geschützte Updates für den main-Stand

Der unter der App-Store-Adresse laufende main-Stand wird als Produktion
genutzt. Der Schutz kann über `GUARDED_MAIN_UPDATES` unabhängig von der
Staging-Variable `GUARDED_STAGING_UPDATES` aktiviert werden. Eine fehlende
Variable bedeutet: Schutz aus. Der bestehende develop-Schutz bleibt unverändert.

Diese Änderung allein aktiviert keinen Schutz auf main. Der Bootstrap darf
erst nach gründlicher Prüfung und Freigabe durch das Team erfolgen. Die
bisherigen Tests beweisen keinen fehlerfreien Produktionsbetrieb: insbesondere
fehlen Tests mit gleichzeitig laufendem echtem Worker-Auftrag, tatsächlichem
Rollback und Fehlern beim Übergang.

## Voraussetzungen vor dem Release

- `main` und `develop` in den betroffenen Repositories auf Unterschiede und
  Konflikte prüfen. Die Release-PRs können auch andere Änderungen enthalten.
- Für die Datenbanken ein geprüftes Backup und einen Wiederherstellungsplan
  bereithalten; ein Image-Rollback macht keine Migration rückgängig.
- Ein Wartungsfenster vereinbaren und laufende App-Aufträge vor den ersten,
  noch ungeschützten Deployments kontrollieren. Ein Release-Merge kann
  automatisch ein Deployment und damit einen VM-Neubau auslösen. Der bisherige
  Timer kann ebenfalls selbstständig Images wechseln.
- Backend-Version mit Wartungssperre und Datenbankmigration auf `main`
  veröffentlichen und prüfen, dass sie im main-Stand läuft und die Migration
  angewendet wurde. Auch die dazugehörigen Änderungen müssen überprüft werden.
- Deployment-Workflow und seine Skripte über den regulären Release-Prozess
  nach `main` übernehmen und den daraus folgenden Lauf überprüfen. Der
  neue Workflow für `repository_dispatch` und `workflow_dispatch` muss zudem
  auf dem Standardbranch liegen, die main-Dateien müssen die neuen Skripte
  enthalten. `GUARDED_MAIN_UPDATES` bleibt vorerst aus.

## Kontrollierter Bootstrap und Aktivierung

1. Mit den Verantwortlichen Zustand, aktive Aufträge, Backups und den
   Wiederherstellungsweg prüfen. Keine produktiven Aktionen durch den Agenten.
2. Berechtigte Person startet im Deployment-Workflow den Bootstrap für `main`
   mit `recreate=false`, `seed=false`, `bootstrap_guarded=true` und leerem
   `bootstrap_resume_owner`. Der alte Timer wird angehalten und ein laufender
   Timer-Job abgewartet, dann werden Sperre, Worker und Broker geprüft und der
   geschützte Timer installiert.
3. Nach erfolgreichem Lauf Backend, Dienste, Timer, Sperre und zentrale
   Funktionen prüfen. Bei einem Fehler nicht blind wiederholen: Timer und
   Wartungssperre könnten bestehen bleiben; den protokollierten Eigentümer
   und den tatsächlichen Zustand prüfen. Ein Resume ist nur mit dem exakten
   Eigentümer des fehlgeschlagenen Laufs vorgesehen.
4. Erst nach erfolgreichem Bootstrap und Prüfung setzt eine berechtigte
   Person `GUARDED_MAIN_UPDATES=true`. Danach ein kontrolliertes Update und
   die relevanten Fehlerfälle prüfen. Die Variable steuert nicht `develop`.

Der geschützte Image-Dispatch kann die bestehende VM behalten, wenn der
OpenTofu-Plan keine Ressourcen löscht oder ersetzt. Andere Auslöser können
weiterhin einen Neubau auslösen. Der Timer-Rollback ist auf die vorhandenen
Image-IDs und Updates ohne erforderliche Migration begrenzt. Einen generellen
automatischen Rollback von Datenbank und Plattform gibt es nicht.

## Lokale Workflow-Prüfung

`python tests/test_workflow_routing.py` liest die
tatsächlichen Bedingungen des Workflows und prüft sie für beide Stände,
unterschiedliche Ereignisse, Schalter und Eingaben. Der Test benötigt PyYAML
und Node.js und greift nicht auf GitHub oder den Stack zu. Ein echter
Workflow-Lauf und die oben genannten Integrationstests werden dadurch nicht
ersetzt.
