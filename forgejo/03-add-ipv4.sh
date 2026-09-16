#!/usr/bin/env bash
# Phase 3: give the Forgejo host an IPv4 address alongside its IPv6 one.
#
# envs/forgejo puts the VM on DHBWV6, so the forge is unreachable from any
# network without IPv6. This attaches a second interface on DHBWv4 and
# configures it in the guest, then stops - the A record is yours to add.
#
# Re-runnable: Terraform skips what exists, and the playbook only rewrites the
# netplan file when its content differs.
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
env_dir="$here/../infrastructure/terraform/envs/forgejo"
ansible_dir="$here/../infrastructure/ansible"
ssh_key=${SSH_KEY:-~/.ssh/id_ed25519}

fail() { echo "error: $*" >&2; exit 1; }
step() { echo; echo "==> $*"; }

command -v terraform >/dev/null || fail "terraform not found in PATH"

[ -f "$env_dir/terraform.tfstate" ] || fail \
  "no state in $env_dir - this script extends an existing VM, run 01-create-vm.sh first"

[ -r "$ssh_key" ] || fail "SSH key not readable: $ssh_key (set SSH_KEY=<path>)"

# Same two ways to authenticate as 01-create-vm.sh; see the comment there.
if [ -n "${OS_CLOUD:-}" ]; then
  :
elif [ -n "${OS_AUTH_URL:-}" ]; then
  [ -n "${OS_APPLICATION_CREDENTIAL_ID:-}${OS_USERNAME:-}" ] || fail \
    "OS_AUTH_URL is set but no credentials (OS_APPLICATION_CREDENTIAL_ID or OS_USERNAME)"
else
  fail "no OpenStack credentials. Either export OS_CLOUD=<name from clouds.yaml>, or OS_AUTH_URL plus credentials."
fi

# Taken from the state rather than from the caller. The public key becomes the
# instance's keypair, and key_pair forces replacement - so a value that differs
# even in its trailing comment would queue the VM for rebuild.
if [ -z "${TF_VAR_ssh_public_key:-}" ]; then
  TF_VAR_ssh_public_key=$(terraform -chdir="$env_dir" state show -no-color \
    module.vm.openstack_compute_keypair_v2.deploy 2>/dev/null \
    | sed -n 's/^ *public_key *= *"\(.*\)"$/\1/p')
  [ -n "$TF_VAR_ssh_public_key" ] || fail \
    "could not read the public key from state. Export TF_VAR_ssh_public_key with the key this VM was built with."
  export TF_VAR_ssh_public_key
fi

# ---------------------------------------------------------------------------
step "terraform init"
# ---------------------------------------------------------------------------
terraform -chdir="$env_dir" init -input=false

# ---------------------------------------------------------------------------
step "terraform plan"
# ---------------------------------------------------------------------------
terraform -chdir="$env_dir" plan -input=false -out=tfplan

# The whole point of attaching a port instead of adding a second `network`
# block is that the instance survives. If the plan destroys anything, that
# assumption did not hold, and applying it would take the forge down with it.
#
# Checked against the machine-readable plan rather than the printed one, so a
# change in Terraform's wording cannot silently disable the guard.
plan_json=$(terraform -chdir="$env_dir" show -json tfplan) \
  || fail "could not read the plan back - not applying"

# Explicit, because grep -c answers "0" for empty input just as it does for a
# clean plan: without this check a failed `show` would read as approval.
[ -n "$plan_json" ] || fail "the plan is empty - not applying"

destroys=$(printf '%s' "$plan_json" | tr ',' '\n' | grep -c '"delete"' || true)
if [ "${destroys:-1}" -ne 0 ]; then
  terraform -chdir="$env_dir" show -no-color tfplan | grep -E 'destroyed|replaced' || true
  fail "this plan destroys or replaces resources - not applying. Nothing has changed yet."
fi

if [ "${CONFIRM:-}" = "yes" ]; then
  answer=yes
elif [ -r /dev/tty ]; then
  printf '\nApply this plan? Only "yes" will be accepted: ' > /dev/tty
  read -r answer < /dev/tty
else
  fail "no terminal to confirm on. Re-run with CONFIRM=yes to apply unattended."
fi

[ "$answer" = "yes" ] || fail "not confirmed - nothing was applied (the plan is in $env_dir/tfplan)"

# ---------------------------------------------------------------------------
step "terraform apply"
# ---------------------------------------------------------------------------
terraform -chdir="$env_dir" apply tfplan

ipv4=$(terraform -chdir="$env_dir" output -raw vm_ipv4)
gateway=$(terraform -chdir="$env_dir" output -raw vm_ipv4_gateway)
mac=$(terraform -chdir="$env_dir" output -raw vm_ipv4_mac)

for pair in "vm_ipv4:$ipv4" "vm_ipv4_gateway:$gateway" "vm_ipv4_mac:$mac"; do
  [ -n "${pair#*:}" ] || fail "apply finished but ${pair%%:*} is empty"
done

echo "    address  $ipv4"
echo "    gateway  $gateway"
echo "    mac      $mac"

# ---------------------------------------------------------------------------
step "Configure the interface in the guest"
# ---------------------------------------------------------------------------
command -v ansible-playbook >/dev/null 2>&1 || fail \
  "ansible-playbook not found in PATH. Install it, e.g. pipx install --include-deps ansible"

# See 02-configure.sh: Ansible reads ansible.cfg from the working directory,
# and this script does not run in the one it belongs to.
export ANSIBLE_CONFIG="$ansible_dir/ansible.cfg"
export ANSIBLE_ROLES_PATH="$ansible_dir/roles:$ansible_dir/roles_external"

# An optional hostname argument is passed through, same as 02-configure.sh.
# Reaching the VM still happens over IPv6 - the address this script just
# created has no DNS record yet.
"$ansible_dir/inventory-forgejo.sh" "${1:-}" >/dev/null

# --tags network restricts this to the two netplan tasks. Without it the run
# would also sync the compose stack and restart the forge, which is a far
# bigger action than adding an address.
ansible-playbook -i "$ansible_dir/inventory.forgejo.ini" \
  --private-key "$ssh_key" \
  --tags network \
  -e "secondary_ipv4=$ipv4" \
  -e "secondary_gateway=$gateway" \
  -e "secondary_mac=$mac" \
  "$ansible_dir/forgejo.yml"

cat <<EOF

==> The host now answers on: $ipv4

Next, by hand:

  1. Add an A record for the forge's hostname pointing at that address.
     Leave the AAAA record in place - both belong to the same name, and
     clients pick whichever family they have.

  2. Verify from a machine without IPv6:
       curl -4 -sS -o /dev/null -w '%{http_code}\\n' https://<hostname>/

The certificate needs no attention: Caddy proves control over dns-01, which
does not depend on how the host is reachable.
EOF
