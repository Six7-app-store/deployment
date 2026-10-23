# VSCode im Browser

VS Code im Browser für Hochschulkurse. Jedes Team bekommt eine **eigene VM**, jedes
Teammitglied darauf einen **eigenen code-server** mit eigenem Passwort. Programmieren,
Terminal und Git laufen komplett im Browser — lokal muss nichts installiert werden.

## Zugang

Die E-Mail des App Stores enthält die Team-Adresse, den Benutzernamen und das
Passwort.

1. `https://[<IPv6-Adresse>]/` öffnen — eine Startseite listet alle Teammitglieder.
2. Den eigenen Namen anklicken und mit dem Passwort anmelden.

Das Zertifikat stellt Caddy aus einer eigenen CA der VM aus, weil es ohne Domain kein
Let's Encrypt gibt. Der Browser warnt deshalb beim ersten Aufruf. Firefox läuft nach
dem Wegklicken der Warnung uneingeschränkt. Chrome blockiert bei nicht
vertrauenswürdigem Zertifikat Service Worker, dann bleiben Markdown-Vorschau und
manche Erweiterungsansichten leer. Abhilfe: `ca.crt` von der Startseite als
vertrauenswürdige Stelle importieren.

## VM-Deployment

Es wird **eine VM pro Team** deployed (Basis-Image `Ubuntu 24.04`, Flavor
`gp1.medium`). Die Zahl gleichzeitiger Team-VMs ist über `max_teams` begrenzt
(Standard 15).

## Deployment-Dauer

Ein Deployment läuft in zwei Phasen:

1. `tofu apply` legt die VMs an.
2. Beim ersten Start richtet cloud-init die VM ein (Phase `VM_SETUP`): code-server,
   Caddy und die Konten der Teammitglieder. Der Store meldet das Deployment erst als
   fertig, wenn diese Einrichtung abgeschlossen ist.

Die Dauer hängt von der Einrichtung ab. Messwerte folgen nach der Abnahme auf Staging.

## Konfigurierbare Variablen

| Variable | Beschreibung |
|---|---|
| `image_name` | Basis-Image (Ubuntu 24.04 empfohlen) |
| `flavor_name` | VM-Größe der Team-VM |
| `network_uuid` | Hauptnetzwerk |
| `floating_ip_pool` | Name des External Networks für Floating IPs |
| `shared_secgroup_id` | ID der gemeinsamen Security Group |
| `web_source_cidr` | IPv6-Präfix, das auf Port 80/443 (IDE) zugreifen darf |
| `max_teams` | Obergrenze gleichzeitiger Team-VMs |
