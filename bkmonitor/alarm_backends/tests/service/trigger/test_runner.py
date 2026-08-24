import logging
from contextlib import nullcontext

import pytest

from alarm_backends.service.trigger import processor as trigger_processor
from alarm_backends.service.trigger import runner
from alarm_backends.service.trigger.processor import TriggerProcessor
from core.errors.alarm_backends import LockError


def test_run_trigger_item_is_available():
    assert callable(getattr(runner, "run_trigger_item", None))


def test_run_trigger_item_records_success_for_nonempty_batch(mocker):
    processor = mocker.MagicMock()
    processor.process.return_value = 2
    processor_cls = mocker.patch.object(runner, "TriggerProcessor", create=True, return_value=processor)
    lock = mocker.patch.object(runner, "service_lock", create=True, return_value=nullcontext())
    fake_metrics = mocker.MagicMock(TOTAL_TAG="__total__")
    fake_metrics.StatusEnum.from_exc.return_value = "success"
    mocker.patch.object(runner, "metrics", fake_metrics, create=True)

    pulled_count = runner.run_trigger_item("1", "2", executor="detect_inline")

    assert pulled_count == 2
    lock.assert_called_once()
    processor_cls.assert_called_once_with("1", "2")
    fake_metrics.TRIGGER_PROCESS_TIME.labels.assert_called_once_with(strategy_id="__total__")
    fake_metrics.TRIGGER_PROCESS_TIME.labels.return_value.observe.assert_called_once()
    fake_metrics.TRIGGER_PROCESS_COUNT.labels.assert_called_once_with(
        strategy_id="__total__", status="success", exception=None
    )
    fake_metrics.TRIGGER_PROCESS_COUNT.labels.return_value.inc.assert_called_once_with()


def test_run_trigger_item_does_not_record_success_for_empty_batch(mocker):
    processor = mocker.MagicMock()
    processor.process.return_value = 0
    mocker.patch.object(runner, "TriggerProcessor", return_value=processor)
    mocker.patch.object(runner, "service_lock", return_value=nullcontext())
    fake_metrics = mocker.MagicMock(TOTAL_TAG="__total__")
    mocker.patch.object(runner, "metrics", fake_metrics)
    mocker.patch.object(
        runner,
        "settings",
        mocker.MagicMock(ENABLE_DETECT_INLINE_TRIGGER=True),
        create=True,
    )

    pulled_count = runner.run_trigger_item("1", "2")

    assert pulled_count == 0
    fake_metrics.TRIGGER_PROCESS_TIME.labels.assert_not_called()
    fake_metrics.TRIGGER_PROCESS_COUNT.labels.assert_not_called()


def test_run_trigger_item_preserves_empty_batch_metrics_when_inline_is_disabled(mocker):
    processor = mocker.MagicMock()
    processor.process.return_value = 0
    mocker.patch.object(runner, "TriggerProcessor", return_value=processor)
    mocker.patch.object(runner, "service_lock", return_value=nullcontext())
    fake_metrics = mocker.MagicMock(TOTAL_TAG="__total__")
    fake_metrics.StatusEnum.from_exc.return_value = "success"
    mocker.patch.object(runner, "metrics", fake_metrics)
    mocker.patch.object(
        runner,
        "settings",
        mocker.MagicMock(ENABLE_DETECT_INLINE_TRIGGER=False),
        create=True,
    )

    pulled_count = runner.run_trigger_item("1", "2")

    assert pulled_count == 0
    fake_metrics.TRIGGER_PROCESS_TIME.labels.assert_called_once_with(strategy_id="__total__")
    fake_metrics.TRIGGER_PROCESS_TIME.labels.return_value.observe.assert_called_once()
    fake_metrics.TRIGGER_PROCESS_COUNT.labels.assert_called_once_with(
        strategy_id="__total__", status="success", exception=None
    )
    fake_metrics.TRIGGER_PROCESS_COUNT.labels.return_value.inc.assert_called_once_with()


def test_run_trigger_item_records_and_swallows_processing_error(mocker):
    error = ValueError("boom")
    processor = mocker.MagicMock()
    processor.process.side_effect = error
    mocker.patch.object(runner, "TriggerProcessor", return_value=processor)
    mocker.patch.object(runner, "service_lock", return_value=nullcontext())
    fake_metrics = mocker.MagicMock(TOTAL_TAG="__total__")
    fake_metrics.StatusEnum.from_exc.return_value = "failed"
    mocker.patch.object(runner, "metrics", fake_metrics)

    pulled_count = runner.run_trigger_item("1", "2", executor="detect_inline")

    assert pulled_count == 0
    fake_metrics.TRIGGER_PROCESS_TIME.labels.return_value.observe.assert_called_once()
    fake_metrics.TRIGGER_PROCESS_COUNT.labels.assert_called_once_with(
        strategy_id="__total__", status="failed", exception=error
    )
    fake_metrics.TRIGGER_PROCESS_COUNT.labels.return_value.inc.assert_called_once_with()


def test_run_trigger_item_event_inline_skips_lock_and_propagates_processing_error(mocker):
    error = ValueError("boom")
    processor = mocker.MagicMock()
    processor.process.side_effect = error
    processor_cls = mocker.patch.object(runner, "TriggerProcessor", return_value=processor)
    lock = mocker.patch.object(runner, "service_lock")
    fake_metrics = mocker.MagicMock(TOTAL_TAG="__total__")
    fake_metrics.StatusEnum.from_exc.return_value = "failed"
    mocker.patch.object(runner, "metrics", fake_metrics)

    with pytest.raises(ValueError) as raised:
        runner.run_trigger_item(
            "1",
            "2",
            executor="event_inline",
            acquire_lock=False,
            max_process_count=1000,
            requeue_on_full=False,
            raise_process_error=True,
            concurrent_rate_limit=True,
        )

    assert raised.value is error
    lock.assert_not_called()
    processor_cls.assert_called_once_with(
        "1",
        "2",
        max_process_count=1000,
        requeue_on_full=False,
        concurrent_rate_limit=True,
    )


def test_run_trigger_item_propagates_lock_error_without_recording_result(mocker):
    error = LockError(msg="locked")
    mocker.patch.object(runner, "service_lock", side_effect=error)
    fake_metrics = mocker.MagicMock(TOTAL_TAG="__total__")
    mocker.patch.object(runner, "metrics", fake_metrics)

    with pytest.raises(LockError) as raised:
        runner.run_trigger_item("1", "2", executor="detect_inline")

    assert raised.value is error
    fake_metrics.TRIGGER_PROCESS_TIME.labels.assert_not_called()
    fake_metrics.TRIGGER_PROCESS_COUNT.labels.assert_not_called()


def test_trigger_processor_returns_pulled_count(mocker):
    processor = object.__new__(TriggerProcessor)
    processor.pull = mocker.MagicMock(return_value=2)
    processor.strategy = mocker.MagicMock()
    processor.strategy.in_alarm_time.return_value = (True, None)
    processor.anomaly_points = ["first", "second"]
    processor.process_point = mocker.MagicMock()
    processor.push = mocker.MagicMock()

    pulled_count = processor.process()

    assert pulled_count == 2
    assert processor.process_point.call_args_list == [mocker.call("first"), mocker.call("second")]
    processor.push.assert_called_once_with()


def test_trigger_processor_pull_returns_actual_count(mocker):
    processor = object.__new__(TriggerProcessor)
    processor.strategy_id = "1"
    processor.item_id = "2"
    processor.anomaly_list_key = "anomaly.list.1.2"
    processor.max_process_count = 100
    processor.requeue_on_full = True

    mocker.patch.object(trigger_processor, "ANOMALY_LIST_KEY")
    native_client = mocker.MagicMock()
    native_client.eval.return_value = ["new", "old"]
    mocker.patch.object(trigger_processor, "routed_client", return_value=nullcontext(native_client))
    mocker.patch.object(trigger_processor, "metrics")

    pulled_count = processor.pull()

    assert pulled_count == 2
    assert processor.anomaly_points == ["old", "new"]
    native_client.eval.assert_called_once_with(
        trigger_processor.ANOMALY_LIST_PULL_SCRIPT,
        1,
        "anomaly.list.1.2",
        100,
    )


def test_trigger_processor_empty_pull_keeps_warning_without_requeue(mocker, caplog):
    processor = object.__new__(TriggerProcessor)
    processor.strategy_id = "1"
    processor.item_id = "2"
    processor.anomaly_list_key = "anomaly.list.1.2"
    processor.max_process_count = 100
    processor.requeue_on_full = True

    mocker.patch.object(trigger_processor, "ANOMALY_LIST_KEY")
    native_client = mocker.MagicMock()
    native_client.eval.return_value = []
    anomaly_signal_key = mocker.patch.object(trigger_processor, "ANOMALY_SIGNAL_KEY")
    mocker.patch.object(trigger_processor, "routed_client", return_value=nullcontext(native_client))
    mocker.patch.object(trigger_processor, "metrics")

    with caplog.at_level(logging.WARNING, logger="trigger"):
        pulled_count = processor.pull()

    assert pulled_count == 0
    anomaly_signal_key.client.delay.assert_not_called()
    assert "pull 0 record" in caplog.text
