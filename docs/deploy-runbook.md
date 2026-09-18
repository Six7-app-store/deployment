# Deploy-Runbook — den Store von Hand ausrollen

Diese Anleitung bringt eine Codeänderung auf die Staging-VM — von Hand, Schritt
für Schritt.

**Der übliche Weg ist das nicht mehr.** Dieselben Schritte führt der Workflow
[`CD - Staging Deployment`](../.forgejo/workflows/staging.yml) auf dem
Forgejo-Runner aus; ein Deploy ist dort ein Knopfdruck. Dieses Runbook ist der
Rückfallweg — für den Fall, dass der Forge-Host steht, und als Nachschlagewerk
dafür, was der Workflow eigentlich tut.

Über GitHub Actions läuft der Deploy in keinem Fall: Die OpenStack-API der DHBW
ist von außen nicht erreichbar, ein gehosteter Runner kommt also gar nicht hin.
Die Begründung samt Messwerten steht in
[deployment-process.md](deployment-process.md), Abschnitt 6.

Ein vollständiger Durchlauf dauert etwa **fünf bis zehn Minuten**.

---

## Der schnelle Weg: `deploy.cmd`

Wer die Schritte nicht einzeln tippen will, startet **`deploy.cmd`** im
Repository-Wurzelverzeichnis per Doppelklick. Das Skript führt genau die unten
beschriebenen Schritte aus — nur in einem Container, sodass auf dem Rechner
weder WSL noch Terraform oder Ansible installiert sein muss. Gebraucht wird nur
Docker Desktop.

Einmalig vorbereiten:

```
copy deploy.local.env.example deploy.local.env
```

Dann die Werte eintragen (OpenStack-Zugang, `PG_CONN_STR`, Pfad zum
SSH-Schlüssel, Pfad zur `.env`). Die Datei steht in `.gitignore`.

Beim Start fragt das Skript, was passieren soll:

| Auswahl | Wirkung |
|---|---|
| **Nur ansehen** | Führt den Terraform-Plan aus und zeigt ihn. Es wird nichts verändert. |
| **Ausrollen** | Wendet die Änderungen an und startet danach Ansible. |

Zwei Sicherungen sind eingebaut, und beide brechen den Lauf ab statt zu warnen:

- **Ohne `PG_CONN_STR` startet es gar nicht.** Terraform würde sonst mit leerem
  State beginnen, die laufende VM nicht erkennen und eine **zweite** anlegen.
- **Ein Plan, der Ressourcen ersetzt oder löscht, stoppt den Lauf.** Bei einem
  gewöhnlichen Deploy darf das nicht vorkommen; die häufigste Ursache ist ein
  falscher State.

Der Rest dieses Dokuments beschreibt dieselben Schritte von Hand — nützlich, um
zu verstehen, was `deploy.cmd` tut, und um einzugreifen, wenn etwas klemmt.

---

## Voraussetzungen

**Du bist im Campusnetz oder im VPN.** Ohne das schlägt bereits Schritt 1 fehl.
Prüfen:

```bash
curl -s -o /dev/null -w '%{http_code}\n' --max-time 10 \
  https://newstack.dhbw.cloud:5000/v3
```

`200` ist gut. `000` heißt: kein VPN.

**Werkzeuge** — Terraform und Ansible. Ansible läuft nicht unter Windows; auf
einem Windows-Rechner also WSL2 benutzen.

```bash
terraform version    # >= 1.5
ansible --version    # >= 2.15
```

**Zugangsdaten**, vier Stück:

| Was | Wo es hingehört |
|---|---|
| `clouds.yaml` | `~/.config/openstack/clouds.yaml` |
| SSH-Schlüssel für die VM | z. B. `~/.ssh/openstack-key`, Rechte `600` |
| `.env` des Stacks | wird in Schritt 3 gebraucht |
| Postgres-Verbindung für den Terraform-State | als `PG_CONN_STR` exportiert |

> Die `.env` und der SSH-Schlüssel liegen beim Team. Sie stehen bewusst nicht
> im Repository — `.gitignore` und der Gitleaks-Scan in der CI sorgen dafür,
> dass das so bleibt.

---

## Schritt 0: Umgebung setzen

```bash
cd deployment
export OS_CLOUD=openstack
export PG_CONN_STR='postgres://…'        # Backend für den Terraform-State
export TF_VAR_ssh_public_key="$(ssh-keygen -y -f ~/.ssh/openstack-key)"
```

`TF_VAR_ssh_public_key` wird aus dem privaten Schlüssel abgeleitet, damit das
OpenStack-Keypair immer zu dem Schlüssel passt, mit dem Ansible sich später
verbindet. Die beiden auseinanderlaufen zu lassen ist der häufigste Grund für
ein „Permission denied (publickey)" in Schritt 3.

---

## Schritt 1: Infrastruktur planen

```bash
cd infrastructure/terraform/envs/staging
terraform init
terraform validate
terraform plan -out=tfplan
```

**Den Plan lesen, bevor du weitermachst.** Erwartet wird bei einem normalen
Deploy:

```
No changes. Your infrastructure matches the configuration.
```

oder eine überschaubare Liste. Zwei Dinge sind ein Stoppsignal:

- **`must be replaced`** an der VM — Terraform würde sie löschen und neu
  anlegen. Alles auf der Maschine wäre weg.
- **`destroy`** an einem Volume — dasselbe für die Daten.

Steht so etwas im Plan und du willst es nicht, brich hier ab und kläre die
Ursache.

---

## Schritt 2: Infrastruktur anwenden

```bash
terraform apply tfplan
```

Danach die Adressen einsammeln, Ansible braucht sie gleich:

```bash
export VM_IP=$(terraform output -raw vm_ip)
export VM_IPV4=$(terraform output -raw vm_ipv4)
export VM_IPV4_GATEWAY=$(terraform output -raw vm_ipv4_gateway)
export VM_IPV4_MAC=$(terraform output -raw vm_ipv4_mac)
echo "VM: $VM_IP"
```

> Ist `VM_IP` leer, hat Terraform nichts ausgegeben. Dann nicht weitermachen —
> Ansible liefe sonst mit „no hosts matched" grün durch und täte nichts.

---

## Schritt 3: Konfigurieren und Stack starten

```bash
cd ../../../ansible
ansible-galaxy role install -r requirements.yml -p roles_external
ansible-galaxy collection install -r requirements.yml
```

Inventory anlegen:

```bash
cat > inventory.ini <<EOF
[docker_vm]
staging ansible_host=${VM_IP} ansible_user=ubuntu
EOF
```

> Die Adresse steht hinter einem Alias und ist nicht selbst der Hostname. Eine
> IPv6-Adresse in eckigen Klammern liest das ini-Plugin sonst als Host-Range
> und bricht mit „host range must be begin:end" ab.

Den Inhalt der `.env` bereitstellen und das Playbook starten:

```bash
export STAGING_ENV_FILE="$(cat /pfad/zur/.env)"
export ANSIBLE_HOST_KEY_CHECKING=False

ansible-playbook -i inventory.ini \
  --private-key ~/.ssh/openstack-key \
  -e "secondary_ipv4=${VM_IPV4}" \
  -e "secondary_gateway=${VM_IPV4_GATEWAY}" \
  -e "secondary_mac=${VM_IPV4_MAC}" \
  staging.yml
```

Das Playbook richtet das zweite Netzwerkinterface ein, installiert Docker,
kopiert Stack und `.env`, rendert den Keycloak-Realm, meldet sich an GHCR an,
zieht die Images, startet alles und wendet die Migrationen an.

**Seed-Daten** nur bei leerer Datenbank — sie legen Nutzer, Kurse und Apps an:

```bash
ansible-playbook … -e seed_data=true … staging.yml
```

> Ohne diesen Schalter fasst ein Deploy keine Anwendungsdaten an. Das Skript
> ist idempotent, ein erneuter Lauf also unbedenklich.

---

## Schritt 4: Aufräumen

```bash
rm -f inventory.ini
unset STAGING_ENV_FILE PG_CONN_STR
```

Das Inventory enthält die Adresse der Maschine, `STAGING_ENV_FILE` sämtliche
Passwörter des Stacks. Beides gehört nicht in die Shell-History einer
Feierabend-Sitzung.

---

## Schritt 5: DNS — nur beim ersten Mal

Die VM ist über beide Adressfamilien erreichbar, also gehören zwei Einträge
unter denselben Hostnamen (TTL 300):

```
A      <APP_HOSTNAME>   <vm_ipv4>
AAAA   <APP_HOSTNAME>   <vm_ip>
```

Bleibt die VM bestehen, bleiben die Adressen — dieser Schritt entfällt dann.
Das Zertifikat braucht keine Aufmerksamkeit: Caddy weist die Kontrolle über
dns-01 nach, unabhängig davon, wie der Host erreichbar ist.

---

## Schritt 6: Nachsehen, ob es läuft

Das Playbook prüft am Ende selbst und bricht bei einem fehlgeschlagenen Health
Check ab. Von Hand bleibt der fachliche Blick:

```bash
ssh ubuntu@${VM_IP} 'cd ~/app && docker compose -f docker-compose.staging.yml ps'
curl -sI https://<APP_HOSTNAME>/ | head -1
```

Dann im Browser: über Keycloak anmelden, eine App ausrollen, durchklicken.

---

## Wenn etwas schiefgeht

| Symptom | Ursache |
|---|---|
| `curl` auf Keystone gibt `000` | Kein VPN |
| `Permission denied (publickey)` | `TF_VAR_ssh_public_key` passt nicht zum privaten Schlüssel aus Schritt 0 |
| `no hosts matched` | `VM_IP` war leer, Inventory ist leer |
| `host range must be begin:end` | IPv6 ohne Alias ins Inventory geschrieben |
| Volume hängt in `creating` | Cinder-Problem. Es lässt sich nicht löschen und blockiert jedes `apply`. Ausweg: `terraform state rm 'module.vm.openstack_blockstorage_volume_v3.docker_data[0]'` — danach verwaltet Terraform es nicht mehr, weg ist es damit nicht. Aufräumen muss ein Operator. |
| `compose pull` findet das Image nicht | `IMAGE_NAMESPACE` zeigt auf einen Namespace ohne Images, siehe [`.env.staging.example`](../.env.staging.example) |

---

## Was davor automatisch passiert ist

Dieses Runbook beginnt erst, wenn das Image bereits in GHCR liegt. Alles davor
— Lint, Tests, Sicherheitsscans, Image-Build und -Push — erledigt die CI in
`backend`, `frontend` und `worker` ohne Zutun. Die Terraform- und
Ansible-Dateien, die du hier ausführst, hat `CI - Infrastructure QA` in diesem
Repository schon geprüft.

Der Gesamtablauf steht in [deployment-process.md](deployment-process.md).
