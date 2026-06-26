import datetime
import random
from types import SimpleNamespace

import pytest
from mockredis.redis import mock_redis_client
from pytest_mock import MockFixture

from bkmonitor.utils.new_env import is_biz_id_in_new_env_scope
from metadata.models import (
    ESStorage,
    Event,
    EventGroup,
    ResultTableField,
    SpaceDataSource,
    TimeSeriesGroup,
)
from metadata.task import check_event_update, custom_report
from metadata.tests.task.conftest import EventGroupFakeES

pytestmark = pytest.mark.django_db(databases="__all__")

RECORDS = 800


class FixedDatetime(datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 1, 1, 0, 0, tzinfo=tz)


@pytest.fixture
def create_and_delete_record():
    event_groups = []
    time_series_groups = []
    space_data_sources = []
    for i in range(RECORDS):
        event_groups.append(
            EventGroup(event_group_name=f"eg_{i}", bk_data_id=2000000 + i, bk_biz_id=1, table_id=f"tb_{i}")
        )
        time_series_groups.append(
            TimeSeriesGroup(
                bk_data_id=3000000 + i,
                bk_biz_id=1,
                table_id=f"tb_{i}",
                time_series_group_name=f"test_group_name_{i}",
                label="applications",
                creator="admin",
            )
        )
        space_data_sources.append(
            SpaceDataSource(space_type_id=f"space_type_{i}", space_id=f"space_id_{i}", bk_data_id=3000000 + i)
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


def test_is_biz_id_in_new_env_scope():
    assert is_biz_id_in_new_env_scope(11, start_biz_id="10") is True
    assert is_biz_id_in_new_env_scope(10, start_biz_id="10") is False
    assert is_biz_id_in_new_env_scope(5, start_biz_id=10, biz_white_list=[5]) is True
    assert is_biz_id_in_new_env_scope(12, start_biz_id=10, biz_black_list=[12]) is False
    assert is_biz_id_in_new_env_scope(12, start_biz_id=10, biz_black_list=[12], biz_white_list=[12]) is False
    assert is_biz_id_in_new_env_scope(0, start_biz_id=10, biz_black_list=[0]) is True
    assert is_biz_id_in_new_env_scope("abc", start_biz_id=10) is False
    assert is_biz_id_in_new_env_scope(10, start_biz_id="") is True
    assert is_biz_id_in_new_env_scope(10, start_biz_id="invalid") is True


def test_refresh_all_log_config_skips_biz_black_list(settings, mocker):
    settings.NEW_ENV_START_BIZ_ID = "10"
    settings.NEW_ENV_BIZ_BLACK_LIST = [12, 0]
    settings.NEW_ENV_BIZ_WHITE_LIST = [5]

    mocker.patch("metadata.task.custom_report.datetime.datetime", FixedDatetime)
    mocker.patch(
        "metadata.task.custom_report.models.LogGroup.objects.filter",
        return_value=[
            SimpleNamespace(log_group_id=0, bk_biz_id=0),
            SimpleNamespace(log_group_id=1, bk_biz_id=12),
            SimpleNamespace(log_group_id=2, bk_biz_id=10),
            SimpleNamespace(log_group_id=3, bk_biz_id=5),
            SimpleNamespace(log_group_id=4, bk_biz_id=11),
        ],
    )
    refresh_custom_log_config = mocker.patch("metadata.task.custom_report.refresh_custom_log_config")

    custom_report.refresh_all_log_config.__wrapped__()

    refresh_custom_log_config.assert_called_once_with(0)


def test_refresh_all_log_config_to_k8s_filters_by_new_env_scope(settings, mocker):
    settings.NEW_ENV_START_BIZ_ID = "10"
    settings.NEW_ENV_BIZ_BLACK_LIST = [12, 0]
    settings.NEW_ENV_BIZ_WHITE_LIST = [5]

    log_groups = [
        SimpleNamespace(log_group_id=0, bk_biz_id=0),
        SimpleNamespace(log_group_id=1, bk_biz_id=12),
        SimpleNamespace(log_group_id=2, bk_biz_id=10),
        SimpleNamespace(log_group_id=3, bk_biz_id=5),
        SimpleNamespace(log_group_id=4, bk_biz_id=11),
    ]
    mocker.patch("metadata.task.custom_report.models.LogGroup.objects.filter", return_value=log_groups)
    refresh_k8s = mocker.patch("metadata.task.custom_report.models.LogSubscriptionConfig.refresh_k8s")

    custom_report.refresh_all_log_config_to_k8s.__wrapped__()

    refresh_k8s.assert_called_once_with([log_groups[0], log_groups[3], log_groups[4]])


def test_refresh_custom_report_2_node_man_full_refresh_passes_filter_options(settings, mocker):
    settings.NEW_ENV_BIZ_BLACK_LIST = [12, 0]

    mocker.patch(
        "metadata.task.custom_report.api.node_man.plugin_info",
        return_value=[{"version": "0.99.0", "is_ready": True}],
    )
    mocker.patch("metadata.task.custom_report.api.bk_login.list_tenant", return_value=[{"id": "system"}])
    refresh_collector_custom_conf = mocker.patch(
        "metadata.task.custom_report.models.CustomReportSubscription.refresh_collector_custom_conf"
    )

    custom_report.refresh_custom_report_2_node_man()

    refresh_collector_custom_conf.assert_called_once_with(
        bk_tenant_id="system",
        bk_biz_id=None,
        node_man_biz_black_list=[12, 0],
        filter_k8s_new_env_scope=True,
    )


def test_refresh_custom_report_2_node_man_single_biz_keeps_explicit_scope(mocker):
    mocker.patch(
        "metadata.task.custom_report.api.node_man.plugin_info",
        return_value=[{"version": "0.99.0", "is_ready": True}],
    )
    mocker.patch("metadata.task.custom_report.bk_biz_id_to_bk_tenant_id", return_value="system")
    refresh_collector_custom_conf = mocker.patch(
        "metadata.task.custom_report.models.CustomReportSubscription.refresh_collector_custom_conf"
    )

    custom_report.refresh_custom_report_2_node_man(bk_biz_id=12)

    refresh_collector_custom_conf.assert_called_once_with(bk_tenant_id="system", bk_biz_id=12)
