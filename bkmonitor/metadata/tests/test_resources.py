# -*- coding: utf-8 -*-
import pytest

from metadata import models

pytestmark = pytest.mark.django_db

REDIS_DATA = [
    {
        'field_name': 'test_metric',
        'tag_value_list': {
            'bk_biz_id': {'last_update_time': 1662009139, 'values': ["1"]},
            'parent_scenario': {'last_update_time': 1662009139, 'values': []},
            'scenario': {'last_update_time': 1662009139, 'values': []},
            'target': {'last_update_time': 1662009139, 'values': []},
            'target_biz_id': {'last_update_time': 1662009139, 'values': []},
            'target_biz_name': {'last_update_time': 1662009139, 'values': []},
        },
        'last_modify_time': 1662009139.0,
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
