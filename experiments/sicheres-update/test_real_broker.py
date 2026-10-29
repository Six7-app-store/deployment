"""Run RabbitMQ and Celery checks in their own uniquely named local project."""
import importlib.util
import json
import os
import subprocess
import time
import unittest
import uuid
from pathlib import Path

folder = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("queues", folder.parents[1] / "scripts" / "check_broker_queues.py")
queues = importlib.util.module_from_spec(spec)
spec.loader.exec_module(queues)


class BrokerIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project = "guardedbroker" + uuid.uuid4().hex[:12]
        info = json.loads(subprocess.check_output(["docker", "inspect", "backend-dev"]))[0]
        venv = next(m["Name"] for m in info["Mounts"] if m["Destination"] == "/app/.venv")
        cls.env = {**os.environ, "BACKEND_TEST_VENV": venv}
        cls.cmd = ["docker", "compose", "-p", cls.project, "-f", str(folder / "broker-test.yaml")]
        try:
            cls.run_compose("up", "-d", "worker", timeout=100)
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                if cls.probe_idle() == 0:
                    return
                time.sleep(1)
            raise RuntimeError("Test worker did not become responsive")
        except BaseException:
            cls.run_compose("down", "--remove-orphans", check=False, timeout=30)
            raise

    @classmethod
    def tearDownClass(cls):
        cls.run_compose("down", "--remove-orphans", timeout=30)

    @classmethod
    def run_compose(cls, *args, check=True, timeout=25):
        return subprocess.run(cls.cmd + list(args), env=cls.env, cwd=folder, check=check,
                              capture_output=True, text=True, timeout=timeout)

    @classmethod
    def probe_idle(cls):
        return cls.run_compose("run", "--rm", "probe", "/app/.venv/bin/python", "-m",
                               "app.services.maintenance_control", "verify-workers",
                               check=False, timeout=25).returncode

    def broker_idle(self):
        response = self.run_compose(
            "exec", "-T", "broker", "rabbitmqctl", "list_queues", "-q", "-p", "/",
            "name", "messages_ready", "messages_unacknowledged", timeout=25,
        )
        return queues.is_idle(response.stdout)

    def test_busy_celery_worker_and_unacknowledged_message_block(self):
        self.assertEqual(self.probe_idle(), 0)
        self.assertTrue(self.broker_idle())
        self.run_compose("exec", "-T", "worker", "/app/.venv/bin/python", "-c",
                         "from mini_worker import app; app.send_task('experiment.long_task')")
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if not self.broker_idle():
                break
            time.sleep(.2)
        self.assertFalse(self.broker_idle())
        self.assertNotEqual(self.probe_idle(), 0)
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if self.broker_idle() and self.probe_idle() == 0:
                break
            time.sleep(.5)
        self.assertTrue(self.broker_idle())
        self.assertEqual(self.probe_idle(), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
