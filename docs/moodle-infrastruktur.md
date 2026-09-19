# Moodle als feste Infrastruktur

Der App Store bindet sich über LTI 1.3 an Moodle an. Diese Seite beschreibt die
Moodle-Instanz, die dafür betrieben wird — nicht die lokale Testumgebung, die
steht in [moodle-lti-dev.md](moodle-lti-dev.md).

## Warum nicht `moodle-docker`

`moodle-docker` ist die Entwicklungsumgebung von moodlehq. Sie bindet einen
Moodle-Quellcodebaum von der Platte ein (`MOODLE_DOCKER_WWWROOT`) und bringt
Selenium, Mailpit und `exttests` mit — sinnvoll, um Moodle selbst zu testen,
untauglich als Server.

Hier läuft stattdessen `bitnami/moodle`: fertig installiert, konfiguriert sich
beim ersten Start aus Umgebungsvariablen.

## Warum feste Infrastruktur und keine App

Moodles Adresse steht als `LTI_PLATFORM_ISSUER` in der Konfiguration des App
Stores und ist der Schlüssel, unter dem **jeder** LTI-Launch nachgeschlagen
wird. Ändert sie sich, bricht die Anbindung für alle Kurse gleichzeitig.

Eine App im App Store wird je Kurs ausgerollt und wieder verworfen — das passt
dazu nicht. Deshalb eine eigene VM, die **nicht** bei jedem Merge abgerissen
wird, anders als Staging (ADR-0003).

## Aufbau

```
moodle.<zone>.users.dhbw.site
        │
     Caddy ──── TLS über dns-01, wie beim App Store
        │
     Moodle (bitnami/moodle:4.5, Port 8080)
        │
     Postgres 16
```

| | |
|---|---|
| VM | `moodle`, Flavor `k8s.node` (4 vCPU, 8 GB, 50 GB) |
| Netz | `DHBWV6`, erreichbar über IPv6 |
| Terraform | `infrastructure/terraform/envs/moodle/` |
| State | `/var/lib/tf-state/moodle/` auf der Runner-VM |
| Playbook | `infrastructure/ansible/moodle.yml` |

**Die Security Group unterscheidet sich vom App Store:** 80 und 443 stehen
offen, nicht nur dem Campusnetz. Das ist nötig, weil Moodle von außen erreichbar
sein muss — sowohl für Lehrende als auch für den App Store, der bei jedem Launch
Moodles JWKS und Token abruft. SSH bleibt auf dem Campus beschränkt.

## Die Anbindung herstellen

Die Reihenfolge ist zwingend: Moodle muss stehen, bevor es die Werte ausstellen
kann, die der App Store braucht.

**1. Moodle ausrollen**

```bash
cd infrastructure/terraform/envs/moodle
terraform init && terraform apply
```

**2. AAAA-Eintrag setzen** auf die Adresse aus `terraform output vm_ip`. Ohne
DNS-Namen kein Zertifikat, und ohne HTTPS kein LTI.

**3. Playbook laufen lassen.** Der erste Start dauert einige Minuten — Bitnami
installiert Moodle und legt die Datenbank an.

**4. Werkzeug registrieren:**

```bash
docker exec moodle php /opt/bitnami/moodle/local_register_lti_tool.php \
    --appstore=https://appstore.<zone>.users.dhbw.site
```

Das Skript legt den App Store als externes LTI-1.3-Werkzeug an und gibt die
sieben Zeilen aus, die in dessen `.env` gehören. Es ist idempotent: ein bereits
registriertes Werkzeug mit derselben Basis-URL wird nur ausgelesen.

**5. Die Ausgabe in `STAGING_ENV_FILE` übernehmen** und den App Store neu
ausrollen.

## Warum ein Skript statt der Oberfläche

Die Registrierung von Hand sind acht Formularfelder, und die fünf Werte danach
abzuschreiben ist genau die Art Handarbeit, bei der ein Zeichendreher
passiert — der dann als `invalid client_id` auftaucht, zwei Ebenen entfernt von
der Ursache.

## Stand

**Geschrieben, nicht erprobt.** Terraform, Compose und Playbook sind formal
geprüft (`fmt`, YAML), aber nie ausgeführt worden. Offen ist insbesondere:

- ob `bitnami/moodle:4.5` hinter Caddy ohne weitere Anpassung läuft
- ob `lti_add_type` in Moodle 4.5 die hier gesetzten Felder erwartet
- ob die Endpunkte des App Stores (`/lti/login`, `/lti/launch`, `/lti/jwks`)
  genau so heißen, wie das Skript sie einträgt — das gehört gegen
  `backend/app/routers/lti.py` geprüft

**Das `MOODLE_ENV_FILE`-Secret existiert noch nicht.** Es braucht
`MOODLE_DB_USER`, `MOODLE_DB_PASSWORD`, `MOODLE_DB_NAME`, `MOODLE_ADMIN_USER`,
`MOODLE_ADMIN_PASSWORD`, `MOODLE_ADMIN_EMAIL`, `MOODLE_HOSTNAME`, `ACME_EMAIL`
und die drei `DNS_TSIG_*`-Werte aus `staging.env`.

**Es gibt keinen Workflow dafür.** Moodle wird derzeit von Hand ausgerollt — was
zu einer Instanz passt, die bewusst stehen bleibt.
