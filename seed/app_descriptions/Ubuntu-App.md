# Ubuntu Terminal App

Eine einfache Linux-Lernumgebung für Hochschulkurse. Jeder Studierende
bekommt einen eigenen SSH-Zugang auf einer gemeinsamen Ubuntu 26.04 VM
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
| VMs pro Team | — |
| VMs pro Nutzer | — |
| Flavor | `gp1.small` |
| Floating IP | Ja (öffentlich erreichbar) |

## Konfigurierbare Variablen

| Variable | Beschreibung | Pflicht |
|---|---|---|
| `network_uuid` | UUID des internen Netzwerks | Ja |
| `floating_ip_pool` | Name des External Networks für Floating IPs | Ja |
| `shared_secgroup_id` | ID der gemeinsamen Security Group | Ja |

## Deployment-Dauer

Ein Deployment läuft in zwei Phasen:

1. `tofu apply` legt VM, Netzanschluss und Floating IP an.
2. Beim ersten Start richtet cloud-init die VM ein (Phase `VM_SETUP`). Der Store
   meldet das Deployment erst als fertig, wenn diese Einrichtung abgeschlossen
   ist.

Es gibt kein vorgebautes Image mehr: Die Software wird bei jedem Deployment
installiert. Die Dauer hängt deshalb von der Einrichtung ab und ist länger als
bei früheren Ständen. Messwerte folgen nach der Abnahme auf Staging.
