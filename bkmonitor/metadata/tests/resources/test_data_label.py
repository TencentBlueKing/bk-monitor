import pytest
from django.conf import settings

from metadata import models
from metadata.resources import (
    CreateEventGroupResource,
    CreateResultTableResource,
    CreateTimeSeriesGroupResource,
    GetEventGroupResource,
    GetTimeSeriesGroupResource,
    IsDataLabelExistResource,
    ListResultTableResource,
    ModifyEventGroupResource,
    ModifyResultTableResource,
    ModifyTimeSeriesGroupResource,
    QueryEventGroupResource,
    QueryResultTableSourceResource,
    QueryTimeSeriesGroupResource,
)
from metadata.tests.common_utils import consul_client

pytestmark = pytest.mark.django_db

DEFAULT_DATA_ID = 3000001
DEFAULT_DATA_ID_ONE = 3000002
DEFAULT_NAME = "test_ES_cluster"
DEFAULT_BIZ_ID = "2"
OPERATOR = "system"
DEFAULT_LABEL = "host_process"
DEFAULT_DATA_LABEL = "data_label_1"
DEFAULT_DATA_LABEL_ONE = "data_label_modify"
DEFAULT_DATA_LABEL_NOT_EXIST = "data_label_not_exist"
DEFAULT_CLUSTER_ID = 10000
DEFAULT_RT_ID = "table_0"
DEFAULT_RT_ID_ONE = "table_1"


@pytest.fixture
def create_and_delete_record(mocker):
    mocker.patch("metadata.models.data_source.DataSource.refresh_consul_config", return_value=True)
    mocker.patch("metadata.models.result_table.ResultTable.create_storage", return_value=True)
    mocker.patch("celery.app.task.Task.delay", return_value=True)
    kafka_topic_info = models.KafkaTopicInfo.objects.create(
        bk_data_id=DEFAULT_DATA_ID,
        topic=DEFAULT_NAME,
        partition=1,
    )

    models.ClusterInfo.objects.create(
        cluster_id=DEFAULT_CLUSTER_ID,
        cluster_name="test_ES_cluster",
        cluster_type=models.ClusterInfo.TYPE_ES,
        domain_name="test.domain.mq",
        port=9090,
        description="",
        is_default_cluster=True,
        version="5.x",
    )

    models.DataSource.objects.create(
        bk_data_id=DEFAULT_DATA_ID,
        data_name=DEFAULT_NAME,
        mq_cluster_id=DEFAULT_CLUSTER_ID,
        mq_config_id=kafka_topic_info.id,
        etl_config="test",
        is_custom_source=False,
    )
    yield
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
    kafka_topic_info.delete()
    models.ClusterInfo.objects.filter(cluster_id=DEFAULT_CLUSTER_ID).delete()
    models.DataSource.objects.filter(bk_data_id=DEFAULT_DATA_ID).delete()
    models.DataSourceResultTable.objects.filter(bk_data_id=DEFAULT_DATA_ID).delete()
    models.ResultTable.objects.filter(table_id__contains=DEFAULT_DATA_ID).delete()
    models.ResultTableOption.objects.filter(table_id__contains=DEFAULT_DATA_ID).delete()
    models.ResultTableField.objects.filter(table_id__contains=DEFAULT_DATA_ID).delete()
    models.ResultTableFieldOption.objects.filter(table_id__contains=DEFAULT_DATA_ID).delete()
    models.DataSourceOption.objects.filter(bk_data_id=DEFAULT_DATA_ID).delete()
    models.EventGroup.objects.all().delete()
    models.TimeSeriesGroup.objects.all().delete()


def test_create_and_modify_result_table_resource(create_and_delete_record):
    table_id = f"test_table_id_{DEFAULT_DATA_ID}"

    assert not models.ResultTable.objects.filter(table_id=table_id, data_label=DEFAULT_DATA_LABEL).exists()

    # 创建结果表
    params = dict(
        bk_data_id=DEFAULT_DATA_ID,
        table_id=table_id,
        table_name_zh=table_id,
        is_custom_table=True,
        schema_type="fix",
        default_storage=models.ClusterInfo.TYPE_INFLUXDB,
        operator=OPERATOR,
        data_label=DEFAULT_DATA_LABEL,
    )
    result_table = CreateResultTableResource().request(**params)
    assert models.ResultTable.objects.filter(table_id=table_id, data_label=DEFAULT_DATA_LABEL).exists()
    # 修改结果表数据标签
    assert ModifyResultTableResource().request(
        operator=OPERATOR, table_id=result_table["table_id"], data_label=DEFAULT_DATA_LABEL_ONE
    )
    assert not models.ResultTable.objects.filter(table_id=table_id, data_label=DEFAULT_DATA_LABEL).exists()
    assert models.ResultTable.objects.filter(table_id=table_id, data_label=DEFAULT_DATA_LABEL_ONE).exists()

    rt = QueryResultTableSourceResource().request(table_id=table_id)
    assert rt.get("data_label") == DEFAULT_DATA_LABEL_ONE


def test_create_and_modify_event_group_resource(create_and_delete_record):
    table_id = "{}_bkmonitor_event_{}".format(DEFAULT_BIZ_ID, DEFAULT_DATA_ID)

    assert not models.ResultTable.objects.filter(table_id=table_id, data_label=DEFAULT_DATA_LABEL).exists()

    # 创建自定义上报事件
    params = dict(
        bk_data_id=DEFAULT_DATA_ID,
        bk_biz_id=DEFAULT_BIZ_ID,
        event_group_name=DEFAULT_NAME,
        label=DEFAULT_LABEL,
        operator=OPERATOR,
        data_label=DEFAULT_DATA_LABEL,
    )
    event_group = CreateEventGroupResource().request(**params)
    assert models.ResultTable.objects.filter(table_id=table_id, data_label=DEFAULT_DATA_LABEL).exists()
    # 修改自定义上报事件数据标签
    assert ModifyEventGroupResource().request(
        operator=OPERATOR, event_group_id=event_group["event_group_id"], data_label=DEFAULT_DATA_LABEL_ONE
    )
    assert not models.ResultTable.objects.filter(table_id=table_id, data_label=DEFAULT_DATA_LABEL).exists()
    assert models.ResultTable.objects.filter(table_id=table_id, data_label=DEFAULT_DATA_LABEL_ONE).exists()

    rt = QueryResultTableSourceResource().request(table_id=table_id)
    assert rt.get("data_label") == DEFAULT_DATA_LABEL_ONE

    eg = QueryEventGroupResource().request(event_group_name=event_group["event_group_name"])
    assert eg[0].get("data_label") == DEFAULT_DATA_LABEL_ONE

    eg = GetEventGroupResource().request(event_group_id=event_group["event_group_id"], with_result_table_info=False)
    assert eg.get("data_label") == DEFAULT_DATA_LABEL_ONE


def test_create_and_modify_ts_group_resource(create_and_delete_record):
    setattr(settings, "USE_TZ", False)
    table_id = "{}_bkmonitor_time_series_{}.{}".format(
        DEFAULT_BIZ_ID, DEFAULT_DATA_ID, models.TimeSeriesGroup.DEFAULT_MEASUREMENT
    )

    assert not models.ResultTable.objects.filter(table_id=table_id, data_label=DEFAULT_DATA_LABEL).exists()

    # 创建自定义上报指标
    params = dict(
        bk_data_id=DEFAULT_DATA_ID,
        bk_biz_id=DEFAULT_BIZ_ID,
        time_series_group_name=DEFAULT_NAME,
        label=DEFAULT_LABEL,
        operator=OPERATOR,
        data_label=DEFAULT_DATA_LABEL,
    )
    ts_group = CreateTimeSeriesGroupResource().request(**params)
    assert models.ResultTable.objects.filter(table_id=table_id, data_label=DEFAULT_DATA_LABEL).exists()
    # 修改自定义上报指标数据标签
    assert ModifyTimeSeriesGroupResource().request(
        operator=OPERATOR, time_series_group_id=ts_group["time_series_group_id"], data_label=DEFAULT_DATA_LABEL_ONE
    )
    assert not models.ResultTable.objects.filter(table_id=table_id, data_label=DEFAULT_DATA_LABEL).exists()
    assert models.ResultTable.objects.filter(table_id=table_id, data_label=DEFAULT_DATA_LABEL_ONE).exists()

    rt = QueryResultTableSourceResource().request(table_id=table_id)
    assert rt.get("data_label") == DEFAULT_DATA_LABEL_ONE

    tg = QueryTimeSeriesGroupResource().request(time_series_group_name=ts_group["time_series_group_name"])
    assert tg[0].get("data_label") == DEFAULT_DATA_LABEL_ONE

    tg = GetTimeSeriesGroupResource().request(
        time_series_group_id=ts_group["time_series_group_id"], with_result_table_info=False
    )
    assert tg[0].get("data_label") == DEFAULT_DATA_LABEL_ONE


@pytest.fixture
def create_and_delete_result_table(mocker):
    models.ResultTable.objects.create(
        table_id=DEFAULT_RT_ID, bk_biz_id=DEFAULT_BIZ_ID, is_custom_table=True, data_label=DEFAULT_DATA_LABEL
    )
    models.ResultTable.objects.create(
        table_id=DEFAULT_RT_ID_ONE, bk_biz_id=DEFAULT_BIZ_ID, is_custom_table=True, data_label=DEFAULT_DATA_LABEL_ONE
    )
    models.DataSourceResultTable.objects.create(table_id=DEFAULT_RT_ID, bk_data_id=DEFAULT_DATA_ID)
    models.DataSourceResultTable.objects.create(table_id=DEFAULT_RT_ID_ONE, bk_data_id=DEFAULT_DATA_ID_ONE)

    yield
    models.ResultTable.objects.filter(table_id__in=[DEFAULT_RT_ID, DEFAULT_RT_ID_ONE]).delete()
    models.DataSourceResultTable.objects.filter(table_id__in=[DEFAULT_RT_ID, DEFAULT_RT_ID_ONE]).delete()


def test_is_data_label_exist_resource(create_and_delete_result_table):
    # 数据标签全局不存在
    assert not IsDataLabelExistResource().request(data_label=DEFAULT_DATA_LABEL_NOT_EXIST)
    # 数据标签全局存在
    assert IsDataLabelExistResource().request(data_label=DEFAULT_DATA_LABEL)
    assert IsDataLabelExistResource().request(data_label=DEFAULT_DATA_LABEL_ONE)
    # 数据标签排除指定数据源不存在
    assert not IsDataLabelExistResource().request(data_label=DEFAULT_DATA_LABEL, bk_data_id=DEFAULT_DATA_ID)
    # 数据标签排除指定数据源存在
    assert IsDataLabelExistResource().request(data_label=DEFAULT_DATA_LABEL, bk_data_id=DEFAULT_DATA_ID_ONE)
    assert IsDataLabelExistResource().request(data_label=DEFAULT_DATA_LABEL_ONE, bk_data_id=DEFAULT_DATA_ID)


def test_query_rt_data_label_field():
    datas = ListResultTableResource().request()
    for data in datas:
        assert "data_label" in data.keys()
