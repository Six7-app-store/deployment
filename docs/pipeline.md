# Deploymentprozess des App-Stores

## Die Kette

```
Entwickler → GitHub Actions → GHCR → Self-hosted Runner → OpenTofu → Ansible → Docker Compose → Staging
```

| Schritt | Was passiert | Wo |
|---|---|---|
| **Entwickler** | Codeänderung, Pull Request | lokal |
| **GitHub Actions** | Lint, Tests, Security Scans, Image-Build | gehosteter Runner |
| **GHCR** | Image liegt als `ghcr.io/six7-app-store/<dienst>:latest` | GitHub |
| **Self-hosted Runner** | nimmt den Deploy an | eigene VM im Campusnetz |
| **OpenTofu** | reißt die alte VM ab, baut eine neue | OpenStack |
| **Ansible** | Docker, `.env`, Images ziehen, starten | auf der neuen VM |
| **Docker Compose** | neun Container: Frontend, Backend, Worker, Keycloak, Postgres, RabbitMQ, Redis, Caddy | auf der neuen VM |
| **Staging** | erreichbar unter `appstore.…users.dhbw.site` | öffentlich über IPv6 |

**Warum ein eigener Runner:** Die OpenStack-API der DHBW ist von außerhalb des Campusnetzes nicht erreichbar. Ein gehosteter GitHub-Runner läuft dort in einen Timeout — unabhängig von Zugangsdaten. Begründung in ADR-0002.

**Warum abreißen statt aktualisieren:** Der Zustand von Staging soll aus dem Repository ableitbar sein, nicht aus dem Gedächtnis derer, die ihn angefasst haben. Begründung und Preis in ADR-0003.

## Automatisiert und manuell

| Automatisiert | Manuell |
|---|---|
| CI, Build, Security Scans | Codeänderung |
| OpenTofu (destroy + apply) | Review und Merge |
| Ansible, Compose, Migrationen | Production Rollout |
| TLS-Zertifikat, DNS-Eintrag | |

Ein Merge nach `main` genügt. Alles danach läuft ohne Eingriff.

## Zwei Ebenen, die man auseinanderhalten muss

Der App-Store ist **selbst eine Anwendung**, die auf Staging läuft — und er **rollt seinerseits Apps aus** für Studierende. Das sind zwei getrennte OpenTofu-Läufe:

| | Plattform-Deploy | App-Deploy |
|---|---|---|
| Ausgelöst durch | Merge nach `main` | Klick im App-Store |
| Läuft auf | Self-hosted Runner | Worker-Container |
| Erzeugt | die Staging-VM | VMs für Studierende |
| State liegt | Datei auf der Runner-VM | Postgres auf der Runner-VM |

Beide States liegen **außerhalb** der Staging-VM. Sonst würde der Plattform-Deploy den State löschen, den er selbst braucht (ADR-0003 und ADR-0005).

## Die Windows-App

Eine von zwei Beispiel-Apps neben der Ubuntu-App. Sie zeigt, dass die Plattform nicht auf Linux beschränkt ist.

```
OpenTofu  →  je Nutzer eine VM aus dem Basis-Image  →  cloudbase-init
```

**Kein eigenes Abbild mehr** ([ADR 0010](adr/0010-opentofu-statt-terraform-und-packer.md)).
Die VM startet vom Basis-Image `Windows 11 25H2 (UEFI)`; was früher Packer
einmalig ins Abbild gebacken hat, installiert cloudbase-init jetzt beim
ersten Start. Das verlängert den ersten Start entsprechend. Das
Windows-App-Repository ist noch auf dem alten Stand (`packer/` +
`terraform/`) und muss auf `tofu/` umgebaut werden, bevor es wieder
deploybar ist.

**OpenTofu** legt **eine VM pro Studierendem** an. Kein geteilter Rechner wie bei Ubuntu: Windows 11 ist ein Client-Betriebssystem und erlaubt nur eine Sitzung gleichzeitig — auf einer geteilten VM würden sich die Teilnehmenden gegenseitig rauswerfen. Das kostet 2 vCPU und 8 GB RAM je Kopf, deshalb eine Obergrenze von zwölf.

**cloudbase-init** richtet jede VM beim ersten Start ein — das Windows-Gegenstück zu cloud-init:

1. Software installieren: Chocolatey, Python, Node.js, Git, VS Code, plus ein Kursverzeichnis mit PowerShell-Übungen
2. Lokales Konto mit zufälligem Passwort anlegen
3. In die Gruppen *Remotedesktopbenutzer* und *Administratoren* aufnehmen
4. **IPv6-Adresse aus den Metadaten setzen** — Windows holt sie sich im DHBW-Netz nicht selbst, ohne diesen Schritt wäre die VM unerreichbar
5. Remotedesktop einschalten, Firewallregel setzen

**Zugang:** RDP auf Port 3389, aus dem Campusnetz oder über VPN. Benutzername mit führendem `.\`, sonst sucht der Client das Konto bei Microsoft.

## Bekannte Schwächen

- **Staging ist während eines Merges nicht erreichbar** (10 bis 15 Minuten). Das ist der Preis von ADR-0003.
- **Das TLS-Zertifikat wird bei jedem Neuaufbau neu ausgestellt**, weil Caddys Datenverzeichnis mit der VM verschwindet. Am 19.09.2026 hing die CA dabei sieben Minuten.
- **Die Anwendungsdatenbank überlebt einen Merge nicht.** Deployments, Benutzer und Kurse werden neu geseedet. Nur die OpenTofu-States liegen außerhalb.
