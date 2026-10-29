"""Exercise real update orchestration with an isolated fake Docker adapter."""
import importlib.util
import json
import unittest
import subprocess
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch

path = Path(__file__).resolve().parents[2] / "scripts" / "guarded_autoupdate.py"
spec = importlib.util.spec_from_file_location("guarded_autoupdate", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FakeDocker:
    def __init__(self):
        self.old = {name: f"old-{name}" for name in module.SERVICES}
        self.new = {name: f"new-{name}" for name in module.SERVICES}
        self.calls = []
        self.owner = None
        self.schema_ok = True
        self.gate_supported = True
        self.health = [True]
        self.fail_apply = False

    def running_image(self, service):
        return self.old[service]

    def pull_candidate(self, service):
        return self.new[service]

    def login(self, token, username):
        self.calls.append(("login", username))

    def logout(self):
        self.calls.append(("logout", None))

    def workers_and_broker_idle(self):
        self.calls.append(("verify-idle", None))

    def candidate_supports_gate(self, image):
        return self.gate_supported

    def schema_matches(self, image):
        assert self.owner is not None
        return self.schema_ok

    def maintenance(self, op, owner, timeout=600):
        self.calls.append((op, owner))
        if op == "begin":
            self.owner = owner
        else:
            assert owner == self.owner
            self.owner = None

    def apply(self, images):
        self.calls.append(("apply", images.copy()))
        if self.fail_apply:
            raise module.UpdateError("simulated")

    def healthy(self, services):
        return self.health.pop(0)

    def diagnostics(self, services):
        return {name: "running" for name in services}


class GuardedUpdateTests(unittest.TestCase):
    def setUp(self):
        self.docker = FakeDocker()

    def test_success_pins_images_and_releases_gate(self):
        self.assertEqual(module.update(self.docker), "updated")
        self.assertEqual([call[0] for call in self.docker.calls], ["begin", "verify-idle", "apply", "end"])
        self.assertEqual(self.docker.calls[2][1], self.docker.new)
        self.assertIsNone(self.docker.owner)

    def test_broken_update_restores_prior_image_ids(self):
        self.docker.health = [False, True]
        self.assertEqual(module.update(self.docker), "rolled_back")
        self.assertEqual(self.docker.calls[3], ("apply", self.docker.old))
        self.assertIsNone(self.docker.owner)

    def test_failed_rollback_keeps_gate_closed(self):
        self.docker.health = [False, False]
        with self.assertRaisesRegex(module.UpdateError, "Rollback failed"):
            module.update(self.docker)
        self.assertIsNotNone(self.docker.owner)
        self.assertNotIn("end", [call[0] for call in self.docker.calls])

    def test_schema_change_does_not_switch_images(self):
        self.docker.schema_ok = False
        with self.assertRaisesRegex(module.UpdateError, "migration required"):
            module.update(self.docker)
        self.assertEqual([call[0] for call in self.docker.calls], ["begin", "verify-idle", "end"])

    def test_unmodified_running_images_release_maintenance(self):
        self.docker.new = self.docker.old.copy()
        self.assertEqual(module.update(self.docker), "unchanged")
        self.assertEqual([call[0] for call in self.docker.calls], ["begin", "verify-idle", "end"])

    def test_candidate_without_gate_is_refused_and_maintenance_released(self):
        self.docker.gate_supported = False
        with self.assertRaisesRegex(module.UpdateError, "lacks the maintenance gate"):
            module.update(self.docker)
        self.assertEqual([call[0] for call in self.docker.calls], ["begin", "verify-idle", "end"])

    def test_registry_login_and_logout_happen_inside_gate(self):
        self.assertEqual(module.update(self.docker, registry_credentials=("secret", "tester")), "updated")
        self.assertEqual(
            [call[0] for call in self.docker.calls], ["begin", "verify-idle", "login", "apply", "logout", "end"]
        )


class RealComposePinTests(unittest.TestCase):
    def test_candidate_ignores_compose_dependency_images(self):
        project = "guardedconfig" + uuid.uuid4().hex[:12]
        with tempfile.TemporaryDirectory(prefix=project) as folder:
            root = Path(folder) / project
            root.mkdir()
            (root / "compose.yaml").write_text(
                "services:\n  backend:\n    image: ghcr.io/example/backend:dev\n"
                "    depends_on: [redis]\n  redis:\n    image: redis:7-alpine\n",
                encoding="utf-8",
            )
            docker = module.Docker(root, "compose.yaml")
            config = json.loads(docker.compose("config", "--format", "json", "backend"))
            self.assertIn("redis", config["services"])
            self.assertEqual(config["services"]["backend"]["image"], "ghcr.io/example/backend:dev")
            image_id = "sha256:" + "a" * 64
            with patch.object(module, "run", side_effect=["", image_id]) as run_mock:
                with patch.object(docker, "compose", return_value=json.dumps(config)):
                    self.assertEqual(docker.pull_candidate("backend"), image_id)
            self.assertEqual(run_mock.call_args_list[0].args[0][-1], "ghcr.io/example/backend:dev")

    def test_compose_switches_and_restores_exact_image_id(self):
        project = "guardedpin" + uuid.uuid4().hex[:12]
        with tempfile.TemporaryDirectory(prefix=project) as folder:
            root = Path(folder) / project
            root.mkdir()
            (root / "compose.yaml").write_text(
                "services:\n  backend:\n    image: python:3.11-alpine\n"
                "    command: ['python', '-c', 'import time; time.sleep(300)']\n",
                encoding="utf-8",
            )
            compose = ["docker", "compose", "-p", project, "-f", str(root / "compose.yaml")]
            docker = module.Docker(root, "compose.yaml")
            try:
                subprocess.run(compose + ["up", "-d", "--no-build"], check=True, capture_output=True)
                old = subprocess.check_output(
                    ["docker", "image", "inspect", "--format", "{{.Id}}", "python:3.11-alpine"],
                    text=True,
                ).strip()
                new = subprocess.check_output(
                    ["docker", "image", "inspect", "--format", "{{.Id}}", "python:3.14-slim"],
                    text=True,
                ).strip()
                self.assertNotEqual(old, new)
                docker.apply({"backend": new})
                container = subprocess.check_output(compose + ["ps", "-q", "backend"], text=True).strip()
                running = subprocess.check_output(
                    ["docker", "inspect", "--format", "{{.Image}}", container], text=True,
                ).strip()
                self.assertEqual(running, new)
                docker.apply({"backend": old})
                container = subprocess.check_output(compose + ["ps", "-q", "backend"], text=True).strip()
                running = subprocess.check_output(
                    ["docker", "inspect", "--format", "{{.Image}}", container], text=True,
                ).strip()
                self.assertEqual(running, old)
            finally:
                subprocess.run(compose + ["down", "--remove-orphans"], check=False, capture_output=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
