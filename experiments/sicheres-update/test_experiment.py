"""Integration tests in disposable local Docker containers, never the live stack."""
import json
import subprocess
import sys
import threading
import time
import unittest
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "demo"))
from controller import Controller  # noqa: E402
from gate import Gate  # noqa: E402


class IsolatedUpdateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = Controller("deployexperiment" + uuid.uuid4().hex[:12])
        try:
            for mode in ("v1", "v2", "broken"):
                subprocess.run(
                    ["docker", "build", "--pull=false", "--build-arg", f"DEMO_MODE={mode}",
                     "-t", f"{cls.c.project}:{mode}", str(Path(__file__).resolve().parent)],
                    check=True, capture_output=True, text=True,
                )
            cls.c.compose("up", "-d", "--no-build", mode="v1")
            if not cls.c.wait_health("v1", 25):
                raise RuntimeError("Experiment application did not become healthy")
        except BaseException:
            cls.c.compose("down", "--remove-orphans", check=False)
            cls.remove_images()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.c.compose("down", "--remove-orphans", check=True)
        cls.remove_images()

    @classmethod
    def remove_images(cls):
        # Exact tags belonging to this unique test project, never a global prune.
        for mode in ("v1", "v2", "broken"):
            subprocess.run(["docker", "image", "rm", f"{cls.c.project}:{mode}"],
                           capture_output=True, check=False)

    def post(self, path, task):
        payload = json.dumps({"task": task}).encode()
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.c.port('app', 8080)}{path}",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            # Docker's DNS can take several seconds to report a stopped service.
            with urllib.request.urlopen(request, timeout=15) as response:
                return response.status
        except urllib.error.HTTPError as error:
            return error.code

    def test_1_blocks_new_work_while_existing_work_drains(self):
        before = self.c.app_image_id()
        self.assertEqual(self.post("/start", "job-existing"), 202)
        result = []
        thread = threading.Thread(target=lambda: result.append(self.c.update("v1", "v2", 6, 12)))
        thread.start()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if self.c.gate().cmd("GET", "maintenance"):
                break
            time.sleep(.05)
        self.assertIsNotNone(self.c.gate().cmd("GET", "maintenance"))
        self.assertEqual(self.post("/start", "job-new"), 503)
        self.assertEqual(self.c.health(), (True, "v1"))
        self.assertEqual(self.post("/finish", "job-existing"), 200)
        thread.join(timeout=30)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result[0]["status"], "updated")
        self.assertEqual(self.c.health(), (True, "v2"))
        self.assertNotEqual(self.c.app_image_id(), before)
        self.assertEqual(self.post("/start", "job-after"), 202)
        self.assertEqual(self.post("/finish", "job-after"), 200)

    def test_2_timeout_leaves_old_service_and_task_untouched(self):
        self.assertEqual(self.post("/start", "long-job"), 202)
        result = self.c.update("v2", "v1", drain_timeout=.3, health_timeout=5)
        self.assertEqual(result["status"], "active_tasks")
        self.assertEqual(self.c.health(), (True, "v2"))
        self.assertEqual(self.c.gate().count(), 1)
        self.assertEqual(self.post("/finish", "long-job"), 200)

    def test_3_failed_healthcheck_rolls_back_and_reports_safe_status(self):
        before = self.c.app_image_id()
        result = self.c.update("v2", "broken", drain_timeout=2, health_timeout=3)
        self.assertEqual(result["status"], "rolled_back")
        self.assertEqual(result["diagnostics"]["health"], "unhealthy")
        self.assertEqual(self.c.health(), (True, "v2"))
        self.assertEqual(self.c.app_image_id(), before)
        self.assertEqual(set(result["diagnostics"]), {"containers", "health"})
        self.assertEqual(self.post("/start", "after-rollback"), 202)
        self.assertEqual(self.post("/finish", "after-rollback"), 200)

    def test_4_second_update_cannot_override_maintenance(self):
        gate = self.c.gate()
        self.assertEqual(gate.begin("other-owner"), 1)
        try:
            self.assertEqual(self.c.update("v2", "v1", health_timeout=4), {"status": "busy"})
            self.assertEqual(gate.release("wrong-owner"), 0)
            self.assertEqual(self.post("/start", "blocked"), 503)
            self.assertEqual(self.c.health(), (True, "v2"))
        finally:
            self.assertEqual(gate.release("other-owner"), 1)

    def test_5_gate_outage_fails_closed(self):
        self.c.compose("stop", "gate")
        try:
            self.assertEqual(self.post("/start", "no-gate"), 503)
            with self.assertRaises((OSError, RuntimeError)):
                Gate("127.0.0.1", 1).begin("owner")
        finally:
            self.c.compose("start", "gate")
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                if self.c.gate().cmd("PING") == "PONG":
                    break
            except (OSError, RuntimeError):
                time.sleep(.1)
        self.assertEqual(self.post("/start", "recovered"), 202)
        self.assertEqual(self.post("/finish", "recovered"), 200)

    def test_6_concurrent_acceptance_cannot_hide_an_active_task(self):
        gate = self.c.gate()
        barrier = threading.Barrier(21)

        def start_task(number):
            barrier.wait(timeout=10)
            return number, gate.accept(f"race-{number}")

        def enter_maintenance():
            barrier.wait(timeout=10)
            return gate.begin("race-owner")

        with ThreadPoolExecutor(max_workers=21) as pool:
            requests = [pool.submit(start_task, number) for number in range(20)]
            maintenance = pool.submit(enter_maintenance)
            results = [future.result(timeout=15) for future in requests]
            self.assertEqual(maintenance.result(timeout=15), 1)
        accepted = [number for number, result in results if result == 1]
        self.assertTrue(all(result in (0, 1) for _, result in results))
        try:
            self.assertEqual(gate.count(), len(accepted))
            self.assertEqual(gate.accept("late-task"), 0)
        finally:
            for number in accepted:
                gate.finish(f"race-{number}")
            self.assertEqual(gate.release("race-owner"), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
