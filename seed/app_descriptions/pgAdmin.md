# pgAdmin 4 – PostgreSQL-Administration mit Beispieldatenbank

Jedes Team bekommt eine eigene VM mit PostgreSQL, der Beispieldatenbank
**Pagila** (Film- und Videoverleih) und pgAdmin 4 im Browser. Die Datenbank ist
in pgAdmin schon als Server eingetragen.

## User-Management

- **Ein pgAdmin-Konto pro Team**, alle Mitglieder teilen sich den Login
- Login ist eine E-Mail-Adresse aus dem Teamnamen, z.B. `Team #1` →
  `team-1@example.com`; das Passwort wird zufällig erzeugt
- Der Datenbanknutzer für Pagila ist `pagila_user` mit dem Passwort `pagila`.
  pgAdmin fragt danach, sobald man den Server öffnet.

## VM-Deployment

| | |
|---|---|
| VMs gesamt | **eine pro Team** (höchstens 15) |
| Größe | wählbar: `gp1.small`, `gp1.medium`, `gp1.large` |
| Erreichbar über | HTTP auf Port 80 unter `/pgadmin4`, über IPv6 (Standard), IPv4 oder beides |
| Floating IP | Nein |

## Konfigurierbare Variablen

| Variable | Beschreibung | Pflicht |
|---|---|---|
| `flavor` | Größe der Team-VM | Nein (Standard `gp1.small`) |
| `disk_size_gb` | Festplatte in GB, `0` = Platte des Flavors | Nein |
| `max_teams` | Obergrenze für Team-VMs | Nein (Standard 15) |
| `ip_mode` | Adressfamilie: `ipv4`, `ipv6` oder `dual` | Nein (Standard `ipv6`) |
| `network_uuid` / `network_v4_uuid` | Netz für IPv6 bzw. IPv4 | Nein (Standard vorhanden) |
| `shared_secgroup_id` | ID der gemeinsamen Security Group | Nein (Standard vorhanden) |

Kein File-Upload.

## Deployment-Dauer

Ein Deployment läuft in zwei Phasen:

1. `tofu apply` legt VM und Netzanschluss an.
2. Beim ersten Start richtet cloud-init die VM ein (Phase `VM_SETUP`). Der Store
   meldet das Deployment erst als fertig, wenn diese Einrichtung abgeschlossen
   ist.

Es gibt kein vorgebautes Image mehr: PostgreSQL, pgAdmin und die
Beispieldatenbank werden bei jedem Deployment installiert. Die Dauer hängt
deshalb von der Einrichtung ab. Messwerte folgen nach der Abnahme auf Staging.
