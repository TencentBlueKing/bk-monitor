import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, PropertyMock

import pytest

from alarm_backends.service.fta_action.bk_incident.processor import ActionProcessor
from alarm_backends.service.fta_action.common import processor as common_processor
from api.bk_incident.default import CreateTaskResource
from bkmonitor.models.fta.action import ActionInstance
from constants.action import ActionSignal


@pytest.fixture
def request_schema():
    return {
        "function": "create_task",
        "resource_module": "api.bk_incident.default",
        "resource_class": "CreateTaskResource",
        "inputs": [
            {"key": "template_id", "value": "execute_config.template_id", "format": "jmespath"},
            {"key": "constants", "value": {"${ip}": "example-host"}},
        ],
        "outputs": [{"key": "task_id", "value": "response.task_id"}],
    }


def make_processor(signal=ActionSignal.DEMO, execute_config=None, processor_class=ActionProcessor):
    processor = object.__new__(processor_class)
    processor.action = SimpleNamespace(
        signal=signal, assignee=["operator"], action_plugin={"plugin_key": "bk_incident"}
    )
    processor.execute_config = {"template_id": 1, **(execute_config or {})}
    processor.inputs = {"execute_config": processor.execute_config}
    return processor


@pytest.mark.parametrize(
    ("signal", "execute_config", "expected"),
    [
        (ActionSignal.DEMO, {}, "bk_monitor_debug"),
        (ActionSignal.DEMO, {"source": None}, "bk_monitor_debug"),
        (ActionSignal.DEMO, {"source": ""}, "bk_monitor_debug"),
        (ActionSignal.ABNORMAL, {}, "bk_monitor"),
        (ActionSignal.MANUAL, {}, "bk_monitor"),
        (ActionSignal.DEMO, {"source": "custom_source"}, "custom_source"),
    ],
)
def test_old_snapshot_passes_source_to_resource(monkeypatch, request_schema, signal, execute_config, expected):
    resource = Mock()
    resource.return_value.request.return_value = {"task_id": 42}
    monkeypatch.setattr(common_processor, "import_module", lambda name: SimpleNamespace(CreateTaskResource=resource))
    processor = make_processor(signal, execute_config)
    before = copy.deepcopy(request_schema)

    assert processor.run_request_action(request_schema) == {"task_id": 42}
    resource.return_value.request.assert_called_once_with(
        template_id=1,
        constants={"${ip}": "example-host"},
        assignee=["operator"],
        action_plugin_key="bk_incident",
        source=expected,
    )
    assert request_schema == before


@pytest.mark.parametrize("source", ["bk_monitor", "custom_source"])
def test_explicit_mapping_is_preserved(request_schema, source):
    request_schema["inputs"].append({"key": "source", "value": source})
    processor = make_processor(execute_config={"source": "bk_monitor_debug"})
    assert processor.get_request_inputs(request_schema)["source"] == source


@pytest.mark.parametrize("source", [None, ""])
def test_empty_mapping_uses_debug_source(request_schema, source):
    request_schema["inputs"].append({"key": "source", "value": source})
    assert make_processor().get_request_inputs(request_schema)["source"] == "bk_monitor_debug"


@pytest.mark.parametrize(
    "signal,execute_config,expected",
    [
        (ActionSignal.DEMO, {"source": "bk_monitor_debug"}, "bk_monitor_debug"),
        (ActionSignal.ABNORMAL, {}, "bk_monitor"),
    ],
)
def test_upgraded_mapping_uses_execute_config(request_schema, signal, execute_config, expected):
    request_schema["inputs"].append(
        {"key": "source", "value": "execute_config.source || 'bk_monitor'", "format": "jmespath"}
    )
    assert make_processor(signal, execute_config).get_request_inputs(request_schema)["source"] == expected


def test_fallback_runs_after_request_mapping_and_rendering(request_schema):
    request_schema["request_data_mapping"] = {"source": "{{ debug_source }}"}
    request_schema["render_inputs"] = True
    processor = make_processor()
    processor.context = {"debug_source": ""}
    assert processor.get_request_inputs(request_schema)["source"] == "bk_monitor_debug"
    processor.context["debug_source"] = "rendered_custom_source"
    assert processor.get_request_inputs(request_schema)["source"] == "rendered_custom_source"


@pytest.mark.parametrize(
    "change",
    [
        {"function": "start_task", "resource_class": "OperateTaskResource"},
        {"function": "schedule", "resource_class": "GetTaskStatusResource"},
        {"resource_module": "api.sops"},
        {"resource_class": "OtherResource"},
    ],
)
def test_other_operations_are_unchanged(request_schema, change):
    request_schema.update(change)
    assert "source" not in make_processor().get_request_inputs(request_schema)


def test_common_processor_does_not_add_incident_source(request_schema):
    processor = make_processor(processor_class=common_processor.ActionProcessor)
    assert "source" not in processor.get_request_inputs(request_schema)


@pytest.fixture
def builtin_create_task_schema():
    initial = Path(__file__).resolve().parents[4] / "support-files/fta/action_plugin_initial.json"
    plugins = json.loads(initial.read_text(encoding="utf-8"))
    plugin = next(plugin for plugin in plugins if plugin["id"] == 110)
    return next(node for node in plugin["backend_config"] if node["function"] == "create_task")


def assert_builtin_request(monkeypatch, schema, signal, execute_config, expected_source, context=None):
    resource = Mock()
    resource.return_value.request.return_value = {"task_id": 42, "task_url": "https://example.com/task/42"}
    monkeypatch.setattr(common_processor, "import_module", lambda name: SimpleNamespace(CreateTaskResource=resource))
    processor = make_processor(signal, {"template_detail_dict": {"${ip}": "example-host"}, **execute_config})
    processor.inputs.update({"bk_biz_id": 2, "action_name": "example"})
    processor.context = {"alarm": {"callback_message": "{}"}, **(context or {})}
    before = copy.deepcopy(schema)

    # 固化 #11470 的请求契约，避免被测实现和动态基线同时改变而掩盖回归。
    assert processor.run_request_action(schema) == {"task_id": 42, "url": "https://example.com/task/42"}
    resource.return_value.request.assert_called_once_with(
        bk_biz_id=2,
        template_id=1,
        constants={"${ip}": "example-host", "${_event_context}": "{}"},
        name="example",
        assignee=["operator"],
        action_plugin_key="bk_incident",
        source=expected_source,
    )
    assert schema == before


@pytest.mark.parametrize(
    "signal,execute_config,expected_source",
    [
        pytest.param(ActionSignal.ABNORMAL, {}, "bk_monitor", id="normal-default"),
        pytest.param(ActionSignal.DEMO, {"source": "bk_monitor_debug"}, "bk_monitor_debug", id="debug-source"),
        pytest.param(ActionSignal.DEMO, {"source": "bk_monitor"}, "bk_monitor", id="explicit-monitor-source"),
        pytest.param(ActionSignal.DEMO, {"source": "custom_source"}, "custom_source", id="custom-source"),
        pytest.param(ActionSignal.DEMO, {"source": ""}, "bk_monitor", id="empty-source-mapping-default"),
        pytest.param(ActionSignal.DEMO, {}, "bk_monitor", id="missing-source-mapping-default"),
    ],
)
def test_pr11470_builtin_template_contract(
    monkeypatch, builtin_create_task_schema, signal, execute_config, expected_source
):
    assert_builtin_request(monkeypatch, builtin_create_task_schema, signal, execute_config, expected_source)


@pytest.mark.parametrize("source", ["bk_monitor", "bk_monitor_debug", "custom_source"])
def test_pr11470_rendered_override_contract(monkeypatch, builtin_create_task_schema, source):
    builtin_create_task_schema["request_data_mapping"] = {"source": "{{ override_source }}"}
    assert_builtin_request(
        monkeypatch,
        builtin_create_task_schema,
        ActionSignal.DEMO,
        {"source": "conflicting_source"},
        source,
        context={"override_source": source},
    )


@pytest.fixture
def converged_callback():
    processor = make_processor(signal=ActionSignal.ABNORMAL, execute_config={"template_detail_dict": {}})
    processor.action = ActionInstance(
        id=101,
        signal=ActionSignal.ABNORMAL,
        alerts=["102"],
        strategy_id=103,
        bk_biz_id="104",
        strategy_relation_id=105,
        strategy={"actions": [{"id": 105, "options": {"converge_config": {"is_enabled": True}}}]},
        create_time=datetime(2025, 1, 1, tzinfo=UTC),
        action_plugin={"plugin_key": "bk_incident"},
    )
    processor.inputs.update({"bk_biz_id": 104, "action_name": "example"})
    group_id = PropertyMock(return_value=106)
    instance_context = SimpleNamespace()
    context_class = type("ActionInstanceContext", (), {"converge_id": group_id})
    instance_context.action_instance = context_class()
    processor.action_context = instance_context
    event_context = {"bk_biz_id": 104, "event": {"event_id": "102"}, "strategy": {"id": 103}}
    return processor, group_id, event_context


@pytest.mark.parametrize("as_json", [True, False], ids=["json-string", "object"])
def test_converged_callback_preserves_representation(
    converged_callback, builtin_create_task_schema, monkeypatch, as_json
):
    processor, group_id, event_context = converged_callback
    schema = builtin_create_task_schema
    processor.context = {"alarm": {"callback_message": json.dumps(event_context)}}
    if not as_json:
        schema["request_data_mapping"] = {"constants": {"${_event_context}": event_context}}
    resource = Mock()
    resource.return_value.request.return_value = {"task_id": 1, "task_url": "https://example.com/task/1"}
    monkeypatch.setattr(common_processor, "import_module", lambda name: SimpleNamespace(CreateTaskResource=resource))

    assert processor.run_request_action(schema) == {"task_id": 1, "url": "https://example.com/task/1"}

    serializer = CreateTaskResource.RequestSerializer(data=resource.return_value.request.call_args.kwargs)
    assert serializer.is_valid(), serializer.errors
    context = serializer.validated_data["constants"]["${_event_context}"]
    assert isinstance(context, str if as_json else dict)
    assert (json.loads(context) if as_json else context) == {
        **event_context,
        "monitor_action_group_ref": {
            "schema_version": 1,
            "action_created_ts": 1735689600,
            "action_id": "101",
            "group_id": "106",
            "alert_id": "102",
        },
    }
    assert "monitor_action_group_ref" not in event_context
    group_id.assert_called_once_with()


@pytest.mark.parametrize(
    "request_overrides,action_overrides,callback",
    [
        ({"source": "custom_source"}, {}, None),
        ({}, {"signal": ActionSignal.DEMO}, None),
        ({}, {"signal": ActionSignal.MANUAL}, None),
        ({}, {"signal": ActionSignal.RECOVERED}, None),
        ({"bk_biz_id": 107}, {}, None),
        ({"scope_value": "107"}, {}, None),
        ({}, {"bk_biz_id": "107"}, None),
        ({}, {"strategy_id": 107}, None),
        ({}, {"alerts": ["107"]}, None),
        ({}, {"strategy": {}}, None),
        ({}, {"strategy": {"actions": [{"id": 105, "options": {"converge_config": {"is_enabled": False}}}]}}, None),
        ({}, {"create_time": None}, None),
        ({}, {}, "{invalid"),
        ({}, {}, "[]"),
        ({}, {}, '{"event": false}'),
    ],
)
def test_ineligible_callback_skips_group_lookup(
    converged_callback, builtin_create_task_schema, request_overrides, action_overrides, callback
):
    processor, group_id, event_context = converged_callback
    for key, value in action_overrides.items():
        setattr(processor.action, key, value)
    builtin_create_task_schema["request_data_mapping"] = request_overrides
    raw_context = callback if callback is not None else json.dumps(event_context)
    processor.context = {"alarm": {"callback_message": raw_context}}

    inputs = processor.get_request_inputs(builtin_create_task_schema)

    assert inputs["constants"]["${_event_context}"] == raw_context
    group_id.assert_not_called()


@pytest.mark.parametrize("group", [None, 0, True, RuntimeError("lookup failed")])
def test_unavailable_group_preserves_dispatch(converged_callback, builtin_create_task_schema, group):
    processor, group_id, event_context = converged_callback
    if isinstance(group, Exception):
        group_id.side_effect = group
    else:
        group_id.return_value = group
    raw_context = json.dumps(event_context)
    processor.context = {"alarm": {"callback_message": raw_context}}

    assert processor.get_request_inputs(builtin_create_task_schema)["constants"]["${_event_context}"] == raw_context
    group_id.assert_called_once_with()
