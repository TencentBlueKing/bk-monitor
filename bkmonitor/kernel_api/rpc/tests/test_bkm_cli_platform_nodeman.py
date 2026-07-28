"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT

NodeMan retained task snapshot platform-source catalog tests.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from django.conf import settings

from core.drf_resource import api

from kernel_api.rpc.functions.bkm_cli.platform_catalog import nodeman
from kernel_api.rpc.functions.bkm_cli.platform_catalog._catalog import ParamsGuardRejected, PlatformSourceCatalog
from kernel_api.rpc.functions.bkm_cli.platform_source import query_platform_source

OPERATION_ID = "get_subscription_task_step_summaries"
GATE_SETTING = "BKM_CLI_NODEMAN_RETAINED_TASK_SNAPSHOTS_ENABLED"


@pytest.fixture(autouse=True)
def isolated_catalog():
    snapshot = dict(PlatformSourceCatalog._domains)
    PlatformSourceCatalog.reset()
    nodeman.register()
    yield
    PlatformSourceCatalog._domains = snapshot
    PlatformSourceCatalog._revision = None


def _valid_sub_step(index: int = 0) -> dict[str, Any]:
    return {
        "index": index,
        "node_name": f"node-{index}",
        "step_code": "render",
        "status": "PENDING",
        "start_time": None,
        "finish_time": None,
        "log": "canary-log",
        "inputs": {"token": "canary-input"},
        "outputs": {"password": "canary-output"},
        "ex_data": "canary-ex-data",
    }


def _valid_step(index: int = 0, sub_steps: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "id": f"step-{index}",
        "type": "PLUGIN",
        "action": "UNINSTALL",
        "status": "PENDING",
        "start_time": None,
        "finish_time": None,
        "node_name": "canary-step-node-name",
        "params": {"password": "canary-param"},
        "context": {"token": "canary-context"},
        "target_hosts": [
            {
                "instance_info": {"password": "canary-instance-info"},
                "sub_steps": sub_steps if sub_steps is not None else [],
            }
        ],
    }


def _valid_task(
    *,
    task_id: int = 10,
    record_id: int = 11,
    instance_id: str = "instance",
    steps: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "record_id": record_id,
        "instance_id": instance_id,
        "create_time": "2026-01-01 00:00:00",
        "start_time": None,
        "finish_time": None,
        "status": "PENDING",
        "pipeline_id": "canary-pipeline",
        "instance_info": {"password": "canary-instance"},
        "steps": steps if steps is not None else [],
    }


def _valid_raw(tasks: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "total": len(tasks or []),
        "status_counter": {
            "SUCCESS": 0,
            "PENDING": len(tasks or []),
            "FAILED": 0,
            "RUNNING": 0,
            "PART_FAILED": 0,
            "TERMINATED": 0,
            "REMOVED": 0,
            "FILTERED": 0,
            "IGNORED": 0,
            "total": len(tasks or []),
            "unknown": "canary-counter",
        },
        "list": tasks or [],
        "unknown": "canary-top-level",
    }


def _invoke(params: dict[str, Any]) -> dict[str, Any]:
    return query_platform_source(
        {
            "mode": "invoke",
            "domain": "nodeman",
            "operation": OPERATION_ID,
            "params": params,
        }
    )


def test_retained_task_snapshot_gate_defaults_disabled():
    assert settings.BKM_CLI_NODEMAN_RETAINED_TASK_SNAPSHOTS_ENABLED is False


def test_nodeman_registers_retained_task_step_summary_operation():
    domain = PlatformSourceCatalog.get_domain("nodeman")
    assert domain is not None

    operation = domain.operations[OPERATION_ID]
    assert operation.handler is api.node_man.task_result
    assert operation.params_guard is nodeman.guard_subscription_task_step_summaries
    assert operation.response_postprocess is nodeman.project_subscription_task_step_summaries
    assert operation.required_params == ["subscription_id", "task_id"]
    assert operation.example_params == {"subscription_id": 101, "task_id": 201, "page": 1, "pagesize": 100}
    assert operation.default_fields == []
    assert operation.allowed_fields == []
    assert operation.params_schema_override == {
        "type": "object",
        "properties": {
            "subscription_id": {"type": "integer", "minimum": 1, "description": "节点管理订阅 ID"},
            "task_id": {"type": "integer", "minimum": 1, "description": "单个节点管理任务 ID"},
            "page": {"type": "integer", "default": 1, "minimum": 1},
            "pagesize": {"type": "integer", "default": 100, "minimum": 1, "maximum": 100},
        },
        "required": ["subscription_id", "task_id"],
        "additionalProperties": False,
    }


def test_disabled_gate_rejects_before_provider_call(monkeypatch):
    monkeypatch.setattr(settings, GATE_SETTING, False, raising=False)
    operation = PlatformSourceCatalog.get_domain("nodeman").operations[OPERATION_ID]
    calls: list[dict[str, Any]] = []

    def handler(**kwargs):
        calls.append(kwargs)
        return _valid_raw()

    operation.handler = handler

    result = _invoke({"subscription_id": 101, "task_id": 201})

    assert result["status"] == "error"
    assert result["error"]["code"] == "unsafe_action_blocked"
    assert calls == []


def test_enabled_invoke_forwards_only_fixed_single_task_parameters(monkeypatch):
    monkeypatch.setattr(settings, GATE_SETTING, True, raising=False)
    operation = PlatformSourceCatalog.get_domain("nodeman").operations[OPERATION_ID]
    calls: list[dict[str, Any]] = []

    def handler(**kwargs):
        calls.append(kwargs)
        return _valid_raw()

    operation.handler = handler

    result = _invoke({"subscription_id": 101, "task_id": 201, "page": 2, "pagesize": 50})

    assert result["status"] == "ok"
    assert calls == [
        {
            "subscription_id": 101,
            "task_id_list": [201],
            "need_detail": False,
            "need_aggregate_all_tasks": False,
            "need_out_of_scope_snapshots": True,
            "page": 2,
            "pagesize": 50,
        }
    ]
    assert result["result"] == {
        "total": 0,
        "status_counter": {
            "SUCCESS": 0,
            "PENDING": 0,
            "FAILED": 0,
            "RUNNING": 0,
            "PART_FAILED": 0,
            "TERMINATED": 0,
            "REMOVED": 0,
            "FILTERED": 0,
            "IGNORED": 0,
            "total": 0,
        },
        "list": [],
        "projection_meta": {"is_partial": False, "dropped_items": 0, "reasons": []},
    }


def test_multi_task_request_is_rejected_before_provider_call(monkeypatch):
    monkeypatch.setattr(settings, GATE_SETTING, True, raising=False)
    operation = PlatformSourceCatalog.get_domain("nodeman").operations[OPERATION_ID]
    calls: list[dict[str, Any]] = []

    def handler(**kwargs):
        calls.append(kwargs)
        return _valid_raw(
            [
                _valid_task(task_id=201, record_id=301, instance_id="same-instance"),
                _valid_task(task_id=202, record_id=302, instance_id="same-instance"),
            ]
        )

    operation.handler = handler

    result = _invoke({"subscription_id": 101, "task_id_list": [201, 202]})

    assert result["status"] == "error"
    assert result["error"]["code"] == "unsafe_action_blocked"
    assert calls == []


def test_guard_defaults_pagination_and_caps_page_size(monkeypatch):
    monkeypatch.setattr(settings, GATE_SETTING, True, raising=False)

    assert nodeman.guard_subscription_task_step_summaries({"subscription_id": 101, "task_id": 201}) == {
        "subscription_id": 101,
        "task_id_list": [201],
        "need_detail": False,
        "need_aggregate_all_tasks": False,
        "need_out_of_scope_snapshots": True,
        "page": 1,
        "pagesize": 100,
    }

    with pytest.raises(ParamsGuardRejected, match="pagesize"):
        nodeman.guard_subscription_task_step_summaries({"subscription_id": 101, "task_id": 201, "pagesize": 101})


@pytest.mark.parametrize("field", ["subscription_id", "task_id"])
@pytest.mark.parametrize("value", [None, "", "1", " 1 ", "+1", 0, -1, True, False, 1.5, [], {}])
def test_guard_rejects_missing_or_invalid_identifiers(monkeypatch, field, value):
    monkeypatch.setattr(settings, GATE_SETTING, True, raising=False)
    params = {"subscription_id": 101, "task_id": 201}
    params[field] = value

    with pytest.raises(ParamsGuardRejected, match=field):
        nodeman.guard_subscription_task_step_summaries(params)


@pytest.mark.parametrize(
    "extra",
    [
        {"task_id_list": [201]},
        {"need_detail": True},
        {"need_aggregate_all_tasks": True},
        {"need_out_of_scope_snapshots": False},
        {"_user_request": "blocked"},
    ],
)
def test_guard_rejects_multi_task_hidden_and_need_parameters(monkeypatch, extra):
    monkeypatch.setattr(settings, GATE_SETTING, True, raising=False)

    with pytest.raises(ParamsGuardRejected, match="未声明参数"):
        nodeman.guard_subscription_task_step_summaries({"subscription_id": 101, "task_id": 201, **extra})


def test_projector_returns_exact_step_summary_whitelist():
    raw = _valid_raw(
        [
            _valid_task(
                steps=[
                    _valid_step(
                        sub_steps=[
                            {
                                **_valid_sub_step(),
                                "node_name": "node",
                                "step_code": "code",
                            }
                        ]
                    )
                ]
            )
        ]
    )

    result = nodeman.project_subscription_task_step_summaries(raw, None)

    assert result == {
        "total": 1,
        "status_counter": {
            "SUCCESS": 0,
            "PENDING": 1,
            "FAILED": 0,
            "RUNNING": 0,
            "PART_FAILED": 0,
            "TERMINATED": 0,
            "REMOVED": 0,
            "FILTERED": 0,
            "IGNORED": 0,
            "total": 1,
        },
        "list": [
            {
                "task_id": 10,
                "record_id": 11,
                "instance_id": "instance",
                "create_time": "2026-01-01 00:00:00",
                "start_time": None,
                "finish_time": None,
                "status": "PENDING",
                "steps": [
                    {
                        "id": "step-0",
                        "type": "PLUGIN",
                        "action": "UNINSTALL",
                        "status": "PENDING",
                        "start_time": None,
                        "finish_time": None,
                        "sub_steps": [
                            {
                                "index": 0,
                                "node_name": "node",
                                "step_code": "code",
                                "status": "PENDING",
                                "start_time": None,
                                "finish_time": None,
                            }
                        ],
                    }
                ],
            }
        ],
        "projection_meta": {"is_partial": False, "dropped_items": 0, "reasons": []},
    }

    serialized = json.dumps(result, ensure_ascii=False)
    for canary in [
        "canary-counter",
        "canary-top-level",
        "canary-pipeline",
        "canary-instance",
        "canary-step-node-name",
        "canary-param",
        "canary-context",
        "canary-instance-info",
        "canary-log",
        "canary-input",
        "canary-output",
        "canary-ex-data",
    ]:
        assert canary not in serialized


def test_projector_marks_malformed_top_level_and_strict_leaf_types_partial():
    assert nodeman.project_subscription_task_step_summaries(["not-an-object"], None) == {
        "total": 0,
        "status_counter": {},
        "list": [],
        "projection_meta": {
            "is_partial": True,
            "dropped_items": 1,
            "reasons": ["invalid_top_level"],
        },
    }

    raw = {
        "total": "1",
        "status_counter": {"PENDING": "1", "SUCCESS": 0, "unknown": 10},
        "list": [
            _valid_task(task_id=True),
            {
                **_valid_task(task_id=10, record_id=11),
                "create_time": {"nested": "blocked"},
                "steps": [
                    {
                        **_valid_step(sub_steps=[_valid_sub_step()]),
                        "action": ["blocked"],
                        "target_hosts": [
                            {"sub_steps": [_valid_sub_step()]},
                            {"sub_steps": [_valid_sub_step(1)]},
                        ],
                    }
                ],
            },
            "not-an-object",
        ],
    }

    result = nodeman.project_subscription_task_step_summaries(raw, None)

    assert result["total"] == 0
    assert result["status_counter"] == {"SUCCESS": 0}
    assert len(result["list"]) == 1
    assert result["list"][0]["create_time"] is None
    assert result["list"][0]["steps"][0]["action"] is None
    assert result["list"][0]["steps"][0]["sub_steps"] == []
    assert result["projection_meta"] == {
        "is_partial": True,
        "dropped_items": 7,
        "reasons": [
            "invalid_total",
            "invalid_status_count",
            "invalid_task_instance_fields",
            "invalid_task_time",
            "invalid_step_nullable_field",
            "invalid_target_hosts",
            "invalid_task_instance",
        ],
    }


@pytest.mark.parametrize(
    "target_hosts",
    [
        None,
        {},
        [],
        [{}, {}],
        ["not-an-object"],
        [{"sub_steps": "not-a-list"}],
    ],
)
def test_projector_rejects_non_single_target_host_sub_step_shapes(target_hosts):
    step = _valid_step()
    step["target_hosts"] = target_hosts

    result = nodeman.project_subscription_task_step_summaries(
        _valid_raw([_valid_task(steps=[step])]),
        None,
    )

    assert result["list"][0]["steps"][0]["sub_steps"] == []
    assert result["projection_meta"]["is_partial"] is True
    assert result["projection_meta"]["dropped_items"] == 1
    assert result["projection_meta"]["reasons"] in (["invalid_target_hosts"], ["invalid_sub_steps"])


def test_projector_caps_task_instances_at_page_size_limit():
    tasks = [
        _valid_task(task_id=201, record_id=record_id, instance_id=f"instance-{record_id}")
        for record_id in range(1, 102)
    ]

    result = nodeman.project_subscription_task_step_summaries(_valid_raw(tasks), None)

    assert len(result["list"]) == 100
    assert result["projection_meta"] == {
        "is_partial": True,
        "dropped_items": 1,
        "reasons": ["task_instance_limit_exceeded"],
    }


def test_projector_enforces_per_instance_step_and_per_step_sub_step_limits():
    steps = [_valid_step(index, [_valid_sub_step(sub_index) for sub_index in range(101)]) for index in range(51)]

    result = nodeman.project_subscription_task_step_summaries(
        _valid_raw([_valid_task(steps=steps)]),
        None,
    )

    assert len(result["list"][0]["steps"]) == 50
    assert all(len(step["sub_steps"]) == 100 for step in result["list"][0]["steps"])
    assert result["projection_meta"] == {
        "is_partial": True,
        "dropped_items": 51,
        "reasons": ["step_limit_exceeded", "sub_step_limit_exceeded"],
    }


def test_projector_caps_page_step_and_sub_step_nodes_at_ten_thousand():
    full_steps = [_valid_step(index, [_valid_sub_step(sub_index) for sub_index in range(100)]) for index in range(50)]
    tasks = [
        _valid_task(task_id=201, record_id=301, instance_id="instance-one", steps=full_steps),
        _valid_task(task_id=201, record_id=302, instance_id="instance-two", steps=full_steps),
    ]

    result = nodeman.project_subscription_task_step_summaries(_valid_raw(tasks), None)

    projected_steps = [step for task in result["list"] for step in task["steps"]]
    projected_node_count = len(projected_steps) + sum(len(step["sub_steps"]) for step in projected_steps)
    assert projected_node_count == 10_000
    assert result["projection_meta"] == {
        "is_partial": True,
        "dropped_items": 100,
        "reasons": ["page_node_limit_exceeded"],
    }
