"""Operate only a uniquely named local Compose project for this experiment."""
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from gate import Gate

ROOT = Path(__file__).resolve().parent.parent


class Controller:
    def __init__(self, project):
        if not re.fullmatch(r"deployexperiment[0-9a-f]{12}", project):
            raise ValueError("Only a uniquely named experiment project is allowed")
        self.project = project

    def compose(self, *args, mode=None, check=True):
        env = os.environ.copy()
        env["APP_IMAGE"] = f"{self.project}:{mode or 'v1'}"
        # Explicit project + file: never target the developer's existing stacks.
        cmd = ["docker", "compose", "-p", self.project, "-f", str(ROOT / "compose.yaml"), *args]
        return subprocess.run(cmd, cwd=ROOT, env=env, check=check, capture_output=True, text=True)

    def port(self, service, internal):
        value = self.compose("port", service, str(internal)).stdout.strip()
        if not value.startswith("127.0.0.1:"):
            raise RuntimeError("Experiment port is not bound to localhost")
        return int(value.rsplit(":", 1)[1])

    def gate(self):
        return Gate("127.0.0.1", self.port("gate", 6379))

    def app_image_id(self):
        container_id = self.compose("ps", "-q", "app").stdout.strip()
        if not re.fullmatch(r"[0-9a-f]{12,64}", container_id):
            raise RuntimeError("No experiment app container")
        return subprocess.run(
            ["docker", "inspect", "--format", "{{.Image}}", container_id],
            check=True, capture_output=True, text=True,
        ).stdout.strip()

    def health(self):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{self.port('app', 8080)}/health", timeout=1) as res:
                return res.status == 200, json.loads(res.read())["version"]
        except (urllib.error.URLError, OSError, ValueError, KeyError, subprocess.SubprocessError):
            return False, None

    def wait_health(self, expected, timeout):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            healthy, version = self.health()
            if healthy and version == expected:
                return True
            time.sleep(.2)
        return False

    def diagnostics(self):
        # Strict allow-list: no raw Docker logs, env vars, command lines or exception text.
        states = []
        for service in ("gate", "app"):
            result = self.compose("ps", "-q", service, check=False)
            container_id = result.stdout.strip()
            if result.returncode or not re.fullmatch(r"[0-9a-f]{12,64}", container_id):
                states.append(f"{service}: unavailable")
                continue
            info = subprocess.run(
                ["docker", "inspect", "--format", "{{.State.Status}}", container_id],
                capture_output=True, text=True, check=False,
            )
            state = info.stdout.strip()
            if state not in {"created", "restarting", "running", "removing", "paused", "exited", "dead"}:
                state = "unavailable"
            states.append(f"{service}: {state}")
        return {"containers": states, "health": "healthy" if self.health()[0] else "unhealthy"}

    def update(self, old, new, drain_timeout=2, health_timeout=2):
        if old not in {"v1", "v2"} or new not in {"v1", "v2", "broken"}:
            raise ValueError("Unknown local test mode")
        if not self.wait_health(old, health_timeout):
            raise RuntimeError("Previous version is not healthy")
        gate = self.gate()
        owner = str(uuid.uuid4())
        if gate.begin(owner) != 1:
            return {"status": "busy"}
        safe_to_release = True
        try:
            deadline = time.monotonic() + drain_timeout
            while gate.count() > 0:
                if time.monotonic() >= deadline:
                    return {"status": "active_tasks", "diagnostics": self.diagnostics()}
                time.sleep(.1)
            self.compose("up", "-d", "--no-deps", "app", mode=new)
            if self.wait_health(new, health_timeout):
                return {"status": "updated", "version": new}
            diagnosis = self.diagnostics()
            self.compose("up", "-d", "--no-deps", "app", mode=old)
            if self.wait_health(old, health_timeout):
                return {"status": "rolled_back", "version": old, "diagnostics": diagnosis}
            safe_to_release = False
            return {"status": "rollback_failed", "diagnostics": self.diagnostics()}
        except Exception:
            # Unknown state: retain maintenance; explicit recovery is needed.
            safe_to_release = False
            raise
        finally:
            if safe_to_release and gate.release(owner) != 1:
                raise RuntimeError("Maintenance gate ownership lost")
