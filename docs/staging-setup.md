# Staging Setup

Staging läuft auf einer eigenen OpenStack-VM und wird nicht von Hand ausgerollt,
sondern über einen Workflow in eurem eigenen Forgejo. Ein Lauf macht beides:
Terraform bringt die Infrastruktur auf Stand, Ansible konfiguriert die VM und
startet den Stack.

Diese Anleitung beschreibt den eingerichteten Zustand. Wie die VM entsteht,
steht in `infrastructure/README.md`.

## Warum ein eigenes Forgejo

Das Projekt beschäftigt sich damit, Infrastruktur aus Vorlagen auszurollen. Es
wäre wenig überzeugend, ausgerechnet die Plattform selbst von Hand aufzusetzen —
deshalb entsteht auch sie aus Terraform und Ansible, mit denselben Werkzeugen und
demselben Review wie eine App-Vorlage.

Das verlangt einen Runner, der die VM erreicht und die Zugangsdaten zu OpenStack
hält. Auf GitHub wäre das ein self-hosted Runner an einem **öffentlichen**
Repository, und davon rät GitHub in aller Deutlichkeit ab:

> Self-hosted runners should almost never be used for public repositories on
> GitHub, because any user can open pull requests against the repository and
> compromise the environment.
>
> — GitHub, [Secure use reference](https://docs.github.com/en/actions/reference/security/secure-use),
> Abschnitt „Hardening for self-hosted runners"

Dieselbe Stelle mahnt zur Vorsicht auch bei privaten und internen Repositories:
wer sie forken und einen Pull Request öffnen kann, erreicht damit die Umgebung
des Runners samt seiner Secrets. Für ein offenes Projekt ist das keine
theoretische Sorge — jeder Fremde könnte einen Fork anlegen.

Beides zusammen führt zu der Aufteilung, die hier beschrieben ist. Der Code
bleibt öffentlich einsehbar; der Runner und die Deploy-Secrets liegen in einer
Forgejo-Instanz, deren Zugriff ihr selbst kontrolliert. Der Workflow auf GitHub
existiert weiter, lässt sich dort aber mangels Secrets und Runner nicht
auslösen.

## Voraussetzungen

**Zugang zum Forgejo**, in dem das `deployment`-Repository liegt. Der Deploy
wird dort ausgelöst, nicht auf GitHub — der Fork dort hat weder Secrets noch
einen Runner, ein Push dorthin bewirkt nichts.

**Der Runner läuft** und hat sein Job-Image. `runs-on: deploy` wählt den Runner,
`docker://forgejo-deploy-job:latest` das Image dahinter. Es bringt Terraform,
Ansible, Trivy und die Galaxy-Rollen mit; gebaut wird es von
`forgejo/02-configure.sh`.

**Die Secrets sind hinterlegt**, im Repository oder in der Organisation unter
**Settings → Actions → Secrets**:

| Secret | Wofür |
|---|---|
| `STAGING_OS_AUTH_URL` | OpenStack-Endpunkt |
| `STAGING_OS_APPLICATION_CREDENTIAL_ID` | OpenStack-Zugangsdaten |
| `STAGING_OS_APPLICATION_CREDENTIAL_SECRET` | dieselben |
| `STAGING_OS_REGION_NAME` | Region |
| `SSH_PRIVATE_KEY` | privater Schlüssel für den Ansible-Zugang zur VM |
| `STAGING_ENV_FILE` | vollständige `.env` des Stacks |
| `PG_CONN_STR` | Terraform-State-Backend |

**Du bist im Campusnetz oder im VPN.** Die Security-Group lässt SSH nur aus dem
Campusbereich zu.

## Schritt 1: Deploy auslösen

Im Forgejo unter **Actions → CD - Staging Deployment (Forgejo) → Run workflow**.
Es gibt drei Eingaben:

| Eingabe | Bedeutung |
|---|---|
| `mode` | `plan` hält vor jeder Änderung an, `apply` rollt aus. Standard ist `plan`. |
| `seed` | legt Seed-Nutzer, Kurse und Apps an. Nur bei leerer Datenbank nötig. |
| `forget_volume` | Notausgang, siehe unten. Bleibt `false`. |

Ein Lauf mit `plan` ist der übliche erste Schritt: er prüft Runner, Image,
Checkout, alle Secrets und eine echte Anmeldung an OpenStack, ändert aber nichts.
Erwartet wird `0 to add, 0 to change, 0 to destroy` und **keine** Zeile mit
`must be replaced`.

Stimmt der Plan, denselben Workflow mit `mode: apply` starten.

## Schritt 2: Was dabei passiert

1. **Terraform** gleicht die VM, ihre Security-Group und das zweite
   IPv4-Interface ab. Die Outputs `vm_ip`, `vm_ipv4`, `vm_ipv4_gateway` und
   `vm_ipv4_mac` gehen an Ansible weiter.
2. **Ansible** richtet das IPv4-Interface ein (Netplan und Connection Marks,
   siehe `infrastructure/README.md`), installiert Docker, kopiert den Stack und
   die `.env`, rendert den Keycloak-Realm, zieht die Images und startet alles.
3. Danach laufen die **Migrationen**, und bei `seed: true` das Seed-Skript.

Ein vollständiger Lauf dauert etwa fünf Minuten. Der Schritt
`Start the application with Docker Compose` ist der längste, weil Caddy mit dem
rfc2136-Modul aus dem Quelltext übersetzt wird.

## Schritt 3: DNS

Die VM ist über beide Adressfamilien erreichbar. Unter demselben Hostnamen
gehören deshalb zwei Einträge, mit TTL 300:

```
A       <APP_HOSTNAME>    <vm_ipv4>
AAAA    <APP_HOSTNAME>    <vm_ip>
```

Beide Adressen liefert Terraform:

```bash
cd infrastructure/terraform/envs/staging
terraform output -raw vm_ipv4
terraform output -raw vm_ip
```

Das Zertifikat braucht dabei keine Aufmerksamkeit: Caddy weist die Kontrolle
über dns-01 nach, und das hängt nicht daran, wie der Host erreichbar ist.

## Verifikation

```bash
curl -4 -sS -o /dev/null -w '%{http_code}\n' https://<APP_HOSTNAME>/
curl -6 -sS -o /dev/null -w '%{http_code}\n' https://<APP_HOSTNAME>/
```

Beide sollten `200` liefern. Eine Anfrage an die nackte IP schlägt über HTTPS
fehl — Caddy wählt den Site-Block über den Namen im SNI, den eine IP nicht
mitbringt. Über HTTP antwortet sie mit `308`, was als Erreichbarkeitsnachweis
genügt.

Der Workflow gibt am Ende `docker compose ps` aus; alle Dienste mit Healthcheck
sollten dort `healthy` sein.

## Login

Die Seed-Nutzer heißen `<vorname>.<nachname>@dhbw.de` mit Passwort `1234`
(Umlaute transliteriert, `ä` wird zu `ae`).

Meldet das Backend ein 401 gegen Keycloak, ist es das Client-Secret: der
Realm-Export trägt es maskiert (`"secret": "**********"`), ein frisch
importierter Realm hat also nicht den Wert aus `STAGING_ENV_FILE`. In der
Admin-Konsole für den Client `appstore-backend` neu erzeugen, in das Secret
eintragen, Deploy wiederholen. Dasselbe beschreibt `dev-setup.md` Schritt 5 für
die Entwicklungsumgebung.

## Wenn es klemmt

| Symptom | Ursache |
|---|---|
| `no space left on device` beim Caddy-Build | Die Root-Disk ist voll. Meist steckt der Platz in `/var/lib/containerd`, nicht in `/var/lib/docker` — containerd hält den Image-Store. |
| Seed scheitert mit `Connection refused` auf `keycloak:8080` | Keycloak importiert bei leerer Datenbank erst den Realm und bindet den Listener zuletzt. Das Playbook wartet darauf; tritt es trotzdem auf, war die Wartezeit zu kurz. |
| Terraform hängt zehn Minuten an einem Volume | Cinder hat es in `creating` stehen lassen. Ein solches Volume lässt sich nicht löschen, dafür braucht es den Betreiber. `forget_volume: true` nimmt es aus dem State, damit Deploys wieder durchlaufen — einmalig, danach zurück auf `false`. |
| `Artifact service responded with 500` | Der Trivy-Bericht wird nicht abgelegt. Bekannt, blockiert nichts. |
| Jeder veröffentlichte Port läuft in einen Timeout, SSH funktioniert | Die Connection Marks fehlen. Siehe `infrastructure/README.md`, Abschnitt „Addressing". |

## Was Staging nicht ist

Kein Produktivsystem. Die Datenbank enthält Seed-Daten, die Nutzer haben ein
bekanntes Passwort, und `/var/lib/docker` liegt auf der Root-Disk der Instanz —
eine Neuerstellung der VM nimmt beide Datenbanken mit. 
