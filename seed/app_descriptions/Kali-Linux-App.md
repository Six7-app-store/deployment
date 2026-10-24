# Kali Linux Desktop

Eine Kali-VM mit XFCE-Desktop und kuratierten Security-Werkzeugen für Kurse zu
IT-Sicherheit. Der Zugang läuft per Remote Desktop (XRDP), jeder Nutzer bekommt
einen eigenen Account und eine eigene Sitzung.

## Enthalten

- **XFCE-Desktop** per XRDP auf Port 3389, erreichbar über IPv6, IPv4 oder beides
- **Kali-Werkzeuge:** nmap, wireshark, tcpdump, burpsuite, metasploit, john, hydra,
  sqlmap, gobuster, nikto, aircrack-ng
- **Desktop-Integration:** Starter, Autostart und ein Kursverzeichnis `~/kali-kurs/`

## User-Management

- **Ein Account pro Nutzer**, abgeleitet aus der E-Mail-Adresse
- Alle Nutzer eines Deployments teilen sich **eine VM**, jeder mit eigener RDP-Sitzung
- Jeder Nutzer erhält ein automatisch generiertes, zufälliges Passwort

## VM-Deployment

Die VM startet vom Basis-Image **Debian 13**. Beim ersten Start stellt cloud-init
Debian vollständig auf **Kali (kali-rolling)** um und installiert Desktop,
Werkzeuge und Kursmaterial. Danach startet die VM einmal neu.

## Deployment-Dauer

Ein Deployment läuft in zwei Phasen:

1. `tofu apply` legt die VM an.
2. Beim ersten Start richtet cloud-init die VM ein (Phase `VM_SETUP`): Umstellung auf
   Kali, Desktop, Werkzeuge. Das lädt mehrere GB. Der Store meldet das Deployment erst
   als fertig, wenn diese Einrichtung abgeschlossen ist.

Die Dauer hängt von der Einrichtung ab und ist deutlich länger als bei einer
Ubuntu-VM. Messwerte folgen nach der Abnahme auf Staging.

## Hinweis

Ein weltweit offener RDP-Port auf einer Kali-VM ist ein lohnendes Ziel. Der erlaubte
Adressbereich lässt sich über `rdp_source_cidr` auf das DHBW-Campusnetz eingrenzen.

## Konfigurierbare Variablen

| Variable | Beschreibung |
|---|---|
| `source_image_name` | Debian-Basis-Image, das beim ersten Start zu Kali umgestellt wird |
| `flavor` | Flavor der Kali-VM (mindestens 20 GB Platte) |
| `ip_mode` | Adressfamilie: `ipv4`, `ipv6` (Standard) oder `dual` |
| `network_uuid` | Netz mit öffentlicher IPv6, für `ipv6` und `dual` |
| `network_v4_uuid` | Netz mit öffentlich gerouteter IPv4, für `ipv4` und `dual` |
| `shared_secgroup_id` | ID der gemeinsamen Security Group |
| `rdp_source_cidr` | IPv6-Präfix, das auf Port 3389 zugreifen darf |
| `rdp_source_cidr_v4` | IPv4-Präfix dafür, bei `ipv4` und `dual` (Standard Campusnetz) |
