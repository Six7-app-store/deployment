# 0002 — Der Staging-Deploy läuft auf einem self-hosted GitHub-Runner auf eigener VM

**Status:** Angenommen
**Datum:** 18.09.2026
**Beteiligt:** Projektteam

## Kontext

Der Staging-Deploy braucht drei Dinge: die OpenStack-API der DHBW (Terraform),
SSH zur erzeugten VM (Ansible) und GHCR (Images). Gemessen von einem gehosteten
GitHub-Runner aus (öffentliche IP 145.132.101.182):

| Ziel | Ergebnis |
|---|---|
| `newstack.dhbw.cloud` DNS | löst öffentlich auf → 141.72.5.140 |
| Keystone `:5000/v3` | `000 TIMEOUT` |
| Horizon `:443` | `000 TIMEOUT` |
| GHCR | erreichbar |

Der Name ist öffentlich, das Netz ist es nicht. Zugangsdaten ändern daran
nichts.

Zum Zeitpunkt der Entscheidung existiert die VM `github-runner` im Tenant,
erreichbar unter `2001:7c0:1b20:c913:1::3f0`, Ubuntu 24.04, 1 vCPU, 2 GB RAM,
8,7 GB Platte. Von dort aus gemessen: Keystone `200`, `api.github.com` `200`.

`ssh_source_cidr_ipv6` in `envs/staging/variables.tf` steht auf
`2001:7c0:1b20::/48`. Die Adresse der Runner-VM liegt in diesem Bereich, die
Security Group lässt sie also an Port 22 der Staging-VM.

Alle fünf Repositories der Organisation sind **öffentlich**. Ein self-hosted
Runner, der an einem Workflow mit `pull_request`-Trigger hängt, führt Code aus
jedem Fork-PR aus — auf einer Maschine mit Zugriff auf die OpenStack-Anmeldedaten.
Aus genau diesem Grund stand in `backend/.github/workflows/ci.yml` bis hierher
der Kommentar, ein self-hosted Runner komme nicht in Frage.

Vorher lief der Deploy in einer eigenen Forgejo-Instanz im Campusnetz. Deren
Betrieb ist ein zweiter Dienst mit eigener VM, eigenem Caddy, eigenem
Pull-Mirror und eigener Benutzerverwaltung, und Forgejo feuert Actions bei einem
Mirror-Sync nicht zuverlässig — der Deploy war dort faktisch immer ein
`workflow_dispatch` von Hand.

## Entscheidung

Wir betreiben einen self-hosted GitHub-Runner auf einer eigenen VM im
Campusnetz, registriert **ausschließlich am Repository `deployment`**, mit den
Labels `self-hosted` und `deploy`. Kein Workflow, der auf diesem Runner läuft,
hat einen `pull_request`-Trigger.

## Konsequenzen

**Leichter:**

- Ein Merge rollt wieder selbst aus. Der Deploy braucht keinen Menschen im VPN
  mehr.
- Ein Dienst weniger im Betrieb: Forgejo, sein Caddy, sein Pull-Mirror und seine
  Benutzerverwaltung fallen als Abhängigkeit des Deploys weg.
- Alles steht in GitHub — Logs, Secrets, Security-Tab, SARIF-Berichte. Vorher
  war der Deploy an dem Ort, an dem sonst niemand nachsieht.
- Die Runner-VM ist eine zweite, dauerhafte Maschine im selben Netz. Damit gibt
  es einen Ort für Zustand, der einen Neuaufbau der Staging-VM überlebt — siehe
  ADR-0003.

**Schwerer:**

- Die Sicherheit hängt jetzt an einer Trigger-Konfiguration statt an einer
  Netzgrenze. Wer dem Deploy-Workflow einen `pull_request`-Trigger hinzufügt
  oder den Runner auf Organisationsebene registriert, öffnet Fremden eine
  Ausführungsumgebung mit OpenStack-Zugang. Das ist eine Zeile in einer
  YAML-Datei und im Review leicht zu übersehen.
- Der Runner ist ein Single Point of Failure ohne Redundanz. Ist die VM aus,
  gibt es keinen Deploy — und keinen gehosteten Runner, der einspringen könnte.
- Die Maschine ist dauerhaft, ihre Arbeitsumgebung damit auch. Ein Lauf, der
  Dateien liegen lässt, beeinflusst den nächsten. Der Workflow räumt Schlüssel
  und Inventar deshalb in einem `if: always()`-Schritt weg.
- Terraform, Ansible und Trivy sind von Hand auf der VM installiert und werden
  von Hand aktualisiert. Es gibt kein Job-Image, das ihre Versionen festhält.
- 1 vCPU und 2 GB RAM tragen Terraform und Ansible, aber keine Test- oder
  Build-Jobs. Die CI der drei Anwendungsrepositories bleibt deshalb auf
  `ubuntu-latest`.

## Verworfene Alternativen

**Weiter über Forgejo deployen.** Die Instanz lief und hatte den Netzzugang.
Sie kostet aber eine zweite VM samt Caddy, Pull-Mirror und Benutzerverwaltung,
und der Mirror-Sync löst in Forgejo keine Actions zuverlässig aus — der
Automatismus, um den es hier geht, war dort gar nicht zu haben. Der Deploy
wurde in der Praxis immer von Hand gestartet.

**Gehosteter GitHub-Runner mit einem Tunnel ins Campusnetz.** Hätte die
Netzgrenze erhalten. Erfordert aber einen dauerhaft erreichbaren Einstiegspunkt
ins Campusnetz, den jemand betreiben und absichern muss — also denselben
Aufwand wie eine Runner-VM, zuzüglich einer neuen Angriffsfläche von außen.
Die Freigabe dafür ist nicht in Sicht.

**Runner auf Organisationsebene registrieren.** Wäre bequemer: ein Runner für
alle fünf Repositories, kein zweiter Registrierungsvorgang. Genau das macht ihn
aber aus jedem der fünf öffentlichen Repositories ansprechbar, und ein einziger
unbedachter `pull_request`-Trigger in irgendeinem davon genügt. Der Runner hängt
deshalb nur am `deployment`-Repository, das als einziges keinen fremden Code baut.

**Die VM zieht selbst, GitHub schiebt nicht** (der bestehende systemd-Timer, der
alle 5 Minuten neue Images aus GHCR holt). Braucht keinen Runner und keine
Zugangsdaten bei GitHub und bleibt als Sicherheitsnetz aktiv. Er kann aber nur
Container austauschen — Terraform und Ansible laufen dabei nie. Eine Änderung an
der Infrastruktur oder am Playbook erreicht Staging so nicht, und genau das war
die Anforderung.
