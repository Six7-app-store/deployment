# Der self-hosted GitHub-Runner

Der Staging-Deploy läuft nicht auf einem gehosteten GitHub-Runner, sondern auf
einer eigenen VM im Campusnetz. Warum, steht in
[ADR-0002](adr/0002-self-hosted-runner-auf-eigener-vm.md). Was er tut, in
[ADR-0003](adr/0003-staging-wird-bei-jedem-merge-neu-gebaut.md). Hier steht, wie
er betrieben wird.

## Die Maschine

| | |
|---|---|
| Hostname | `github-runner` |
| Adresse | `2001:7c0:1b20:c913:1::3f0` |
| System | Ubuntu 24.04 LTS |
| Ausstattung | 1 vCPU, 2 GB RAM, 8,7 GB Platte |
| Benutzer | `ubuntu`, Zugang über den Deploy-Schlüssel |
| Runner-Version | 2.322.0, unter `~/actions-runner` |
| Registriert an | **nur** `Six7-app-store/deployment` |
| Labels | `self-hosted`, `deploy`, `Linux`, `X64` |
| Dienst | `actions.runner.Six7-app-store-deployment.github-runner-dhbw` |

> **Die Registrierung gehört an das Repository, nicht an die Organisation.**
> Alle fünf Repositories sind öffentlich. Ein Runner auf Organisationsebene wäre
> aus jedem von ihnen ansprechbar, und ein einziger `pull_request`-Trigger
> genügte, damit ein fremder Fork-PR Code auf einer Maschine mit
> OpenStack-Zugang ausführt.

## Was darauf installiert ist

Von Hand installiert, nicht durch ein Job-Image festgehalten — bei einem Update
also selbst nachziehen:

| Werkzeug | Version | Quelle |
|---|---|---|
| Terraform | 1.16.3 | apt, `apt.releases.hashicorp.com` |
| Ansible | core 2.21.4 | `pip3 --break-system-packages` |
| Trivy | 0.74.0 | Installskript nach `/usr/local/bin` |
| nsupdate, dig | 9.18 | apt, `bind9-dnsutils` |
| jq, rsync, unzip, python3-pip | Distribution | apt |

Der Workflow prüft sie im Schritt **Werkzeuge prüfen**, bevor er irgendetwas
anfasst. Fehlt eins, bricht der Lauf dort ab statt später mitten im `apply`.

`nsupdate` setzt nach dem `apply` den `AAAA`-Record auf die Adresse der neuen
VM. Ohne diesen Schritt wäre der Neuaufbau wertlos: die neue VM bekommt eine
neue IPv6-Adresse, und unter dem Hostnamen wäre nichts mehr erreichbar. Der
dafür benutzte TSIG-Schlüssel ist derselbe, den Caddy für die
dns-01-Prüfung verwendet — er steht als `DNS_TSIG_KEY` in `STAGING_ENV_FILE`
und darf nachweislich auch `AAAA` schreiben.

## Der Terraform-State

Liegt unter `/var/lib/tf-state/staging/terraform.tfstate`, gehört `ubuntu`.

Der Pfad liegt **außerhalb** des Runner-Workspace: `actions/checkout` räumt den
Workspace vor jedem Lauf. Und er liegt auf der **Runner**-VM, nicht auf der
AppStore-VM — sonst würde `terraform destroy` die Datei mitlöschen, in der
steht, was gerade gelöscht wird.

**Diese Datei ist der wunde Punkt des Aufbaus.** Geht sie verloren, sieht
Terraform die laufenden Ressourcen nicht mehr und scheitert beim Anlegen am
schon vergebenen Namen `staging-dhbw-appstore`. Aufräumen geht dann nur von Hand
in Horizon. Vor einem Eingriff an der Runner-VM also sichern:

```bash
ssh ubuntu@2001:7c0:1b20:c913:1::3f0 \
  'cat /var/lib/tf-state/staging/terraform.tfstate' > tfstate-sicherung.json
```

## Die Terraform-State-Datenbank

Seit [ADR-0005](adr/0005-tfstate-der-app-deployments-gehoert-von-der-staging-vm-herunter.md)
läuft auf dieser VM zusätzlich Postgres. Es hält den Terraform-State **jedes
App-Deployments** — und damit die einzige Kenntnis darüber, welche VMs die
Plattform angelegt hat, samt der Passwörter der Studierenden.

| | |
|---|---|
| Version | PostgreSQL 16, über `apt` |
| Lauscht auf | `10.200.1.55` und `localhost`, Port 5432 |
| Datenbank | `tfstate`, Eigentümer `terraform` |
| Erreichbar aus | `10.200.0.0/19`, Security Group `tfstate-db` |
| Konfiguration | `/etc/postgresql/16/main/` |

Der Worker auf der Staging-VM verbindet sich über `TFSTATE_DB_HOST` aus der
`.env`. **Die Adresse ist per DHCP vergeben** — wird diese VM je neu gebaut,
muss der Wert nachgezogen werden.

**Diese Datenbank ist die zweite Stelle auf dieser Maschine, deren Verlust
teuer ist.** Beim Terraform-State von Staging geht es um eine VM; hier um jedes
laufende Deployment. Ein verlorenes Windows-Deployment kostet 30 bis 60 Minuten
Neuaufbau je Studierendem. Sichern:

```bash
ssh ubuntu@2001:7c0:1b20:c913:1::3f0   'sudo -u postgres pg_dump -d tfstate --no-owner --no-acl' > tfstate-sicherung.sql
```

Nachsehen, was drinsteht:

```bash
sudo -u postgres psql -d tfstate -c   "SELECT schema_name FROM information_schema.schemata WHERE schema_name LIKE 'deployment_%';"
```

## Nachsehen, ob er läuft

In GitHub: **Settings → Actions → Runners** am `deployment`-Repository, oder:

```bash
gh api repos/Six7-app-store/deployment/actions/runners \
  --jq '.runners[] | "\(.name) \(.status)"'
```

Auf der Maschine:

```bash
sudo ~/actions-runner/svc.sh status
journalctl -u actions.runner.Six7-app-store-deployment.github-runner-dhbw -n 50
```

`Listening for Jobs` im Log heißt: er wartet auf Arbeit. Steht dort nichts
weiter, ist das der Normalzustand.

## Neu registrieren

Nötig, wenn die VM ersetzt wird oder die Registrierung verloren geht. Das Token
ist eine Stunde gültig und wird nicht gespeichert — deshalb die Pipe:

```bash
gh api -X POST repos/Six7-app-store/deployment/actions/runners/registration-token \
  --jq '.token' \
| ssh ubuntu@2001:7c0:1b20:c913:1::3f0 \
    'read -r T; cd ~/actions-runner && ./config.sh --unattended --replace \
       --url https://github.com/Six7-app-store/deployment --token "$T" \
       --name github-runner-dhbw --labels self-hosted,deploy,linux,x64 --work _work'

ssh ubuntu@2001:7c0:1b20:c913:1::3f0 \
  'cd ~/actions-runner && sudo ./svc.sh install ubuntu && sudo ./svc.sh start'
```

Auf einer frischen VM vorher noch das State-Verzeichnis anlegen und die
Werkzeuge aus der Tabelle oben installieren:

```bash
sudo mkdir -p /var/lib/tf-state/staging && sudo chown -R ubuntu:ubuntu /var/lib/tf-state
```

## Secrets, die der Deploy braucht

Alle am Repository `Six7-app-store/deployment`:

| Secret | Woher |
|---|---|
| `STAGING_OS_AUTH_URL` | `secrets/os-env.sh` |
| `STAGING_OS_APPLICATION_CREDENTIAL_ID` | `secrets/os-env.sh` |
| `STAGING_OS_APPLICATION_CREDENTIAL_SECRET` | `secrets/os-env.sh` |
| `STAGING_OS_REGION_NAME` | `secrets/os-env.sh` |
| `SSH_PRIVATE_KEY` | `secrets/openstack-deploy` (privater Schlüssel, PEM) |
| `STAGING_ENV_FILE` | `secrets/staging.env`, vollständiger Inhalt |

Der öffentliche Schlüssel wird im Workflow aus `SSH_PRIVATE_KEY` abgeleitet und
als `TF_VAR_ssh_public_key` an Terraform gereicht. Dadurch passt das
OpenStack-Keypair immer zu dem Schlüssel, mit dem Ansible sich gleich verbindet
— es gibt keinen zweiten Ort, an dem beide auseinanderlaufen könnten.

Dazu auf Organisationsebene `CROSS_REPO_PAT`, freigegeben für alle vier
Repositories. Damit schicken frontend, backend und worker ihren
`repository_dispatch` hierher. Das Token braucht nur `repo`-Schreibrechte am
`deployment`-Repository und sonst nichts.

## Wenn der Deploy hängt

Ein Lauf blockiert alle folgenden — die `concurrency`-Gruppe `staging-deploy`
bricht nichts ab, sie stellt in eine Schlange. Das ist gewollt: ein halb
abgebrochener `terraform apply` ist schlimmer als ein wartender Job.

Hängt tatsächlich etwas, den Lauf in der GitHub-Oberfläche abbrechen und danach
den State prüfen:

```bash
ssh ubuntu@2001:7c0:1b20:c913:1::3f0
cd /tmp && git clone https://github.com/Six7-app-store/deployment
cd deployment/infrastructure/terraform/envs/staging
export OS_AUTH_TYPE=v3applicationcredential OS_IDENTITY_API_VERSION=3
# OS_* aus secrets/os-env.sh setzen
terraform init && terraform plan
```

Steht im Plan etwas, das niemand erklären kann, ist der State nicht mehr in
Übereinstimmung mit OpenStack. Dann in Horizon nachsehen, was tatsächlich läuft.
