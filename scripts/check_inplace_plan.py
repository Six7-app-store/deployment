#!/usr/bin/env python3
"""Reject an OpenTofu JSON plan that deletes or replaces any resource.

Read stdin only; never print resource values or the plan because it may
contain credentials. Designed for the optional in-place staging path.
"""
import json
import sys


def is_safe(plan):
    if (not isinstance(plan, dict) or not isinstance(plan.get("format_version"), str)
            or plan.get("errored", False) is not False or plan.get("complete", True) is not True):
        return False
    changes = plan.get("resource_changes", [])
    if not isinstance(changes, list):
        return False
    allowed = {"no-op", "create", "read", "update"}
    for entry in changes:
        if not isinstance(entry, dict) or not isinstance(entry.get("change"), dict):
            return False
        actions = entry["change"].get("actions")
        if not isinstance(actions, list) or not actions or any(action not in allowed for action in actions):
            return False
    return True


def main():
    try:
        plan = json.load(sys.stdin)
        safe = is_safe(plan)
    except (ValueError, TypeError):
        safe = False
    if not safe:
        print("In-place plan is unsafe or unreadable.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
