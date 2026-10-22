# JupyterHub – Gemeinsame Notebook-Umgebung

Eine JupyterHub-Instanz auf einer gemeinsamen VM, die allen Teilnehmern eines Deployments individuelle JupyterLab-Sessions bereitstellt. Jeder Nutzer meldet sich mit persönlichen Zugangsdaten an und arbeitet in einer isolierten Notebook-Umgebung.

## User-Management

Jeder Nutzer erhält einen eigenen Linux-Account (abgeleitet aus der E-Mail-Adresse) und ein automatisch generiertes Passwort. JupyterHub nutzt PAM-Authentifizierung — der Login entspricht direkt dem Linux-Account. Alle Nutzer aller Teams teilen dieselbe VM, haben aber voneinander isolierte Home-Verzeichnisse und JupyterLab-Sessions. Zugangsdaten werden nach dem Deployment per Mail versendet.

## VM-Deployment

Es wird **eine gemeinsame VM** für alle Nutzer und alle Teams deployed — unabhängig von der Anzahl der Teams oder Nutzer. Die VM erhält eine öffentliche Floating IP und ist über Port `8000` erreichbar.

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

Kein File-Upload. Alle Defaults sind auf die DHBW-OpenStack-Infrastruktur vorkonfiguriert und müssen in der Regel nicht geändert werden.
