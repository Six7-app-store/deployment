# Forgejo deploy stack — Phase 1 (local)

Goal of this phase: prove the staging workflow runs under Forgejo Actions
**before** spending OpenStack quota on a Forgejo VM. The riskiest part of the
whole migration is Actions compatibility, and it costs nothing to find out here.

Topology (per the decision made): **GitHub stays primary.** Forgejo pull-mirrors
`DHBW-AppStore/deployment` and contributes only the runner and the secrets. No
code review moves.

```
GitHub (public, unchanged)          Forgejo (local Docker, Phase 1)
  deployment  ──── pull-mirror ────►  deployment (read-only mirror)
  .forgejo/workflows/staging.yml         └─ runs on the `deploy` runner
  .github/workflows/*  (unchanged)          secrets: OS_*, SSH_PRIVATE_KEY,
                                                     STAGING_ENV_FILE
```

Because a pull-mirror is **read-only in Forgejo**, every file it executes has to
arrive through the mirror — so `.forgejo/workflows/staging.yml` gets committed to
the **GitHub** repo. That is a feature here: the deploy definition stays publicly
reviewable, which is worth keeping for grading.

## Layout

| Path | What it is |
|---|---|
| `docker-compose.yml` | Forgejo + Postgres + runner |
| `.env.example` | instance config (not deploy secrets) |
| `runner/config.yml` | runner labels, job network, tfstate volume |
| `runner/entrypoint.sh` | register-once-then-daemon wrapper |
| `job-image/Dockerfile` | image jobs execute in — terraform, ansible, trivy pre-baked |
| `../.forgejo/workflows/staging.yml` | the deploy workflow Forgejo runs (repo root, not here) |

## Setup

### 1. Hostname

```bash
echo '127.0.0.1 forgejo' | sudo tee -a /etc/hosts
```

This is what lets `http://forgejo:3000/` work from **both** your browser and job
containers. Skipping it is the most likely cause of `actions/checkout` failing
with a connection error.

### 2. Configure

```bash
cp .env.example .env
# set FORGEJO_DB_PASSWORD to anything strong; leave FORGEJO_RUNNER_TOKEN empty for now
```

### 3. Start Forgejo

```bash
docker compose up -d db forgejo
```

Open <http://forgejo:3000>, complete the installer, create the admin account.
The database fields are already set via env — do not change them.

### 4. Build the job image

```bash
docker build -t forgejo-deploy-job:latest ./job-image
```

Takes a few minutes the first time. `requirements.yml` here is a copy of
`infrastructure/ansible/requirements.yml`; re-copy it if the pinned versions in
the repo change.

### 5. Register the runner

Site admin → **Actions → Runners → Create new runner**, copy the token into
`.env` as `FORGEJO_RUNNER_TOKEN`, then:

```bash
docker compose up -d runner
docker compose logs -f runner     # expect "registering runner" then "starting runner daemon"
```

The runner should appear as **Idle** with label `deploy` in the admin UI.

### 6. Mirror the repo

**+ → New Migration → GitHub**, URL
`https://github.com/DHBW-AppStore/deployment`, tick **"This repository will be a
mirror"**. No token needed while the repo is public.

Then in the mirrored repo: **Settings → Repository → enable Actions**.

### 7. Add the deploy secrets

Repo → **Settings → Actions → Secrets**:

| Secret | Source |
|---|---|
| `STAGING_OS_AUTH_URL` | OpenStack |
| `STAGING_OS_APPLICATION_CREDENTIAL_ID` | OpenStack |
| `STAGING_OS_APPLICATION_CREDENTIAL_SECRET` | OpenStack |
| `STAGING_OS_REGION_NAME` | OpenStack |
| `SSH_PRIVATE_KEY` | the deploy key, full PEM |
| `STAGING_ENV_FILE` | the whole staging `.env` |

Note `STAGING_ENV_FILE` is **missing from `deployment/.secrets.template`** in the
repo — worth adding there separately, it is a real gap.

### 8. Push the workflow to GitHub

`.forgejo/workflows/staging.yml` already exists in this repo — commit and push it
to GitHub, then hit **Synchronize now** on the Forgejo mirror. Forgejo can only
run files that arrive through the mirror, so it has to reach GitHub first.

### 9. Run it

Repo → **Actions → CD - Staging Deployment (Forgejo) → Run workflow**.

You must be on VPN for this phase — the runner is on your Mac, so Keystone is
still only reachable through the tunnel. Removing that constraint is what
Phase 2 is for.

## What to watch for

- **Both workflow sets may be picked up.** Forgejo reads `.forgejo/workflows/`
  and can also read `.github/workflows/`. If the GitHub `staging.yml` and
  `secret-scan.yml` show up in Forgejo's Actions tab, they will sit unassigned
  forever — no runner carries the `self-hosted` label. Harmless but noisy;
  check on the first sync.
- **The job image is built and verified** (terraform 1.9.8, ansible-core 2.17.14,
  trivy 0.73.0, node 20.20.2, git/rsync/ssh). `geerlingguy.docker` 7.1.0 resolves
  from `/opt/ansible-roles` even with the repo's `ansible.cfg` in scope, and
  `infrastructure/ansible/staging.yml` passes `--syntax-check` inside it. What is
  **not** yet proven is Forgejo actually dispatching a job into it — that needs
  steps 3–9 above.
- **`actions/upload-artifact@v3`, not v4.** v4 is known to misbehave on
  Gitea/Forgejo runners.
- **tfstate lives in the `tf-state` docker volume**, not in the repo. `docker
  compose down -v` destroys it and orphans the staging VM. Back it up before
  tearing anything down:
  ```bash
  docker run --rm -v tf-state:/s -v "$PWD":/out alpine \
    tar czf /out/tf-state-backup.tgz -C /s .
  ```

## Phase 2 (later)

Move Forgejo and the runner onto OpenStack VMs so deploys stop needing VPN.
The compose file transfers as-is; what changes is `FORGEJO_ROOT_URL` (real
hostname + TLS), a Terraform env for the two VMs, and a real backup story for
the Forgejo volume.
