# Deploymentprozess des App-Stores

## Die Kette

```
Entwickler → GitHub Actions → GHCR → Self-hosted Runner → Terraform → Ansible → Docker Compose → Staging
```

| Schritt | Was passiert | Wo |
|---|---|---|
| **Entwickler** | Codeänderung, Pull Request | lokal |
| **GitHub Actions** | Lint, Tests, Security Scans, Image-Build | gehosteter Runner |
| **GHCR** | Image liegt als `ghcr.io/six7-app-store/<dienst>:latest` | GitHub |
| **Self-hosted Runner** | nimmt den Deploy an | eigene VM im Campusnetz |
| **Terraform** | reißt die alte VM ab, baut eine neue | OpenStack |
| **Ansible** | Docker, `.env`, Images ziehen, starten | auf der neuen VM |
| **Docker Compose** | neun Container: Frontend, Backend, Worker, Keycloak, Postgres, RabbitMQ, Redis, Caddy | auf der neuen VM |
| **Staging** | erreichbar unter `appstore.…users.dhbw.site` | öffentlich über IPv6 |

**Warum ein eigener Runner:** Die OpenStack-API der DHBW ist von außerhalb des Campusnetzes nicht erreichbar. Ein gehosteter GitHub-Runner läuft dort in einen Timeout — unabhängig von Zugangsdaten. Begründung in ADR-0002.

**Warum abreißen statt aktualisieren:** Der Zustand von Staging soll aus dem Repository ableitbar sein, nicht aus dem Gedächtnis derer, die ihn angefasst haben. Begründung und Preis in ADR-0003.

## Automatisiert und manuell

| Automatisiert | Manuell |
|---|---|
| CI, Build, Security Scans | Codeänderung |
| Terraform (destroy + apply) | Review und Merge |
| Ansible, Compose, Migrationen | Production Rollout |
| TLS-Zertifikat, DNS-Eintrag | |

Ein Merge nach `main` genügt. Alles danach läuft ohne Eingriff.

## Zwei Ebenen, die man auseinanderhalten muss

Der App-Store ist **selbst eine Anwendung**, die auf Staging läuft — und er **rollt seinerseits Apps aus** für Studierende. Das sind zwei getrennte Terraform-Läufe:

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
Packer  →  Golden Image in Glance  →  Terraform  →  je Nutzer eine VM  →  cloudbase-init
```

**Packer** baut einmalig ein Abbild aus `Windows 11 25H2 (UEFI)`: Chocolatey, Python, Node.js, Git, VS Code, plus ein Kursverzeichnis mit PowerShell-Übungen. Verbindung über **WinRM**, nicht SSH — Windows bringt keinen SSH-Server mit. Dauer 25 bis 40 Minuten, danach wird das Abbild wiederverwendet.

**Terraform** legt daraus **eine VM pro Studierendem** an. Kein geteilter Rechner wie bei Ubuntu: Windows 11 ist ein Client-Betriebssystem und erlaubt nur eine Sitzung gleichzeitig — auf einer geteilten VM würden sich die Teilnehmenden gegenseitig rauswerfen. Das kostet 2 vCPU und 8 GB RAM je Kopf, deshalb eine Obergrenze von zwölf.

**cloudbase-init** richtet jede VM beim ersten Start ein — das Windows-Gegenstück zu cloud-init:

1. Lokales Konto mit zufälligem Passwort anlegen
2. In die Gruppen *Remotedesktopbenutzer* und *Administratoren* aufnehmen
3. **IPv6-Adresse aus den Metadaten setzen** — Windows holt sie sich im DHBW-Netz nicht selbst, ohne diesen Schritt wäre die VM unerreichbar
4. Remotedesktop einschalten, Firewallregel setzen
5. Das Build-Konto von Packer entfernen

**Zugang:** RDP auf Port 3389, aus dem Campusnetz oder über VPN. Benutzername mit führendem `.\`, sonst sucht der Client das Konto bei Microsoft.

### Warum kein Sysprep

Der Lehrbuchweg wäre `sysprep /generalize`, damit jede VM eine eigene Maschinen-SID bekommt. Auf einem Windows-11-Client mit frisch installierter Software bricht Sysprep aber regelmäßig ab und macht das Abbild dabei unbrauchbar, ohne dass der Build es merkt. Die gemeinsame SID ist hier vertretbar: jede VM gehört einem Studierenden, keine tritt einer Domäne bei.

## Bekannte Schwächen

- **Staging ist während eines Merges nicht erreichbar** (10 bis 15 Minuten). Das ist der Preis von ADR-0003.
- **Das TLS-Zertifikat wird bei jedem Neuaufbau neu ausgestellt**, weil Caddys Datenverzeichnis mit der VM verschwindet. Am 19.09.2026 hing die CA dabei sieben Minuten.
- **Die Anwendungsdatenbank überlebt einen Merge nicht.** Deployments, Benutzer und Kurse werden neu geseedet. Nur die Terraform-States liegen außerhalb.
