# JupyterHub – gemeinsame Notebook-Umgebung

Eine JupyterHub-Instanz auf einer gemeinsamen VM. Jede Person meldet sich mit
eigenen Zugangsdaten an und bekommt eine eigene JupyterLab-Sitzung mit eigenem
Home-Verzeichnis.

## Vorinstallierte Software

- JupyterHub und JupyterLab mit Python-Kernel
- Python 3 (inkl. pip, venv), Git

Weitere Pakete installiert jede Person selbst, etwa mit
`pip install --user pandas` im Terminal von JupyterLab.

## User-Management

- **Ein Linux-Konto pro Person**, abgeleitet aus der E-Mail-Adresse
  (z.B. `anna.alt@dhbw.de` → `annaalt`)
- JupyterHub meldet über dieses Konto an; das Passwort gilt auch für `sudo`
  und SSH
- Alle Teams landen auf **einer gemeinsamen VM**, jedes Team als eigene
  Linux-Gruppe

## VM-Deployment

| | |
|---|---|
| VMs gesamt | **1** (geteilt von allen Teams und Personen) |
| Größe | wählbar: `gp1.small`, `gp1.medium`, `gp1.large` |
| Erreichbar über | HTTP auf Port 8000, über IPv6 (Standard), IPv4 oder beides |
| Floating IP | Nein |

Über IPv4 ist JupyterHub nur aus dem Campusnetz und dem VPN erreichbar.

## Konfigurierbare Variablen

| Variable | Beschreibung | Pflicht |
|---|---|---|
| `flavor` | Größe der VM | Nein (Standard `gp1.small`) |
| `disk_size_gb` | Festplatte in GB, `0` = Platte des Flavors | Nein |
| `ip_mode` | Adressfamilie: `ipv4`, `ipv6` oder `dual` | Nein (Standard `ipv6`) |
| `network_uuid` / `network_v4_uuid` | Netz für IPv6 bzw. IPv4 | Nein (Standard vorhanden) |
| `shared_secgroup_id` | ID der gemeinsamen Security Group | Nein (Standard vorhanden) |
| `web_source_v4` / `web_source_v6` | Wer JupyterHub erreichen darf | Nein (Campus bzw. alle) |

Kein File-Upload.

## Deployment-Dauer

Ein Deployment läuft in zwei Phasen:

1. `tofu apply` legt VM und Netzanschluss an.
2. Beim ersten Start richtet cloud-init die VM ein (Phase `VM_SETUP`). Der Store
   meldet das Deployment erst als fertig, wenn diese Einrichtung abgeschlossen
   ist.

Es gibt kein vorgebautes Image mehr: JupyterHub wird bei jedem Deployment
installiert. Die Dauer hängt deshalb von der Einrichtung ab. Messwerte folgen
nach der Abnahme auf Staging.
