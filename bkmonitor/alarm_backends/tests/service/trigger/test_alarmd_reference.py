"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
import json
from types import SimpleNamespace
from unittest import mock

import pytest
from django.conf import settings

from alarm_backends.core.alarmd import reference_publisher as reference_publisher_module
from alarm_backends.core.alert.adapter import MonitorEventAdapter
from alarm_backends.service.trigger.processor import TriggerProcessor
from alarm_backends.tests.alarmd_fixtures import TRIGGER_POINT, TRIGGER_STRATEGY


def test_trigger_reference_capture_is_lightweight_and_follows_real_checker_result():
    point = copy.deepcopy(TRIGGER_POINT)
    strategy = copy.deepcopy(TRIGGER_STRATEGY)
    event_record = _triggered_event(point)
    processor = _processor()
    processor.get_strategy_snapshot = mock.Mock(return_value=strategy)
    processor.get_strategy_snapshot_legacy_json = mock.Mock()

    checker = mock.Mock()
    checker.check.return_value = ([], event_record)
    checker.is_no_data_point.return_value = False
    with (
        mock.patch("alarm_backends.service.trigger.processor.AnomalyChecker", return_value=checker),
        mock.patch.object(processor, "is_alarmd_reference_selected", return_value=True),
    ):
        processor.process_point(json.dumps(point))

    assert processor.reference_candidates == [
        {
            "strategy_snapshot_key": point["strategy_snapshot_key"],
            "point": point,
            "event_record": event_record,
        }
    ]
    processor.get_strategy_snapshot_legacy_json.assert_not_called()


def test_trigger_reference_is_not_captured_outside_the_detection_selector():
    processor = _processor()
    processor.get_strategy_snapshot = mock.Mock(return_value=copy.deepcopy(TRIGGER_STRATEGY))
    processor.get_strategy_snapshot_legacy_json = mock.Mock()
    checker = mock.Mock()
    checker.check.return_value = ([], None)

    with (
        mock.patch("alarm_backends.service.trigger.processor.AnomalyChecker", return_value=checker),
        mock.patch.object(processor, "is_alarmd_reference_selected", return_value=False),
    ):
        processor.process_point(json.dumps(copy.deepcopy(TRIGGER_POINT)))

    assert processor.reference_candidates == []
    processor.get_strategy_snapshot_legacy_json.assert_not_called()


def test_trigger_reference_does_not_capture_nodata_points():
    processor = _processor()
    processor.get_strategy_snapshot = mock.Mock(return_value=copy.deepcopy(TRIGGER_STRATEGY))
    processor.capture_alarmd_reference_candidate = mock.Mock()
    checker = mock.Mock()
    checker.check.return_value = ([], None)
    checker.is_no_data_point.return_value = True

    with (
        mock.patch("alarm_backends.service.trigger.processor.AnomalyChecker", return_value=checker),
        mock.patch.object(processor, "is_alarmd_reference_selected", return_value=True),
    ):
        processor.process_point(json.dumps(copy.deepcopy(TRIGGER_POINT)))

    processor.capture_alarmd_reference_candidate.assert_not_called()


def test_trigger_reference_reuses_detection_selector_and_excludes_double_check():
    processor = _processor()

    with (
        mock.patch.object(settings, "ALARMD_DETECTION_SHADOW_ENABLED", True, create=True),
        mock.patch.object(settings, "ALARMD_TRIGGER_REFERENCE_SHADOW_ENABLED", True, create=True),
        mock.patch.object(settings, "ALARMD_DETECTION_SHADOW_STRATEGY_IDS", (1,), create=True),
        mock.patch.object(settings, "DOUBLE_CHECK_SUM_STRATEGY_IDS", [], create=True),
    ):
        assert processor.is_alarmd_reference_selected()

    with (
        mock.patch.object(settings, "ALARMD_DETECTION_SHADOW_ENABLED", True, create=True),
        mock.patch.object(settings, "ALARMD_TRIGGER_REFERENCE_SHADOW_ENABLED", True, create=True),
        mock.patch.object(settings, "ALARMD_DETECTION_SHADOW_STRATEGY_IDS", (1,), create=True),
        mock.patch.object(settings, "DOUBLE_CHECK_SUM_STRATEGY_IDS", [1], create=True),
    ):
        assert not processor.is_alarmd_reference_selected()


def test_trigger_push_completes_monitor_event_before_reference_publish():
    processor = _processor()
    processor.event_records = [{"event_record": {"data": {}}, "anomaly_records": []}]
    processor.reference_candidates = [{"input_id": "candidate"}]
    calls = []
    processor.push_event_to_kafka = lambda records: calls.append(("monitor-event", records))
    processor.publish_alarmd_reference_candidates = lambda: calls.append(("reference", None))

    processor.push()

    assert [name for name, _value in calls] == ["monitor-event", "reference"]


def test_trigger_monitor_event_failure_prevents_reference_publish():
    processor = _processor()
    processor.event_records = [{"event_record": {"data": {}}, "anomaly_records": []}]
    processor.reference_candidates = [{"input_id": "candidate"}]
    processor.push_event_to_kafka = mock.Mock(side_effect=RuntimeError("monitor event failed"))
    processor.publish_alarmd_reference_candidates = mock.Mock()

    with pytest.raises(RuntimeError, match="monitor event failed"):
        processor.push()

    processor.publish_alarmd_reference_candidates.assert_not_called()


def test_trigger_reference_unexpected_failure_does_not_change_legacy_push_result():
    processor = _processor()
    processor.reference_candidates = [{"input_id": "candidate"}]
    processor.publish_alarmd_reference_candidates = mock.Mock(side_effect=RuntimeError("reference failed"))

    processor.push()

    assert processor.reference_candidates == []


def test_trigger_reference_publisher_uses_candidate_identity_and_is_fail_open():
    processor = _processor()
    processor.reference_candidates = [
        {"strategy_snapshot_key": "first", "point": "first", "event_record": None},
        {"strategy_snapshot_key": "second", "point": "second", "event_record": None},
    ]
    processor.get_strategy_snapshot = mock.Mock(return_value=copy.deepcopy(TRIGGER_STRATEGY))
    processor.get_strategy_snapshot_legacy_json = mock.Mock(return_value=b"strategy")
    batches = [
        {"tenant_id": "default", "purpose": "DETECT", "strategy_ref": {}, "decisions": [{"input_id": "one"}]},
        {"tenant_id": "default", "purpose": "DETECT", "strategy_ref": {}, "decisions": [{"input_id": "two"}]},
    ]
    published_groups = []

    def publish_batches(batch_iter):
        published_groups.append(list(batch_iter))
        return len(published_groups[-1])

    publisher = SimpleNamespace(publish_batches=mock.Mock(side_effect=publish_batches))

    with (
        mock.patch.object(
            settings,
            "ALARMD_TRIGGER_REFERENCE_SHADOW_KAFKA_CONFIG",
            {"topic": "alarmd-reference-shadow", "bootstrap.servers": "kafka:9092"},
            create=True,
        ),
        mock.patch.object(
            settings,
            "ALARMD_TRIGGER_REFERENCE_SHADOW_ALLOWED_TOPICS",
            ("alarmd-reference-shadow",),
            create=True,
        ),
        mock.patch.object(
            settings,
            "ALARMD_DETECTION_SHADOW_ALLOWED_TOPICS",
            ("alarmd-detection-shadow",),
            create=True,
        ),
        mock.patch.object(MonitorEventAdapter, "get_output_topic", return_value="monitor-event-nondefault"),
        mock.patch(
            "alarm_backends.core.alarmd.reference.build_reference_trigger_decision_candidate",
            side_effect=batches,
        ) as candidate_builder,
        mock.patch.object(
            reference_publisher_module,
            "get_cached_kafka_reference_decision_publisher",
            return_value=publisher,
        ) as factory,
    ):
        assert processor.publish_alarmd_reference_candidates() == 1

    assert published_groups == [batches]
    assert processor.get_strategy_snapshot_legacy_json.call_args_list == [mock.call("first"), mock.call("second")]
    assert [call.kwargs["legacy_json"] for call in candidate_builder.call_args_list] == [b"strategy", b"strategy"]
    assert factory.call_args.args[2] == ("alarmd-detection-shadow", "monitor-event-nondefault")


def test_trigger_reference_publisher_flushes_candidates_in_bounded_groups():
    processor = _processor()
    processor.reference_candidates = [
        {"strategy_snapshot_key": "snapshot", "point": index, "event_record": None} for index in range(501)
    ]
    processor.get_strategy_snapshot = mock.Mock(return_value=copy.deepcopy(TRIGGER_STRATEGY))
    processor.get_strategy_snapshot_legacy_json = mock.Mock(return_value=b"strategy")
    published_groups = []

    def publish_batches(batch_iter):
        published_groups.append(list(batch_iter))
        return len(published_groups[-1])

    publisher = SimpleNamespace(publish_batches=mock.Mock(side_effect=publish_batches))

    with (
        mock.patch.object(
            settings,
            "ALARMD_TRIGGER_REFERENCE_SHADOW_KAFKA_CONFIG",
            {"topic": "alarmd-reference-shadow", "bootstrap.servers": "kafka:9092"},
            create=True,
        ),
        mock.patch.object(
            settings,
            "ALARMD_TRIGGER_REFERENCE_SHADOW_ALLOWED_TOPICS",
            ("alarmd-reference-shadow",),
            create=True,
        ),
        mock.patch.object(
            settings,
            "ALARMD_DETECTION_SHADOW_ALLOWED_TOPICS",
            ("alarmd-detection-shadow",),
            create=True,
        ),
        mock.patch.object(MonitorEventAdapter, "get_output_topic", return_value="monitor-event-nondefault"),
        mock.patch(
            "alarm_backends.core.alarmd.reference.build_reference_trigger_decision_candidate",
            side_effect=lambda **kwargs: {"decisions": [{"input_id": str(kwargs["point"])}]},
        ),
        mock.patch.object(
            reference_publisher_module,
            "get_cached_kafka_reference_decision_publisher",
            return_value=publisher,
        ),
    ):
        assert processor.publish_alarmd_reference_candidates() == 501

    assert [len(group) for group in published_groups] == [500, 1]


def test_trigger_reference_stops_projecting_when_the_publisher_stops_consuming():
    processor = _processor()
    processor.reference_candidates = [
        {"strategy_snapshot_key": "snapshot", "point": index, "event_record": None} for index in range(501)
    ]
    processor.get_strategy_snapshot = mock.Mock(return_value=copy.deepcopy(TRIGGER_STRATEGY))
    processor.get_strategy_snapshot_legacy_json = mock.Mock(return_value=b"strategy")

    def fail_after_first_batch(batches):
        next(iter(batches))
        raise RuntimeError("broker stopped consuming")

    publisher = SimpleNamespace(publish_batches=mock.Mock(side_effect=fail_after_first_batch))
    with (
        mock.patch.object(
            settings,
            "ALARMD_TRIGGER_REFERENCE_SHADOW_KAFKA_CONFIG",
            {"topic": "alarmd-reference-shadow", "bootstrap.servers": "kafka:9092"},
            create=True,
        ),
        mock.patch.object(
            settings,
            "ALARMD_TRIGGER_REFERENCE_SHADOW_ALLOWED_TOPICS",
            ("alarmd-reference-shadow",),
            create=True,
        ),
        mock.patch.object(
            settings,
            "ALARMD_DETECTION_SHADOW_ALLOWED_TOPICS",
            ("alarmd-detection-shadow",),
            create=True,
        ),
        mock.patch.object(MonitorEventAdapter, "get_output_topic", return_value="monitor-event-nondefault"),
        mock.patch(
            "alarm_backends.core.alarmd.reference.build_reference_trigger_decision_candidate",
            return_value={"decisions": [{"input_id": "one"}]},
        ) as candidate_builder,
        mock.patch.object(
            reference_publisher_module,
            "get_cached_kafka_reference_decision_publisher",
            return_value=publisher,
        ),
    ):
        assert processor.publish_alarmd_reference_candidates() == 0

    candidate_builder.assert_called_once()


def test_trigger_reference_stops_after_publisher_initialization_failure():
    processor = _processor()
    processor.reference_candidates = [
        {"strategy_snapshot_key": "snapshot", "point": index, "event_record": None} for index in range(501)
    ]
    processor.get_strategy_snapshot = mock.Mock(return_value=copy.deepcopy(TRIGGER_STRATEGY))
    processor.get_strategy_snapshot_legacy_json = mock.Mock(return_value=b"strategy")

    with (
        mock.patch.object(
            settings,
            "ALARMD_TRIGGER_REFERENCE_SHADOW_KAFKA_CONFIG",
            {"topic": "alarmd-reference-shadow", "bootstrap.servers": "kafka:9092"},
            create=True,
        ),
        mock.patch.object(
            settings,
            "ALARMD_TRIGGER_REFERENCE_SHADOW_ALLOWED_TOPICS",
            ("alarmd-reference-shadow",),
            create=True,
        ),
        mock.patch.object(
            settings,
            "ALARMD_DETECTION_SHADOW_ALLOWED_TOPICS",
            ("alarmd-detection-shadow",),
            create=True,
        ),
        mock.patch.object(MonitorEventAdapter, "get_output_topic", return_value="monitor-event-nondefault"),
        mock.patch(
            "alarm_backends.core.alarmd.reference.build_reference_trigger_decision_candidate",
            return_value={"decisions": [{"input_id": "one"}]},
        ) as candidate_builder,
        mock.patch.object(
            reference_publisher_module,
            "get_cached_kafka_reference_decision_publisher",
            side_effect=RuntimeError("publisher initialization failed"),
        ),
    ):
        assert processor.publish_alarmd_reference_candidates() == 0

    candidate_builder.assert_called_once()


def _processor():
    processor = object.__new__(TriggerProcessor)
    processor.strategy_id = 1
    processor.item_id = 1
    processor.strategy = SimpleNamespace(bk_biz_id=2, name="strategy")
    processor.anomaly_points = []
    processor.anomaly_records = []
    processor.event_records = []
    processor.reference_candidates = []
    processor._strategy_snapshot_legacy_json = {}
    return processor


def _triggered_event(point):
    source_time = point["data"]["time"]
    event = copy.deepcopy(point)
    event["trigger"] = {
        "level": "1",
        "anomaly_ids": [f"55a76cf628e46c04a052f4e19bdb9dbf.{source_time}.1.1.1"],
    }
    return event
