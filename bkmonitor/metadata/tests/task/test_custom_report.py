import random

import pytest
from mockredis import mock_redis_client
from pytest_mock import MockFixture

from metadata.models import (
    ESStorage,
    Event,
    EventGroup,
    ResultTableField,
    SpaceDataSource,
    TimeSeriesGroup,
)
from metadata.task import check_event_update, check_update_ts_metric
from metadata.tests.task.conftest import EventGroupFakeES

pytestmark = pytest.mark.django_db

RECORDS = 800


@pytest.fixture
def create_and_delete_record():
    event_groups = []
    time_series_groups = []
    space_data_sources = []
    for i in range(RECORDS):
        event_groups.append(
            EventGroup(
                event_group_name="eg_{}".format(i), bk_data_id=2000000 + i, bk_biz_id=1, table_id="tb_{}".format(i)
            )
        )
        time_series_groups.append(
            TimeSeriesGroup(
                bk_data_id=3000000 + i,
                bk_biz_id=1,
                table_id="tb_{}".format(i),
                time_series_group_name="test_group_name_{}".format(i),
                label="applications",
                creator="admin",
            )
        )
        space_data_sources.append(
            SpaceDataSource(
                space_type_id="space_type_{}".format(i), space_id="space_id_{}".format(i), bk_data_id=3000000 + i
            )
        )

    EventGroup.objects.bulk_create(event_groups)
    TimeSeriesGroup.objects.bulk_create(time_series_groups)
    SpaceDataSource.objects.bulk_create(space_data_sources)
    es_clusters = []
    for event_group in event_groups:
        es_clusters.append(ESStorage(storage_cluster_id=random.randint(0, 40), table_id=event_group.table_id))
    ESStorage.objects.bulk_create(es_clusters)
    Event.objects.all().delete()
    yield
    EventGroup.objects.filter(table_id__startswith="tb_").delete()
    ESStorage.objects.filter(table_id__startswith="tb_").delete()
    Event.objects.all().delete()
    TimeSeriesGroup.objects.filter(time_series_group_name__startswith="test_group_name_").delete()
    SpaceDataSource.objects.filter(space_type_id__startswith="space_type_").delete()
    ResultTableField.objects.filter(table_id__startswith="tb_").delete()


def test_check_event_update(mocker: MockFixture, create_and_delete_record):
    mocker.patch("redis.Redis", side_effect=mock_redis_client)
    # 正常情况，每个EventGroup更新一条Even记录
    mocker.patch("metadata.utils.es_tools.get_client", return_value=EventGroupFakeES()).start()
    mocker.patch("alarm_backends.core.storage.redis.Cache.__new__", return_value=mock_redis_client())
    check_event_update()
    assert Event.objects.count() == EventGroup.objects.filter(table_id__startswith="tb_").count()


def test_check_update_ts_metric(mocker: MockFixture, create_and_delete_record):
    mocker.patch("metadata.task.tasks.push_and_publish_space_router", return_value=None)
    mocker.patch("metadata.models.custom_report.time_series.TimeSeriesGroup.update_tag_fields", return_value=True)
    mock_redis_data = [
        {
            "field_name": "test_field1",
            "tag_value_list": {
                "bcs_cluster_id": {"last_update_time": 1667961028, "values": []},
                "bk_biz_id": {"last_update_time": 1667961028, "values": []},
                "time": {"last_update_time": 1667961028, "values": []},
                "test_field1": {"last_update_time": 1667961028, "values": []},
            },
            "last_modify_time": 1667961028.0,
        },
        {
            "field_name": "test_field2",
            "tag_value_list": {
                "bcs_cluster_id": {"last_update_time": 1667961028, "values": []},
                "bk_biz_id": {"last_update_time": 1667961028, "values": []},
            },
            "last_modify_time": 1667961028.0,
        },
    ]
    mocker.patch(
        "metadata.models.custom_report.time_series.TimeSeriesGroup.get_metrics_from_redis", return_value=mock_redis_data
    )
    mocker.patch("alarm_backends.core.storage.redis.Cache.__new__", return_value=mock_redis_client())
    check_update_ts_metric()
    assert 2 * RECORDS == ResultTableField.objects.filter(table_id__startswith="tb_").count()
