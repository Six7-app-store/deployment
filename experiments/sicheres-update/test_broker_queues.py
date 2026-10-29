import importlib.util
import unittest
from pathlib import Path

path = Path(__file__).resolve().parents[2] / "scripts" / "check_broker_queues.py"
spec = importlib.util.spec_from_file_location("check_broker_queues", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class BrokerQueueTests(unittest.TestCase):
    def test_broker_must_return_at_least_one_empty_queue(self):
        self.assertTrue(module.is_idle("celery\t0\t0\n"))
        self.assertTrue(module.is_idle("name\tmessages_ready\tmessages_unacknowledged\ncelery\t0\t0\n"))
        self.assertTrue(module.is_idle("celery\t0\t0\nother\t0\t0\n"))
        for output in ("", "celery 1 0", "celery 0 1", "celery unknown 0", "celery 0"):
            with self.subTest(output=output):
                self.assertFalse(module.is_idle(output))


if __name__ == "__main__":
    unittest.main(verbosity=2)
