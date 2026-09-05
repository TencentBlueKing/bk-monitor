import importlib
import sys
from pathlib import Path

import pytest
import yaml
from django.test import override_settings


MODE_MODULE = "bkmonitor.nodeman_integration.mode"
CELERY_CONFIG_MODULE = "config.celery.config"
V3_TASK_MODULE = "monitor_web.nodeman_integration.v3.tasks"
V3_QUEUE = "celery"
SNAPSHOT_PATH = Path(__file__).with_name("fixtures") / "v2_contract_snapshots.yaml"
SUPERVISOR_CONFIG_PATH = Path(__file__).resolve().parents[2] / "support-files/supervisord.conf"


def _reload_config(mode):
    with override_settings(NODEMAN_INTEGRATION_MODE=mode):
        mode_module = importlib.import_module(MODE_MODULE)
        importlib.reload(mode_module)
        config_module = importlib.import_module(CELERY_CONFIG_MODULE)
        importlib.reload(config_module)
    return config_module.Config


@pytest.fixture(autouse=True)
def restore_v2_config():
    yield
    _reload_config("v2")
    sys.modules.pop(V3_TASK_MODULE, None)


def test_v2_celery_config_is_exactly_the_frozen_baseline():
    from tests.nodeman_v3.test_v2_zero_impact_contract import _celery_config_contract

    sys.modules.pop(V3_TASK_MODULE, None)
    _reload_config("v2")
    expected = yaml.safe_load(SNAPSHOT_PATH.read_text(encoding="utf-8"))["static_contract"]["celery_config"]

    assert _celery_config_contract() == expected
    assert V3_TASK_MODULE not in sys.modules


def test_v3_worker_and_beat_use_the_same_explicit_queue():
    config = _reload_config("v3_fresh")
    task_names = {
        "monitor_web.nodeman_integration.v3.tasks.poll_operation",
        "monitor_web.nodeman_integration.v3.tasks.poll_pending_operations",
        "monitor_web.nodeman_integration.v3.tasks.reconcile_binding",
    }

    assert config.imports == (V3_TASK_MODULE,)
    assert {config.task_routes[name]["queue"] for name in task_names} == {V3_QUEUE}
    assert config.beat_schedule["nodeman_v3_poll_pending_operations"]["task"] in task_names
    assert config.beat_schedule["nodeman_v3_poll_pending_operations"]["options"] == {"queue": V3_QUEUE}
    assert "nodeman_v3_reconcile_active_bindings" not in config.beat_schedule
    assert f"{V3_TASK_MODULE}.reconcile_active_bindings" not in config.task_routes
    supervisor_config = SUPERVISOR_CONFIG_PATH.read_text(encoding="utf-8")
    default_worker_command = next(
        line for line in supervisor_config.splitlines() if "manage.py celery worker" in line and "-Q" not in line
    )
    assert "manage.py celery worker" in default_worker_command
