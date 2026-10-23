# Gruppen-Netzwerk

Mehrere Ubuntu-VMs je Gruppe für Ping- und SSH-Übungen. Jede Gruppe erhält ein eigenes
L2-Netz ohne Router zu anderen Gruppen, in dem ihre VMs sich gegenseitig erreichen.

## Netzwerk

Standardmäßig entstehen zwei VMs je Gruppe (`vms_per_group`: 2 bis 8) mit festen
Übungsadressen, z. B. `10.77.0.11` und `10.77.0.12` bzw. `fd77:77::b` und `fd77:77::c`.
Ping und SSH sind nur innerhalb der Gruppe freigegeben. Getrennte Gruppen nutzen
dieselben Adressen in getrennten Netzen.

`ip_mode` wählt die Adressfamilie für den Zugang:

| Modus | Zugang |
|---|---|
| `ipv4` | geroutete IPv4 |
| `ipv6` | IPv6 (Standard), niemals die private NAT-IPv4 |
| `dual` | IPv6 primär, zusätzlich ein separates IPv4-Netz |

## User-Management

- **Ein persönliches Konto pro Nutzer** auf allen VMs seiner Gruppe, ohne sudo
- Der Kontoname wird stabil aus der E-Mail-Adresse gebildet
- Jeder Nutzer erhält ein automatisch generiertes, zufälliges Passwort
- Kollisionen von Kontonamen innerhalb einer Gruppe werden abgelehnt

## Deployment-Dauer

Ein Deployment läuft in zwei Phasen:

1. `tofu apply` legt Netze, Security Groups und VMs an.
2. Beim ersten Start richtet cloud-init die VMs ein (Phase `VM_SETUP`): Pakete, Konten
   und die zusätzlichen Netzwerkkarten. Der Store meldet das Deployment erst als fertig,
   wenn diese Einrichtung abgeschlossen ist.

Die Dauer hängt von der Einrichtung ab. Messwerte folgen nach der Abnahme auf Staging.

## Konfigurierbare Variablen

| Variable | Beschreibung |
|---|---|
| `ip_mode` | Adressfamilie: `ipv4`, `ipv6` oder `dual` |
| `network_v4_uuid`, `network_v6_uuid` | ausgewählte Zugangsnetze |
| `shared_secgroup_id` | vorhandene Zugangs-Security-Group |
| `flavor` | VM-Größe (`gp1.small`, `gp1.medium`, `gp1.large`) |
| `disk_size_gb` | `0` = Flavor-Standard; 10 bis 200 = Bootvolume je VM |
| `vms_per_group` | Anzahl VMs je Gruppe, 2 bis 8 |
