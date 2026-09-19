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

**Ausgerollt und geprueft am 19.09.2026.** Die Instanz laeuft unter
`moodle.s241699-at-student-dhbw-mannheim-de.users.dhbw.site` auf der VM
`2001:7c0:1b20:c913:1::43a`, mit Zertifikat der DHBW-CA. Login, `/mod/lti/certs.php`
und die Registrierung sind von aussen erreichbar; das Registrierungsskript legt
beim ersten Lauf an und liest beim zweiten nur aus.

`STAGING_ENV_FILE` und `MOODLE_ENV_FILE` sind gesetzt. Wirksam wird die
Anbindung mit dem naechsten Deploy nach `main`.

### Was beim ersten Ausrollen nicht funktionierte

Fuenf Dinge, die die Datei vorher anders beschrieb, als die Wirklichkeit es
zuliess — hier festgehalten, weil jedes davon beim naechsten Aufbau sonst
wiederkommt:

| | |
|---|---|
| `bitnami/moodle` | existiert auf Docker Hub nicht mehr, der Pull endet auf `not found` |
| `MOODLE_SITENAME` mit Leerzeichen | das Entrypoint reicht den Wert unquotiert an Moodles Installations-CLI weiter, jedes Wort wird ein eigenes Argument, `config.php` entsteht nie |
| durchgereichter `Host`-Kopf | Moodle wirft mit `reverseproxy=true` `reverseproxyabused`, sobald der empfangene Host dem `wwwroot` gleicht. Der Proxy muss den **internen** Namen senden |
| `lti_get_lti_types()` | steht in `mod/lti/lib.php`, nicht in `locallib.php` |
| Idempotenzpruefung | `lti_add_type()` speichert `lti_toolurl` als `baseurl`, nicht die uebergebene Basis — der Vergleich traf nie zu, jeder Lauf legte eine neue Registrierung mit neuer `client_id` an |

### Kein Workflow

Moodle wird von Hand ausgerollt — was zu einer Instanz passt, die bewusst
stehen bleibt. Der Weg dorthin steht oben unter *Die Anbindung herstellen*.

### Keine Sicherung

Die Kursdaten liegen auf der Instanzplatte, ohne Cinder-Volume und ohne
Sicherung. Fuer ein Mock-Moodle vertretbar; fuer alles andere nicht.
