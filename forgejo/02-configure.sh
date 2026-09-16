#!/usr/bin/env bash
# Phase 2, part two: configure the VM until Forgejo is serving and its runner
# is registered.
#
# Assumes the VM exists (terraform apply in ../infrastructure/terraform/envs/
# forgejo), an AAAA record points at it, and .env in this directory is filled
# in. Everything after that is mechanical, including the runner token — Forgejo
# can issue one from its CLI, so the round trip through the web UI is not
# actually necessary.
#
# Re-runnable. The playbook is idempotent, the admin account is only created
# when no account exists, and the runner token is only issued when .env has
# none.
#
#   SSH_KEY=~/.ssh/my-key ./02-configure.sh
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
env_dir="$here/../infrastructure/terraform/envs/forgejo"
ansible_dir="$here/../infrastructure/ansible"
env_file="$here/.env"
ssh_key="${SSH_KEY:-$HOME/.ssh/id_ed25519}"

fail() { echo "error: $*" >&2; exit 1; }
step() { printf '\n==> %s\n' "$*"; }

read_env() { grep -E "^$1=" "$env_file" | head -n1 | cut -d= -f2- | tr -d '"'\''\r'; }

# ---------------------------------------------------------------------------
# Preflight. Every check here is something that otherwise fails much later, in
# a place where the cause is no longer obvious.
# ---------------------------------------------------------------------------
step "Preflight"

[ -f "$env_file" ] || fail ".env not found - copy .env.example and fill it in"
[ -f "$ssh_key" ]  || fail "SSH key $ssh_key not found - set SSH_KEY"
[ -f "$env_dir/terraform.tfstate" ] || fail "no Terraform state in $env_dir - build the VM first"

for v in FORGEJO_DB_PASSWORD FORGEJO_ROOT_URL FORGEJO_HOSTNAME ACME_EMAIL \
         DNS_TSIG_KEY_NAME DNS_TSIG_KEY; do
  [ -n "$(read_env "$v")" ] || fail "$v is missing or empty in .env"
done

root_url=$(read_env FORGEJO_ROOT_URL)
hostname=$(read_env FORGEJO_HOSTNAME)

# ROOT_URL is written into clone URLs and webhooks on first start and is stored,
# not derived. Catching the Phase 1 value here is worth more than catching it
# in the playbook, because this script may be the only thing anyone runs.
case "$root_url" in
  *forgejo:3000*|*localhost*)
    fail "FORGEJO_ROOT_URL is still the local Phase 1 value ($root_url)" ;;
esac

# A mismatch here yields a valid certificate for one name while Forgejo hands
# out links to another - which looks like a DNS problem and is not.
case "$root_url" in
  *"$hostname"*) ;;
  *) fail "FORGEJO_HOSTNAME ($hostname) does not appear in FORGEJO_ROOT_URL ($root_url)" ;;
esac

ip=$(terraform -chdir="$env_dir" output -raw vm_ip)
[ -n "$ip" ] || fail "terraform output produced no vm_ip"

# Resolved rather than assumed: without a record, Caddy's dns-01 attempt fails
# after the stack is already up, and the failure reads like a TSIG problem.
#
# dig first, getent second. getent comes from glibc and is the obvious choice on
# Linux, but on macOS it does not answer for AAAA records at all - it returns
# nothing for a name that resolves perfectly well, which turned this check into
# a false alarm on the very machine it runs from.
if command -v dig >/dev/null 2>&1; then
  resolved=$(dig +short AAAA "$hostname" | tail -n1)
  [ -n "$resolved" ] || resolved=$(dig +short A "$hostname" | tail -n1)
else
  resolved=$(getent hosts "$hostname" | awk '{print $1}' | head -n1)
fi

[ -n "$resolved" ] || fail "$hostname does not resolve - create the DNS record before continuing"

# A record pointing somewhere else is usually a leftover from an earlier VM.
# Worth catching here: the stack would come up, and only the certificate would
# fail, several steps later and with a message about ACME rather than DNS.
if [ "$resolved" != "$ip" ]; then
  fail "$hostname resolves to $resolved, but this environment's VM is $ip"
fi

remote() { ssh -i "$ssh_key" -o BatchMode=yes -o StrictHostKeyChecking=no "ubuntu@$ip" "$@"; }
remote true 2>/dev/null || fail "cannot reach ubuntu@$ip over SSH with $ssh_key"

echo "    VM        $ip"
echo "    hostname  $hostname -> $resolved"

# ---------------------------------------------------------------------------
step "Inventory and playbook"
# ---------------------------------------------------------------------------
command -v ansible-playbook >/dev/null 2>&1 || fail \
  "ansible-playbook not found in PATH. Install it, e.g. pipx install --include-deps ansible"

# Ansible reads ansible.cfg from the current working directory, and this script
# runs from its own - so infrastructure/ansible/ansible.cfg was being ignored
# entirely. Naming it here restores everything it declares at once:
# host_key_checking (without which the first connection stops on an interactive
# prompt and the play dies with "Broken pipe"), remote_user, pipelining and the
# ssh_args that keep the connection alive between tasks.
export ANSIBLE_CONFIG="$ansible_dir/ansible.cfg"

# Still set separately, and absolute. ansible.cfg declares
# `roles_path = ./roles:./roles_external`, and those are relative - to a working
# directory that is not the one they were written for. An absolute path removes
# the question.
export ANSIBLE_ROLES_PATH="$ansible_dir/roles_external"

# Reported, not installed. Fetching from Galaxy would mean this script reaches
# out to the network and writes files nobody asked it to write; naming the
# command keeps the side effects where the operator can see them.
[ -d "$ANSIBLE_ROLES_PATH/geerlingguy.docker" ] || fail \
"Galaxy dependencies are missing. Install them once:

    cd $ansible_dir
    ansible-galaxy install -r requirements.yml -p roles_external
    ansible-galaxy collection install -r requirements.yml"

# The hostname rather than the raw address, deliberately - see the note in
# inventory-forgejo.sh. The preflight above has already confirmed it resolves
# to this environment's VM, so nothing is lost by using it.
"$ansible_dir/inventory-forgejo.sh" "$hostname" >/dev/null

# The playbook reads the .env content from this variable rather than a path, so
# the file here stays the single source of truth. In a CI-driven setup the same
# variable comes from a secret instead.
FORGEJO_ENV_FILE="$(cat "$env_file")" \
ansible-playbook -i "$ansible_dir/inventory.forgejo.ini" \
  --private-key "$ssh_key" "$ansible_dir/forgejo.yml"

# ---------------------------------------------------------------------------
step "Admin account"
# ---------------------------------------------------------------------------
# -u 1000 because Forgejo refuses to run its CLI as root and `exec` defaults to
# it. Without this the command fails with a message about privileged ports that
# has nothing to do with the actual problem.
fj() { remote "cd forgejo && docker compose exec -T -u 1000 forgejo forgejo $*"; }

if fj admin user list 2>/dev/null | tail -n +2 | grep -q .; then
  echo "    accounts already exist - skipping"
else
  echo "    no account exists yet; registration is disabled, so create one here."
  read -r -p "    username: " admin_user
  read -r -p "    email:    " admin_mail
  read -r -s -p "    initial password: " admin_pass; echo
  [ -n "$admin_user" ] && [ -n "$admin_mail" ] && [ -n "$admin_pass" ] \
    || fail "username, email and password are all required"

  # --must-change-password so the value typed here does not stay in effect, and
  # --admin because an instance whose only account is unprivileged cannot be
  # administered at all.
  fj admin user create --username "$admin_user" --email "$admin_mail" \
     --password "'$admin_pass'" --admin --must-change-password
  echo "    created $admin_user (must change password at first login)"
fi

# ---------------------------------------------------------------------------
step "Runner"
# ---------------------------------------------------------------------------
if [ -n "$(read_env FORGEJO_RUNNER_TOKEN)" ]; then
  echo "    token already in .env - skipping issuance"
else
  token=$(fj actions generate-runner-token | tr -d '\r\n')
  [ -n "$token" ] || fail "generate-runner-token produced nothing"

  # Written back to the local .env because that file is what the playbook
  # deploys. Leaving the token only on the VM would mean the next playbook run
  # overwrites it and the runner silently de-registers.
  if grep -qE '^FORGEJO_RUNNER_TOKEN=' "$env_file"; then
    tmp=$(mktemp)
    sed "s|^FORGEJO_RUNNER_TOKEN=.*|FORGEJO_RUNNER_TOKEN=$token|" "$env_file" > "$tmp"
    mv "$tmp" "$env_file"
  else
    printf 'FORGEJO_RUNNER_TOKEN=%s\n' "$token" >> "$env_file"
  fi
  chmod 600 "$env_file"
  echo "    token issued and written to .env"

  remote "cat > forgejo/.env && chmod 600 forgejo/.env" < "$env_file"
fi

remote "cd forgejo && docker compose --profile tls up -d runner" >/dev/null
echo "    runner started"

# ---------------------------------------------------------------------------
step "Verify"
# ---------------------------------------------------------------------------
remote "cd forgejo && docker compose ps --format '    {{.Service}}\t{{.State}}'"

code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 "$root_url" || echo000)
echo "    GET $root_url -> $code"

if [ "$code" != "200" ]; then
  cat >&2 <<EOF

    Not serving yet. The usual causes, in order of likelihood:
      - Caddy is still obtaining the certificate; give it a minute, then
        ssh ubuntu@$ip 'docker logs forgejo-caddy --tail 30'
      - you are not on the campus network or VPN; 80 and 443 are restricted
        to it by envs/forgejo/security_group.tf
EOF
  exit 1
fi

cat <<EOF

==> Done. $root_url is serving.

Remaining, in the web UI:
  - push the deployment repo to this instance
  - add the six workflow secrets under Settings -> Actions -> Secrets
  - create further accounts; give at least two people the admin flag, so a
    lost password does not mean going into the container
EOF
