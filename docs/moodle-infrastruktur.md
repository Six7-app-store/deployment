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

## Ausrollen

Zwei Schichten: Terraform legt in OpenStack eine VM an, auf dieser VM laufen
drei Container über Docker Compose. Kein Kubernetes.

```
OpenStack ── Terraform ── VM `moodle`
                             └── docker compose -f docker-compose.moodle-infra.yml
                                     moodle · postgres · caddy
```

**Alles läuft von der Runner-VM aus**, nicht vom Arbeitsrechner. Die
OpenStack-API der DHBW ist von außerhalb des Campusnetzes nicht erreichbar, und
der Terraform-State liegt ohnehin dort (ADR-0002, ADR-0003).

Es gibt **keinen Workflow** dafür. Das passt zu einer Instanz, die bewusst
stehen bleibt — aber es heißt, dass die folgenden Schritte von Hand kommen.

### 0. Auf die Runner-VM und Arbeitskopie holen

```bash
ssh -i <deploy-key> ubuntu@2001:7c0:1b20:c913:1::3f0
git clone --branch main https://github.com/Six7-app-store/deployment.git ~/moodle-deploy
sudo mkdir -p /var/lib/tf-state/moodle && sudo chown ubuntu:ubuntu /var/lib/tf-state/moodle
```

### 1. Zugangsdaten hinlegen

Drei Dateien, alle `chmod 600`, alle nach getaner Arbeit mit `shred -u`
entfernen — die Runner-VM ist dauerhaft und wird von mehreren Leuten benutzt:

| Datei | Inhalt | Quelle |
|---|---|---|
| `moodle.env` | die `.env` des Compose-Stacks | Secret `MOODLE_ENV_FILE` |
| `os.env` | `export OS_*=…` | `secrets/os-env.sh` |
| `openstack-deploy` | privater SSH-Schlüssel | Secret `SSH_PRIVATE_KEY` |

Terraform braucht den **öffentlichen** Schlüssel, abgeleitet statt separat
gepflegt — zwei Werte, die zusammenpassen müssen, sind zwei Werte, die
auseinanderlaufen können:

```bash
ssh-keygen -y -f openstack-deploy > deploy.pub
```

### 2. VM anlegen

```bash
. ~/moodle-deploy/os.env
cd ~/moodle-deploy/infrastructure/terraform/envs/moodle
terraform init -input=false
terraform plan -input=false -out=moodle.plan -var "ssh_public_key=$(cat ~/moodle-deploy/deploy.pub)"
terraform apply -input=false moodle.plan
```

Erst planen, dann anwenden. **Im Plan muss `0 to destroy` stehen** — diese VM
soll überleben, und ein `destroy` hier nähme Moodles Kursdaten mit, die auf der
Instanzplatte liegen. Ergebnis ist `vm_ip`.

### 3. AAAA-Eintrag setzen

Ohne DNS-Namen kein Zertifikat, ohne HTTPS kein LTI. Derselbe TSIG-Schlüssel
wie beim App Store, und derselbe, den Caddy gleich für die `dns-01`-Prüfung
benutzt — er darf nachweislich auch `AAAA` schreiben.

Die Zone wird **erfragt, nicht geraten**: ein falscher `zone`-Eintrag lässt
`nsupdate` mit `NOTZONE` scheitern, und das sieht aus wie ein Rechteproblem.

```bash
zone=$(dig +noall +authority +answer SOA "$hostname" @"$nshost" -p "$nsport"        | awk '$4=="SOA"{print $1; exit}')
nsupdate -k "$keyfile" <<UPDATE
server $nshost $nsport
zone $zone
update delete $hostname. AAAA
update add $hostname. 60 AAAA $vm_ip
send
UPDATE
```

Der Schlüssel geht über eine **Datei**, nicht über `-y`: die Kommandozeile wäre
auf dieser dauerhaften Maschine für jeden sichtbar, der zur selben Zeit `ps`
aufruft. Der Workflow des App Stores macht es genauso.

### 4. Playbook laufen lassen

```bash
ansible-galaxy role install geerlingguy.docker
cat > ~/moodle-deploy/inv/hosts.yml <<EOS
all:
  children:
    moodle_vm:
      hosts:
        moodle:
          ansible_host: <vm_ip>
          ansible_user: ubuntu
          ansible_ssh_private_key_file: /home/ubuntu/moodle-deploy/openstack-deploy
EOS

export MOODLE_ENV_FILE="$(cat ~/moodle-deploy/moodle.env)"
ansible-playbook -i inv/hosts.yml infrastructure/ansible/moodle.yml
```

Das Playbook wartet bis zu 15 Minuten auf Moodles Erstinstallation und bricht
ab, wenn sie nicht kommt. Der Hostname muss zu diesem Zeitpunkt bereits
aufgelöst werden, sonst holt Caddy kein Zertifikat.

### 5. Werkzeug registrieren

```bash
docker exec moodle php /var/www/html/local_register_lti_tool.php     --appstore=https://appstore.<zone>.users.dhbw.site
```

Gibt die sieben Zeilen aus, die in die `.env` des App Stores gehören.
Idempotent: ein bereits registriertes Werkzeug wird nur ausgelesen.

### 6. Secret setzen und App Store neu ausrollen

Neben den sieben Zeilen braucht `STAGING_ENV_FILE` noch zwei Werte, die Moodle
**nicht** ausstellt und die man leicht übersieht:

```bash
# Der private Schlüssel dieses Tools. Die öffentliche Hälfte leitet das
# Backend beim Start daraus ab und serviert sie unter /lti/jwks - dort holt
# Moodle sie bei jedem Launch.
python -c "import base64;from cryptography.hazmat.primitives import serialization as s;from cryptography.hazmat.primitives.asymmetric import rsa;k=rsa.generate_private_key(public_exponent=65537,key_size=2048);print(base64.b64encode(k.private_bytes(s.Encoding.PEM,s.PrivateFormat.PKCS8,s.NoEncryption())).decode())"
# LTI_SESSION_SECRET: 48 zufällige Zeichen.
```

```bash
gh secret set STAGING_ENV_FILE < secrets/staging.env
```

Wirksam wird es erst beim nächsten Deploy nach `main` — und der reißt Staging
für rund zehn Minuten ab.

### 7. Aufräumen

```bash
shred -u ~/moodle-deploy/os.env ~/moodle-deploy/openstack-deploy ~/moodle-deploy/deploy.pub
```

`moodle.env` darf bleiben, wenn Wiederholungen anstehen — sonst mit weg. Es
steht ohnehin im Secret `MOODLE_ENV_FILE`.

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
