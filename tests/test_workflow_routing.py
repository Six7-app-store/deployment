"""Check real workflow conditions against a matrix of synthetic events.

No GitHub, VM, database or Docker access. Requires PyYAML and Node.js. This is
a narrow evaluator for the boolean expressions used in the selected steps, not
a general GitHub Actions interpreter.
"""
import itertools
import json
import subprocess
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = yaml.safe_load((ROOT / ".github/workflows/staging.yml").read_text(encoding="utf-8"))
STEPS = {step.get("name"): step for step in WORKFLOW["jobs"]["deploy"]["steps"]}


def expression(value):
    value = str(value).strip()
    return value[3:-2].strip() if value.startswith("${{") and value.endswith("}}") else value


class WorkflowRoutingTests(unittest.TestCase):
    def test_event_and_guard_matrix(self):
        checks = {
            "protect": STEPS["Laufende App-Auftraege vor Plattform-Neubau schuetzen"]["if"],
            "backup": STEPS["Caddy-Zertifikat der alten VM sichern"]["if"],
            "destroy": STEPS["OpenTofu Destroy (alten Stack abreissen)"]["if"],
            "plan_in_place": STEPS["OpenTofu Plan & Apply (neuen Stack aufbauen)"]["env"]["GUARDED_IN_PLACE"],
            **{key: STEPS["Ansible Playbook ausfuehren"]["env"][key]
               for key in ("SEED", "GUARDED_UPDATES", "IN_PLACE_UPDATE")},
        }
        checks = {name: expression(value) for name, value in checks.items()}
        cases = []
        for stand, event, staging, production, bootstrap, recreate, seed in itertools.product(
            ("develop", "main"), ("push", "repository_dispatch", "workflow_dispatch"),
            (False, True), (False, True), (False, True), (False, True), (False, True)
        ):
            # bootstrap_guarded is only a workflow_dispatch input.
            if bootstrap and event != "workflow_dispatch":
                continue
            cases.append({"env": {"STAND": stand},
                          "vars": {"GUARDED_STAGING_UPDATES": str(staging).lower(),
                                   "GUARDED_MAIN_UPDATES": str(production).lower()},
                          "github": {"event_name": event},
                          "inputs": {"bootstrap_guarded": bootstrap, "recreate": recreate, "seed": seed}})
        js = """const fs = require('fs'); const data = JSON.parse(fs.readFileSync(0, 'utf8'));
const out = data.cases.map(c => Object.fromEntries(Object.entries(data.checks).map(([key, exp]) => {
  const fn = new Function('env', 'vars', 'github', 'inputs', `return (${exp})`);
  return [key, fn(c.env, c.vars, c.github, c.inputs)];
}))); process.stdout.write(JSON.stringify(out));"""
        result = subprocess.run(["node", "-e", js], input=json.dumps({"cases": cases, "checks": checks}),
                                text=True, capture_output=True, check=True)
        for case, actual in zip(cases, json.loads(result.stdout), strict=True):
            stand = case["env"]["STAND"]
            event = case["github"]["event_name"]
            inputs = case["inputs"]
            enabled = case["vars"]["GUARDED_STAGING_UPDATES" if stand == "develop" else "GUARDED_MAIN_UPDATES"] == "true"
            bootstrap = event == "workflow_dispatch" and inputs["bootstrap_guarded"]
            in_place = (event == "repository_dispatch" and enabled) or bootstrap
            with self.subTest(case=case):
                self.assertEqual(bool(actual["protect"]), enabled or bootstrap)
                self.assertEqual(bool(actual["backup"]), not in_place)
                self.assertEqual(bool(actual["destroy"]), (event != "workflow_dispatch" or inputs["recreate"]) and not (event == "repository_dispatch" and enabled))
                self.assertEqual(bool(actual["plan_in_place"]), in_place)
                self.assertEqual(bool(actual["IN_PLACE_UPDATE"]), in_place)
                self.assertEqual(bool(actual["GUARDED_UPDATES"]), enabled or bootstrap)
                expected_seed = "false" if event == "repository_dispatch" and enabled else ("true" if event != "workflow_dispatch" else inputs["seed"])
                self.assertEqual(actual["SEED"], expected_seed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
