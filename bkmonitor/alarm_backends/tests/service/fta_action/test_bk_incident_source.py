import copy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from alarm_backends.service.fta_action.bk_incident.processor import ActionProcessor
from alarm_backends.service.fta_action.common import processor as common_processor
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
