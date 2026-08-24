from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from alarm_backends.core.control.mixins.detect import DetectMixin
from alarm_backends.core.control.mixins.nodata import CheckMixin
from alarm_backends.core.detect_result.trim import (
    begin_check_result_producer,
    check_result_producer,
    trim_item_check_results_if_trigger_idle,
)
from alarm_backends.core.detect_result_retention import InvalidRetentionConfig
from core.errors.alarm_backends import LockError


class DetectSubject(DetectMixin):
    id = 2
    strategy = SimpleNamespace(id=1)

    @staticmethod
    def get_detect_result_expire_ttl():
        return 1800

    @staticmethod
    def is_detect_result_rank_trim_eligible():
        return True


class NoDataSubject(CheckMixin):
    id = 2
    strategy = SimpleNamespace(id=1)
    no_data_config = {"is_enabled": True, "continuous": 5}
    query_configs = [{"agg_interval": 60}]

    @staticmethod
    def get_detect_result_expire_ttl():
        return 1800

    @staticmethod
    def is_detect_result_rank_trim_eligible():
        return True


def _mock_check_result():
    check_result_class = MagicMock()
    write_pipeline = MagicMock()
    check_result_class.begin_pipeline_batch.return_value = write_pipeline
    check_result_class.return_value.check_result_cache_key = "check-result-key"
    return check_result_class, write_pipeline


def _trim_item(cache_keys=None):
    item = MagicMock()
    item.id = 2
    item.strategy.id = 1
    item.pop_check_result_trim_cache_keys.return_value = cache_keys or {"check-result-key"}
    item.is_detect_result_rank_trim_eligible.return_value = True
    item.get_detect_result_retention_point_required.return_value = 12
    return item


def _producer_key(*, count=1, current=True):
    producer_key = MagicMock()
    producer_key.get_key.return_value = "producer-key"
    producer_key.client.hlen.return_value = count
    producer_key.client.hexists.return_value = current
    return producer_key


def _producer_lock():
    producer_lock = MagicMock()
    producer_lock.refresh.return_value = True
    return producer_lock


def test_check_result_producer_clears_token_when_processing_fails():
    with (
        patch("alarm_backends.core.detect_result.trim.begin_check_result_producer", return_value="producer-token"),
        patch("alarm_backends.core.detect_result.trim.end_check_result_producer") as end_producer,
    ):
        try:
            with check_result_producer(1):
                raise RuntimeError("detect failed")
        except RuntimeError:
            pass

    end_producer.assert_called_once_with(1, "producer-token")


def test_check_result_producer_registration_failure_stops_before_gate():
    producer_key = MagicMock()
    producer_key.get_key.return_value = "producer-key"
    producer_key.client.hset.side_effect = RuntimeError("redis failed")

    with (
        patch("alarm_backends.core.detect_result.trim.CHECK_RESULT_PRODUCER_INFLIGHT_KEY", producer_key),
        patch("alarm_backends.core.detect_result.trim.service_lock") as producer_gate,
        pytest.raises(RuntimeError, match="redis failed"),
    ):
        begin_check_result_producer(1)

    producer_gate.assert_not_called()


def test_check_result_producer_waits_until_trim_gate_is_released():
    producer_key = MagicMock()
    producer_key.get_key.return_value = "producer-key"

    with (
        patch("alarm_backends.core.detect_result.trim.CHECK_RESULT_PRODUCER_INFLIGHT_KEY", producer_key),
        patch("alarm_backends.core.detect_result.trim.uniqid4", return_value="producer-token"),
        patch(
            "alarm_backends.core.detect_result.trim.service_lock",
            side_effect=[LockError(msg="trim active"), nullcontext()],
        ) as producer_gate,
    ):
        token = begin_check_result_producer(1)

    assert token == "producer-token"
    assert producer_gate.call_count == 2


def test_detect_registers_written_key_without_trimming_inside_write_pipeline():
    subject = DetectSubject()
    subject.register_check_result_trim_cache_key = MagicMock()
    check_result_class, write_pipeline = _mock_check_result()
    checkpoints = MagicMock()
    records = [
        SimpleNamespace(record_id="dimension.100", timestamp=100, value=1),
        SimpleNamespace(record_id="dimension.101", timestamp=101, value=2),
    ]

    with (
        patch("alarm_backends.core.control.mixins.detect.CheckResult", check_result_class),
        patch("alarm_backends.core.control.mixins.detect.LAST_CHECKPOINTS_CACHE_KEY", checkpoints),
    ):
        subject._update_monitor_d_checkpoint(records, [], level=1)

    write_pipeline.execute.assert_called_once_with()
    assert subject.register_check_result_trim_cache_key.call_count == 2
    subject.register_check_result_trim_cache_key.assert_called_with("check-result-key")
    check_result_class.trim_check_result_caches.assert_not_called()


def test_detect_event_item_does_not_register_for_rank_trim():
    subject = DetectSubject()
    subject.is_detect_result_rank_trim_eligible = MagicMock(return_value=False)
    subject.register_check_result_trim_cache_key = MagicMock()
    check_result_class, write_pipeline = _mock_check_result()
    checkpoints = MagicMock()
    records = [SimpleNamespace(record_id="dimension.100", timestamp=100, value=1)]

    with (
        patch("alarm_backends.core.control.mixins.detect.CheckResult", check_result_class),
        patch("alarm_backends.core.control.mixins.detect.LAST_CHECKPOINTS_CACHE_KEY", checkpoints),
    ):
        subject._update_monitor_d_checkpoint(records, [], level=1)

    write_pipeline.execute.assert_called_once_with()
    subject.register_check_result_trim_cache_key.assert_not_called()


def test_nodata_registers_written_key_without_trimming_inside_write_pipeline():
    subject = NoDataSubject()
    subject.register_check_result_trim_cache_key = MagicMock()
    check_result_class, write_pipeline = _mock_check_result()
    dimensions = {"bk_target_ip": "127.0.0.1", "__NO_DATA_DIMENSION__": True}

    with patch("alarm_backends.core.control.mixins.nodata.CheckResult", check_result_class):
        subject._update_dimensions_checkpoint(
            check_timestamp=100,
            target_instance_dimensions=[dimensions],
            target_dimensions_md5=["dimension"],
            data_dimensions=[],
            data_dimensions_md5=[],
            dimensions_md5_timestamp={},
        )

    write_pipeline.execute.assert_called_once_with()
    subject.register_check_result_trim_cache_key.assert_called_with("check-result-key")
    check_result_class.trim_check_result_caches.assert_not_called()


def test_pending_anomaly_prevents_subsequent_detect_batch_from_trimming():
    item = _trim_item()
    anomaly_list_key = MagicMock()
    anomaly_list_key.get_key.return_value = "anomaly-list-key"
    anomaly_list_key.client.llen.return_value = 1
    inflight_key = MagicMock()
    inflight_key.get_key.return_value = "inflight-key"
    inflight_key.client.hlen.return_value = 0
    producer_key = _producer_key()

    with (
        patch("alarm_backends.core.detect_result.trim.ANOMALY_LIST_KEY", anomaly_list_key),
        patch("alarm_backends.core.detect_result.trim.TRIGGER_CHECK_RESULT_INFLIGHT_KEY", inflight_key),
        patch("alarm_backends.core.detect_result.trim.CHECK_RESULT_PRODUCER_INFLIGHT_KEY", producer_key),
        patch("alarm_backends.core.detect_result.trim.routing_snapshot", return_value=nullcontext()),
        patch("alarm_backends.core.detect_result.trim.service_lock") as service_lock,
        patch("alarm_backends.core.detect_result.trim.CheckResult") as check_result,
    ):
        trimmed = trim_item_check_results_if_trigger_idle(item, "producer-token", _producer_lock())

    assert trimmed is False
    item.get_detect_result_retention_point_required.assert_called_once_with()
    service_lock.assert_not_called()
    check_result.trim_check_result_caches.assert_not_called()


def test_trigger_inflight_lock_prevents_detect_batch_from_trimming():
    item = _trim_item()
    anomaly_list_key = MagicMock()
    anomaly_list_key.get_key.return_value = "anomaly-list-key"
    anomaly_list_key.client.llen.return_value = 0
    inflight_key = MagicMock()
    inflight_key.get_key.return_value = "inflight-key"
    inflight_key.client.hlen.return_value = 0
    producer_key = _producer_key()

    with (
        patch("alarm_backends.core.detect_result.trim.ANOMALY_LIST_KEY", anomaly_list_key),
        patch("alarm_backends.core.detect_result.trim.TRIGGER_CHECK_RESULT_INFLIGHT_KEY", inflight_key),
        patch("alarm_backends.core.detect_result.trim.CHECK_RESULT_PRODUCER_INFLIGHT_KEY", producer_key),
        patch("alarm_backends.core.detect_result.trim.routing_snapshot", return_value=nullcontext()),
        patch(
            "alarm_backends.core.detect_result.trim.service_lock",
            side_effect=LockError(msg="trigger is processing"),
        ),
        patch("alarm_backends.core.detect_result.trim.CheckResult") as check_result,
    ):
        trimmed = trim_item_check_results_if_trigger_idle(item, "producer-token", _producer_lock())

    assert trimmed is False
    check_result.trim_check_result_caches.assert_not_called()


def test_trigger_inflight_marker_blocks_trim_after_lock_ttl_expires():
    item = _trim_item()
    anomaly_list_key = MagicMock()
    anomaly_list_key.get_key.return_value = "anomaly-list-key"
    anomaly_list_key.client.llen.return_value = 0
    inflight_key = MagicMock()
    inflight_key.get_key.return_value = "inflight-key"
    inflight_key.client.hlen.return_value = 1
    producer_key = _producer_key()

    with (
        patch("alarm_backends.core.detect_result.trim.ANOMALY_LIST_KEY", anomaly_list_key),
        patch("alarm_backends.core.detect_result.trim.TRIGGER_CHECK_RESULT_INFLIGHT_KEY", inflight_key),
        patch("alarm_backends.core.detect_result.trim.CHECK_RESULT_PRODUCER_INFLIGHT_KEY", producer_key),
        patch("alarm_backends.core.detect_result.trim.routing_snapshot", return_value=nullcontext()),
        patch("alarm_backends.core.detect_result.trim.service_lock") as service_lock,
        patch("alarm_backends.core.detect_result.trim.CheckResult") as check_result,
    ):
        trimmed = trim_item_check_results_if_trigger_idle(item, "producer-token", _producer_lock())

    assert trimmed is False
    service_lock.assert_not_called()
    check_result.trim_check_result_caches.assert_not_called()


def test_idle_trigger_allows_detect_batch_to_trim_exact_registered_keys():
    item = _trim_item({"key-1", "key-2"})
    anomaly_list_key = MagicMock()
    anomaly_list_key.get_key.return_value = "anomaly-list-key"
    anomaly_list_key.client.llen.return_value = 0
    inflight_key = MagicMock()
    inflight_key.get_key.return_value = "inflight-key"
    inflight_key.client.hlen.return_value = 0
    producer_key = _producer_key()
    producer_lock = _producer_lock()
    trigger_lock = _producer_lock()
    producer_gate_lock = _producer_lock()

    with (
        patch("alarm_backends.core.detect_result.trim.ANOMALY_LIST_KEY", anomaly_list_key),
        patch("alarm_backends.core.detect_result.trim.TRIGGER_CHECK_RESULT_INFLIGHT_KEY", inflight_key),
        patch("alarm_backends.core.detect_result.trim.CHECK_RESULT_PRODUCER_INFLIGHT_KEY", producer_key),
        patch("alarm_backends.core.detect_result.trim.routing_snapshot", return_value=nullcontext()),
        patch(
            "alarm_backends.core.detect_result.trim.service_lock",
            side_effect=[nullcontext(trigger_lock), nullcontext(producer_gate_lock)],
        ),
        patch("alarm_backends.core.detect_result.trim.CheckResult") as check_result,
    ):
        trimmed = trim_item_check_results_if_trigger_idle(item, "producer-token", producer_lock)
        args, kwargs = check_result.trim_check_result_caches.call_args
        before_chunk_result = kwargs["before_chunk"]()

    assert trimmed is True
    assert args == ({"key-1", "key-2"}, 12)
    assert before_chunk_result is True
    trigger_lock.refresh.assert_called_once_with()
    producer_gate_lock.refresh.assert_called_once_with()


def test_explicit_invalid_config_skips_hot_trim_and_logs(caplog):
    item = _trim_item()
    item.get_detect_result_retention_point_required.side_effect = InvalidRetentionConfig("invalid trigger window")
    anomaly_list_key = MagicMock()
    anomaly_list_key.get_key.return_value = "anomaly-list-key"
    inflight_key = MagicMock()
    inflight_key.get_key.return_value = "inflight-key"
    producer_key = _producer_key()

    with (
        patch("alarm_backends.core.detect_result.trim.ANOMALY_LIST_KEY", anomaly_list_key),
        patch("alarm_backends.core.detect_result.trim.TRIGGER_CHECK_RESULT_INFLIGHT_KEY", inflight_key),
        patch("alarm_backends.core.detect_result.trim.CHECK_RESULT_PRODUCER_INFLIGHT_KEY", producer_key),
        patch("alarm_backends.core.detect_result.trim.routing_snapshot", return_value=nullcontext()),
        patch("alarm_backends.core.detect_result.trim.service_lock") as service_lock,
        patch("alarm_backends.core.detect_result.trim.CheckResult") as check_result,
        caplog.at_level("WARNING", logger="core.detect_result"),
    ):
        trimmed = trim_item_check_results_if_trigger_idle(item, "producer-token", _producer_lock())

    assert trimmed is False
    assert "invalid trigger window" in caplog.text
    service_lock.assert_not_called()
    check_result.trim_check_result_caches.assert_not_called()


def test_other_check_result_producer_prevents_hot_trim():
    item = _trim_item()
    anomaly_list_key = MagicMock()
    anomaly_list_key.get_key.return_value = "anomaly-list-key"
    anomaly_list_key.client.llen.return_value = 0
    inflight_key = MagicMock()
    inflight_key.get_key.return_value = "inflight-key"
    inflight_key.client.hlen.return_value = 0
    producer_key = _producer_key(count=2)

    with (
        patch("alarm_backends.core.detect_result.trim.ANOMALY_LIST_KEY", anomaly_list_key),
        patch("alarm_backends.core.detect_result.trim.TRIGGER_CHECK_RESULT_INFLIGHT_KEY", inflight_key),
        patch("alarm_backends.core.detect_result.trim.CHECK_RESULT_PRODUCER_INFLIGHT_KEY", producer_key),
        patch("alarm_backends.core.detect_result.trim.routing_snapshot", return_value=nullcontext()),
        patch("alarm_backends.core.detect_result.trim.service_lock") as service_lock,
        patch("alarm_backends.core.detect_result.trim.CheckResult") as check_result,
    ):
        trimmed = trim_item_check_results_if_trigger_idle(item, "producer-token", _producer_lock())

    assert trimmed is False
    service_lock.assert_not_called()
    check_result.trim_check_result_caches.assert_not_called()


def test_lost_detect_lock_prevents_hot_trim():
    item = _trim_item()
    anomaly_list_key = MagicMock()
    anomaly_list_key.get_key.return_value = "anomaly-list-key"
    anomaly_list_key.client.llen.return_value = 0
    inflight_key = MagicMock()
    inflight_key.get_key.return_value = "inflight-key"
    inflight_key.client.hlen.return_value = 0
    producer_key = _producer_key()
    producer_lock = _producer_lock()
    producer_lock.refresh.return_value = False
    producer_lock.acquire.return_value = False

    with (
        patch("alarm_backends.core.detect_result.trim.ANOMALY_LIST_KEY", anomaly_list_key),
        patch("alarm_backends.core.detect_result.trim.TRIGGER_CHECK_RESULT_INFLIGHT_KEY", inflight_key),
        patch("alarm_backends.core.detect_result.trim.CHECK_RESULT_PRODUCER_INFLIGHT_KEY", producer_key),
        patch("alarm_backends.core.detect_result.trim.routing_snapshot", return_value=nullcontext()),
        patch("alarm_backends.core.detect_result.trim.service_lock", return_value=nullcontext()),
        patch("alarm_backends.core.detect_result.trim.CheckResult") as check_result,
    ):
        trimmed = trim_item_check_results_if_trigger_idle(item, "producer-token", producer_lock)

    assert trimmed is False
    producer_lock.refresh.assert_called_once_with()
    producer_lock.acquire.assert_called_once_with(0.1)
    check_result.trim_check_result_caches.assert_not_called()
