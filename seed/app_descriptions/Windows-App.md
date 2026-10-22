# Windows 11 Desktop

Eine Windows-Lernumgebung für Hochschulkurse. Jeder Studierende bekommt eine eigene
Windows-11-VM mit Remote-Desktop-Zugang und ein vorgefertigtes Kursverzeichnis mit
Übungsaufgaben und einer PowerShell-Kurzreferenz.

## Vorinstallierte Software

- Python 3 (inkl. pip), Node.js (aktuelle LTS), Git
- Visual Studio Code, Notepad++, 7-Zip, Chrome
- Chocolatey als Paketmanager

## Kursverzeichnis

Nach der ersten Anmeldung liegt auf dem Desktop ein Ordner `Windows-Kurs` mit einer
PowerShell-Kurzreferenz (mit Linux-Vergleich), Beispieldaten und fünf Übungen.

## User-Management

- **Ein Account und eine eigene VM pro Nutzer**, abgeleitet aus der E-Mail-Adresse
- Benutzernamen werden auf 20 Zeichen gekürzt
- Jeder Nutzer erhält ein automatisch generiertes, zufälliges Passwort
- Mitglied in *Remotedesktopbenutzer* und *Administratoren*
- Anmeldung per RDP auf Port 3389 mit Benutzername `.\<name>` und Passwort

## VM-Deployment

Es wird **eine VM pro Nutzer** deployed, weil Windows 11 nur eine interaktive Sitzung
gleichzeitig erlaubt. Flavor `win11.medium` (2 vCPU, 8 GB RAM, 80 GB). Die Obergrenze
liegt bei 12 gleichzeitigen VMs (`max_users`). Die Adresse ist die IPv6-Adresse der VM,
in eckigen Klammern. Studierende brauchen das DHBW-VPN.

## Deployment-Dauer

Ein Deployment läuft in zwei Phasen:

1. `tofu apply` legt die VMs an.
2. Beim ersten Start richtet cloudbase-init die VM ein (Phase `VM_SETUP`): Software,
   Kursverzeichnis, Konto, IPv6 und Remotedesktop. Der Store meldet das Deployment
   erst als fertig, wenn diese Einrichtung abgeschlossen ist.

Das Basis-Image ist 80 GB groß. Die Dauer hängt von der Einrichtung ab und ist
deutlich länger als bei Linux-VMs. Messwerte folgen nach der Abnahme auf Staging.

## Konfigurierbare Variablen

| Variable | Beschreibung |
|---|---|
| `network_uuid` | Hauptnetzwerk |
| `floating_ip_pool` | Name des External Networks für Floating IPs |
| `shared_secgroup_id` | ID der gemeinsamen Security Group |
| `max_users` | Obergrenze gleichzeitiger Nutzer-VMs (Standard 12) |
