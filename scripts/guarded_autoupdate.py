#!/usr/bin/env python3
"""Experimental guarded image updater. Not installed or invoked automatically.

Requires the experimental backend maintenance gate to be deployed first and a
separately coordinated platform workflow. Refuses schema-changing upgrades.
"""
from __future__ import annotations

import os
import importlib.util
import re
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

SERVICES = ("backend", "worker", "frontend")
CONTAINERS = {"backend": "backend-prod", "worker": "worker-prod", "frontend": "frontend-prod"}
IMAGE_ID = re.compile(r"sha256:[a-f0-9]{64}\Z")
REVISION = re.compile(r"[a-f0-9]{12,64}\Z")


class UpdateError(Exception):
    pass


def run(args, *, stdin=None):
    """Keep stderr private: Docker and database errors may include credentials."""
    proc = subprocess.run(args, input=stdin, text=True, capture_output=True, check=False)
    if proc.returncode:
        raise UpdateError("A Docker or maintenance operation failed; inspect private diagnostics.")
    return proc.stdout.strip()


class Docker:
    def __init__(self, root: Path, compose_file: str):
        self.root = root
        self.compose_file = compose_file

    def compose(self, *args):
        return run(["docker", "compose", "--project-directory", str(self.root),
                    "-f", str(self.root / self.compose_file), *args])

    def login(self, token, username):
        run(["docker", "login", "ghcr.io", "--username", username, "--password-stdin"], stdin=token)

    def logout(self):
        subprocess.run(["docker", "logout", "ghcr.io"], capture_output=True, check=False)

    def running_image(self, service):
        result = run(["docker", "inspect", "--format", "{{.Image}}", CONTAINERS[service]])
        if not IMAGE_ID.fullmatch(result):
            raise UpdateError(f"Cannot identify current {service} image")
        return result

    def pull_candidate(self, service):
        ref = self.compose("config", "--images", service).splitlines()
        if len(ref) != 1 or not ref[0].startswith("ghcr.io/"):
            raise UpdateError(f"Invalid image configuration for {service}")
        run(["docker", "pull", "--quiet", ref[0]])
        result = run(["docker", "image", "inspect", "--format", "{{.Id}}", ref[0]])
        if not IMAGE_ID.fullmatch(result):
            raise UpdateError(f"Cannot identify candidate {service} image")
        return result

    def maintenance(self, operation, owner, timeout=600):
        run(["docker", "exec", CONTAINERS["backend"], "python", "-m",
             "app.services.maintenance_control", operation, "--owner", owner, "--timeout", str(timeout)])

    def workers_and_broker_idle(self):
        run(["docker", "exec", CONTAINERS["backend"], "python", "-m",
             "app.services.maintenance_control", "verify-workers"])
        counts = run(["docker", "exec", "rabbitmq-prod", "sh", "-c",
                      'exec rabbitmqctl list_queues -q -p "$RABBITMQ_DEFAULT_VHOST" '
                      'name messages_ready messages_unacknowledged'])
        spec = importlib.util.spec_from_file_location("check_broker_queues", Path(__file__).with_name("check_broker_queues.py"))
        checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(checker)
        if not checker.is_idle(counts):
            raise UpdateError("Broker queues are busy or could not be checked.")

    def schema_matches(self, candidate):
        db_command = (
            "from app.database import engine; from alembic.runtime.migration import MigrationContext; "
            "c=engine.connect(); print(','.join(sorted(MigrationContext.configure(c).get_current_heads()))); c.close()"
        )
        image_command = (
            "from alembic.config import Config; from alembic.script import ScriptDirectory; "
            "print(','.join(sorted(ScriptDirectory.from_config(Config('alembic.ini')).get_heads())))"
        )
        current = run(["docker", "exec", CONTAINERS["backend"], "python", "-c", db_command])
        candidate_heads = run(["docker", "run", "--rm", "--network", "none", "--entrypoint", "python",
                               candidate, "-c", image_command])
        return (current == candidate_heads and current != "" and
                all(REVISION.fullmatch(revision) for revision in current.split(",")))

    def candidate_supports_gate(self, candidate):
        try:
            run(["docker", "run", "--rm", "--network", "none", "--entrypoint", "python", candidate,
                 "-c", "import importlib.util,sys; sys.exit(importlib.util.find_spec('app.services.maintenance_control') is None)"])
            return True
        except UpdateError:
            return False

    def apply(self, images):
        # Compose override pins the actual image IDs, not mutable branch tags.
        contents = "services:\n" + "".join(
            f"  {name}:\n    image: {image}\n    pull_policy: never\n" for name, image in images.items()
        )
        fd, path = tempfile.mkstemp(prefix="appstore-images-", suffix=".yml")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as override:
                override.write(contents)
            run(["docker", "compose", "--project-directory", str(self.root),
                 "-f", str(self.root / self.compose_file), "-f", path,
                 "up", "-d", "--no-deps", "--no-build", *images.keys()])
        finally:
            Path(path).unlink(missing_ok=True)

    def diagnostics(self, services):
        result = {}
        for service in services:
            proc = subprocess.run(
                ["docker", "inspect", "--format", "{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}",
                 CONTAINERS[service]], capture_output=True, text=True, check=False,
            )
            fields = proc.stdout.strip().split()
            safe = {"created", "running", "restarting", "exited", "dead", "healthy", "unhealthy", "starting"}
            result[service] = " ".join(fields) if fields and all(f in safe for f in fields) else "unavailable"
        return result

    def healthy(self, services, timeout=90):
        end = time.monotonic() + timeout
        consecutive = 0
        while time.monotonic() < end:
            statuses = self.diagnostics(set(services) | {"backend"})
            if all(status == "running" or status == "running healthy" for status in statuses.values()):
                # Backend has a configured healthcheck; a plain running state is insufficient.
                if statuses.get("backend") == "running healthy":
                    consecutive += 1
                    if consecutive >= 3:
                        return True
                else:
                    consecutive = 0
            else:
                consecutive = 0
            time.sleep(2)
        return False


def update(docker: Docker, *, drain_timeout=600, registry_credentials=None):
    owner = str(uuid.uuid4())
    docker.maintenance("begin", owner, drain_timeout)
    release_safe = True
    logged_in = False
    try:
        docker.workers_and_broker_idle()
        # Do not touch the VM's shared Docker credential store while a full
        # platform deployment owns the gate and is pulling images via Ansible.
        if registry_credentials is not None:
            docker.login(*registry_credentials)
            logged_in = True
        # Pulling also changes local mutable tags. Keep it under the shared
        # gate so it cannot race with the platform workflow's compose pull/up.
        old = {service: docker.running_image(service) for service in SERVICES}
        new = {service: docker.pull_candidate(service) for service in SERVICES}
        changed = {service: new[service] for service in SERVICES if old[service] != new[service]}
        if not changed:
            return "unchanged"
        if not docker.candidate_supports_gate(new["backend"]):
            raise UpdateError("Candidate backend lacks the maintenance gate; rollout is not safe.")
        # Check under the gate: another platform update must not migrate the
        # database between this check and the container switch.
        if not docker.schema_matches(new["backend"]):
            raise UpdateError("Database migration required; automatic update is blocked.")
        # No state is assumed after 'up' starts, even if Docker reports failure.
        release_safe = False
        try:
            docker.apply(changed)
            if not docker.healthy(changed):
                raise UpdateError("Candidate services did not become healthy.")
        except UpdateError:
            print(f"Update failed; safe status: {docker.diagnostics(changed)}", file=sys.stderr)
            try:
                docker.apply({service: old[service] for service in changed})
                if not docker.healthy(changed):
                    raise UpdateError("Rollback services did not become healthy.")
            except UpdateError:
                raise UpdateError("Rollback failed; maintenance stays enabled for manual recovery.") from None
            release_safe = True
            return "rolled_back"
        release_safe = True
        return "updated"
    finally:
        if logged_in:
            docker.logout()
        if release_safe:
            docker.maintenance("end", owner)


def main():
    token = os.getenv("GIT_ACCESS_TOKEN", "")
    if not token:
        raise UpdateError("GIT_ACCESS_TOKEN is required")
    root = Path(os.getenv("PROJECT_ROOT", "/home/ubuntu/app"))
    docker = Docker(root, os.getenv("COMPOSE_FILE", "docker-compose.staging.yml"))
    result = update(docker, registry_credentials=(token, os.getenv("GIT_USER", "x-access-token")))
    print(f"Guarded update: {result}")
    return 1 if result == "rolled_back" else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except UpdateError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
