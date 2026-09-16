# Running the two setup scripts

`01-create-vm.sh` builds the VM. `02-configure.sh` takes it from there to a
running Forgejo with a registered runner. The gap between them is where DNS and
the certificate credentials have to be arranged by hand.

Both are re-runnable and both stop with a message rather than doing half a job.

## Before you start

```bash
export OS_CLOUD=newstack                                  # entry in ~/.config/openstack/clouds.yaml
export TF_VAR_ssh_public_key="$(cat ~/.ssh/<key>.pub)"
```

`OS_CLOUD` is the same mechanism as `openstack --os-cloud newstack`: if the CLI
works, so does Terraform. In CI the credentials come from secrets as `OS_*`
variables instead — the scripts accept either.

**Note which key you pick.** Script 1 registers its public half as the VM's
OpenStack keypair; script 3 logs in with the private half and needs to be told
where it is:

```bash
export TF_VAR_ssh_public_key="$(cat ~/.ssh/openstack-key.pub)"   # step 1
SSH_KEY=~/.ssh/openstack-key ./02-configure.sh                   # step 3
```

Two different keys means step 3 cannot get in, and the error — `cannot reach
ubuntu@… over SSH` — points at the network rather than at the mismatch.
`SSH_KEY` defaults to `~/.ssh/id_ed25519`, which is almost certainly not the
one you used.

> The `.secrets` file is here not a substitute. Its keys carry a `STAGING_` prefix

## 1. Build the VM

```bash
cd deployment/forgejo
./01-create-vm.sh
```

Writes a Terraform plan, shows it, and asks before applying it. Read it once —
it should be 12 resources: the instance, a keypair, a 50 GB volume with its
attachment, the security group and its rules. Only `yes` is accepted. The VM's
address is printed at the end.

What gets applied is the saved plan, not one recalculated afterwards, so what
you approved is what runs.

The question is asked on `/dev/tty` rather than standard input, so it works no
matter how the script was started. Where there is no terminal at all — a cron
job, a CI step — it refuses instead of guessing; `CONFIRM=yes ./01-create-vm.sh`
is the deliberate way to apply unattended.

Keep `infrastructure/terraform/envs/forgejo/terraform.tfstate`. It is not in
git and exists only on the  machine where it is started.

## 2. By hand, between the two

1. Point an **AAAA** record at the address from step 1.
2. Fetch the zone's TSIG key from the TLS certificates page in the
   self-service UI.
3. Fill in `.env` — copy `.env.example` if it does not exist yet:

```bash
FORGEJO_ROOT_URL=https://<hostname>/
FORGEJO_HOSTNAME=<hostname>          # no scheme; must match the line above
ACME_EMAIL=<contact address>
DNS_TSIG_KEY_NAME=<from step 2>
DNS_TSIG_KEY=<from step 2>
FORGEJO_RUNNER_TOKEN=                # leave empty, script 2 issues one
```

`FORGEJO_ROOT_URL` has to be right before the first start: Forgejo stores it in
clone URLs and webhooks, and correcting it later means chasing it through the
database.

## 3. Configure

```bash
SSH_KEY=~/.ssh/<key> ./02-configure.sh
```

Checks the `.env`, that the hostname resolves and that SSH works, then runs the
playbook, creates the first account if the instance is empty, issues a runner
token and starts the runner. Ends with the HTTP status of the site.

## 4. Point your checkout at the new instance

Per-developer, and easy to overlook because nothing complains: pushes keep
going wherever the remote already pointed.

```bash
cd deployment
git remote set-url forgejo https://<hostname>/<org>/deployment.git
```

This edits `.git/config` in your working copy only. It does not touch GitHub,
it leaves the `origin` remote alone, and it is invisible to anyone else's
clone — remotes are per-checkout, never part of the repository's contents.

Coming from the Phase 1 setup, two things change at once: the host (the local
instance reachable as `forgejo:3000` via `/etc/hosts`, versus the VM) and the
path (a personal account, versus the organisation the repository was
transferred to).

The first push asks for credentials. Forgejo does not accept account passwords
over HTTPS — create an access token under **Settings → Applications** and use
that in place of the password.

Once everything is verified, the Phase 1 stack can be retired:

```bash
cd deployment/forgejo && docker compose down
```

Without `-v`, so the volumes survive. Keep them until you are sure nothing was
left behind; `docker compose down -v` is the irreversible step.

## 5. Optional: make the host reachable over IPv4

The VM sits on DHBWV6, so it answers only over IPv6 — from a network without
it, the forge is simply unreachable. `03-add-ipv4.sh` attaches a second
interface on DHBWv4 and configures it:

```bash
cd deployment/forgejo
export OS_CLOUD=newstack
SSH_KEY=~/.ssh/<key> ./03-add-ipv4.sh
```

`OS_CLOUD` names an entry in `~/.config/openstack/clouds.yaml`. If you have
several and are unsure which project holds this VM, ask before applying —
credentials for the wrong project make Terraform miss the resources in the
state and plan to build a second VM beside the first:

```bash
openstack --os-cloud newstack server show ci-dhbw-appstore
```

It takes the public key from the Terraform state rather than the environment,
because a key that differs even in its comment would queue the VM for
replacement.

**What the plan should say.** Two resources to add — the port and the interface
attachment — and `0 to destroy`. The script reads the plan back before applying
it and stops on anything that would be destroyed or replaced, so a bad plan
never reaches the confirmation prompt.

That check guards the assumption the whole approach rests on: the interface is
attached to the running VM rather than added as a second `network` block, which
is what would force a rebuild. If the script does stop there, keep the output —
the assumption did not hold, and nothing has been changed yet.

Ansible runs with `--tags network`, so only the two netplan tasks execute; the
compose stack is not touched and the forge keeps running.

Afterwards, add an **A** record for the same hostname next to the existing AAAA
one. Both belong to the same name and clients pick whichever family they have.
The certificate needs no attention — dns-01 does not care how the host is
reachable.

## If it stops

The message names the cause. The three that come up most:

| Message | Meaning |
|---|---|
| `no OpenStack credentials` | neither `OS_CLOUD` nor `OS_AUTH_URL` is exported |
| `not confirmed - nothing was applied` | the prompt got something other than `yes` |
| `<host> does not resolve` | the DNS record from step 2.1 is missing or has not propagated |
| `cannot reach ubuntu@… over SSH` | wrong `SSH_KEY`, or you are not on the campus network |
| `FORGEJO_ROOT_URL is still the local Phase 1 value` | `.env` was not switched over in step 2.3 |
| `this plan destroys or replaces resources` | step 5 only. Do not work around it — post the plan instead |
| `could not read the public key from state` | step 5 only. Export `TF_VAR_ssh_public_key` with the key the VM was built with |

Re-running after a fix is safe: the playbook is idempotent, the account is only
created when none exists, and the token is only issued when `.env` has none.
