"""Exercise the timer bootstrap against a fake systemctl, never a host service."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "quiesce-autoupdate.sh"


class QuiesceTests(unittest.TestCase):
    def run_script(self, *, state="inactive", job="", stop_rc=0, show_rc=0, timeout=0):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = root / "systemctl"
            fake.write_text(
                '#!/bin/sh\n'
                'case "$1" in\n'
                '  stop) printf "stopped\\n" >> "$TEST_CALLS"; exit "$TEST_STOP_RC" ;;\n'
                '  show) [ "$TEST_SHOW_RC" = 0 ] || exit "$TEST_SHOW_RC"; '
                'case "$3" in --property=ActiveState) '
                'if [ "$TEST_STATE" = active_once ]; then '
                'if [ -f "$TEST_SEEN" ]; then echo inactive; else touch "$TEST_SEEN"; echo active; fi; '
                'else echo "$TEST_STATE"; fi ;; '
                '--property=Job) printf "%s\\n" "$TEST_JOB" ;; *) exit 9 ;; esac ;;\n'
                '  *) exit 9 ;;\n'
                'esac\n', encoding="utf-8",
            )
            fake.chmod(0o755)
            calls = root / "calls"
            env = {**os.environ, "PATH": directory + os.pathsep + os.environ["PATH"],
                   "TEST_CALLS": str(calls), "TEST_STATE": state, "TEST_JOB": job,
                   "TEST_STOP_RC": str(stop_rc), "TEST_SHOW_RC": str(show_rc),
                   "TEST_SEEN": str(root / "seen")}
            result = subprocess.run(["bash", str(SCRIPT), str(timeout)], env=env, capture_output=True,
                                    text=True, timeout=10)
            return result, calls.read_text() if calls.exists() else ""

    def test_stopped_timer_with_idle_service_succeeds(self):
        result, calls = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, "stopped\n")

    def test_running_service_or_queued_job_prevents_bootstrap(self):
        for kwargs in ({"state": "active"}, {"state": "inactive", "job": "123"}):
            with self.subTest(kwargs=kwargs):
                result, calls = self.run_script(**kwargs)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(calls, "stopped\n")

    def test_running_service_is_allowed_to_finish(self):
        result, calls = self.run_script(state="active_once", timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, "stopped\n")

    def test_systemctl_error_or_failed_service_prevents_bootstrap(self):
        for kwargs in ({"stop_rc": 1}, {"show_rc": 1}, {"state": "failed"}, {"state": "unknown"}):
            with self.subTest(kwargs=kwargs):
                result, _ = self.run_script(**kwargs)
                self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
