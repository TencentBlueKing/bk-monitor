"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from __future__ import annotations

from typing import Any

import pytest

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc.functions.bkm_cli.commands import run_readonly_command
from metadata import models

pytestmark = pytest.mark.django_db(databases="__all__")

DATA_ID = 10_001
GROUP_ID = 1_001
BK_BIZ_ID = 123
TABLE_ID = "123_bkapm_metric_test.__default__"
TENANT_ID = "tenant-a"


def _create_group(
    *,
    data_id: int = DATA_ID,
    group_id: int = GROUP_ID,
    table_id: str = TABLE_ID,
    tenant_id: str = TENANT_ID,
    is_enable: bool = True,
) -> models.TimeSeriesGroup:
    return models.TimeSeriesGroup.objects.create(
        time_series_group_id=group_id,
        time_series_group_name=f"group-{group_id}",
        bk_data_id=data_id,
        bk_biz_id=BK_BIZ_ID,
        bk_tenant_id=tenant_id,
        table_id=table_id,
        is_enable=is_enable,
        creator="system",
        last_modify_user="system",
    )


def _create_metric(
    field_name: str,
    *,
    field_scope: str = "default",
    tag_list: list[str] | None = None,
    scope_id: int | None = None,
    group_id: int = GROUP_ID,
    is_active: bool = True,
) -> models.TimeSeriesMetric:
    return models.TimeSeriesMetric.objects.create(
        group_id=group_id,
        table_id=f"{TABLE_ID}.{field_scope}",
        field_name=field_name,
        field_scope=field_scope,
        tag_list=tag_list or [],
        scope_id=scope_id,
        is_active=is_active,
    )


def _create_rt_field(
    field_name: str,
    *,
    tag: str,
    tenant_id: str = TENANT_ID,
    table_id: str = TABLE_ID,
    is_disabled: bool = False,
) -> models.ResultTableField:
    return models.ResultTableField.objects.create(
        bk_tenant_id=tenant_id,
        table_id=table_id,
        field_name=field_name,
        field_type=models.ResultTableField.FIELD_TYPE_FLOAT,
        tag=tag,
        is_disabled=is_disabled,
        is_config_by_user=True,
        creator="system",
        last_modify_user="system",
    )


def _run(**params: Any) -> dict[str, Any]:
    return run_readonly_command({"command_id": "inspect_ts_metric_metadata", "params": params})


def _all_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for child in value.values() for key in _all_keys(child)}
    if isinstance(value, list):
        return {key for child in value for key in _all_keys(child)}
    return set()


def test_inspect_exact_scope_returns_fixed_projection_and_deduplicates_in_order(mocker, django_assert_num_queries):
    _create_group()
    _create_metric("metric_b", field_scope="custom", tag_list=["host", "zone"], scope_id=1)
    _create_rt_field("metric_b", tag=models.ResultTableField.FIELD_TAG_METRIC)
    _create_rt_field("host", tag=models.ResultTableField.FIELD_TAG_DIMENSION)

    source_scan = mocker.patch(
        "metadata.models.custom_report.time_series.TimeSeriesGroup.get_metrics_from_redis",
        side_effect=AssertionError("source scan must not run"),
    )
    redis_factory = mocker.patch(
        "utils.redis_client.RedisClient.from_envs",
        side_effect=AssertionError("Redis must not run"),
    )
    bkdata_query = mocker.patch(
        "metadata.models.custom_report.time_series.api.bkdata.query_metric_and_dimension",
        side_effect=AssertionError("BKData must not run"),
    )

    with django_assert_num_queries(3):
        result = _run(
            data_id=DATA_ID,
            metrics=["metric_b", "metric_b"],
            dimensions=["host", "host"],
            field_scope="custom",
        )

    assert result["context"] == {
        "data_id": DATA_ID,
        "bk_biz_id": BK_BIZ_ID,
        "bk_tenant_id": TENANT_ID,
        "time_series_group_id": GROUP_ID,
        "table_id": TABLE_ID,
        "group_is_enable": True,
        "group_is_delete": False,
        "scope_mode": "exact",
        "field_scope": "custom",
    }
    assert [item["field_name"] for item in result["metrics"]] == ["metric_b"]
    metric = result["metrics"][0]
    assert metric["structural_alignment_state"] == "aligned"
    assert metric["effective_registration_state"] == "effective"
    assert metric["time_series_metric"]["structural_record_count"] == 1
    assert metric["time_series_metric"]["effective_record_count"] == 1
    assert metric["time_series_metric"]["inactive_record_count"] == 0
    assert metric["time_series_metric"]["scope_disabled_record_count"] == 0
    assert metric["time_series_metric"]["records"][0] == {
        "field_scope": "custom",
        "table_id": f"{TABLE_ID}.custom",
        "is_active": True,
        "is_scope_disabled": False,
        "is_effective": True,
        "last_modify_time": metric["time_series_metric"]["records"][0]["last_modify_time"],
    }
    assert isinstance(metric["time_series_metric"]["records"][0]["last_modify_time"], str)
    assert metric["dimensions"][0]["membership"] == {
        "evaluation": "evaluated",
        "state": "present",
        "structural_metric_scope_count": 1,
        "effective_metric_scope_count": 1,
        "structural_present_scope_count": 1,
        "effective_present_scope_count": 1,
        "present_in_all_effective_scopes": True,
    }
    assert metric["dimensions"][0]["consistency_state"] == "aligned"
    assert not {"tag_list", "field_config"} & _all_keys(result)
    source_scan.assert_not_called()
    redis_factory.assert_not_called()
    bkdata_query.assert_not_called()


def test_inspect_exact_nondefault_scope_miss_does_not_claim_global_absence():
    _create_group()
    _create_metric("requests_total", field_scope="default")
    _create_rt_field("requests_total", tag=models.ResultTableField.FIELD_TAG_METRIC)

    result = _run(data_id=DATA_ID, metrics=["requests_total"], field_scope="custom")

    metric = result["metrics"][0]
    assert metric["time_series_metric"] == {
        "structural_record_count": 0,
        "effective_record_count": 0,
        "inactive_record_count": 0,
        "scope_disabled_record_count": 0,
        "records": [],
    }
    assert metric["structural_alignment_state"] == "rtf_only"
    assert metric["effective_registration_state"] == "metric_not_found_in_scope"


def test_inspect_exact_default_scope_miss_only_reports_requested_scope():
    _create_group()
    _create_metric("requests_total", field_scope="custom")

    result = _run(data_id=DATA_ID, metrics=["requests_total"], field_scope="default")

    assert result["context"]["scope_mode"] == "exact"
    assert result["metrics"][0]["structural_alignment_state"] == "missing_both"
    assert result["metrics"][0]["effective_registration_state"] == "metric_not_found_in_scope"


def test_inspect_all_bounded_reports_multiple_scopes_and_dimension_alignment_states():
    _create_group()
    _create_metric("requests_total", field_scope="scope-a", tag_list=["host", "disabled_dim", "wrong_tag"])
    _create_metric("requests_total", field_scope="scope-b", tag_list=["disabled_dim", "wrong_tag"])
    _create_rt_field("requests_total", tag=models.ResultTableField.FIELD_TAG_METRIC)
    _create_rt_field("host", tag=models.ResultTableField.FIELD_TAG_DIMENSION)
    _create_rt_field("rtf_only", tag=models.ResultTableField.FIELD_TAG_DIMENSION)
    _create_rt_field("wrong_tag", tag=models.ResultTableField.FIELD_TAG_METRIC)
    _create_rt_field("disabled_dim", tag=models.ResultTableField.FIELD_TAG_DIMENSION, is_disabled=True)

    result = _run(
        data_id=DATA_ID,
        metrics=["requests_total"],
        dimensions=["host", "tsm_only", "rtf_only", "missing", "wrong_tag", "disabled_dim"],
    )

    assert result["context"]["scope_mode"] == "all_bounded"
    metric = result["metrics"][0]
    assert metric["time_series_metric"]["structural_record_count"] == 2
    assert metric["time_series_metric"]["effective_record_count"] == 2
    dimensions = {item["field_name"]: item for item in metric["dimensions"]}
    assert dimensions["host"]["membership"] == {
        "evaluation": "evaluated",
        "state": "present",
        "structural_metric_scope_count": 2,
        "effective_metric_scope_count": 2,
        "structural_present_scope_count": 1,
        "effective_present_scope_count": 1,
        "present_in_all_effective_scopes": False,
    }
    assert dimensions["host"]["consistency_state"] == "partially_aligned"
    assert dimensions["tsm_only"]["consistency_state"] == "missing_both"
    assert dimensions["rtf_only"]["consistency_state"] == "rtf_only"
    assert dimensions["missing"]["consistency_state"] == "missing_both"
    assert dimensions["wrong_tag"]["consistency_state"] == "rtf_not_dimension"
    assert dimensions["disabled_dim"]["consistency_state"] == "rtf_disabled"


def test_inspect_dimension_present_in_tsm_but_missing_from_rtf_is_tsm_only():
    _create_group()
    _create_metric("requests_total", tag_list=["hostname"])

    result = _run(data_id=DATA_ID, metrics=["requests_total"], dimensions=["hostname"])

    dimension = result["metrics"][0]["dimensions"][0]
    assert dimension["membership"]["state"] == "present"
    assert dimension["result_table_field"] == {"exists": False}
    assert dimension["consistency_state"] == "tsm_only"


def test_inspect_dimension_denominator_uses_only_effective_tsm_rows():
    _create_group()
    _create_metric("requests_total", field_scope="active", scope_id=1, tag_list=["host"])
    _create_metric("requests_total", field_scope="inactive", scope_id=2, tag_list=[], is_active=False)
    _create_metric("requests_total", field_scope="disabled", scope_id=0, tag_list=[])
    _create_rt_field("requests_total", tag=models.ResultTableField.FIELD_TAG_METRIC)
    _create_rt_field("host", tag=models.ResultTableField.FIELD_TAG_DIMENSION)

    result = _run(data_id=DATA_ID, metrics=["requests_total"], dimensions=["host"])

    metric = result["metrics"][0]
    assert metric["time_series_metric"]["structural_record_count"] == 3
    assert metric["time_series_metric"]["effective_record_count"] == 1
    assert metric["time_series_metric"]["inactive_record_count"] == 1
    assert metric["time_series_metric"]["scope_disabled_record_count"] == 1
    assert metric["structural_alignment_state"] == "aligned"
    assert metric["effective_registration_state"] == "effective"
    assert metric["dimensions"][0]["membership"] == {
        "evaluation": "evaluated",
        "state": "present",
        "structural_metric_scope_count": 3,
        "effective_metric_scope_count": 1,
        "structural_present_scope_count": 1,
        "effective_present_scope_count": 1,
        "present_in_all_effective_scopes": True,
    }
    assert metric["dimensions"][0]["consistency_state"] == "aligned"


@pytest.mark.parametrize(
    ("metric_kwargs", "effective_state"),
    [
        ({"scope_id": 1, "is_active": False}, "tsm_inactive"),
        ({"scope_id": 0, "is_active": True}, "scope_disabled"),
    ],
)
def test_inspect_exact_scope_distinguishes_ineffective_tsm_lifecycle(metric_kwargs, effective_state):
    _create_group()
    _create_metric("requests_total", field_scope="custom", tag_list=["host"], **metric_kwargs)
    _create_rt_field("requests_total", tag=models.ResultTableField.FIELD_TAG_METRIC)
    _create_rt_field("host", tag=models.ResultTableField.FIELD_TAG_DIMENSION)

    result = _run(
        data_id=DATA_ID,
        metrics=["requests_total"],
        dimensions=["host"],
        field_scope="custom",
    )

    metric = result["metrics"][0]
    assert metric["structural_alignment_state"] == "aligned"
    assert metric["effective_registration_state"] == effective_state
    assert metric["time_series_metric"]["effective_record_count"] == 0
    assert metric["dimensions"][0]["membership"]["evaluation"] == "not_evaluable"
    assert metric["dimensions"][0]["membership"]["state"] == "unknown"
    assert metric["dimensions"][0]["consistency_state"] == "not_evaluable"


def test_inspect_metric_reports_structural_and_effective_states():
    _create_group()
    _create_metric("aligned")
    _create_rt_field("aligned", tag=models.ResultTableField.FIELD_TAG_METRIC)
    _create_metric("tsm_only")
    _create_rt_field("rtf_only", tag=models.ResultTableField.FIELD_TAG_METRIC)
    _create_metric("rtf_disabled")
    _create_rt_field("rtf_disabled", tag=models.ResultTableField.FIELD_TAG_METRIC, is_disabled=True)
    _create_metric("rtf_not_metric")
    _create_rt_field("rtf_not_metric", tag=models.ResultTableField.FIELD_TAG_DIMENSION)

    result = _run(
        data_id=DATA_ID,
        metrics=["aligned", "tsm_only", "rtf_only", "missing_both", "rtf_disabled", "rtf_not_metric"],
    )

    metrics = {item["field_name"]: item for item in result["metrics"]}
    expected = {
        "aligned": ("aligned", "effective"),
        "tsm_only": ("tsm_only", "tsm_only"),
        "rtf_only": ("rtf_only", "rtf_only"),
        "missing_both": ("missing_both", "missing_both"),
        "rtf_disabled": ("rtf_disabled", "rtf_disabled"),
        "rtf_not_metric": ("rtf_not_metric", "rtf_not_metric"),
    }
    assert {
        field_name: (item["structural_alignment_state"], item["effective_registration_state"])
        for field_name, item in metrics.items()
    } == expected


def test_inspect_returns_disabled_group_without_calling_it_effective():
    _create_group(is_enable=False)
    _create_metric("requests_total")
    _create_rt_field("requests_total", tag=models.ResultTableField.FIELD_TAG_METRIC)

    result = _run(data_id=DATA_ID, metrics=["requests_total"])

    assert result["context"]["group_is_enable"] is False
    assert result["context"]["group_is_delete"] is False
    assert result["metrics"][0]["structural_alignment_state"] == "aligned"
    assert result["metrics"][0]["effective_registration_state"] == "group_disabled"


@pytest.mark.parametrize("field_scope", [None, "default"])
def test_inspect_dimension_is_not_evaluable_when_metric_has_no_selected_tsm_rows(field_scope):
    _create_group()
    _create_rt_field("host", tag=models.ResultTableField.FIELD_TAG_DIMENSION)
    params = {"data_id": DATA_ID, "metrics": ["missing_metric"], "dimensions": ["host"]}
    if field_scope is not None:
        params["field_scope"] = field_scope

    result = _run(**params)

    dimension = result["metrics"][0]["dimensions"][0]
    assert dimension["membership"] == {
        "evaluation": "not_evaluable",
        "state": "unknown",
        "structural_metric_scope_count": 0,
        "effective_metric_scope_count": 0,
        "structural_present_scope_count": 0,
        "effective_present_scope_count": 0,
        "present_in_all_effective_scopes": None,
    }
    assert dimension["consistency_state"] == "not_evaluable"


def test_inspect_all_bounded_rejects_more_than_100_tsm_rows():
    _create_group()
    models.TimeSeriesMetric.objects.bulk_create(
        [
            models.TimeSeriesMetric(
                group_id=GROUP_ID,
                table_id=f"{TABLE_ID}.scope-{index}",
                field_name="requests_total",
                field_scope=f"scope-{index}",
                tag_list=[],
            )
            for index in range(101)
        ]
    )

    with pytest.raises(CustomException, match="more than 100.*field_scope"):
        _run(data_id=DATA_ID, metrics=["requests_total"])


def test_inspect_result_table_field_is_isolated_by_group_tenant():
    _create_group()
    _create_metric("requests_total")
    _create_rt_field("requests_total", tag=models.ResultTableField.FIELD_TAG_DIMENSION, tenant_id="tenant-b")
    _create_rt_field("requests_total", tag=models.ResultTableField.FIELD_TAG_METRIC, tenant_id=TENANT_ID)

    result = _run(data_id=DATA_ID, metrics=["requests_total"])

    assert result["metrics"][0]["result_table_field"]["tag"] == models.ResultTableField.FIELD_TAG_METRIC
    assert result["metrics"][0]["structural_alignment_state"] == "aligned"
    assert result["metrics"][0]["effective_registration_state"] == "effective"


def test_inspect_rejects_missing_and_ambiguous_groups():
    with pytest.raises(CustomException, match="not found"):
        _run(data_id=DATA_ID, metrics=["requests_total"])

    _create_group()
    _create_group(group_id=GROUP_ID + 1, tenant_id="tenant-b", table_id="other.table")
    with pytest.raises(CustomException, match="integrity conflict"):
        _run(data_id=DATA_ID, metrics=["requests_total"])


def test_inspect_stays_available_when_legacy_diagnose_source_scan_times_out(mocker):
    _create_group()
    _create_metric("requests_total")
    _create_rt_field("requests_total", tag=models.ResultTableField.FIELD_TAG_METRIC)
    mocker.patch("bkmonitor.utils.ts_metric_diagnosis.RedisClient.from_envs", return_value=mocker.MagicMock())
    mocker.patch("bkmonitor.utils.ts_metric_diagnosis._detect_source_backend", return_value="bkdata")
    mocker.patch(
        "metadata.models.custom_report.time_series.TimeSeriesGroup.get_metrics_from_redis",
        side_effect=TimeoutError("source catalog timed out"),
    )

    with pytest.raises(TimeoutError, match="source catalog timed out"):
        run_readonly_command(
            {
                "command_id": "diagnose_ts_metric_sync",
                "params": {"data_id": DATA_ID, "metrics": ["requests_total"]},
            }
        )

    result = _run(data_id=DATA_ID, metrics=["requests_total"])
    assert result["metrics"][0]["structural_alignment_state"] == "aligned"
    assert result["metrics"][0]["effective_registration_state"] == "effective"


@pytest.mark.parametrize(
    ("params", "message"),
    [
        ({"metrics": ["m"]}, "data_id is required"),
        ({"data_id": True, "metrics": ["m"]}, "data_id must be an integer"),
        ({"data_id": 1.2, "metrics": ["m"]}, "data_id must be an integer"),
        ({"data_id": "not-an-int", "metrics": ["m"]}, "data_id must be an integer"),
        ({"data_id": DATA_ID, "metrics": "m"}, "metrics must be a list"),
        ({"data_id": DATA_ID, "metrics": []}, "metrics must contain 1 to 20"),
        ({"data_id": DATA_ID, "metrics": [f"m{i}" for i in range(21)]}, "metrics must contain 1 to 20"),
        ({"data_id": DATA_ID, "metrics": [1]}, "metrics items must be strings"),
        ({"data_id": DATA_ID, "metrics": [" "]}, "metrics items must be non-empty"),
        ({"data_id": DATA_ID, "metrics": ["m"], "dimensions": "host"}, "dimensions must be a list"),
        (
            {"data_id": DATA_ID, "metrics": ["m"], "dimensions": [f"d{i}" for i in range(21)]},
            "dimensions must contain 0 to 20",
        ),
        ({"data_id": DATA_ID, "metrics": ["m"], "dimensions": [1]}, "dimensions items must be strings"),
        ({"data_id": DATA_ID, "metrics": ["m"], "dimensions": [" "]}, "dimensions items must be non-empty"),
        ({"data_id": DATA_ID, "metrics": ["m"], "field_scope": 1}, "field_scope must be a string"),
        ({"data_id": DATA_ID, "metrics": ["m"], "field_scope": " "}, "field_scope must be non-empty"),
        (
            {
                "data_id": DATA_ID,
                "metrics": [f"m{i}" for i in range(11)],
                "dimensions": [f"d{i}" for i in range(10)],
            },
            "metrics x max",
        ),
    ],
)
def test_inspect_validates_bounded_exact_inputs(params, message):
    with pytest.raises(CustomException, match=message):
        _run(**params)
