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

from alarm_backends.core.cache import key
from alarm_backends.core.alarm_engine import publisher as publisher_module
from alarm_backends.service.detect.process import DetectProcess
from alarm_backends.tests.alarm_engine_fixtures import DETECT_RECORDS, DETECT_STRATEGY


def test_alarm_engine_shadow_is_inert_when_disabled():
    processor = object.__new__(DetectProcess)

    with mock.patch.object(settings, "ALARM_ENGINE_DETECTION_SHADOW_ENABLED", False, create=True):
        assert processor.prepare_alarm_engine_detection_batches() == []


def test_alarm_engine_shadow_requires_an_explicit_strategy_selector():
    processor = object.__new__(DetectProcess)
    processor.strategy_id = "1"

    with (
        mock.patch.object(settings, "ALARM_ENGINE_DETECTION_SHADOW_ENABLED", True, create=True),
        mock.patch.object(settings, "ALARM_ENGINE_DETECTION_SHADOW_STRATEGY_IDS", (), create=True),
    ):
        assert processor.prepare_alarm_engine_detection_batches() == []


@pytest.mark.parametrize("selector", [(True,), (1.9,), ("01",), (" 1 ",), "1,"])
def test_alarm_engine_shadow_rejects_noncanonical_strategy_selectors(selector):
    processor = object.__new__(DetectProcess)
    processor.strategy_id = "1"

    with (
        mock.patch.object(settings, "ALARM_ENGINE_DETECTION_SHADOW_ENABLED", True, create=True),
        mock.patch.object(settings, "ALARM_ENGINE_DETECTION_SHADOW_STRATEGY_IDS", selector, create=True),
    ):
        assert processor.prepare_alarm_engine_detection_batches() == []


def test_alarm_engine_shadow_projects_finalized_threshold_records():
    strategy = copy.deepcopy(DETECT_STRATEGY)
    anomalous_record, normal_record = copy.deepcopy(DETECT_RECORDS)
    processor = object.__new__(DetectProcess)
    processor.strategy_id = "1"
    source_strategy = SimpleNamespace(id=1, config=strategy)
    processor.strategy = SimpleNamespace(
        id=1,
        bk_tenant_id="default",
        config=strategy,
        items=[SimpleNamespace(id=2)],
        snapshot_key="snapshot-key",
    )
    processor.inputs = {
        2: [
            SimpleNamespace(item=SimpleNamespace(strategy=source_strategy), as_dict=lambda: anomalous_record),
            SimpleNamespace(item=SimpleNamespace(strategy=source_strategy), as_dict=lambda: normal_record),
        ]
    }
    processor.outputs = {
        2: [
            {
                "data": anomalous_record,
                "anomaly": {"3": {"anomaly_id": f"{anomalous_record['record_id']}.1.2.3"}},
            }
        ]
    }

    with (
        mock.patch.object(settings, "ALARM_ENGINE_DETECTION_SHADOW_ENABLED", True, create=True),
        mock.patch.object(settings, "ALARM_ENGINE_DETECTION_SHADOW_STRATEGY_IDS", (1,), create=True),
        mock.patch.object(settings, "DOUBLE_CHECK_SUM_STRATEGY_IDS", []),
        mock.patch.object(key.STRATEGY_SNAPSHOT_KEY.client, "get", return_value=json.dumps(strategy).encode()),
    ):
        batches = processor.prepare_alarm_engine_detection_batches()

    assert len(batches) == 1
    assert [outcome["outcome"] for outcome in batches[0]["outcomes"]] == ["ANOMALOUS", "NORMAL"]
    assert "_alarm_engine" not in processor.outputs[2][0]


@pytest.mark.parametrize("stale_update_time", ["stale", True, 1.0])
def test_alarm_engine_shadow_rejects_inputs_from_a_stale_strategy_snapshot(stale_update_time):
    strategy = copy.deepcopy(DETECT_STRATEGY)
    stale_strategy = copy.deepcopy(strategy)
    strategy["update_time"] = 1
    stale_strategy["update_time"] = stale_update_time
    record = copy.deepcopy(DETECT_RECORDS[0])
    processor = object.__new__(DetectProcess)
    processor.strategy_id = "1"
    processor.strategy = SimpleNamespace(
        id=1,
        bk_tenant_id="default",
        config=strategy,
        items=[SimpleNamespace(id=2)],
        snapshot_key="snapshot-key",
    )
    processor.inputs = {
        2: [
            SimpleNamespace(
                item=SimpleNamespace(strategy=SimpleNamespace(id=1, config=stale_strategy)),
                as_dict=lambda: record,
            )
        ]
    }
    processor.outputs = {2: []}

    with (
        mock.patch.object(settings, "ALARM_ENGINE_DETECTION_SHADOW_ENABLED", True, create=True),
        mock.patch.object(settings, "ALARM_ENGINE_DETECTION_SHADOW_STRATEGY_IDS", (1,), create=True),
        mock.patch.object(settings, "DOUBLE_CHECK_SUM_STRATEGY_IDS", []),
        mock.patch.object(key.STRATEGY_SNAPSHOT_KEY.client, "get", return_value=json.dumps(strategy).encode()),
    ):
        assert processor.prepare_alarm_engine_detection_batches() == []


def test_detect_push_keeps_legacy_delivery_before_shadow_publish():
    processor = object.__new__(DetectProcess)
    processor.strategy_id = "1"
    processor.strategy = SimpleNamespace(bk_biz_id=2, name="strategy")
    processor.inputs = {}
    processor.outputs = {}
    calls = []
    processor.prepare_alarm_engine_detection_batches = lambda: calls.append("prepare") or ["batch"]
    processor.push_abnormal_data = lambda *_args: calls.append("legacy") or 0
    processor.publish_alarm_engine_detection_batches = lambda batches: calls.append(("shadow", batches))

    processor.push_data()

    assert calls == ["legacy", "prepare", ("shadow", ["batch"])]


def test_alarm_engine_shadow_publishes_with_process_cached_producer():
    published = []
    fake_publisher = SimpleNamespace(publish_batch=lambda batch: published.append(batch) or len(batch["outcomes"]))
    batches = [{"strategy_ir": {}, "outcomes": [{"input_id": "one"}]}]

    with (
        mock.patch.object(
            settings,
            "ALARM_ENGINE_DETECTION_SHADOW_KAFKA_CONFIG",
            {"topic": "alarm-engine-detection-shadow", "bootstrap.servers": "kafka:9092"},
            create=True,
        ),
        mock.patch.object(
            settings,
            "ALARM_ENGINE_DETECTION_SHADOW_ALLOWED_TOPICS",
            ("alarm-engine-detection-shadow",),
            create=True,
        ),
        mock.patch.object(publisher_module, "get_cached_kafka_detection_publisher", return_value=fake_publisher),
    ):
        assert DetectProcess.publish_alarm_engine_detection_batches(batches) == 1

    assert published == batches
