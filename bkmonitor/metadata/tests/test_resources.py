import pytest

from metadata import models

pytestmark = pytest.mark.django_db(databases="__all__")

REDIS_DATA = [
    {
        "field_name": "test_metric",
        "tag_value_list": {
            "bk_biz_id": {"last_update_time": 1662009139, "values": ["1"]},
            "parent_scenario": {"last_update_time": 1662009139, "values": []},
            "scenario": {"last_update_time": 1662009139, "values": []},
            "target": {"last_update_time": 1662009139, "values": []},
            "target_biz_id": {"last_update_time": 1662009139, "values": []},
            "target_biz_name": {"last_update_time": 1662009139, "values": []},
        },
        "last_modify_time": 1662009139.0,
    }
]
DEFAULT_DATA_ID = 10000
DEFAULT_BIZ_ID = 10000
DEFAULT_GROUP_ID = 10000
DEFAULT_TABLE_ID = "test_table_id"


@pytest.fixture
def create_and_delete_ts_group_record():
    models.TimeSeriesGroup.objects.create(
        bk_data_id=DEFAULT_DATA_ID,
        bk_biz_id=DEFAULT_BIZ_ID,
        table_id=DEFAULT_TABLE_ID,
        time_series_group_id=DEFAULT_GROUP_ID,
    )
    yield
    models.TimeSeriesGroup.objects.filter(
        bk_data_id=DEFAULT_DATA_ID, bk_biz_id=DEFAULT_BIZ_ID, table_id=DEFAULT_TABLE_ID
    ).delete()


def test_get_ts_metrics_by_dimension(mocker, create_and_delete_ts_group_record):
    obj = models.TimeSeriesGroup.objects.get(table_id=DEFAULT_TABLE_ID)
    mocker.patch(
        "metadata.models.custom_report.time_series.TimeSeriesGroup.get_metrics_from_redis", return_value=REDIS_DATA
    )
    # 匹配到数据的场景
    metric_list = obj.get_ts_metrics_by_dimension("bk_biz_id", None)
    assert metric_list == ["test_metric"]

    metric_list = obj.get_ts_metrics_by_dimension(None, "1")
    assert metric_list == ["test_metric"]

    metric_list = obj.get_ts_metrics_by_dimension("bk_biz_id", "1")
    assert metric_list == ["test_metric"]

    # 匹配不到数据的场景
    metric_list = obj.get_ts_metrics_by_dimension("bk_biz_id12", None)
    assert metric_list == []

    metric_list = obj.get_ts_metrics_by_dimension("bk_biz_id", "2")
    assert metric_list == []

    metric_list = obj.get_ts_metrics_by_dimension(None, "2")
    assert metric_list == []


def test_get_ts_metrics_by_dimension_skip_fetch_without_dimension(mocker, create_and_delete_ts_group_record):
    """无维度过滤时结果不会被使用，应提前返回且不拉取 redis/bkdata 指标（避免无谓的 bkdata /v4/dd/ 调用）"""
    obj = models.TimeSeriesGroup.objects.get(table_id=DEFAULT_TABLE_ID)
    mock_fetch = mocker.patch(
        "metadata.models.custom_report.time_series.TimeSeriesGroup.get_metrics_from_redis", return_value=REDIS_DATA
    )

    # 无维度过滤：直接返回空列表，且不触发拉取
    assert obj.get_ts_metrics_by_dimension("", "") == []
    assert obj.get_ts_metrics_by_dimension(None, None) == []
    mock_fetch.assert_not_called()

    # 存在维度过滤时仍会正常拉取
    assert obj.get_ts_metrics_by_dimension("bk_biz_id", "1") == ["test_metric"]
    mock_fetch.assert_called_once()


def _create_rt_field(table_id, bk_tenant_id, field_name, field_type, tag):
    return models.ResultTableField.objects.create(
        table_id=table_id,
        bk_tenant_id=bk_tenant_id,
        field_name=field_name,
        field_type=field_type,
        unit="",
        tag=tag,
        description=f"{field_name} desc",
        is_config_by_user=True,
    )


def test_batch_get_metric_info_maps_prefetch_equivalence(create_and_delete_ts_group_record):
    """批量预取路径(batch_get_metric_info_maps + 传入 get_metric_info_list_with_label)
    与逐 group 自查路径的结果必须完全一致，保证 N+1 优化不改变功能"""
    group = models.TimeSeriesGroup.objects.get(table_id=DEFAULT_TABLE_ID)

    # last_modify_time 为 auto_now，创建即落在过期分界线内
    models.TimeSeriesMetric.objects.create(
        group_id=DEFAULT_GROUP_ID,
        table_id=DEFAULT_TABLE_ID,
        field_name="metric_a",
        tag_list=["dim_x"],
    )
    _create_rt_field(DEFAULT_TABLE_ID, group.bk_tenant_id, "metric_a", "double", "metric")
    _create_rt_field(DEFAULT_TABLE_ID, group.bk_tenant_id, "dim_x", "string", "dimension")

    # 逐 group 自查（原路径）
    result_self = group.get_metric_info_list_with_label("", "")

    # 批量预取路径
    field_map_by_table, scope_map_by_group, metrics_by_group = models.TimeSeriesGroup.batch_get_metric_info_maps(
        [group], group.bk_tenant_id
    )
    result_batch = group.get_metric_info_list_with_label(
        "",
        "",
        field_map=field_map_by_table.get(group.table_id, {}),
        scope_map=scope_map_by_group.get(group.time_series_group_id, {}),
        metrics=metrics_by_group.get(group.time_series_group_id, []),
    )

    # 关键断言：两条路径结果完全一致，且确实产出了指标
    assert result_self == result_batch
    assert len(result_batch) == 1
    assert result_batch[0]["field_name"] == "metric_a"

    # 预取数据确实按 table_id / group_id 正确分桶命中
    assert "metric_a" in field_map_by_table[group.table_id]
    assert [m.field_name for m in metrics_by_group[group.time_series_group_id]] == ["metric_a"]
