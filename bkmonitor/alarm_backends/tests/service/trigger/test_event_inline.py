from contextlib import contextmanager

from alarm_backends.service.trigger import processor as trigger_processor
from alarm_backends.service.trigger import runner
from alarm_backends.service.trigger.processor import TriggerProcessor


def test_event_trigger_lease_uses_routed_native_client(mocker):
    native_client = mocker.MagicMock()
    native_client.eval.return_value = 1

    @contextmanager
    def fake_routed_client(*args, **kwargs):
        yield native_client

    lease_key = mocker.patch.object(runner, "EVENT_INLINE_TRIGGER_LEASE_KEY", create=True)
    lease_key.get_key.return_value = "event-trigger-lease"
    mocker.patch.object(runner, "routed_client", side_effect=fake_routed_client, create=True)
    mocker.patch.object(runner.time, "time", return_value=100)

    acquired = runner._acquire_event_trigger_lease(1, 2, "token", 3)

    assert acquired is True
    native_client.eval.assert_called_once_with(
        runner.EVENT_TRIGGER_ACQUIRE_LEASE_SCRIPT,
        1,
        "event-trigger-lease",
        100,
        100 + runner.EVENT_TRIGGER_LEASE_TTL,
        "token",
        3,
        runner.EVENT_TRIGGER_LEASE_TTL * 2,
    )


def test_event_inline_trigger_drains_batches_until_list_is_empty(mocker):
    mocker.patch.object(runner.settings, "EVENT_INLINE_TRIGGER_MAX_CONCURRENCY_PER_ITEM", 2, create=True)
    mocker.patch.object(runner, "_acquire_event_trigger_lease", return_value=True, create=True)
    run_trigger_item = mocker.patch.object(runner, "run_trigger_item", side_effect=[1000, 5])
    finish_batch = mocker.patch.object(
        runner,
        "_finish_event_trigger_batch",
        side_effect=[True, False],
        create=True,
    )

    pulled_count = runner.run_event_trigger_item(1, 2)

    assert pulled_count == 1005
    assert run_trigger_item.call_count == 2
    run_trigger_item.assert_called_with(
        1,
        2,
        executor="event_inline",
        acquire_lock=False,
        max_process_count=runner.EVENT_TRIGGER_BATCH_SIZE,
        requeue_on_full=False,
        raise_process_error=True,
        concurrent_rate_limit=True,
    )
    assert finish_batch.call_count == 2


def test_event_inline_trigger_returns_when_item_concurrency_is_full(mocker):
    mocker.patch.object(runner.settings, "EVENT_INLINE_TRIGGER_MAX_CONCURRENCY_PER_ITEM", 2, create=True)
    mocker.patch.object(runner, "_acquire_event_trigger_lease", return_value=False, create=True)
    run_trigger_item = mocker.patch.object(runner, "run_trigger_item")

    assert runner.run_event_trigger_item(1, 2) == 0
    run_trigger_item.assert_not_called()


def test_event_inline_trigger_releases_lease_and_publishes_fallback_signal_on_error(mocker):
    mocker.patch.object(runner.settings, "EVENT_INLINE_TRIGGER_MAX_CONCURRENCY_PER_ITEM", 2, create=True)
    mocker.patch.object(runner, "_acquire_event_trigger_lease", return_value=True, create=True)
    mocker.patch.object(runner, "run_trigger_item", side_effect=RuntimeError("boom"))
    mocker.patch.object(runner, "_release_event_trigger_lease", return_value=3, create=True)
    publish_signals = mocker.patch.object(runner.BaseAbnormalPushProcessor, "publish_anomaly_signals", create=True)

    assert runner.run_event_trigger_item(1, 2) == 0
    publish_signals.assert_called_once_with(["1.2"])


def test_atomic_rate_limit_reservation_never_over_allows(mocker):
    processor = object.__new__(TriggerProcessor)
    processor.strategy_id = 1
    processor.item_id = 2
    records = [{"event_record": {"data": {"time": 100, "record_id": str(index)}}} for index in range(3)]
    rate_limit_key = mocker.patch.object(trigger_processor, "TRIGGER_EVENT_RATE_LIMIT_KEY")
    rate_limit_key.get_key.return_value = "rate-limit"
    rate_limit_key.client.pipeline.return_value.execute.return_value = [7, True]
    mocker.patch.object(trigger_processor, "TRIGGER_EVENT_RATE_LIMIT_THRESHOLD", 5)

    allowed_records, batch_counts, ts_keys, drop_counts = processor._reserve_rate_limit(records)

    assert allowed_records == records[:1]
    assert batch_counts == {}
    assert ts_keys == {}
    assert drop_counts == {100: 2}
    rate_limit_key.client.pipeline.return_value.incrby.assert_called_once_with("rate-limit", 3)
    rate_limit_key.client.pipeline.return_value.expire.assert_called_once_with("rate-limit", rate_limit_key.ttl)
