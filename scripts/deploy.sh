#!/usr/bin/env bash
# Rollt den Store auf die Staging-VM aus. Läuft im Deploy-Container
# (forgejo/job-image/Dockerfile), damit weder WSL noch lokal installiertes
# Terraform oder Ansible nötig ist.
#
# Nicht direkt aufrufen — deploy.cmd (Windows) bzw. deploy.sh im Repo-Wurzel
# starten den Container und rufen dann dieses Skript auf.
#
# set -u: ein Tippfehler in einem Variablennamen soll auffallen und nicht
# stillschweigend einen leeren Wert einsetzen. Gerade beim Inventory wäre das
# fatal — Ansible liefe mit "no hosts matched" grün durch, ohne etwas zu tun.
set -euo pipefail

MODE="${1:-plan}"
SEED="${2:-false}"

say()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m  OK\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m  !!\033[0m %s\n' "$*"; }
die()  { printf '\n\033[1;31mABBRUCH:\033[0m %s\n\n' "$*" >&2; exit 1; }

# ----------------------------------------------------------------------
# 0. Vorprüfungen — lieber hier abbrechen als nach zehn Minuten
# ----------------------------------------------------------------------
say "Vorprüfungen"

for v in OS_AUTH_URL OS_APPLICATION_CREDENTIAL_ID \
         OS_APPLICATION_CREDENTIAL_SECRET OS_REGION_NAME; do
  [ -n "${!v:-}" ] || die "$v ist nicht gesetzt. Siehe deploy.local.env"
done
ok "OpenStack-Credentials vorhanden"

# Der wichtigste Check des ganzen Skripts.
#
# Der Terraform-State liegt in Postgres (envs/staging/backend.tf, Schema
# "staging"). Fehlt die Verbindung, fällt Terraform auf einen leeren lokalen
# State zurück — es sieht die laufende VM dann NICHT und legt eine zweite an.
# Das kostet Quota, bricht das DNS und ist mühsam zurückzudrehen.
[ -n "${PG_CONN_STR:-}" ] || die \
"PG_CONN_STR fehlt.

Ohne diese Verbindung kennt Terraform den bestehenden Zustand nicht und
würde eine ZWEITE Staging-VM anlegen statt der vorhandenen.

Der Wert steht im Team-Passwortspeicher und gehört in deploy.local.env."
ok "State-Backend konfiguriert"

[ -f /run/secrets/ssh-key ] || die "SSH-Schlüssel nicht eingehängt (SSH_KEY_PATH in deploy.local.env)"
[ -f /run/secrets/stack-env ] || die "Die .env des Stacks fehlt (ENV_FILE_PATH in deploy.local.env)"

# Das Playbook erwartet den Inhalt der Datei in einer Variablen, nicht ihren
# Pfad. Eingelesen wird hier und nicht im Aufrufer: eine mehrzeilige Datei
# durch die Argumentverarbeitung von cmd.exe zu reichen geht schief, sobald
# Anführungszeichen oder Prozentzeichen darin vorkommen — und in Passwörtern
# kommen beide vor.
#
# Zuweisung getrennt vom export: `export VAR="$(cmd)"` maskiert den Exit-Code
# von cmd, ein Lesefehler käme trotz `set -e` unbemerkt durch (SC2155).
STAGING_ENV_FILE="$(cat /run/secrets/stack-env)"
export STAGING_ENV_FILE
ok "SSH-Schlüssel und .env vorhanden"

say "Erreichbarkeit von OpenStack"
code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "${OS_AUTH_URL}/v3" || echo 000)
[ "$code" = "200" ] || die \
"Keystone antwortet nicht (HTTP $code).

Die OpenStack-API der DHBW ist von außen nicht erreichbar.
Bist du im Campusnetz oder im VPN?"
ok "Keystone antwortet (HTTP $code)"

# ----------------------------------------------------------------------
# 1. SSH-Schlüssel einrichten
# ----------------------------------------------------------------------
say "SSH-Schlüssel vorbereiten"
mkdir -p ~/.ssh && chmod 700 ~/.ssh
cp /run/secrets/ssh-key ~/.ssh/openstack-key
chmod 600 ~/.ssh/openstack-key

# Der öffentliche Teil wird aus dem privaten abgeleitet, damit das
# OpenStack-Keypair immer zu dem Schlüssel passt, mit dem Ansible sich
# später verbindet. Laufen die beiden auseinander, endet der Deploy in
# "Permission denied (publickey)".
#
# -P '' erzwingt eine leere Passphrase: ein geschützter Schlüssel scheitert
# damit sofort und mit klarer Meldung, statt auf /dev/tty zu warten.
ssh-keygen -y -P '' -f ~/.ssh/openstack-key > ~/.ssh/openstack-key.pub \
  || die "Der SSH-Schlüssel ist passphrasegeschützt oder unlesbar."
TF_VAR_ssh_public_key="$(cat ~/.ssh/openstack-key.pub)"
export TF_VAR_ssh_public_key
ok "Schlüsselpaar bereit"

cleanup() {
  rm -f ~/.ssh/openstack-key ~/.ssh/openstack-key.pub
  rm -f /repo/infrastructure/ansible/inventory.ini
}
trap cleanup EXIT

# ----------------------------------------------------------------------
# 2. Terraform
# ----------------------------------------------------------------------
cd /repo/infrastructure/terraform/envs/staging

say "Terraform initialisieren"
terraform init -input=false
terraform validate
ok "Konfiguration gültig"

say "Terraform-Plan"
terraform plan -input=false -out=tfplan

# Ein Plan, der die VM ersetzt oder ein Volume löscht, vernichtet Daten.
# Das soll niemand übersehen, nur weil die Ausgabe lang ist.
PLAIN=$(terraform show -no-color tfplan)
DANGER=0
echo "$PLAIN" | grep -q "must be replaced"      && { warn "Der Plan will Ressourcen ERSETZEN"; DANGER=1; }
echo "$PLAIN" | grep -qE "^  # .* will be destroyed" && { warn "Der Plan will Ressourcen LÖSCHEN";  DANGER=1; }

if [ "$DANGER" = "1" ]; then
  echo
  echo "------------------------------------------------------------"
  echo "$PLAIN" | grep -E "must be replaced|will be destroyed" | head -20
  echo "------------------------------------------------------------"
  die \
"Der Plan würde bestehende Infrastruktur zerstören.

Das ist bei einem gewöhnlichen Deploy NICHT normal. Häufigste Ursache:
ein anderer State als der echte — also ein falscher PG_CONN_STR.

Hier wird bewusst nicht weitergemacht. Erst die Ursache klären."
fi
ok "Plan enthält keine zerstörenden Änderungen"

if [ "$MODE" != "apply" ]; then
  echo
  echo "$PLAIN" | tail -25
  echo
  say "Modus 'plan' — es wurde nichts verändert."
  echo "   Zum Ausrollen erneut starten und 'apply' wählen."
  exit 0
fi

say "Terraform anwenden"
terraform apply -input=false tfplan
ok "Infrastruktur auf Stand"

VM_IP=$(terraform output -raw vm_ip)
[ -n "$VM_IP" ] || die "terraform output lieferte keine Adresse."
VM_IPV4=$(terraform output -raw vm_ipv4 2>/dev/null || echo "")
VM_IPV4_GATEWAY=$(terraform output -raw vm_ipv4_gateway 2>/dev/null || echo "")
VM_IPV4_MAC=$(terraform output -raw vm_ipv4_mac 2>/dev/null || echo "")
ok "VM: $VM_IP"

# ----------------------------------------------------------------------
# 3. Ansible
# ----------------------------------------------------------------------
cd /repo/infrastructure/ansible

say "Inventory erzeugen"
# Die Adresse steht hinter einem Alias in ansible_host und ist nicht selbst
# der Hostname: eine IPv6-Literal in eckigen Klammern liest das ini-Plugin
# als Host-Range und bricht mit "host range must be begin:end" ab.
cat > inventory.ini <<EOF
[docker_vm]
staging ansible_host=${VM_IP} ansible_user=ubuntu
EOF
ok "Ziel eingetragen"

say "Playbook ausführen (dauert einige Minuten)"
export ANSIBLE_HOST_KEY_CHECKING=False
export ANSIBLE_FORCE_COLOR=True
ansible-playbook -i inventory.ini \
  --private-key ~/.ssh/openstack-key \
  -e "seed_data=${SEED}" \
  -e "secondary_ipv4=${VM_IPV4}" \
  -e "secondary_gateway=${VM_IPV4_GATEWAY}" \
  -e "secondary_mac=${VM_IPV4_MAC}" \
  staging.yml
ok "Stack läuft"

# ----------------------------------------------------------------------
# 4. Nachsehen
# ----------------------------------------------------------------------
if [ -n "${APP_HOSTNAME:-}" ]; then
  say "Abnahme"
  for path in "/" "/api/health"; do
    c=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "https://${APP_HOSTNAME}${path}" || echo 000)
    if [ "$c" = "200" ]; then ok "https://${APP_HOSTNAME}${path} → $c"
    else warn "https://${APP_HOSTNAME}${path} → $c"; fi
  done
  # 000 heißt hier meist nicht "kaputt", sondern "von hier nicht erreichbar":
  # die VM hängt im DHBWV6-Netz und hat keine öffentliche IPv4.
  warn "Antwortet nichts? Der Store ist nur über IPv6 erreichbar — prüfe den Tunnel."
fi

say "Fertig."
