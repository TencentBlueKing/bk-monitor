"""DataSource 模型的聚焦回归用例。"""

import pytest
from django.conf import settings

from constants.common import DEFAULT_TENANT_ID
from metadata import models
from metadata.models.constants import DataIdCreatedFromSystem

pytestmark = pytest.mark.django_db(databases="__all__")


@pytest.fixture
def v4_data_source_records():
    """创建 v4 数据源所需的最小标签与 Kafka 集群。"""
    models.Label.objects.update_or_create(
        label_id="test_v4_source",
        defaults={"label_name": "V4 test source", "label_type": models.Label.LABEL_TYPE_SOURCE},
    )
    models.Label.objects.update_or_create(
        label_id="test_v4_type",
        defaults={"label_name": "V4 test type", "label_type": models.Label.LABEL_TYPE_TYPE},
    )
    models.ClusterInfo.objects.filter(
        bk_tenant_id=DEFAULT_TENANT_ID,
        cluster_type=models.ClusterInfo.TYPE_KAFKA,
        is_default_cluster=True,
    ).update(is_default_cluster=False)
    models.ClusterInfo.objects.update_or_create(
        cluster_id=990123,
        defaults={
            "bk_tenant_id": DEFAULT_TENANT_ID,
            "cluster_name": "test_v4_kafka_cluster",
            "cluster_type": models.ClusterInfo.TYPE_KAFKA,
            "domain_name": "test-v4-kafka.service",
            "port": 9092,
            "is_default_cluster": True,
            "registered_to_bkbase": True,
        },
    )


@pytest.mark.parametrize(
    ("etl_config", "data_name", "expected_namespace", "expected_event_type", "expected_bkbase_data_name"),
    [
        (
            "bk_standard_v2_time_series",
            "v4_metric_data_source",
            "bkmonitor",
            "metric",
            "bkm_v4_metric_data_source",
        ),
        ("bk_standard_v2_event", "v4_log_data_source", "bklog", "log", "bkm_v4_log_data_source"),
        (
            "bk_multi_tenancy_basereport",
            "v4_base_data_source",
            "bkmonitor",
            "metric",
            "v4_base_data_source",
        ),
    ],
)
def test_create_v4_data_source_applies_from_gse_then_registers_to_bkbase(
    mocker,
    v4_data_source_records,
    etl_config,
    data_name,
    expected_namespace,
    expected_event_type,
    expected_bkbase_data_name,
):
    """V4 数据源应先由 GSE 分配 Data ID，再作为预定义数据源注册到 BKBase。"""
    mocker.patch.object(settings, "IS_ASSIGN_DATAID_BY_GSE", True)
    mocker.patch.object(settings, "ENABLE_V2_VM_DATA_LINK", True)

    operations = []
    bk_data_id = 1900999
    apply_from_gse = mocker.patch.object(
        models.DataSource,
        "apply_for_data_id_from_gse",
        side_effect=lambda *args, **kwargs: operations.append("gse") or bk_data_id,
    )
    apply_from_bkdata = mocker.patch.object(models.DataSource, "apply_for_data_id_from_bkdata")
    bkbase_biz = mocker.Mock(label_biz_id=0, data_biz_id=0)
    mocker.patch("metadata.models.data_source.get_tenant_datalink_biz_id", return_value=bkbase_biz)
    mocker.patch("metadata.models.data_link.data_link_configs.get_tenant_datalink_biz_id", return_value=bkbase_biz)
    apply_data_link = mocker.patch(
        "metadata.models.data_source.api.bkdata.apply_data_link",
        side_effect=lambda *args, **kwargs: operations.append("bkbase"),
    )

    data_source = models.DataSource.create_data_source(
        data_name=data_name,
        etl_config=etl_config,
        operator="operator",
        type_label="test_v4_type",
        source_label="test_v4_source",
        is_refresh_config=False,
    )

    assert operations == ["gse", "bkbase"]
    apply_from_gse.assert_called_once_with(DEFAULT_TENANT_ID, "operator")
    apply_from_bkdata.assert_not_called()
    apply_data_link.assert_called_once()
    apply_config = apply_data_link.call_args.kwargs["config"][0]
    assert apply_config["metadata"]["name"] == expected_bkbase_data_name
    assert apply_config["metadata"]["namespace"] == expected_namespace
    assert apply_config["spec"]["predefined"]["dataId"] == bk_data_id
    assert apply_config["spec"]["eventType"] == expected_event_type
    assert data_source.bk_data_id == bk_data_id
    assert data_source.created_from == DataIdCreatedFromSystem.BKDATA.value
