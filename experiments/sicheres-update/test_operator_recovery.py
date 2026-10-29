"""Recovery keeps a persisted maintenance gate until the owner releases it."""
import subprocess

import pytest
from sqlalchemy import text

from app.models import TaskStatus, TaskType
from tests.test_deployments_pause_resume import _make_deployment_with_creds


def operator(action, owner="gha-12345-1"):
    return subprocess.run(
        ["bash", "/deployment/scripts/maintenance-operator.sh", action, "experiment", owner, "0"],
        capture_output=True, text=True, timeout=10,
    )


@pytest.mark.integration
def test_resume_requires_same_owner_and_releases_only_at_end(db):
    assert operator("begin").returncode == 0
    assert operator("resume", "gha-1-1").returncode == 2
    assert operator("resume").returncode == 0
    assert db.execute(text("SELECT owner FROM platform_maintenance WHERE id=1")).scalar_one() == "gha-12345-1"
    db.rollback()
    assert operator("end").returncode == 0


@pytest.mark.integration
def test_resume_timeout_does_not_release_existing_gate(db, mock_user):
    assert operator("begin").returncode == 0
    _make_deployment_with_creds(
        db, mock_user, latest_task_type=TaskType.DEPLOY, latest_task_status=TaskStatus.RUNNING,
    )
    assert operator("resume").returncode == 2
    assert db.execute(text("SELECT owner FROM platform_maintenance WHERE id=1")).scalar_one() == "gha-12345-1"
    db.rollback()
    assert operator("end").returncode == 0
