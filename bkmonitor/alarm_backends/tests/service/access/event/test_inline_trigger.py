import pytest

from alarm_backends.service.access.event import processor as event_processor
from alarm_backends.service.access.event import processorv2 as event_processor_v2
from alarm_backends.service.trigger import runner
from bkmonitor.define import global_config


@pytest.mark.parametrize(
    ("module", "processor_cls"),
    [
        (event_processor, event_processor.BaseAccessEventProcess),
        (event_processor_v2, event_processor_v2.BaseAccessEventProcess),
    ],
)
def test_event_push_defers_signal_and_records_inline_items_when_enabled(mocker, module, processor_cls):
    processor = processor_cls()
    item = mocker.MagicMock(id=2)
    item.strategy.id = 1
    event = mocker.MagicMock(
        md5_dimension="dimension",
        items=[item],
        is_retains={2: True},
        inhibitions={2: False},
    )
    event.to_str.return_value = "point"
    processor.record_list = [event]
    mocker.patch.object(processor, "check_qos")
    mocker.patch.object(processor, "push_to_check_result")
    mocker.patch.object(module.PriorityChecker, "check_records")
    mocker.patch.object(module.settings, "ENABLE_EVENT_INLINE_TRIGGER", True, create=True)
    mocker.patch.object(module, "metrics")

    list_key = mocker.patch.object(module.key, "ANOMALY_LIST_KEY")
    list_key.get_key.return_value = "anomaly-list"
    list_pipeline = list_key.client.pipeline.return_value
    signal_key = mocker.patch.object(module.key, "ANOMALY_SIGNAL_KEY")

    processor.push()

    list_pipeline.lpush.assert_called_once_with("anomaly-list", "point")
    list_pipeline.expire.assert_called_once_with("anomaly-list", list_key.ttl)
    list_pipeline.execute.assert_called_once_with()
    signal_key.client.lpush.assert_not_called()
    assert processor.inline_trigger_items == [(1, 2)]


@pytest.mark.parametrize(
    ("module", "processor_cls"),
    [
        (event_processor, event_processor.BaseAccessEventProcess),
        (event_processor_v2, event_processor_v2.BaseAccessEventProcess),
    ],
)
def test_event_push_keeps_signal_path_when_inline_is_disabled(mocker, module, processor_cls):
    processor = processor_cls()
    item = mocker.MagicMock(id=2)
    item.strategy.id = 1
    event = mocker.MagicMock(
        md5_dimension="dimension",
        items=[item],
        is_retains={2: True},
        inhibitions={2: False},
    )
    event.to_str.return_value = "point"
    processor.record_list = [event]
    mocker.patch.object(processor, "check_qos")
    mocker.patch.object(processor, "push_to_check_result")
    mocker.patch.object(module.PriorityChecker, "check_records")
    mocker.patch.object(module.settings, "ENABLE_EVENT_INLINE_TRIGGER", False, create=True)
    mocker.patch.object(module, "metrics")

    list_key = mocker.patch.object(module.key, "ANOMALY_LIST_KEY")
    list_key.get_key.return_value = "anomaly-list"
    signal_key = mocker.patch.object(module.key, "ANOMALY_SIGNAL_KEY")
    signal_key.get_key.return_value = "anomaly-signal"

    processor.push()

    signal_key.client.lpush.assert_called_once_with("anomaly-signal", "1.2")
    signal_key.client.expire.assert_called_once_with("anomaly-signal", signal_key.ttl)
    assert processor.inline_trigger_items == []


@pytest.mark.parametrize(
    "processor_cls",
    [event_processor.BaseAccessEventProcess, event_processor_v2.BaseAccessEventProcess],
)
def test_event_process_runs_recorded_inline_items(mocker, processor_cls):
    processor = processor_cls()
    processor.inline_trigger_items = [(1, 2), (3, 4)]
    run_event_trigger_item = mocker.patch.object(runner, "run_event_trigger_item", create=True)

    processor.run_inline_trigger()

    assert run_event_trigger_item.call_args_list == [mocker.call(1, 2), mocker.call(3, 4)]


def test_event_inline_trigger_settings_are_dynamic():
    enabled = global_config.ADVANCED_OPTIONS["ENABLE_EVENT_INLINE_TRIGGER"]
    concurrency = global_config.ADVANCED_OPTIONS["EVENT_INLINE_TRIGGER_MAX_CONCURRENCY_PER_ITEM"]

    assert enabled.default is False
    assert concurrency.default == 1
    assert concurrency.min_value == 1
