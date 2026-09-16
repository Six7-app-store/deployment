#!/usr/bin/env bash
# Phase 2, part one: build the VM that will host Forgejo.
#
# Stops there on purpose. The DNS record and the TSIG key have to exist before
# the stack starts — Caddy proves control of the name over dns-01, and
# FORGEJO_ROOT_URL is written into the database on first start, so getting it
# wrong is expensive to undo. Both come from systems this script cannot reach.
#
# Continue with 02-configure.sh once those are in place; it checks for all of
# them before it touches anything.
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
env_dir="$here/../infrastructure/terraform/envs/forgejo"

fail() { echo "error: $*" >&2; exit 1; }

command -v terraform >/dev/null || fail "terraform not found in PATH"

# Checked before the apply rather than during it: the public key becomes an
# OpenStack keypair, and discovering it is missing after the security group
# already exists means a partial apply to clean up.
[ -n "${TF_VAR_ssh_public_key:-}" ] || fail \
  'TF_VAR_ssh_public_key is not set. Try: export TF_VAR_ssh_public_key="$(cat ~/.ssh/<key>.pub)"'

# Two ways to authenticate, and the provider accepts either:
#
#   OS_CLOUD=<name>  read that entry from clouds.yaml - the same mechanism as
#                    `openstack --os-cloud <name>`. What an operator uses.
#   OS_AUTH_URL=...  plus credentials, all in the environment. What CI uses,
#                    because a workflow has secrets rather than a clouds.yaml.
#
# .secrets is not a third way: its keys carry a STAGING_ prefix because they are
# GitHub secret names, and the workflow maps them to OS_*. Sourcing it directly
# leaves the provider without credentials.
if [ -n "${OS_CLOUD:-}" ]; then
  :
elif [ -n "${OS_AUTH_URL:-}" ]; then
  [ -n "${OS_APPLICATION_CREDENTIAL_ID:-}${OS_USERNAME:-}" ] || fail \
    "OS_AUTH_URL is set but no credentials (OS_APPLICATION_CREDENTIAL_ID or OS_USERNAME)"
else
  fail "no OpenStack credentials. Either export OS_CLOUD=<name from clouds.yaml>, or OS_AUTH_URL plus credentials."
fi

echo "==> terraform init"
terraform -chdir="$env_dir" init -input=false

# Plan to a file, then apply that file — the same shape as the staging
# workflow, and safer than -auto-approve: what gets applied is the plan you
# just read, not one recalculated afterwards.
#
# `terraform apply` on its own would prompt, but its prompt reads standard
# input, and a script's standard input is not necessarily the terminal. When it
# is not, Terraform sees end-of-file immediately and answers itself:
#
#     Enter a value:
#     Apply cancelled.
#
# which looks like a refusal but is really a missing terminal. Asking through
# /dev/tty below sidesteps that, because /dev/tty is the controlling terminal
# regardless of how standard input was wired up.
echo "==> terraform plan"
terraform -chdir="$env_dir" plan -input=false -out=tfplan

if [ "${CONFIRM:-}" = "yes" ]; then
  answer=yes
elif [ -r /dev/tty ]; then
  printf '\nApply this plan? Only "yes" will be accepted: ' > /dev/tty
  read -r answer < /dev/tty
else
  # No controlling terminal at all — a cron job, a CI step, a pipeline. Refuse
  # rather than guess, and name the flag that makes it deliberate.
  fail "no terminal to confirm on. Re-run with CONFIRM=yes to apply unattended."
fi

[ "$answer" = "yes" ] || fail "not confirmed - nothing was applied (the plan is in $env_dir/tfplan)"

echo "==> terraform apply"
terraform -chdir="$env_dir" apply tfplan

ip=$(terraform -chdir="$env_dir" output -raw vm_ip)
[ -n "$ip" ] || fail "apply finished but vm_ip is empty"

cat <<EOF

==> VM is up at: $ip

Next, by hand:

  1. Point an AAAA record at that address. (envs/forgejo defaults to DHBWV6 /
     fixed_ipv6, so it is IPv6; use an A record if you changed connect_via.)

  2. Fetch the zone's TSIG key from the TLS certificates page in the
     self-service UI.

  3. Fill in $here/.env — copy .env.example if it does not exist:
       FORGEJO_ROOT_URL   https://<hostname>/
       FORGEJO_HOSTNAME   <hostname>, no scheme, must match the line above
       ACME_EMAIL         contact address for the ACME account
       DNS_TSIG_KEY_NAME  from step 2
       DNS_TSIG_KEY       from step 2

Then: ./02-configure.sh

Keep $env_dir/terraform.tfstate.
It is not in git and exists only here; without it Terraform can no longer
manage this VM, and the next apply builds a second one beside it.
EOF
