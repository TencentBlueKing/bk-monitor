"""自定义事件建索引失败时保留元数据，并由周期任务补建。"""

from concurrent.futures import Future

import pytest
from django.db import IntegrityError, transaction
from elasticsearch import RequestError
from tenacity import RetryError

from metadata import config, models
from metadata.task.tasks import _manage_es_storage

pytestmark = pytest.mark.django_db(databases="__all__")

TENANT_ID = "system"
DATA_ID = 990101


@pytest.fixture
def event_records(mocker, settings):
    settings.ENABLE_MULTI_TENANT_MODE = True
    settings.ENABLE_INFLUXDB_STORAGE = False
    cluster = models.ClusterInfo.objects.create(
        bk_tenant_id=TENANT_ID,
        cluster_name="event_index_failure_es",
        cluster_type=models.ClusterInfo.TYPE_ES,
        domain_name="127.0.0.1",
        port=9200,
        is_default_cluster=True,
    )
    models.Label.objects.get_or_create(
        label_id="other_rt",
        label_type=models.Label.LABEL_TYPE_RESULT_TABLE,
        defaults={"label_name": "其他"},
    )
    data_source = models.DataSource.objects.create(
        bk_tenant_id=TENANT_ID,
        bk_data_id=DATA_ID,
        data_name="event_index_failure",
        etl_config="bk_standard_v2_event",
        mq_cluster_id=0,
        mq_config_id=0,
        is_custom_source=True,
    )
    mocker.patch("metadata.models.space.space_table_id_redis.SpaceTableIDRedis.push_table_id_detail")
    mocker.patch.object(models.ResultTable, "refresh_etl_config")
    mocker.patch("metadata.task.tasks.refresh_custom_report_config.delay")
    return cluster, data_source


@pytest.fixture
def index_failure(mocker):
    future = Future()
    future.set_exception(RequestError(400, "validation_exception", "maximum normal shards open"))
    error = RetryError(future)
    return mocker.patch.object(models.ESStorage, "create_index_and_aliases", side_effect=error)


def assert_event_records(bk_data_id):
    group = models.EventGroup.objects.get(bk_tenant_id=TENANT_ID, bk_data_id=bk_data_id)
    assert models.DataSource.objects.filter(bk_tenant_id=TENANT_ID, bk_data_id=bk_data_id).exists()
    assert models.DataSourceResultTable.objects.filter(
        bk_tenant_id=TENANT_ID, bk_data_id=bk_data_id, table_id=group.table_id
    ).exists()
    assert models.ResultTable.objects.filter(bk_tenant_id=TENANT_ID, table_id=group.table_id).exists()
    assert models.StorageClusterRecord.objects.filter(
        bk_tenant_id=TENANT_ID, table_id=group.table_id, is_current=True
    ).exists()
    storage = models.ESStorage.objects.get(bk_tenant_id=TENANT_ID, table_id=group.table_id)
    assert storage.need_create_index is True
    assert models.DataSourceOption.objects.filter(
        bk_tenant_id=TENANT_ID, bk_data_id=bk_data_id, name="flat_batch_key"
    ).exists()
    return storage


def test_event_creation_survives_index_failure_and_recovers(event_records, index_failure, mocker):
    apply_datalink = mocker.patch.object(models.ResultTable, "apply_datalink")

    models.EventGroup.create_event_group(
        bk_tenant_id=TENANT_ID,
        bk_data_id=DATA_ID,
        bk_biz_id=2,
        event_group_name="event_index_failure",
        label="other_rt",
        operator="admin",
        event_info_list=[{"event_name": "test_event", "dimension_list": ["namespace"]}],
    )

    index_failure.assert_called_once()
    apply_datalink.assert_called_once()
    storage = assert_event_records(DATA_ID)
    group = models.EventGroup.objects.get(bk_data_id=DATA_ID)
    assert models.Event.objects.filter(event_group_id=group.event_group_id, event_name="test_event").exists()

    # ES 恢复后，周期任务使用保留下来的存储记录初始化索引，无需重新申请 Data ID。
    index_failure.side_effect = None
    index_failure.return_value = True
    mocker.patch.object(storage, "index_exist", return_value=False)
    for method in ("create_snapshot", "clean_index_v2", "clean_history_es_index", "clean_snapshot", "reallocate_index"):
        mocker.patch.object(storage, method)
    mocker.patch("metadata.task.tasks.metrics.report_all")

    _manage_es_storage(storage)

    assert index_failure.call_count == 2
    assert models.EventGroup.objects.filter(bk_data_id=DATA_ID).count() == 1
    assert_event_records(DATA_ID)


def test_bcs_registration_survives_event_index_failure(event_records, index_failure, mocker, settings):
    cluster, _ = event_records
    settings.BCS_CUSTOM_EVENT_STORAGE_CLUSTER_ID = cluster.cluster_id
    mocker.patch.object(models.ResultTable, "apply_datalink")

    def create_data_source(**kwargs):
        return models.DataSource.objects.create(
            bk_tenant_id=kwargs["bk_tenant_id"],
            data_name=kwargs["data_name"],
            etl_config=kwargs["etl_config"],
            mq_cluster_id=0,
            mq_config_id=0,
            is_custom_source=True,
        )

    allocate_data_id = mocker.patch.object(models.DataSource, "create_data_source", side_effect=create_data_source)
    register_kwargs = {
        "bk_tenant_id": TENANT_ID,
        "bk_biz_id": 2,
        "cluster_id": "BCS-K8S-index-failure",
        "project_id": "test_project",
        "creator": "admin",
    }

    bcs_cluster = models.BCSClusterInfo.register_cluster(**register_kwargs)

    bcs_cluster.refresh_from_db()
    assert bcs_cluster.K8sMetricDataID > 0
    assert bcs_cluster.CustomMetricDataID > 0
    assert bcs_cluster.K8sEventDataID > 0
    assert_event_records(bcs_cluster.K8sEventDataID)
    index_failure.assert_called_once()
    assert allocate_data_id.call_count == len(models.BCSClusterInfo.DATASOURCE_REGISTER_INFO)

    with pytest.raises(ValueError, match="集群已经接入"):
        models.BCSClusterInfo.register_cluster(**register_kwargs)
    assert allocate_data_id.call_count == len(models.BCSClusterInfo.DATASOURCE_REGISTER_INFO)


def test_other_es_storage_still_rolls_back_on_index_failure(event_records, index_failure):
    cluster, _ = event_records
    table_id = "2_bklog.index_failure"

    with pytest.raises(RetryError):
        with transaction.atomic(using=config.DATABASE_CONNECTION_NAME):
            models.ESStorage.create_table(table_id=table_id, bk_tenant_id=TENANT_ID, cluster_id=cluster.cluster_id)

    assert not models.ESStorage.objects.filter(bk_tenant_id=TENANT_ID, table_id=table_id).exists()
    assert not models.StorageClusterRecord.objects.filter(bk_tenant_id=TENANT_ID, table_id=table_id).exists()


def test_event_storage_validation_errors_still_fail(event_records, mocker):
    mocker.patch.object(models.ResultTable, "apply_datalink")

    with pytest.raises(ValueError, match="存储集群配置有误"):
        with transaction.atomic(using=config.DATABASE_CONNECTION_NAME):
            models.EventGroup.create_custom_group(
                bk_tenant_id=TENANT_ID,
                bk_data_id=DATA_ID,
                bk_biz_id=2,
                custom_group_name="invalid_event_storage",
                label="other_rt",
                operator="admin",
                default_storage_config={"cluster_id": -1},
            )

    assert not models.EventGroup.objects.filter(bk_data_id=DATA_ID).exists()
    assert not models.DataSourceResultTable.objects.filter(bk_data_id=DATA_ID).exists()


def test_event_database_errors_still_roll_back(event_records, mocker):
    mocker.patch.object(models.ESStorage.objects, "create", side_effect=IntegrityError("storage insert failed"))

    with pytest.raises(IntegrityError, match="storage insert failed"):
        models.EventGroup.create_event_group(
            bk_tenant_id=TENANT_ID,
            bk_data_id=DATA_ID,
            bk_biz_id=2,
            event_group_name="event_database_failure",
            label="other_rt",
            operator="admin",
        )

    assert not models.EventGroup.objects.filter(bk_data_id=DATA_ID).exists()
    assert not models.DataSourceResultTable.objects.filter(bk_data_id=DATA_ID).exists()
