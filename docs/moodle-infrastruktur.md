# Moodle als feste Infrastruktur

Der App Store bindet sich über LTI 1.3 an Moodle an. Diese Seite beschreibt die
Moodle-Instanz, die dafür betrieben wird — nicht die lokale Testumgebung, die
steht in [moodle-lti-dev.md](moodle-lti-dev.md).

## Das Image

Hier läuft `erseco/alpine-moodle:v5.2.2` — dasselbe Image wie die lokale
Testinstanz. Es ist fertig installiert und konfiguriert sich beim ersten Start
aus Umgebungsvariablen.

Zwei Bewerber schieden aus. `moodle-docker` von moodlehq ist eine
Entwicklungsumgebung: sie bindet einen Quellcodebaum von der Platte ein
(`MOODLE_DOCKER_WWWROOT`) und bringt Selenium, Mailpit und `exttests` mit —
sinnvoll, um Moodle selbst zu testen, untauglich als Server. `bitnami/moodle`
stand zuerst hier, existiert auf Docker Hub aber nicht mehr; der Pull scheitert
mit `not found`, nur ein eingefrorenes `bitnamilegacy` ist geblieben.

Dass es jetzt dasselbe Image wie lokal ist, hat einen Nebennutzen: Die
LTI-Anbindung wurde gegen genau diesen Moodle-Stand entwickelt.

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
     Moodle (erseco/alpine-moodle:v5.2.2, Port 8080)
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
| Compose | `docker-compose.moodle-infra.yml` |

Der Name trennt diesen Stack von `docker-compose.moodle.yml` — das ist das
lokale Entwicklungs-Moodle aus [moodle-lti-dev.md](moodle-lti-dev.md) und hat
mit dem Server nichts zu tun.

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
docker exec moodle php /var/www/html/local_register_lti_tool.php \
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

- ob `erseco/alpine-moodle:v5.2.2` hinter Caddy ohne weitere Anpassung läuft
- ob `lti_add_type` in Moodle 4.5 die hier gesetzten Felder erwartet
Die Endpunkte des App Stores sind dagegen geprüft: `/lti/login` (OIDC-Start,
`api_route` für GET und POST), `/lti/launch` und `/lti/jwks` existieren genau
so, wie das Skript sie einträgt.

**Das `MOODLE_ENV_FILE`-Secret existiert noch nicht.** Es braucht
`MOODLE_DB_USER`, `MOODLE_DB_PASSWORD`, `MOODLE_DB_NAME`, `MOODLE_ADMIN_USER`,
`MOODLE_ADMIN_PASSWORD`, `MOODLE_ADMIN_EMAIL`, `MOODLE_HOSTNAME`, `ACME_EMAIL`
und die drei `DNS_TSIG_*`-Werte aus `staging.env`.

**Es gibt keinen Workflow dafür.** Moodle wird derzeit von Hand ausgerollt — was
zu einer Instanz passt, die bewusst stehen bleibt.
