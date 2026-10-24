# Ubuntu Terminal App

Eine einfache Linux-Lernumgebung für Hochschulkurse. Jeder Studierende
bekommt einen eigenen SSH-Zugang auf einer gemeinsamen Ubuntu 24.04 VM
und ein vorgefertigtes Lernverzeichnis mit Übungsaufgaben und Kurzreferenz
zu den wichtigsten Terminal-Befehlen.

## Vorinstallierte Software

- Python 3 (inkl. pip, venv)
- Node.js 24 (inkl. npm)
- Git, curl, tree, nano, vim, htop

## Lernverzeichnis

Jeder Nutzer findet nach dem Login unter `~/linux-kurs/` folgende Struktur vor:

    ~/linux-kurs/
    ├── LIES_MICH.txt              ← Kurzreferenz aller wichtigen Befehle
    ├── beispieldaten/
    │   ├── studenten.csv          ← CSV für Übungen mit cut, grep, sort
    │   └── server.log             ← Logdatei für Übungen mit grep, tail, wc
    └── uebungen/
        ├── 01-navigation/
        ├── 02-dateien/
        ├── 03-berechtigungen/
        ├── 04-prozesse/
        └── 05-textverarbeitung/

## User-Management

- **Ein Account pro Nutzer**, abgeleitet aus der E-Mail-Adresse
  (z.B. `alice.smith@dhbw.de` → Benutzername `alicesmith`)
- Alle Nutzer aller Teams landen auf **einer gemeinsamen VM**
- Jeder Nutzer erhält ein automatisch generiertes, zufälliges Passwort
- SSH-Login mit Passwort-Authentifizierung (kein Key nötig)

## VM-Deployment

| | |
|---|---|
| VMs gesamt | **1** (geteilt von allen Teams und Nutzern) |
| Größe | wählbar: `gp1.small`, `gp1.medium`, `gp1.large` |
| Festplatte | wählbar: 10–200 GB, Standard ist die Platte des Flavors |
| Erreichbar über | SSH, wählbar über IPv6 (Standard), IPv4 oder beides |
| Floating IP | Nein |

## Konfigurierbare Variablen

| Variable | Beschreibung | Pflicht |
|---|---|---|
| `flavor` | Größe der VM | Nein (Standard `gp1.small`) |
| `disk_size_gb` | Festplatte in GB, `0` = Platte des Flavors | Nein |
| `ip_mode` | Adressfamilie: `ipv4`, `ipv6` oder `dual` | Nein (Standard `ipv6`) |
| `network_uuid` / `network_v4_uuid` | Netz für IPv6 bzw. IPv4 | Nein (Standard vorhanden) |
| `shared_secgroup_id` | ID der gemeinsamen Security Group | Nein (Standard vorhanden) |

## Deployment-Dauer

Ein Deployment läuft in zwei Phasen:

1. `tofu apply` legt VM und Netzanschluss an.
2. Beim ersten Start richtet cloud-init die VM ein (Phase `VM_SETUP`). Der Store
   meldet das Deployment erst als fertig, wenn diese Einrichtung abgeschlossen
   ist.

Es gibt kein vorgebautes Image mehr: Die Software wird bei jedem Deployment
installiert. Die Dauer hängt deshalb von der Einrichtung ab und ist länger als
bei früheren Ständen. Messwerte folgen nach der Abnahme auf Staging.
