# 0011 — Ein Deploy ist erst fertig, wenn cloud-init in allen VMs durchgelaufen ist

**Status:** Angenommen
**Datum:** 14.10.2026
**Beteiligt:** Projektteam

## Kontext

Seit ADR 0010 baut die Plattform keine Images mehr. Eine App richtet ihre
VM beim ersten Boot über cloud-init selbst ein. `tofu apply` endet aber,
sobald OpenStack die Instanz als ACTIVE meldet. Der Worker meldete das
Deployment in diesem Moment als erfolgreich, das Frontend zeigte es als
fertig an, und die Zugangsdaten gingen hinaus.

Am 14.10.2026 zeigte die Kali-App die Folgen. Ihre Einrichtung (Umstellung
von Debian auf Kali, Desktop, Werkzeuge) dauert auf newstack etwa eine halbe
Stunde. In dieser Zeit stand das Deployment als fertig da, RDP antwortete
aber nicht. Zweimal brach die Einrichtung sogar ab, weil die EFI-Partition
vollgelaufen war. Auch dann blieb das Deployment „erfolgreich“, und der
Fehler war nur in der Serienkonsole der VM zu finden.

Für das Ende der Einrichtung gibt es ein Signal, das keine App selbst
liefern muss. systemd schreibt das Ergebnis der letzten cloud-init-Stufe
in die Serienkonsole, die über die OpenStack-API lesbar ist:

- `[  OK  ] Finished cloud-final.service`, wenn die Einrichtung durchlief
  (gesehen an Staging-, k8s- und group-network-VMs)
- `[FAILED] Failed to start cloud-final.service`, wenn sie scheiterte
  (gesehen an der abgebrochenen Kali-VM)

Der Worker quittiert Celery-Tasks erst an deren Ende (`task_acks_late`).
RabbitMQ 3.13 gibt einen Task nach `consumer_timeout`, standardmäßig
30 Minuten, unquittiert erneut aus. Gesetzt war der Wert nirgends.

## Entscheidung

Der Worker meldet ein Deployment erst als erfolgreich, wenn cloud-init in
allen seinen VMs durchgelaufen ist. Er erkennt das an der Serienkonsole und
wartet höchstens 90 Minuten. Den `consumer_timeout` von RabbitMQ setzen wir
in allen Umgebungen auf 3 Stunden.

Im Einzelnen:

- **Neue letzte Phase `VM_SETUP`** im Worker, nach `tofu apply` und dem
  Einsammeln von State und Outputs. Sie liest alle 30 Sekunden die
  Konsole jeder VM.
- **Scheitert die Einrichtung**, scheitert das Deployment. Die passenden
  Zeilen aus der Konsole landen im Deployment-Log, ohne Zeilen, die nach
  Passwörtern aussehen. Die VMs werden **nicht** abgerissen, damit man
  nachsehen kann; gelöscht wird wie gewohnt über den App Store.
- **Startet eine App am Ende ihrer Einrichtung neu** (Kali), zählt erst die
  Meldung aus dem Boot danach.
- **Keine Endlosschleife:** Zeigt eine Konsole nach 10 Minuten gar kein
  cloud-init (ein Image ohne cloud-init) oder ist sie 10 Minuten lang nicht
  lesbar, wartet der Worker auf diese VM nicht weiter. Nach 90 Minuten
  ohne Ergebnis scheitert das Deployment.

## Konsequenzen

Leichter wird:

- „Erfolgreich“ heißt jetzt benutzbar. Zugangsdaten gehen erst hinaus, wenn
  der Zugang funktioniert.
- Ein Fehler in der Einrichtung ist ein fehlgeschlagenes Deployment mit der
  Ursache im Log, statt eines scheinbar fertigen, das nicht antwortet.
- Keine App muss etwas dafür tun, und es hängt an keiner bestimmten App.

Schwerer wird:

- **Ein Deploy belegt einen Worker-Platz so lange, wie die Einrichtung
  dauert**, bei Kali etwa eine halbe Stunde statt zwei Minuten. Laufen
  viele Deployments gleichzeitig, warten weitere in der Schlange.
- **Der Broker muss länger warten als der Worker.** Wird die Wartezeit im
  Worker (`VM_SETUP_TIMEOUT_S`) erhöht, muss `consumer_timeout` in den
  Compose-Dateien mitwachsen. Sonst gibt RabbitMQ den Deploy erneut aus,
  und er liefe doppelt.
- Ein Deploy kann jetzt an etwas scheitern, das vorher unbemerkt blieb.
  Bestehende Apps, deren Einrichtung schon immer scheiterte, fallen damit
  erstmals auf. Das ist gewollt.
- Pause, Resume und das Neuausrollen einzelner VMs warten bisher nicht. Das
  Neuausrollen erzeugt eine frische VM und hätte denselben Bedarf.

## Verworfene Alternativen

**Nur die Anzeige ändern.** Das Backend hätte beim Anzeigen die Konsole lesen
und pro VM „richtet sich ein / bereit / fehlgeschlagen“ zeigen können, ohne
Worker-Platz zu belegen. Der Gesamtstatus hätte aber weiter zu früh
„erfolgreich“ gelautet, und die Zugangsdaten wären weiter sofort
hinausgegangen.

**Jede App meldet selbst, wann sie fertig ist**, etwa über einen Port, den
die Plattform abfragt. Das verlangt einen neuen Teil im App-Vertrag, den
jede App umsetzen muss, und erkennt einen Abbruch nicht, nur das Ausbleiben
der Fertigmeldung. Die cloud-init-Meldung gibt es bei jeder App schon.

**Warten in OpenTofu**, etwa mit `time_sleep` wie in der Ubuntu-App. Eine
feste Zeit ist entweder zu kurz oder unnötig lang. Außerdem bricht der
Worker `tofu apply` nach 30 Minuten ab, und bei einem Abbruch würde der
Fehlerpfad alles abreißen, auch die VM, die man untersuchen will.

**Den Task kurz halten und sich selbst neu einplanen lassen**, also ein
Prüf-Task pro Minute statt eines langen Tasks. Belegt keinen Worker-Platz,
braucht aber einen neuen Zwischenstatus im Datenmodell des Backends und
ein eigenes Ende für Erfolg und Fehler. Für den heutigen Bedarf zu viel.
