import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import yaml
from celery import current_app
from django.test import override_settings
from rest_framework.fields import empty
from rest_framework.serializers import BaseSerializer

from core.drf_resource import api
from core.drf_resource.base import Resource
from config.celery.config import Config as CeleryConfig
from monitor_web.collecting.constant import OperationResult, OperationType
from monitor_web.collecting.deploy import node_man
from monitor_web.collecting.deploy.node_man import NodeManInstaller


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_PATH = Path(__file__).with_name("fixtures") / "v2_contract_snapshots.yaml"


class FakeDeploymentConfig:
    def __init__(self, subscription_id):
        self.subscription_id = subscription_id
        self.task_ids = []
        self.save_called = 0

    def save(self):
        self.save_called += 1


class FakeCollectConfig:
    def __init__(self, subscription_id=123):
        self.bk_tenant_id = "tenant-a"
        self.plugin = SimpleNamespace(plugin_type="Script")
        self.deployment_config = FakeDeploymentConfig(subscription_id)
        self.operation_result = OperationResult.SUCCESS
        self.last_operation = OperationType.START
        self.save_called = 0

    def save(self):
        self.save_called += 1


def _sha256(relative_path: str) -> str:
    return hashlib.sha256((PROJECT_ROOT / relative_path).read_bytes()).hexdigest()


def _normalize_value(value):
    if value is empty:
        return "<empty>"
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(key): _normalize_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_normalize_value(item) for item in value]
    if callable(value):
        return f"<callable:{value.__module__}.{value.__qualname__}>"
    return f"<{value.__class__.__module__}.{value.__class__.__qualname__}>"


def _field_contract(field) -> dict:
    contract = {
        "type": field.__class__.__name__,
        "required": field.required,
        "read_only": field.read_only,
        "write_only": field.write_only,
        "allow_null": field.allow_null,
        "default": _normalize_value(field.default),
    }
    if hasattr(field, "allow_blank"):
        contract["allow_blank"] = field.allow_blank
    if hasattr(field, "choices"):
        contract["choices"] = [_normalize_value(choice) for choice in field.choices]
    if hasattr(field, "child"):
        contract["child"] = _field_contract(field.child)
    if isinstance(field, BaseSerializer):
        contract["fields"] = {name: _field_contract(child) for name, child in field.fields.items()}
    return contract


def _serializer_contract(serializer_class) -> dict | None:
    if serializer_class is None:
        return None
    serializer = serializer_class()
    return {name: _field_contract(field) for name, field in serializer.fields.items()}


def _resource_contract(resource: Resource) -> dict:
    with override_settings(BKNODEMAN_API_BASE_URL="", ENABLE_MULTI_TENANT_MODE=False):
        esb_action = getattr(resource, "action", None)
    with override_settings(BKNODEMAN_API_BASE_URL="https://nodeman.invalid", ENABLE_MULTI_TENANT_MODE=True):
        apigw_action = getattr(resource, "action", None)

    response_serializer = getattr(resource.__class__, "ResponseSerializer", None)
    misspelled_response_serializer = getattr(resource.__class__, "ReponseSerializer", None)
    return {
        "class": resource.__class__.__name__,
        "method": getattr(resource, "method", None),
        "timeout": getattr(resource, "TIMEOUT", None),
        "esb_action": esb_action,
        "apigw_action": apigw_action,
        "request": _serializer_contract(resource.RequestSerializer),
        "response": _serializer_contract(response_serializer or misspelled_response_serializer),
    }


def _celery_config_contract() -> dict:
    beat_schedule = {}
    for name, item in sorted(CeleryConfig.beat_schedule.items()):
        schedule = item["schedule"]
        beat_schedule[name] = {
            "task": item["task"],
            "schedule": {
                "minute": schedule._orig_minute,
                "hour": schedule._orig_hour,
                "day_of_week": schedule._orig_day_of_week,
                "day_of_month": schedule._orig_day_of_month,
                "month_of_year": schedule._orig_month_of_year,
            },
            "enabled": item.get("enabled"),
            "options": item.get("options", {}),
        }
    return {
        "imports_defined": hasattr(CeleryConfig, "imports"),
        "task_routes_defined": hasattr(CeleryConfig, "task_routes"),
        "task_queues_defined": hasattr(CeleryConfig, "task_queues"),
        "beat_schedule": beat_schedule,
    }


def _clean_v2_celery_task_names() -> list[str]:
    environment = os.environ.copy()
    environment.update(
        {
            "DJANGO_SETTINGS_MODULE": "settings",
            "DJANGO_CONF_MODULE": "config.web.development.community",
            "BKAPP_DEPLOY_PLATFORM": "community",
            "USE_DYNAMIC_SETTINGS": "0",
            "BK_MONITOR_APP_CODE": "bk_monitorv3",
            "BK_MONITOR_APP_SECRET": "secret",
            "BKAPP_NODEMAN_INTEGRATION_MODE": "v2",
        }
    )
    script = """
import json
import django

django.setup()
from celery import current_app
print("NODEMAN_V2_TASKS=" + json.dumps(sorted(current_app.tasks.keys())))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = next(line for line in result.stdout.splitlines() if line.startswith("NODEMAN_V2_TASKS="))
    return json.loads(payload.removeprefix("NODEMAN_V2_TASKS="))


def capture_v2_static_contract() -> dict:
    resource_names = api.node_man.list_method()
    resources = {}
    for name in resource_names:
        candidate = getattr(api.node_man, name)
        if isinstance(candidate, Resource):
            resources[name] = _resource_contract(candidate)

    return {
        "source_sha256": {
            "api/node_man/default.py": _sha256("api/node_man/default.py"),
            "packages/monitor_web/collecting/deploy/node_man.py": _sha256(
                "packages/monitor_web/collecting/deploy/node_man.py"
            ),
        },
        "node_man_resource_names": resource_names,
        "node_man_resources": resources,
        "celery_task_names": _clean_v2_celery_task_names(),
        "celery_config": _celery_config_contract(),
        "authentication": {
            "identity": "tenant_admin",
            "origin_user_forwarding": "_origin_user_when_request_user_is_empty",
            "base_url_selection": "BKNODEMAN_API_BASE_URL_then_APIGW_or_ESB",
        },
    }


def test_v2_static_contract_matches_baseline():
    snapshot = yaml.safe_load(SNAPSHOT_PATH.read_text(encoding="utf-8"))

    assert snapshot["baseline_commit"] == "e4a29134be1c61c3b7a96b57aefdc555b48c7eb7"
    assert snapshot["static_contract"] == capture_v2_static_contract()


def test_v2_runtime_contract_matches_baseline(monkeypatch):
    snapshot = yaml.safe_load(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    collect_config = FakeCollectConfig()
    installer = NodeManInstaller(collect_config)
    outbound_calls = []
    celery_calls = []
    sql_calls = []

    def raise_if_called(*args, **kwargs):
        raise AssertionError("stop should not rebuild deploy params")

    monkeypatch.setattr(installer, "_get_deploy_params", raise_if_called)
    monkeypatch.setattr(
        node_man.api.node_man,
        "switch_subscription",
        lambda **kwargs: outbound_calls.append({"action": "switch_subscription", "parameters": kwargs}),
    )
    monkeypatch.setattr(
        node_man.api.node_man,
        "subscription_info",
        lambda **kwargs: (
            outbound_calls.append({"action": "subscription_info", "parameters": kwargs})
            or [{"steps": [{"id": "plugin_step"}, {"id": "bkmonitorbeat"}]}]
        ),
    )
    monkeypatch.setattr(
        node_man.api.node_man,
        "run_subscription",
        lambda **kwargs: (
            outbound_calls.append({"action": "run_subscription", "parameters": kwargs}) or {"task_id": 456}
        ),
    )
    monkeypatch.setattr(
        current_app,
        "send_task",
        lambda *args, **kwargs: celery_calls.append({"args": list(args), "kwargs": kwargs}),
    )
    monkeypatch.setattr(
        "django.db.backends.utils.CursorWrapper.execute",
        lambda *args, **kwargs: sql_calls.append({"args": list(args[1:]), "kwargs": kwargs}),
    )
    monkeypatch.setattr(
        "django.db.backends.utils.CursorWrapper.executemany",
        lambda *args, **kwargs: sql_calls.append({"args": list(args[1:]), "kwargs": kwargs}),
    )

    installer.stop()

    actual = {
        "outbound_calls": outbound_calls,
        "normalized_response": {"task_id": 456, "step_ids": ["plugin_step", "bkmonitorbeat"]},
        "state": {
            "operation_result": collect_config.operation_result,
            "last_operation": collect_config.last_operation,
            "task_ids": collect_config.deployment_config.task_ids,
            "collect_config_save_count": collect_config.save_called,
            "deployment_config_save_count": collect_config.deployment_config.save_called,
        },
        "sql": {"count": len(sql_calls), "tables": []},
        "celery_calls": celery_calls,
    }

    assert actual == snapshot["representative_runtime"]["collecting_stop"]


def test_v2_performance_acceptance_definition_is_enforced():
    acceptance = yaml.safe_load(SNAPSHOT_PATH.read_text(encoding="utf-8"))["performance_acceptance"]

    assert acceptance["warmup_iterations"] >= 10
    assert acceptance["sample_iterations"] >= 100
    assert acceptance["confidence_level"] == 0.95
    assert acceptance["metrics"] == ["p50", "p95"]
    assert acceptance["relative_regression_floor_percent"] == 1
    assert acceptance["threshold"] == "max(baseline_noise_upper_bound, relative_regression_floor_percent)"
    assert set(acceptance["exact_gates"]) == {
        "normalized_sql",
        "accessed_tables",
        "remote_actions_and_parameters",
        "celery_messages",
        "imported_v3_modules",
    }
    assert set(acceptance["v2_hot_path"].values()) == {0}
