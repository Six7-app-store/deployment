# pgAdmin 4 – PostgreSQL-Administration mit Beispieldatenbank

Eine pgAdmin4-Instanz pro Team mit einer vorinstallierten PostgreSQL-Datenbank (Pagila-Beispieldatensatz). Jedes Team erhält eine eigene VM mit einem dedizierten pgAdmin-Login und direktem Datenbankzugriff.

## User-Management

Es wird **ein pgAdmin-Account pro Team** erstellt — alle Mitglieder eines Teams teilen sich denselben Login. Die Login-E-Mail hat die Form `<teamname>@example.com`, das Passwort wird automatisch generiert. Zugangsdaten werden nach dem Deployment per Mail an alle Teammitglieder versendet. Der pgAdmin-Account wird direkt in die interne SQLite-Datenbank geschrieben (PBKDF2-SHA512).

Die VM enthält außerdem eine lokale PostgreSQL-Instanz mit der **Pagila-Beispieldatenbank** (Film-/Videoverleih-Schema), die im pgAdmin-Account bereits vorkonfiguriert ist. Das Passwort dazu ist "pagila".

## VM-Deployment

Es wird **eine VM pro Team** deployed. Bei zwei Teams entstehen zwei VMs, jede mit eigener Floating IP und eigenem pgAdmin-Login. Flavor: `gp1.small`.

## Deployment-Dauer

Ein Deployment läuft in zwei Phasen:

1. `tofu apply` legt VM, Netzanschluss und Floating IP an.
2. Beim ersten Start richtet cloud-init die VM ein (Phase `VM_SETUP`). Der Store
   meldet das Deployment erst als fertig, wenn diese Einrichtung abgeschlossen
   ist.

Es gibt kein vorgebautes Image mehr: Die Software wird bei jedem Deployment
installiert. Die Dauer hängt deshalb von der Einrichtung ab und ist länger als
bei früheren Ständen. Messwerte folgen nach der Abnahme auf Staging.

## Konfigurierbare Variablen

| Variable | Beschreibung | Pflicht |
|---|---|---|
| `network_uuid` | UUID des internen Netzwerks | Ja (Default vorhanden) |
| `floating_ip_pool` | Name des External Networks für die öffentliche IP | Ja (Default vorhanden) |
| `shared_secgroup_id` | ID der Security Group | Ja (Default vorhanden) |

Kein File-Upload. Alle Defaults sind auf die DHBW-OpenStack-Infrastruktur vorkonfiguriert.
