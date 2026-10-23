# 0018 — Forgejo wird nicht weiterbetrieben

**Status:** Angenommen
**Datum:** 22.10.2026
**Beteiligt:** Projektteam

## Kontext

Bis zum 18.09.2026 lief der Staging-Deploy in einer eigenen Forgejo-Instanz im
Campusnetz. [ADR 0002](0002-self-hosted-runner-auf-eigener-vm.md) hat ihn auf
einen self-hosted GitHub-Runner verlegt. Die Forgejo-VM lief danach weiter, war
ein Pull-Mirror von GitHub und wurde von keiner Pipeline mehr gebraucht.

Im Repository blieben ihr Compose-Stack und die Setup-Skripte (`forgejo/`), die
Terraform-Umgebung `infrastructure/terraform/envs/forgejo`, das Ansible-Playbook
`forgejo.yml` samt Inventory-Skript und mehrere Dokumente, die den Forgejo-Weg
noch als den tatsächlichen beschrieben. Das Job-Image des Forgejo-Runners
diente nebenbei als Werkzeug-Image für `deploy.cmd`.

## Entscheidung

Wir betreiben Forgejo nicht weiter. Die VM wird abgerissen, Code und Doku
verschwinden aus dem Repository.

Das Werkzeug-Image von `deploy.cmd` bleibt erhalten und liegt als
`deploy-image/` im Repository-Wurzelverzeichnis, ohne Forgejo-Bezug.

## Konsequenzen

- Ein Dienst weniger im Betrieb: keine Forgejo-Instanz, kein eigener Caddy, kein
  Pull-Mirror, keine Datenbank-Sicherungen dafür.
- Die Terraform-Übergangsinsel (ADR 0010) schrumpft auf `envs/moodle`.
- Es gibt keinen zweiten Ort mehr, an dem eine Pipeline laufen könnte. Alles
  läuft in GitHub Actions auf dem Runner aus ADR 0002.
- Das Abreißen der VM ist ein Schritt auf echter Infrastruktur und gehört einer
  Person mit Zugang. Vorher ist zu prüfen, ob auf der Instanz etwas liegt, das
  es sonst nirgends gibt. Voraussichtlich nicht, sie war ein Spiegel. Ist der
  Terraform-State der Umgebung nicht mehr auffindbar, werden VM, Security
  Group, Keypair und Port in Horizon von Hand gelöscht, danach die DNS-Einträge.

## Verworfene Alternativen

**Forgejo als Spiegel oder Ausweichort behalten.** Verworfen, weil dafür eine
VM, ein Proxy und Zertifikate gepflegt werden müssten, ohne dass irgendein
Ablauf davon abhängt. ADR 0002 hat gezeigt, dass der Mirror-Sync Actions nicht
zuverlässig auslöst.
