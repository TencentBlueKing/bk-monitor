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

from alarm_backends.core.alert.adapter import MonitorEventAdapter
from alarm_backends.core.alert.event import Event
from alarm_backends.core.cache.strategy import StrategyCacheManager
from alarm_backends.core.control.mixins.detect import DetectMixin
from alarm_backends.core.control.strategy import Strategy
from alarm_backends.service.access.data.records import DataRecord
from alarm_backends.service.detect import DataPoint
from alarm_backends.service.detect.strategy import adapter_data_access_2_detect

from .config import FORMAT_RAW_DATA, STANDARD_DATA, STRATEGY_CONFIG_V3


class TestRecords:
    def test_record(self, mocker):
        get_strategy_by_id = mocker.patch.object(StrategyCacheManager, "get_strategy_by_id")
        get_strategy_by_id.return_value = copy.deepcopy(STRATEGY_CONFIG_V3)

        strategy_id = 1
        strategy = Strategy(strategy_id)

        record = DataRecord(strategy.items[0], FORMAT_RAW_DATA)
        record.clean()
        record.data.pop("access_time", None)
        record.data.pop("dimension_fields", None)
        assert record.data == STANDARD_DATA

    def test_partial_query_flag_is_propagated_only_for_partial_data(self, mocker):
        get_strategy_by_id = mocker.patch.object(StrategyCacheManager, "get_strategy_by_id")
        get_strategy_by_id.return_value = copy.deepcopy(STRATEGY_CONFIG_V3)
        item = Strategy(1).items[0]

        item.query.is_partial = True
        partial_record = DataRecord(item, FORMAT_RAW_DATA).clean()
        assert partial_record.data["is_partial"] is True

        item.query.is_partial = False
        complete_record = DataRecord(item, FORMAT_RAW_DATA).clean()
        assert "is_partial" not in complete_record.data

    def test_named_output_snapshot_is_attached_after_identity_cleaning(self, mocker):
        get_strategy_by_id = mocker.patch.object(StrategyCacheManager, "get_strategy_by_id")
        strategy_config = copy.deepcopy(STRATEGY_CONFIG_V3)
        strategy_config["items"][0]["query_configs"][0]["agg_dimension"].append("service")
        get_strategy_by_id.return_value = strategy_config
        mocker.patch("alarm_backends.core.alert.adapter.bk_biz_id_to_bk_tenant_id", return_value="system")
        item = Strategy(1).items[0]
        item.query_output_config = {"legacy_output_ref": "C"}
        baseline_raw_data = {**FORMAT_RAW_DATA, "service": "order"}
        raw_data = {
            **baseline_raw_data,
            "_ref_values_": {
                "A": {"value": 42, "state": "SUCCESS"},
                "B": {"value": 1000, "state": "SUCCESS"},
                "C": {"value": FORMAT_RAW_DATA["_result_"], "state": "SUCCESS"},
            },
        }

        baseline = DataRecord(item, baseline_raw_data).clean()
        with_snapshot = DataRecord(item, raw_data).clean()

        assert with_snapshot.data["ref_values"] == raw_data["_ref_values_"]
        assert with_snapshot.data["record_id"] == baseline.data["record_id"]
        assert with_snapshot.data["dimensions"] == baseline.data["dimensions"]
        assert with_snapshot.clean_dimension_fields() == baseline.clean_dimension_fields()
        assert with_snapshot.data["values"] == baseline.data["values"]

        def build_event(data):
            anomaly_id = f"{data['record_id']}.1.1.1"
            origin_alarm = {
                "data": data,
                "anomaly": {"1": {"anomaly_id": anomaly_id, "anomaly_message": "threshold exceeded"}},
                "trigger": {"level": "1", "anomaly_ids": [anomaly_id]},
                "strategy_snapshot_key": "strategy-snapshot",
            }
            event = Event(MonitorEventAdapter(origin_alarm, strategy_config).adapt(time=data["time"]))
            event.cal_dedupe_md5()
            return event

        baseline_event = build_event(baseline.data)
        snapshot_event = build_event(with_snapshot.data)

        assert snapshot_event.data["tags"] == baseline_event.data["tags"]
        assert snapshot_event.data["dedupe_keys"] == baseline_event.data["dedupe_keys"]
        assert snapshot_event.data["dedupe_md5"] == baseline_event.data["dedupe_md5"]

    def test_legacy_ref_value_uses_the_same_normalized_value_as_detect(self, mocker):
        get_strategy_by_id = mocker.patch.object(StrategyCacheManager, "get_strategy_by_id")
        strategy_config = copy.deepcopy(STRATEGY_CONFIG_V3)
        strategy_config["items"][0]["query_output_config"] = {
            "response_contract": "named_outputs/v1",
            "legacy_output_ref": "C",
            "output_list": [
                {"reference_name": "A", "expression": "A"},
                {"reference_name": "C", "expression": "A"},
            ],
        }
        get_strategy_by_id.return_value = strategy_config
        item = Strategy(1).items[0]
        raw_value = 4.123456789012345
        raw_ref_values = {
            "A": {"value": 42.123456789012345, "state": "SUCCESS"},
            "C": {"value": raw_value, "state": "SUCCESS"},
        }
        raw_data = {**FORMAT_RAW_DATA, "_result_": raw_value, "_ref_values_": raw_ref_values}

        cleaned = DataRecord(item, raw_data).clean().data

        assert cleaned["value"] == cleaned["ref_values"]["C"]["value"]
        assert cleaned["ref_values"]["C"]["value"] != raw_value
        assert cleaned["ref_values"]["A"] == raw_ref_values["A"]
        assert raw_ref_values["C"]["value"] == raw_value

    def test_named_output_snapshot_survives_async_and_access_detect_merge_adapters(self, mocker):
        get_strategy_by_id = mocker.patch.object(StrategyCacheManager, "get_strategy_by_id")
        get_strategy_by_id.return_value = copy.deepcopy(STRATEGY_CONFIG_V3)
        item = Strategy(1).items[0]
        item.query_output_config = {"legacy_output_ref": "C"}
        ref_values = {
            "A": {"value": 42, "state": "SUCCESS"},
            "C": {"value": FORMAT_RAW_DATA["_result_"], "state": "SUCCESS"},
        }
        raw_data = {**FORMAT_RAW_DATA, "_ref_values_": ref_values}

        async_payload = json.loads(json.dumps(DataRecord(item, raw_data).clean().data))
        async_point = DataPoint(async_payload, item)
        merged_point = adapter_data_access_2_detect(DataRecord(item, raw_data), item)

        assert async_point.ref_values == ref_values
        assert merged_point.ref_values == ref_values

        detector = SimpleNamespace(strategy=SimpleNamespace(snapshot_key="strategy-snapshot"))
        for point in (async_point, merged_point):
            anomaly_point = SimpleNamespace(
                data_point=point,
                anomaly_message="threshold exceeded",
                anomaly_id="anomaly-id",
                anomaly_time="2026-08-31 10:00:00",
                context={},
            )
            origin_alarm = DetectMixin._update_anomaly_info_with_point(detector, anomaly_point, 1)

            assert origin_alarm["data"]["value"] == point.value
            assert origin_alarm["data"]["ref_values"] == ref_values
