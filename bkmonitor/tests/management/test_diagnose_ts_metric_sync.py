"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
from io import StringIO

import pytest
from django.core.management import call_command

from bkmonitor.models.metric_list_cache import MetricListCache
from constants.data_source import DataSourceLabel, DataTypeLabel
from metadata import models

pytestmark = pytest.mark.django_db(databases="__all__")

DEFAULT_DATA_ID = 1579347
DEFAULT_BK_BIZ_ID = 101068
DEFAULT_TABLE_ID = "101068_bkapm_metric_ugc_plat.__default__"
DEFAULT_GROUP_ID = 9522
DEFAULT_USERNAME = "system"


class FakeRedisClient:
    """用于命令测试的简易 Redis 假实现。"""

    def __init__(self, scores: dict[tuple[str, str], float] | None = None, dimensions: dict | None = None) -> None:
        self.scores = scores or {}
        self.dimensions = dimensions or {}

    def zscore(self, key: str, member: str) -> float | None:
        """返回 zset member 的分值。"""
        return self.scores.get((key, member))

    def hget(self, key: str, field: str) -> bytes | None:
        """返回 hash field 的值。"""
        return self.dimensions.get((key, field))

    def zrangebyscore(self, key: str, min: float, max: float, withscores: bool = True) -> list[tuple[bytes, float]]:
        """返回分值窗口内的全部 member。"""
        result = []
        for (stored_key, member), score in self.scores.items():
            if stored_key == key and min <= score <= max:
                result.append((member.encode("utf-8"), score))
        return result


@pytest.fixture
def create_ts_group() -> None:
    """创建排障命令所需的最小 TimeSeriesGroup 测试数据。"""
    models.TimeSeriesGroup.objects.create(
        time_series_group_id=DEFAULT_GROUP_ID,
        bk_data_id=DEFAULT_DATA_ID,
        bk_biz_id=DEFAULT_BK_BIZ_ID,
        table_id=DEFAULT_TABLE_ID,
        creator=DEFAULT_USERNAME,
        last_modify_user=DEFAULT_USERNAME,
        time_series_group_name="test_ts_group",
    )
    yield
    models.TimeSeriesMetric.objects.all().delete()
    models.ResultTableField.objects.all().delete()
    MetricListCache.objects.all().delete()
    models.TimeSeriesGroup.objects.filter(bk_data_id=DEFAULT_DATA_ID).delete()


def test_diagnose_ts_metric_sync_stages(mocker, create_ts_group) -> None:
    """覆盖 source 缺失、web 缓存缺失、全部命中三种主要排障结论。"""
    metric_name = "wea_agent_http_request"
    score = 1775808502
    metrics_key = f"bkmonitor:metrics_{DEFAULT_DATA_ID}"
    dimensions_key = f"bkmonitor:metric_dimensions_{DEFAULT_DATA_ID}"
    redis_client = FakeRedisClient(
        scores={(metrics_key, metric_name): score},
        dimensions={(dimensions_key, metric_name): b'{"dimensions": {"target": {"values": []}}}'},
    )
    mock_metric_info = {
        "field_name": metric_name,
        "field_scope": "default",
        "tag_value_list": {"target": {"last_update_time": score, "values": []}},
        "last_modify_time": score,
    }

    mocker.patch(
        "bkmonitor.management.commands.diagnose_ts_metric_sync.RedisClient.from_envs",
        return_value=redis_client,
    )
    mocker.patch("bkmonitor.management.commands.diagnose_ts_metric_sync.RedisTools.get_list", return_value=[])

    test_cases = [
        {
            "name": "source_missing",
            "metrics_from_source": [[], []],
            "prepare": None,
            "expected_stage": "source",
            "expected_cache": False,
        },
        {
            "name": "web_cache_missing",
            "metrics_from_source": [[mock_metric_info], [mock_metric_info]],
            "prepare": "metadata_only",
            "expected_stage": "web_cache",
            "expected_cache": False,
        },
        {
            "name": "all_ok",
            "metrics_from_source": [[mock_metric_info], [mock_metric_info]],
            "prepare": "metadata_and_cache",
            "expected_stage": "ok",
            "expected_cache": True,
        },
    ]

    for case in test_cases:
        models.TimeSeriesMetric.objects.all().delete()
        models.ResultTableField.objects.all().delete()
        MetricListCache.objects.all().delete()

        if case["prepare"] in {"metadata_only", "metadata_and_cache"}:
            _create_metadata_records(metric_name)

        if case["prepare"] == "metadata_and_cache":
            _create_metric_cache(metric_name)

        mocker.patch(
            "metadata.models.custom_report.time_series.TimeSeriesGroup.get_metrics_from_redis",
            side_effect=case["metrics_from_source"],
        )

        out = StringIO()
        call_command(
            "diagnose_ts_metric_sync",
            data_id=DEFAULT_DATA_ID,
            metrics=metric_name,
            json=True,
            stdout=out,
        )

        output = json.loads(out.getvalue())
        metric_output = output["metrics"][0]
        assert metric_output["diagnosis"]["stage"] == case["expected_stage"], case["name"]
        assert metric_output["status"]["web_metric_cache_exists"] is case["expected_cache"], case["name"]
        assert output["context"]["source"]["backend"] == "redis", case["name"]
        assert metric_output["status"]["source_recent_discovered"] is (case["name"] != "source_missing"), case["name"]
        assert "redis" in metric_output["details"]["source"], case["name"]


def test_diagnose_ts_metric_sync_bkdata_source(mocker, create_ts_group) -> None:
    """命中 BKData 分支时，不应把 Redis 缺失误判为 source 异常。"""
    metric_name = "wea_agent_http_request"
    score = 1775808502
    mock_metric_info = {
        "field_name": metric_name,
        "field_scope": "default",
        "tag_value_list": {"target": {"last_update_time": score, "values": []}},
        "last_modify_time": score,
    }

    mocker.patch(
        "bkmonitor.management.commands.diagnose_ts_metric_sync.RedisClient.from_envs",
        return_value=FakeRedisClient(),
    )
    mocker.patch(
        "bkmonitor.management.commands.diagnose_ts_metric_sync.RedisTools.get_list",
        return_value=[DEFAULT_TABLE_ID],
    )
    mocker.patch(
        "metadata.models.custom_report.time_series.TimeSeriesGroup.get_metrics_from_redis",
        side_effect=[[mock_metric_info], [mock_metric_info]],
    )

    _create_metadata_records(metric_name)
    _create_metric_cache(metric_name)

    out = StringIO()
    call_command(
        "diagnose_ts_metric_sync",
        data_id=DEFAULT_DATA_ID,
        metrics=metric_name,
        json=True,
        stdout=out,
    )

    output = json.loads(out.getvalue())
    assert output["context"]["source"]["backend"] == "bkdata"
    assert output["metrics"][0]["diagnosis"]["stage"] == "ok"
    assert output["metrics"][0]["status"]["source_recent_discovered"] is True
    assert "redis" not in output["metrics"][0]["details"]["source"]
    assert output["context"]["source"] == {"backend": "bkdata", "query_path": "bkdata.query_metric_and_dimension"}


def _create_metadata_records(metric_name: str) -> None:
    """创建 metadata 层命中的测试数据。"""
    models.TimeSeriesMetric.objects.create(
        group_id=DEFAULT_GROUP_ID,
        table_id=f"{DEFAULT_TABLE_ID.split('.')[0]}.{metric_name}",
        field_name=metric_name,
        field_scope="default",
        tag_list=["target"],
    )
    models.ResultTableField.objects.create(
        table_id=DEFAULT_TABLE_ID,
        field_name=metric_name,
        field_type=models.ResultTableField.FIELD_TYPE_FLOAT,
        tag=models.ResultTableField.FIELD_TAG_METRIC,
        is_config_by_user=True,
        default_value="0",
        description="",
        unit="",
        alias_name="",
        creator=DEFAULT_USERNAME,
        last_modify_user=DEFAULT_USERNAME,
    )


def _create_metric_cache(metric_name: str) -> None:
    """创建 web 缓存命中的测试数据。"""
    MetricListCache.objects.create(
        bk_tenant_id="system",
        bk_biz_id=DEFAULT_BK_BIZ_ID,
        result_table_id=DEFAULT_TABLE_ID,
        result_table_name="",
        metric_field=metric_name,
        metric_field_name=metric_name,
        unit="",
        unit_conversion=1.0,
        dimensions=[],
        plugin_type="",
        related_name="",
        related_id="",
        collect_config="",
        collect_config_ids=[],
        result_table_label="other_rt",
        data_source_label=DataSourceLabel.CUSTOM,
        data_type_label=DataTypeLabel.TIME_SERIES,
        data_target="none_target",
        default_dimensions=[],
        default_condition=[],
        description="",
        collect_interval=60,
        category_display="",
        result_table_label_name="",
        extend_fields={},
        data_label="",
    )
