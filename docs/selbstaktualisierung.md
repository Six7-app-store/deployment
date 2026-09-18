# Staging aktualisiert sich selbst

Nach einem Merge auf `main` liegt wenige Minuten später das neue Image auf der
Staging-VM — ohne dass jemand einen Deploy startet.

## Wie das läuft

```
  Merge auf main
        │
        ▼
  GitHub Actions: Lint, Tests, Scans, Build
        │
        ▼
  Image nach ghcr.io/six7-app-store/<dienst>:latest
        │
        │   ⟵ hier endet, was GitHub tun kann
        ▼
  Staging-VM, Timer alle 5 Minuten:
        neues Image da?  ── nein ──▶ nichts tun
                │ ja
                ▼
        pull · up -d --no-deps · Migrationen
```

## Warum die VM zieht, statt dass GitHub schiebt

Weil die andere Richtung nicht geht. Von einem GitHub-Runner aus ist erreichbar:

| Ziel | |
|---|---|
| OpenStack-API (für Terraform) | ❌ Firewall — der Name löst öffentlich auf, das Netz ist es nicht |
| SSH zur Staging-VM (für Ansible) | ❌ Security Group lässt Port 22 nur aus dem Campusnetz zu |
| GHCR | ✅ |

Und GHCR erreicht auch die VM. Das ist der einzige Punkt, an dem sich beide
Seiten treffen — also wird er benutzt. Es braucht dafür **keine** Öffnung in der
Firewall, **keinen** SSH-Zugang von außen und **keine** Zugangsdaten bei GitHub.

## Was der Timer kann und was nicht

**Er tauscht Container.** `backend`, `worker` und `frontend` werden auf das neue
Image gehoben; ist das Backend dabei, laufen anschließend die Migrationen.

**Er fasst keine Infrastruktur an.** Änderungen an Terraform, Ansible oder der
Compose-Datei erfasst er nicht — dafür bleibt der Deploy über
[`deploy.cmd`](../deploy.cmd) bzw. das [Runbook](deploy-runbook.md) zuständig.
Das ist Absicht: Ein Skript, das sich seine eigene Ausführungsgrundlage
nachlädt, lässt sich nicht mehr nachvollziehbar machen.

**Datenbank, Broker und Keycloak fasst er nicht an.** Die hängen an gepinnten
Upstream-Tags, und ein unbeaufsichtigter Neustart einer Datenbank ist nichts,
das man sich nebenbei einhandelt.

## Einrichten

Steckt im normalen Deploy. Einmal `deploy.cmd` ausführen (oder das Playbook von
Hand) — die Tasks am Ende von `staging.yml` legen Skript, Service und Timer an
und starten ihn.

**Eine Voraussetzung:** `IMAGE_NAMESPACE` in der `.env` der VM muss auf euren
eigenen Namespace zeigen (`six7-app-store`). Steht dort der Default
`dhbw-appstore`, zieht die VM die Images des Upstream-Projekts, und eure Merges
ändern auf Staging nichts.

## Nachsehen, ob er läuft

Auf der VM:

```bash
systemctl list-timers appstore-autoupdate.timer   # wann der nächste Lauf ist
journalctl -u appstore-autoupdate.service -n 50   # was die letzten Läufe taten
systemctl start appstore-autoupdate.service       # sofort einen Lauf auslösen
```

Im Log steht pro Lauf entweder `Keine neuen Images.` oder welcher Dienst
getauscht wurde.

## Abschalten

In `staging.yml` `auto_update: false` setzen und das Playbook laufen lassen.
Die Tasks halten den Timer an und räumen Units und Skript weg.

Das Intervall steuert `auto_update_interval` (Standard `5min`).
