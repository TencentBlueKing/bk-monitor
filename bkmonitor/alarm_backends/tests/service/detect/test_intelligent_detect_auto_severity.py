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
import threading
import time
from types import SimpleNamespace
from unittest import mock

import pytest
from django.test import override_settings

from alarm_backends.service.detect import DataPoint
from alarm_backends.service.detect.strategy.intelligent_detect import IntelligentDetect
from alarm_backends.tests.service.detect.mocked_data import mocked_item
from config.default import _parse_aiops_sas_threshold


class MetricRecorder:
    def __init__(self):
        self.increments = []
        self.observations = []

    def labels(self, **labels):
        return BoundMetricRecorder(self, labels)

    def inc(self, value=1):
        self.increments.append(({}, value))

    def observe(self, value):
        self.observations.append(({}, value))


class BoundMetricRecorder:
    def __init__(self, recorder, labels):
        self.recorder = recorder
        self.labels = labels

    def inc(self, value=1):
        self.recorder.increments.append((self.labels, value))

    def observe(self, value):
        self.recorder.observations.append((self.labels, value))


def patch_sas_metrics(monkeypatch):
    metric_names = [
        "AIOPS_SAS_REQUEST_COUNT",
        "AIOPS_SAS_REQUEST_LATENCY",
        "AIOPS_SAS_REQUEST_POINT_COUNT",
        "AIOPS_SAS_BATCH_COUNT",
        "AIOPS_SAS_BATCH_LATENCY",
        "AIOPS_SAS_BATCH_POINT_COUNT",
        "AIOPS_SAS_BATCH_REQUEST_COUNT",
        "AIOPS_DYNAMIC_ALERT_LEVEL_POINT_COUNT",
        "AIOPS_SAS_RESULT_COUNT",
        "AIOPS_SAS_FALLBACK_COUNT",
        "AIOPS_SAS_ALERT_LEVEL_COUNT",
        "AIOPS_SAS_ALERT_LEVEL_PROJECTION_COUNT",
    ]
    recorders = {name: MetricRecorder() for name in metric_names}
    for name, recorder in recorders.items():
        monkeypatch.setattr(f"alarm_backends.service.detect.strategy.intelligent_detect.metrics.{name}", recorder)
    return recorders


def increment_total(recorder, **labels):
    return sum(value for actual_labels, value in recorder.increments if actual_labels == labels)


def make_item():
    item = copy.deepcopy(mocked_item)
    item.strategy = SimpleNamespace(id=101, name="auto severity", bk_biz_id=2, scenario="os", bk_tenant_id="tenant")
    item.bk_tenant_id = "tenant"
    item.query_configs[0]["agg_dimension"] = ["mocked"]
    item.query_configs[0]["agg_interval"] = 60
    item.query_configs[0]["intelligent_detect"] = {"use_sdk": True, "status": "ready"}
    return item


def make_point(item, dimension, timestamp):
    return DataPoint(
        {
            "record_id": f"{dimension}.{timestamp}",
            "value": 10,
            "values": {"value": 10, "timestamp": timestamp * 1000},
            "dimensions": {"mocked": dimension},
            "dimension_fields": ["mocked"],
            "time": timestamp,
        },
        item,
    )


def make_kpi_result(point, *, is_anomaly=1, extra_info=None):
    return {
        "__index__": point.record_id,
        "is_anomaly": is_anomaly,
        "timestamp": point.timestamp * 1000,
        "value": point.value,
        "extra_info": json.dumps(extra_info or {"alert_msg": "突升", "anomaly_score": 0.9}),
    }


def make_detector(mode="auto", alert_levels=None):
    config = {
        "args": {"$sensitivity": 5},
        "plan_id": 1,
        "visual_type": "score",
        "alert_level_mode": mode,
    }
    if mode == "auto":
        config["alert_levels"] = alert_levels or [1, 2, 3]
    detector = IntelligentDetect(config=config)
    detector.history_point_fetcher = mock.Mock(return_value=None)
    return detector


@override_settings(
    AIOPS_SAS_PREDICT_CONCURRENCY=2,
    AIOPS_SAS_FATAL_THRESHOLD=0.8,
    AIOPS_SAS_WARNING_THRESHOLD=0.5,
)
def test_auto_level_calls_sas_only_for_kpi_anomalies():
    item = make_item()
    anomaly = make_point(item, "host-a", 1_780_000_000)
    normal = make_point(item, "host-a", 1_780_000_060)
    detector = make_detector()
    detector._local_pre_detect_results = {
        anomaly.record_id: make_kpi_result(anomaly),
        normal.record_id: make_kpi_result(normal, is_anomaly=0),
    }
    sas_predict = mock.Mock(
        return_value=[
            {
                "severity_score": 0.9,
                "timestamp": anomaly.timestamp * 1000,
                "value": anomaly.value,
                "is_anomaly": 1,
            }
        ]
    )
    detector.SAS_PREDICT_FUNC = sas_predict

    anomaly_points = detector.detect_records([anomaly, normal], 2)

    assert len(anomaly_points) == 1
    assert anomaly_points[0].anomaly_id.endswith(".2")
    assert sas_predict.call_count == 1
    assert sas_predict.call_args.kwargs == {
        "data": [
            {
                "timestamp": anomaly.timestamp * 1000,
                "value": anomaly.value,
                "is_anomaly": 1,
            }
        ],
        "dimensions": {"mocked": "host-a", "strategy_id": 101},
        "predict_args": {"predict_start_time": anomaly.timestamp * 1000},
        "interval": 60,
        "extra_data": {},
        "serving_config": {"pre_service_name": "default", "serving_with_ts_depend": True},
        "bk_tenant_id": "tenant",
    }
    extra_info = json.loads(anomaly_points[0].data_point.values["extra_info"])
    assert extra_info["alert_msg"] == "突升"
    assert extra_info["anomaly_score"] == 0.9
    assert extra_info["alert_level_msg"] == {
        "alert_level": 1,
        "raw_alert_level": 1,
        "severity_score": 0.9,
        "status": "success",
    }


@pytest.mark.parametrize("mode", ["manual", None])
def test_manual_level_does_not_call_sas(mode):
    item = make_item()
    point = make_point(item, "host-a", 1_780_000_000)
    detector = make_detector(mode or "manual")
    if mode is None:
        detector.config.pop("alert_level_mode", None)
        detector.validated_config.pop("alert_level_mode", None)
    detector._local_pre_detect_results = {point.record_id: make_kpi_result(point)}
    detector.SAS_PREDICT_FUNC = mock.Mock()

    anomaly_points = detector.detect_records([point], 2)

    assert len(anomaly_points) == 1
    detector.SAS_PREDICT_FUNC.assert_not_called()
    assert "alert_level_msg" not in json.loads(anomaly_points[0].data_point.values["extra_info"])


def test_auto_level_does_not_call_sas_outside_sdk_mode():
    item = make_item()
    item.query_configs[0]["intelligent_detect"]["use_sdk"] = False
    point = make_point(item, "host-a", 1_780_000_000)
    point.values.update(make_kpi_result(point))
    detector = make_detector()
    detector.SAS_PREDICT_FUNC = mock.Mock()

    anomaly_points = detector.detect_records([point], 2)

    assert len(anomaly_points) == 1
    detector.SAS_PREDICT_FUNC.assert_not_called()
    assert "alert_level_msg" not in json.loads(anomaly_points[0].data_point.values["extra_info"])


@override_settings(
    AIOPS_SAS_PREDICT_CONCURRENCY=2,
    AIOPS_SAS_FATAL_THRESHOLD=0.8,
    AIOPS_SAS_WARNING_THRESHOLD=0.5,
)
@pytest.mark.parametrize(
    ("score", "expected_level"),
    [(0.0, 3), (0.499, 3), (0.5, 2), (0.799, 2), (0.8, 1), (1.0, 1)],
)
def test_score_boundary_mapping(score, expected_level):
    assert IntelligentDetect.score_to_alert_level(score) == expected_level


@pytest.mark.parametrize(
    ("raw_level", "alert_levels", "expected_level"),
    [
        (1, [1, 2, 3], 1),
        (1, [2, 3], 2),
        (2, [1, 3], 1),
        (3, [1, 2], 2),
        (3, [1], 1),
        (1, [3], 3),
    ],
)
def test_alert_level_is_projected_to_nearest_allowed_level(raw_level, alert_levels, expected_level):
    assert IntelligentDetect.project_alert_level(raw_level, alert_levels) == expected_level


@override_settings(
    AIOPS_SAS_PREDICT_CONCURRENCY=2,
    AIOPS_SAS_FATAL_THRESHOLD=0.8,
    AIOPS_SAS_WARNING_THRESHOLD=0.5,
)
def test_sas_raw_level_is_projected_and_kept_for_audit():
    item = make_item()
    point = make_point(item, "host-a", 1_780_000_000)
    detector = make_detector(alert_levels=[1, 3])
    detector._local_pre_detect_results = {point.record_id: make_kpi_result(point)}
    detector.SAS_PREDICT_FUNC = mock.Mock(return_value=[{"severity_score": 0.5, "timestamp": point.timestamp * 1000}])

    anomaly_points = detector.detect_records([point], 2)

    level_msg = json.loads(anomaly_points[0].data_point.values["extra_info"])["alert_level_msg"]
    assert level_msg == {
        "alert_level": 1,
        "raw_alert_level": 2,
        "severity_score": 0.5,
        "status": "success",
    }


@override_settings(
    AIOPS_SAS_PREDICT_CONCURRENCY=2,
    AIOPS_SAS_FATAL_THRESHOLD=0.8,
    AIOPS_SAS_WARNING_THRESHOLD=0.5,
)
def test_sas_metrics_cover_feature_request_batch_result_and_projection(monkeypatch):
    recorders = patch_sas_metrics(monkeypatch)
    item = make_item()
    points = [
        make_point(item, "host-a", 1_780_000_000),
        make_point(item, "host-a", 1_780_000_060),
        make_point(item, "host-b", 1_780_000_000),
        make_point(item, "host-c", 1_780_000_000),
    ]
    detector = make_detector(alert_levels=[1, 3])
    detector._local_pre_detect_results = {
        points[0].record_id: make_kpi_result(points[0]),
        points[1].record_id: make_kpi_result(points[1]),
        points[2].record_id: make_kpi_result(points[2]),
        points[3].record_id: make_kpi_result(points[3], is_anomaly=0),
    }

    def sas_predict(**kwargs):
        if kwargs["dimensions"]["mocked"] == "host-a":
            return [{"severity_score": 0.5, "timestamp": points[0].timestamp * 1000}]
        return [{"severity_score": 0.1, "timestamp": points[2].timestamp * 1000}]

    detector.SAS_PREDICT_FUNC = mock.Mock(side_effect=sas_predict)

    anomaly_points = detector.detect_records(points, 2)

    assert len(anomaly_points) == 3
    assert increment_total(recorders["AIOPS_DYNAMIC_ALERT_LEVEL_POINT_COUNT"], mode="auto", stage="input") == 4
    assert increment_total(recorders["AIOPS_DYNAMIC_ALERT_LEVEL_POINT_COUNT"], mode="auto", stage="anomaly") == 3
    assert increment_total(recorders["AIOPS_SAS_REQUEST_COUNT"], status="success") == 1
    assert increment_total(recorders["AIOPS_SAS_REQUEST_COUNT"], status="partial") == 1
    assert sorted(value for _labels, value in recorders["AIOPS_SAS_REQUEST_POINT_COUNT"].observations) == [1, 2]
    assert {labels["status"] for labels, _value in recorders["AIOPS_SAS_REQUEST_LATENCY"].observations} == {
        "partial",
        "success",
    }
    assert increment_total(recorders["AIOPS_SAS_BATCH_COUNT"], status="partial") == 1
    assert len(recorders["AIOPS_SAS_BATCH_LATENCY"].observations) == 1
    assert recorders["AIOPS_SAS_BATCH_LATENCY"].observations[0][0] == {"status": "partial"}
    assert recorders["AIOPS_SAS_BATCH_LATENCY"].observations[0][1] >= 0
    assert recorders["AIOPS_SAS_BATCH_POINT_COUNT"].observations == [({}, 3)]
    assert recorders["AIOPS_SAS_BATCH_REQUEST_COUNT"].observations == [({}, 2)]
    assert increment_total(recorders["AIOPS_SAS_RESULT_COUNT"], status="success") == 2
    assert increment_total(recorders["AIOPS_SAS_RESULT_COUNT"], status="fallback") == 1
    assert increment_total(recorders["AIOPS_SAS_FALLBACK_COUNT"], reason="missing_result") == 1
    assert increment_total(recorders["AIOPS_SAS_ALERT_LEVEL_COUNT"], source="sas", alert_level="1") == 1
    assert increment_total(recorders["AIOPS_SAS_ALERT_LEVEL_COUNT"], source="sas", alert_level="3") == 1
    assert increment_total(recorders["AIOPS_SAS_ALERT_LEVEL_COUNT"], source="fallback", alert_level="2") == 1
    assert (
        increment_total(recorders["AIOPS_SAS_ALERT_LEVEL_PROJECTION_COUNT"], raw_alert_level="2", alert_level="1") == 1
    )
    assert (
        increment_total(recorders["AIOPS_SAS_ALERT_LEVEL_PROJECTION_COUNT"], raw_alert_level="3", alert_level="3") == 1
    )


def test_manual_mode_reports_feature_coverage_without_sas_requests(monkeypatch):
    recorders = patch_sas_metrics(monkeypatch)
    item = make_item()
    anomaly = make_point(item, "host-a", 1_780_000_000)
    normal = make_point(item, "host-a", 1_780_000_060)
    detector = make_detector(mode="manual")
    detector._local_pre_detect_results = {
        anomaly.record_id: make_kpi_result(anomaly),
        normal.record_id: make_kpi_result(normal, is_anomaly=0),
    }
    detector.SAS_PREDICT_FUNC = mock.Mock()

    anomaly_points = detector.detect_records([anomaly, normal], 2)

    assert len(anomaly_points) == 1
    assert increment_total(recorders["AIOPS_DYNAMIC_ALERT_LEVEL_POINT_COUNT"], mode="manual", stage="input") == 2
    assert increment_total(recorders["AIOPS_DYNAMIC_ALERT_LEVEL_POINT_COUNT"], mode="manual", stage="anomaly") == 1
    assert recorders["AIOPS_SAS_REQUEST_COUNT"].increments == []
    assert recorders["AIOPS_SAS_BATCH_COUNT"].increments == []


@override_settings(
    AIOPS_SAS_PREDICT_CONCURRENCY=2,
    AIOPS_SAS_FATAL_THRESHOLD=0.8,
    AIOPS_SAS_WARNING_THRESHOLD=0.5,
)
@pytest.mark.parametrize("score", [None, True, -0.1, 1.1, float("nan"), float("inf")])
def test_invalid_score_falls_back_without_dropping_kpi_anomaly(score):
    item = make_item()
    point = make_point(item, "host-a", 1_780_000_000)
    detector = make_detector()
    detector._local_pre_detect_results = {point.record_id: make_kpi_result(point)}
    detector.SAS_PREDICT_FUNC = mock.Mock(return_value=[{"severity_score": score, "timestamp": point.timestamp * 1000}])

    anomaly_points = detector.detect_records([point], 2)

    assert len(anomaly_points) == 1
    level_msg = json.loads(anomaly_points[0].data_point.values["extra_info"])["alert_level_msg"]
    assert level_msg == {
        "alert_level": 2,
        "severity_score": None,
        "status": "fallback",
        "reason": "invalid_score",
    }


@override_settings(
    AIOPS_SAS_PREDICT_CONCURRENCY=2,
    AIOPS_SAS_FATAL_THRESHOLD=0.8,
    AIOPS_SAS_WARNING_THRESHOLD=0.5,
)
@pytest.mark.parametrize("response", [[], {"result": True, "data": []}, None])
def test_invalid_response_falls_back_without_dropping_kpi_anomaly(response):
    item = make_item()
    point = make_point(item, "host-a", 1_780_000_000)
    detector = make_detector()
    detector._local_pre_detect_results = {point.record_id: make_kpi_result(point)}
    detector.SAS_PREDICT_FUNC = mock.Mock(return_value=response)

    anomaly_points = detector.detect_records([point], 2)

    assert len(anomaly_points) == 1
    level_msg = json.loads(anomaly_points[0].data_point.values["extra_info"])["alert_level_msg"]
    assert level_msg["alert_level"] == 2
    assert level_msg["status"] == "fallback"


@override_settings(
    AIOPS_SAS_PREDICT_CONCURRENCY=2,
    AIOPS_SAS_FATAL_THRESHOLD=0.8,
    AIOPS_SAS_WARNING_THRESHOLD=0.5,
)
def test_sas_request_failure_falls_back_without_dropping_kpi_anomaly():
    item = make_item()
    point = make_point(item, "host-a", 1_780_000_000)
    detector = make_detector()
    detector._local_pre_detect_results = {point.record_id: make_kpi_result(point)}
    detector.SAS_PREDICT_FUNC = mock.Mock(side_effect=TimeoutError("sas timeout"))

    anomaly_points = detector.detect_records([point], 2)

    assert len(anomaly_points) == 1
    level_msg = json.loads(anomaly_points[0].data_point.values["extra_info"])["alert_level_msg"]
    assert level_msg == {
        "alert_level": 2,
        "severity_score": None,
        "status": "fallback",
        "reason": "request_failed",
    }


@override_settings(
    AIOPS_SAS_PREDICT_CONCURRENCY=2,
    AIOPS_SAS_FATAL_THRESHOLD=0.8,
    AIOPS_SAS_WARNING_THRESHOLD=0.5,
)
def test_sas_setup_failure_falls_back_without_dropping_kpi_anomaly():
    item = make_item()
    point = make_point(item, "host-a", 1_780_000_000)
    detector = make_detector()
    detector._local_pre_detect_results = {point.record_id: make_kpi_result(point)}
    detector.generate_dimensions = mock.Mock(side_effect=RuntimeError("invalid dimensions"))

    anomaly_points = detector.detect_records([point], 2)

    assert len(anomaly_points) == 1
    level_msg = json.loads(anomaly_points[0].data_point.values["extra_info"])["alert_level_msg"]
    assert level_msg == {
        "alert_level": 2,
        "severity_score": None,
        "status": "fallback",
        "reason": "request_failed",
    }


@pytest.mark.parametrize(("fatal_threshold", "warning_threshold"), [(0.5, 0.8), ("invalid", 0.5), (0.8, "")])
def test_invalid_thresholds_fall_back_without_dropping_kpi_anomaly(fatal_threshold, warning_threshold):
    item = make_item()
    point = make_point(item, "host-a", 1_780_000_000)
    detector = make_detector()
    detector._local_pre_detect_results = {point.record_id: make_kpi_result(point)}
    detector.SAS_PREDICT_FUNC = mock.Mock(return_value=[{"severity_score": 0.9, "timestamp": point.timestamp * 1000}])

    with override_settings(
        AIOPS_SAS_PREDICT_CONCURRENCY=2,
        AIOPS_SAS_FATAL_THRESHOLD=fatal_threshold,
        AIOPS_SAS_WARNING_THRESHOLD=warning_threshold,
    ):
        anomaly_points = detector.detect_records([point], 2)

    assert len(anomaly_points) == 1
    level_msg = json.loads(anomaly_points[0].data_point.values["extra_info"])["alert_level_msg"]
    assert level_msg["alert_level"] == 2
    assert level_msg["reason"] == "invalid_threshold"


def test_invalid_threshold_environment_value_does_not_break_settings_import(monkeypatch):
    monkeypatch.setenv("BKAPP_AIOPS_SAS_FATAL_THRESHOLD", "not-a-number")

    assert _parse_aiops_sas_threshold("BKAPP_AIOPS_SAS_FATAL_THRESHOLD", 0.8) is None


@override_settings(
    AIOPS_SAS_PREDICT_CONCURRENCY=2,
    AIOPS_SAS_FATAL_THRESHOLD=0.8,
    AIOPS_SAS_WARNING_THRESHOLD=0.5,
)
def test_result_is_correlated_by_dimension_and_timestamp():
    item = make_item()
    points = [
        make_point(item, "host-a", 1_780_000_000),
        make_point(item, "host-a", 1_780_000_060),
        make_point(item, "host-b", 1_780_000_000),
    ]
    detector = make_detector()
    detector._local_pre_detect_results = {point.record_id: make_kpi_result(point) for point in points}
    completion_order = []
    barrier = threading.Barrier(2)

    def sas_predict(**kwargs):
        host = kwargs["dimensions"]["mocked"]
        barrier.wait(timeout=1)
        if host == "host-a":
            time.sleep(0.02)
            completion_order.append(host)
            return [
                {"severity_score": 0.5, "timestamp": points[1].timestamp * 1000},
                {"severity_score": 0.9, "timestamp": points[0].timestamp * 1000},
            ]
        completion_order.append(host)
        return [{"severity_score": 0.1, "timestamp": points[2].timestamp * 1000}]

    detector.SAS_PREDICT_FUNC = mock.Mock(side_effect=sas_predict)

    anomaly_points = detector.detect_records(points, 2)

    levels = {
        point.data_point.record_id: json.loads(point.data_point.values["extra_info"])["alert_level_msg"]["alert_level"]
        for point in anomaly_points
    }
    assert levels == {
        points[0].record_id: 1,
        points[1].record_id: 2,
        points[2].record_id: 3,
    }
    assert completion_order == ["host-b", "host-a"]
    assert detector.SAS_PREDICT_FUNC.call_count == 2


@override_settings(
    AIOPS_SAS_PREDICT_CONCURRENCY=2,
    AIOPS_SAS_FATAL_THRESHOLD=0.8,
    AIOPS_SAS_WARNING_THRESHOLD=0.5,
)
def test_missing_result_only_falls_back_matching_point():
    item = make_item()
    first = make_point(item, "host-a", 1_780_000_000)
    second = make_point(item, "host-a", 1_780_000_060)
    detector = make_detector()
    detector._local_pre_detect_results = {
        first.record_id: make_kpi_result(first),
        second.record_id: make_kpi_result(second),
    }
    detector.SAS_PREDICT_FUNC = mock.Mock(return_value=[{"severity_score": 0.9, "timestamp": first.timestamp * 1000}])

    anomaly_points = detector.detect_records([first, second], 2)

    level_messages = {
        point.data_point.record_id: json.loads(point.data_point.values["extra_info"])["alert_level_msg"]
        for point in anomaly_points
    }
    assert level_messages[first.record_id]["alert_level"] == 1
    assert level_messages[second.record_id] == {
        "alert_level": 2,
        "severity_score": None,
        "status": "fallback",
        "reason": "missing_result",
    }


@override_settings(
    AIOPS_SAS_PREDICT_CONCURRENCY=2,
    AIOPS_SAS_FATAL_THRESHOLD=0.8,
    AIOPS_SAS_WARNING_THRESHOLD=0.5,
)
def test_duplicate_timestamp_only_falls_back_matching_point():
    item = make_item()
    first = make_point(item, "host-a", 1_780_000_000)
    second = make_point(item, "host-a", 1_780_000_060)
    detector = make_detector()
    detector._local_pre_detect_results = {
        first.record_id: make_kpi_result(first),
        second.record_id: make_kpi_result(second),
    }
    detector.SAS_PREDICT_FUNC = mock.Mock(
        return_value=[
            {"severity_score": 0.9, "timestamp": first.timestamp * 1000},
            {"severity_score": 0.8, "timestamp": first.timestamp * 1000},
            {"severity_score": 0.1, "timestamp": second.timestamp * 1000},
        ]
    )

    anomaly_points = detector.detect_records([first, second], 2)

    level_messages = {
        point.data_point.record_id: json.loads(point.data_point.values["extra_info"])["alert_level_msg"]
        for point in anomaly_points
    }
    assert level_messages[first.record_id]["alert_level"] == 2
    assert level_messages[first.record_id]["reason"] == "duplicate_result"
    assert level_messages[second.record_id]["alert_level"] == 3
