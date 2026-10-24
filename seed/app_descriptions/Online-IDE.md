# Online-IDE – Java-Entwicklungsumgebung im Browser

Jedes Team bekommt eine eigene VM, und jede Person darauf einen eigenen
code-server (VS Code im Browser) mit eigenem Port und eigenem Passwort.

## Vorinstallierte Software

- OpenJDK 21 (`java`, `javac`), direkt aus dem Terminal der IDE nutzbar
- Python 3 (inkl. pip, venv), `build-essential`, Git

## Aufgaben

Jede Person findet nach dem Login `~/Coding-Aufgabe/` vor. Ohne Upload liegen
dort zehn Java-Übungen von „Hello World" bis zur binären Suche. Eine
hochgeladene ZIP ersetzt sie für alle Mitglieder des Teams.

## User-Management

- **Ein Account pro Person**, abgeleitet aus der E-Mail-Adresse
  (z.B. `anna.alt@dhbw.de` → `annaalt`)
- Das Passwort gilt für die IDE, für `sudo` und für SSH
- Jede Person hat einen eigenen Port ab 8080; die Zugangsdaten nennen ihn

## VM-Deployment

| | |
|---|---|
| VMs gesamt | **eine pro Team** (höchstens 15, je Team bis 20 Personen) |
| Größe | wählbar: `gp1.small`, `gp1.medium`, `gp1.large` |
| Erreichbar über | HTTP auf Port 8080 + n, über IPv6 (Standard), IPv4 oder beides |
| Floating IP | Nein |

Über IPv4 ist die IDE nur aus dem Campusnetz und dem VPN erreichbar.

## Konfigurierbare Variablen

| Variable | Beschreibung | Pflicht |
|---|---|---|
| `assignment_files` | Aufgaben als ZIP pro Team, landen in `~/Coding-Aufgabe` | Nein |
| `flavor` | Größe der Team-VM | Nein (Standard `gp1.small`) |
| `disk_size_gb` | Festplatte in GB, `0` = Platte des Flavors | Nein |
| `max_teams` | Obergrenze für Team-VMs | Nein (Standard 15) |
| `ip_mode` | Adressfamilie: `ipv4`, `ipv6` oder `dual` | Nein (Standard `ipv6`) |
| `network_uuid` / `network_v4_uuid` | Netz für IPv6 bzw. IPv4 | Nein (Standard vorhanden) |
| `shared_secgroup_id` | ID der gemeinsamen Security Group | Nein (Standard vorhanden) |
| `web_source_v4` / `web_source_v6` | Wer die IDE erreichen darf | Nein (Campus bzw. alle) |

Die ZIP darf höchstens etwa 30 KB groß sein, weil sie beim Start der VM
mitreist.

## Deployment-Dauer

Ein Deployment läuft in zwei Phasen:

1. `tofu apply` legt VM und Netzanschluss an.
2. Beim ersten Start richtet cloud-init die VM ein (Phase `VM_SETUP`). Der Store
   meldet das Deployment erst als fertig, wenn diese Einrichtung abgeschlossen
   ist.

Es gibt kein vorgebautes Image mehr: JDK und code-server werden bei jedem
Deployment installiert. Die Dauer hängt deshalb von der Einrichtung ab.
Messwerte folgen nach der Abnahme auf Staging.
