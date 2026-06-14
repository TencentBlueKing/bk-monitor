"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from types import SimpleNamespace

import pytest

from metadata.models.record_rule.constants import RecordRuleV4DesiredStatus, RecordRuleV4InputType
from metadata.models.record_rule.v4.as_code import build_export_entries, dump_rule, parse_config


class FakeRecordManager:
    def __init__(self, records):
        self.records = records

    def order_by(self, *args):
        return self.records


def test_parse_expr_recording_rule():
    declarations = parse_config(
        {
            "groups": [
                {
                    "name": "rr_resource_group",
                    "interval": "60s",
                    "labels": {"env": "prod"},
                    "bkmonitor": {
                        "description": "CPU 预计算",
                        "data_label": "rr_cpu",
                        "auto_refresh": True,
                        "desired_status": "running",
                    },
                    "rules": [
                        {
                            "record": "cpu_usage_avg",
                            "expr": "avg(rate(system_cpu_usage[5m]))",
                            "labels": {"scenario": "dashboard"},
                        }
                    ],
                }
            ]
        },
        source_path="record_rules/cpu.yaml",
    )

    declaration = declarations[0]
    assert declaration["name"] == "rr_resource_group"
    assert declaration["interval"] == "1min"
    assert declaration["labels"] == [{"env": "prod"}]
    assert declaration["desired_status"] == RecordRuleV4DesiredStatus.RUNNING.value
    assert declaration["raw_config"]["labels"] == {"env": "prod"}
    assert declaration["raw_config"]["rules"][0]["expr"] == "avg(rate(system_cpu_usage[5m]))"
    assert declaration["records"] == [
        {
            "input_type": RecordRuleV4InputType.PROMQL.value,
            "input_config": {"promql": "avg(rate(system_cpu_usage[5m]))"},
            "metric_name": "cpu_usage_avg",
            "labels": [{"scenario": "dashboard"}],
        }
    ]


def test_parse_query_with_simplified_query_configs():
    declarations = parse_config(
        {
            "groups": [
                {
                    "name": "rr_resource_group",
                    "interval": "1min",
                    "rules": [
                        {
                            "record": "disk_cpu_ratio",
                            "query": {
                                "data_source": "bk_monitor",
                                "data_type": "time_series",
                                "expression": "a / b",
                                "query_configs": [
                                    {
                                        "metric": "system.disk.in_use",
                                        "method": "avg",
                                        "interval": 60,
                                        "group_by": ["bk_target_cloud_id"],
                                        "where": 'mount_point="/data1"',
                                        "functions": ["rate(2m)"],
                                        "alias": "a",
                                    }
                                ],
                            },
                        }
                    ],
                }
            ]
        }
    )

    record = declarations[0]["records"][0]
    input_config = record["input_config"]
    query_config = input_config["query_configs"][0]
    assert record["input_type"] == RecordRuleV4InputType.QUERY_TS.value
    assert input_config["expression"] == "a / b"
    assert query_config["data_source_label"] == "bk_monitor"
    assert query_config["data_type_label"] == "time_series"
    assert query_config["table"] == "system.disk"
    assert query_config["metrics"] == [{"field": "in_use", "method": "AVG", "alias": "a"}]
    assert query_config["interval"] == 60
    assert query_config["group_by"] == ["bk_target_cloud_id"]
    assert query_config["functions"][0]["id"] == "rate"
    assert declarations[0]["raw_config"]["rules"][0]["query"]["query_configs"][0]["method"] == "avg"


@pytest.mark.parametrize("field_name", ["bk_biz_id", "bk_tenant_id", "space_uid", "bk_biz_ids"])
def test_parse_rejects_business_context_fields(field_name):
    config = {
        "groups": [
            {
                "name": "rr_resource_group",
                field_name: "forbidden",
                "rules": [{"record": "cpu_usage_avg", "expr": "up"}],
            }
        ]
    }

    with pytest.raises(ValueError, match=field_name):
        parse_config(config)


@pytest.mark.parametrize("field_name", ["alert", "for", "annotations", "limit", "query_offset"])
def test_parse_rejects_unsupported_prometheus_fields(field_name):
    config = {
        "groups": [
            {
                "name": "rr_resource_group",
                "rules": [{"record": "cpu_usage_avg", "expr": "up", field_name: "unsupported"}],
            }
        ]
    }

    with pytest.raises(ValueError, match=field_name):
        parse_config(config)


def test_parse_rejects_deleted_desired_status():
    config = {
        "groups": [
            {
                "name": "rr_resource_group",
                "bkmonitor": {"desired_status": "deleted"},
                "rules": [{"record": "cpu_usage_avg", "expr": "up"}],
            }
        ]
    }

    with pytest.raises(ValueError, match="unsupported desired_status: deleted"):
        parse_config(config)


def test_dump_rule_prefers_raw_config_and_refreshes_metadata():
    raw_config = {
        "name": "old_name",
        "interval": "1min",
        "labels": {"env": "prod"},
        "bkmonitor": {"description": "old"},
        "rules": [{"record": "cpu_usage_avg", "expr": "up"}],
    }
    rule = SimpleNamespace(
        name="new_name",
        description="new description",
        data_label="rr_cpu",
        auto_refresh=False,
        desired_status=RecordRuleV4DesiredStatus.STOPPED.value,
        current_spec=SimpleNamespace(raw_config=raw_config, interval="5min", labels=[{"env": "stag"}]),
    )

    group = dump_rule(rule)

    assert group["name"] == "new_name"
    assert group["interval"] == "5min"
    assert group["labels"] == {"env": "stag"}
    assert group["rules"] == [{"record": "cpu_usage_avg", "expr": "up"}]
    assert group["bkmonitor"] == {
        "description": "new description",
        "data_label": "rr_cpu",
        "auto_refresh": False,
        "desired_status": RecordRuleV4DesiredStatus.STOPPED.value,
    }


def test_dump_rule_falls_back_to_spec_records_when_raw_config_missing():
    spec_record = SimpleNamespace(
        input_type=RecordRuleV4InputType.PROMQL.value,
        input_config={"promql": "sum(cpu_usage)"},
        metric_name="cpu_usage_sum",
        labels=[{"scenario": "fallback"}],
    )
    spec = SimpleNamespace(
        raw_config={},
        interval="1min",
        labels=[{"env": "prod"}],
        records=FakeRecordManager([spec_record]),
    )
    rule = SimpleNamespace(
        pk=100,
        table_id="bkm_rr_100_cpu_abcd.__default__",
        name="cpu_rule",
        description="",
        data_label="",
        auto_refresh=True,
        desired_status=RecordRuleV4DesiredStatus.RUNNING.value,
        current_spec=spec,
    )

    group = dump_rule(rule)
    entries = build_export_entries([rule], lock_filename=True)

    assert group["rules"] == [
        {
            "record": "cpu_usage_sum",
            "expr": "sum(cpu_usage)",
            "labels": {"scenario": "fallback"},
        }
    ]
    assert entries[0].filename == "bkm_rr_100_cpu_abcd.yaml"
    assert entries[0].content == {"groups": [group]}
