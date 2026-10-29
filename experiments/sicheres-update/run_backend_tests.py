"""Run integration checks on an isolated DB without touching the dev stack."""
import base64
import json
import os
import secrets
import subprocess
import sys
import uuid
from pathlib import Path

folder = Path(__file__).resolve().parent
project = "deploybackendtest" + uuid.uuid4().hex[:12]
info = json.loads(subprocess.check_output(["docker", "inspect", "backend-dev"]))[0]
venv = next(
    mount["Name"] for mount in info["Mounts"]
    if mount["Destination"] == "/app/.venv" and mount["Type"] == "volume"
)
env = os.environ.copy()
env["BACKEND_TEST_VENV"] = venv
env["EXPERIMENT_FERNET_KEY"] = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
cmd = ["docker", "compose", "-p", project, "-f", str(folder / "backend-test.yaml")]
try:
    result = subprocess.run(
        cmd + ["run", "--rm", "test", "--no-cov", "-q", *sys.argv[1:]],
        env=env,
        cwd=folder,
        check=False,
    )
finally:
    subprocess.run(cmd + ["down", "--remove-orphans"], env=env, cwd=folder, check=False)
raise SystemExit(result.returncode)
