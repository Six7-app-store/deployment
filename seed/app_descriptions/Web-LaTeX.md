# Web-LaTeX Editor

Ein LaTeX-Editor im Browser. Jedes Team bekommt eine eigene VM mit TeX Live,
Syntax-Highlighting und PDF-Vorschau. Die Mitglieder eines Teams teilen sich
die VM, arbeiten aber jeweils in einem eigenen Projektverzeichnis.

## Funktionen

- PDF-Vorschau nach dem Kompilieren (`pdflatex`, zwei Läufe für
  Inhaltsverzeichnis und Verweise), Kompilieren auch mit `Strg+Enter`
- Datei-Explorer mit mehreren `.tex`-Dateien und Unterverzeichnissen
- Neue `.tex`-Dateien direkt im Browser anlegen
- Bilder (PNG, JPG, GIF, bis 10 MB) hochladen und per `\includegraphics{}`
  einbinden
- Automatisches Speichern während des Schreibens

## User-Management

- **Ein Login pro Person**: Benutzername ist die E-Mail-Adresse, das Passwort
  wird zufällig erzeugt
- Alle Mitglieder eines Teams arbeiten auf derselben VM, jede Person in ihrem
  eigenen Verzeichnis

## VM-Deployment

| | |
|---|---|
| VMs gesamt | **eine pro Team** (höchstens 15) |
| Größe | wählbar: `gp1.small`, `gp1.medium`, `gp1.large` |
| Erreichbar über | HTTP auf Port 80, über IPv6 (Standard), IPv4 oder beides |
| Floating IP | Nein |

## Konfigurierbare Variablen

| Variable | Beschreibung | Pflicht |
|---|---|---|
| `assignment_files` | Startprojekt als ZIP pro Team, mit `master.tex` im obersten Verzeichnis | Nein |
| `flavor` | Größe der Team-VM | Nein (Standard `gp1.small`) |
| `disk_size_gb` | Festplatte in GB, `0` = Platte des Flavors | Nein |
| `max_teams` | Obergrenze für Team-VMs | Nein (Standard 15) |
| `ip_mode` | Adressfamilie: `ipv4`, `ipv6` oder `dual` | Nein (Standard `ipv6`) |
| `network_uuid` / `network_v4_uuid` | Netz für IPv6 bzw. IPv4 | Nein (Standard vorhanden) |
| `shared_secgroup_id` | ID der gemeinsamen Security Group | Nein (Standard vorhanden) |

Ohne Upload startet jede Person mit einem kleinen Demo-Projekt. Die ZIP darf
höchstens etwa 25 KB groß sein, weil sie beim Start der VM mitreist.

## Deployment-Dauer

Ein Deployment läuft in zwei Phasen:

1. `tofu apply` legt VM und Netzanschluss an.
2. Beim ersten Start richtet cloud-init die VM ein (Phase `VM_SETUP`). Der Store
   meldet das Deployment erst als fertig, wenn diese Einrichtung abgeschlossen
   ist.

Es gibt kein vorgebautes Image mehr: TeX Live wird bei jedem Deployment
installiert. Die Dauer hängt deshalb von der Einrichtung ab. Messwerte folgen
nach der Abnahme auf Staging.
