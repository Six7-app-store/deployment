# Online-IDE – Browserbasierte Java-Entwicklungsumgebung

Eine cloud-init-basierte VS Code Server Instanz pro Team, die jedem Studierenden eine
individuelle Entwicklungsumgebung im Browser bereitstellt. Jeder Nutzer meldet sich mit
persönlichen Zugangsdaten an und erhält eine eigene code-server-Session auf einem
dedizierten Port.

## User-Management

Jeder Nutzer bekommt einen eigenen Linux-Account (abgeleitet aus der E-Mail-Adresse)
und ein automatisch generiertes Passwort. Der Login in code-server erfolgt über dieses
Passwort. Zugangsdaten werden nach dem Deployment per Mail versendet. Innerhalb eines
Teams teilen sich alle Nutzer dieselbe VM, arbeiten aber auf isolierten Ports und in
separaten Home-Verzeichnissen.

## VM-Deployment

Es wird **eine VM pro Team** deployed. Bei zwei Teams entstehen zwei VMs. Jeder Nutzer
eines Teams erhält einen eigenen Port ab 8080 (aufsteigend pro Nutzer). Flavor: `gp1.small`.

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
| `assignment_files` | Java-Aufgabendatei pro User (`.java`) — landet unter `~/Coding-Aufgabe/` | Ja |
| `team_flavor_ids` | Flavor-ID pro Team — Picker-Auswahl | Nein |
| `network_uuid` | UUID des internen Netzwerks | Ja (Default vorhanden) |
| `floating_ip_pool` | Name des External Networks für öffentliche IP | Ja (Default vorhanden) |
| `shared_secgroup_id` | ID der Security Group | Ja (Default vorhanden) |

### Aufgabendateien (`assignment_files`)

Über den Wizard muss pro Nutzer eine individuelle `.java`-Datei hochgeladen werden.
Diese wird beim VM-Start automatisch unter `~/Coding-Aufgabe/<dateiname>.java`
abgelegt und ist direkt in code-server sichtbar.
