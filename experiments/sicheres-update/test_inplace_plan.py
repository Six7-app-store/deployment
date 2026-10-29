import importlib.util
import unittest
from pathlib import Path

path = Path(__file__).resolve().parents[2] / "scripts" / "check_inplace_plan.py"
spec = importlib.util.spec_from_file_location("check_inplace_plan", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class InPlacePlanTests(unittest.TestCase):
    def test_non_destructive_changes_are_allowed(self):
        for action in ("no-op", "create", "read", "update"):
            with self.subTest(action=action):
                self.assertTrue(module.is_safe({"format_version": "1.2", "resource_changes": [{"change": {"actions": [action]}}]}))

    def test_deletions_and_replacements_are_rejected(self):
        for actions in (["delete"], ["delete", "create"], ["create", "delete"]):
            with self.subTest(actions=actions):
                self.assertFalse(module.is_safe({"format_version": "1.2", "resource_changes": [{"change": {"actions": actions}}]}))

    def test_malformed_plan_is_not_accepted(self):
        for plan in (None, [], {}, {"format_version": "1.2", "errored": True},
                     {"format_version": "1.2", "complete": False},
                     {"format_version": "1.2", "resource_changes": None},
                     {"format_version": "1.2", "resource_changes": [{"change": {"actions": []}}]},
                     {"format_version": "1.2", "resource_changes": [{"change": {"actions": ["unknown"]}}]}):
            with self.subTest(plan=plan):
                self.assertFalse(module.is_safe(plan))


if __name__ == "__main__":
    unittest.main(verbosity=2)
