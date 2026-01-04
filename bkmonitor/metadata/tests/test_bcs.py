"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import datetime
import logging

import elasticsearch5
import pytest
from django.conf import settings
from kubernetes.dynamic import client as dynamic_client
from unittest.mock import patch, MagicMock

from api.kubernetes.default import FetchK8sClusterListResource
from bkm_space.api import SpaceApi
from core.drf_resource import api
from metadata import models
from metadata.models import (
    InfluxDBClusterInfo,
    InfluxDBStorage,
    Space,
    BkBaseResultTable,
)
from metadata.models.influxdb_cluster import InfluxDBProxyStorage
from metadata.models.bcs.resource import BCSClusterInfo
from metadata.models.storage import ClusterInfo, StorageClusterRecord, ESStorage
from metadata.task.bcs import discover_bcs_clusters, update_bcs_cluster_cloud_id_config
from metadata.models.result_table import ResultTable
from metadata.tests.common_utils import consul_client
from constants.common import DEFAULT_TENANT_ID
from metadata.utils import consul_tools
from .conftest import MockHashConsul, MockDynamicClient
from metadata.models.data_link.data_link import DataLink
from bkmonitor.utils import tenant

logger = logging.getLogger("metadata")

pytestmark = pytest.mark.django_db(databases="__all__")
IS_CONSUL_MOCK = False
es_index = {}


class TestOperateConsulConfig:
    data_name = "2_system.cpu"
    etl_config = "basereport"
    operator = "operator"

    result_table_label = "service_module"
    data_source_label = "bk_monitor"
    data_type_label = "bk_event"

    transfer_cluster_name = "test_transfer"

    influxdb_cluster_name = "my_cluster"
    influxdb_host_name = "host1"
    influxdb_username = "username"
    influxdb_password = "password"

    create_index_mock = None

    @pytest.fixture
    def create_base_cluster(self):
        clusters = list(models.ClusterInfo.objects.all())
        models.ClusterInfo.objects.all().delete()
        models.ClusterInfo.objects.create(
            cluster_name="test_ES_cluster",
            cluster_type=models.ClusterInfo.TYPE_ES,
            domain_name="test.domain.mq",
            port=9090,
            description="",
            is_default_cluster=True,
            version="5.x",
        )
        models.ClusterInfo.objects.create(
            cluster_name="test_KAFKA_cluster",
            cluster_type=models.ClusterInfo.TYPE_KAFKA,
            domain_name="test.domain.mq2",
            port=1234,
            description="",
            is_default_cluster=True,
            version="5.x",
        )
        cluster = models.ClusterInfo.objects.create(
            cluster_name="test_INFLUX_cluster",
            cluster_type=models.ClusterInfo.TYPE_INFLUXDB,
            domain_name="test.domain.mq2",
            port=80,
            is_default_cluster=False,
        )

        models.InfluxDBProxyStorage.objects.create(
            instance_cluster_name="test_cluster", is_default=True, proxy_cluster_id=cluster.cluster_id
        )

        # 提前准备好proxy对应的信息
        models.InfluxDBHostInfo.create_host_info(
            host_name=self.influxdb_host_name,
            domain_name="domain.com",
            port=123,
            username=self.influxdb_username,
            password=self.influxdb_password,
        )
        models.InfluxDBClusterInfo.objects.update_or_create(
            host_name=self.influxdb_host_name, cluster_name=self.influxdb_cluster_name
        )
        models.InfluxDBClusterInfo.objects.update_or_create(host_name=self.influxdb_host_name, cluster_name="default")

        yield
        models.InfluxDBHostInfo.objects.filter(host_name=self.influxdb_host_name).delete()
        models.ClusterInfo.objects.filter(
            cluster_name__in=["test_ES_cluster", "test_KAFKA_cluster", "test_INFLUX_cluster"]
        ).delete()
        models.InfluxDBProxyStorage.objects.all().delete()
        models.InfluxDBClusterInfo.objects.all().delete()
        models.BCSClusterInfo.objects.all().delete()
        models.ESStorage.objects.all().delete()
        models.DataSource.objects.filter(data_name__contains="test_cluster_id").delete()
        models.ClusterInfo.objects.bulk_create(clusters)
        models.DataSourceResultTable.objects.filter(bk_data_id__gte=1500000).delete()
        models.KafkaTopicInfo.objects.filter(bk_data_id__gte=1500000).delete()
        models.DataSourceOption.objects.filter(bk_data_id__gte=1500000).delete()
        models.TimeSeriesGroup.objects.filter(bk_data_id__gte=1500000).delete()
        models.ResultTable.objects.filter(table_name_zh__contains="test_cluster_id").delete()
        models.ResultTableOption.objects.all().delete()
        models.InfluxDBStorage.objects.filter(proxy_cluster_name="test_cluster").delete()
        models.EventGroup.objects.filter(event_group_name__contains="test_cluster_id").delete()
        models.ResultTableField.objects.all().delete()
        models.ResultTableFieldOption.objects.all().delete()

    def test_redirect_consul_config(self, mocker, create_base_cluster):
        # ===================== mock start ===========================
        # mock gse 请求接口依赖
        base_channel_id = 1500005

        def gen_channel_id(*args, **kwargs):
            nonlocal base_channel_id
            base_channel_id += 1
            return {"channel_id": base_channel_id}

        mocker.patch("core.drf_resource.api.gse.add_route", side_effect=gen_channel_id)

        mocker.patch("metadata.models.DataSource.create_mq", return_value=True)
        mocker.patch("metadata.models.DataSource.refresh_gse_config", return_value=True)
        mocker.patch("metadata.models.InfluxDBStorage.create_database", return_value=True)
        mocker.patch("metadata.models.InfluxDBStorage.create_rp", return_value=True)
        mocker.patch("metadata.models.KafkaStorage.ensure_topic", return_value=True)
        mocker.patch("metadata.task.tasks.refresh_custom_report_config.delay", return_value=True)
        mocker.patch("metadata.models.DataSource.refresh_outer_config", return_value=True)
        mocker.patch("metadata.models.storage.InfluxDBStorage.refresh_consul_cluster_config", return_value=True)
        mocker.patch("metadata.models.data_source.DataSource.refresh_consul_config", return_value=True)
        mocker.patch("metadata.models.data_source.DataSource.delete_consul_config", return_value=True)
        mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)

        def es_exists(index, *args, **kwargs):
            return index in es_index

        def add_es_index(index, *args, **kwargs):
            es_index[index] = True
            return True

        self.put_alias_mock = mocker.patch("elasticsearch5.client.indices.IndicesClient.put_alias", return_value=True)

        self.create_index_mock = mocker.patch(
            "elasticsearch5.client.indices.IndicesClient.create",
            side_effect=add_es_index,
        )

        mocker.patch(
            "elasticsearch5.client.indices.IndicesClient.exists",
            side_effect=es_exists,
        )

        def es_get_index(index_name, *args, **kwargs):
            # 先找到原本的table_id
            table_id = index_name[:-1].replace(".", "_")

            # 返回两个index -- 一个是过期（三年前），一个未过期（一天后）
            out_date = (datetime.datetime.utcnow() - datetime.timedelta(days=365 * 3)).strftime("%Y%m%d%H")
            new_date = (datetime.datetime.utcnow() + datetime.timedelta(days=1)).strftime("%Y%m%d%H")

            return {f"{table_id}_{out_date}_0": "", f"{table_id}_{new_date}_0": ""}

        mocker.patch("elasticsearch5.client.indices.IndicesClient.get", side_effect=es_get_index)

        self.delete_index_mock = mocker.patch(
            "elasticsearch5.client.indices.IndicesClient.delete",
        )

        self.delete_alias_mock = mocker.patch(
            "elasticsearch5.client.indices.IndicesClient.delete_alias",
        )

        # def empty_stat(*args, **kwargs):
        empty_stat = [
            {"indices": {"v2_2_bkmonitor_event_1500008_20220223_0": {"primaries": {"store": {"size_in_bytes": 566}}}}},
            {"indices": {"v2_2_bkmonitor_event_1500009_20220223_0": {"primaries": {"store": {"size_in_bytes": 566}}}}},
        ]

        stat_mock = mocker.patch("elasticsearch5.client.indices.IndicesClient.stats", side_effect=empty_stat)  # noqa

        count_mock = mocker.patch(  # noqa
            "elasticsearch5.client.Elasticsearch.count", side_effect=elasticsearch5.NotFoundError()
        )

        mocker.patch("elasticsearch5.client.indices.IndicesClient.get_alias", side_effect=elasticsearch5.NotFoundError)

        mocker.patch("elasticsearch5.client.indices.IndicesClient.update_aliases", return_value={"acknowledged": True})

        mocker.patch("metadata.models.ESStorage.is_index_enable", return_value=True)

        mocker.patch("celery.app.task.Task.delay", return_value=True)

        settings.BCS_API_GATEWAY_TOKEN = "test_token"

        settings.INFLUXDB_DEFAULT_PROXY_CLUSTER_NAME_FOR_K8S = "test_cluster"
        settings.DEFAULT_TRANSFER_CLUSTER_ID_FOR_K8S = self.transfer_cluster_name

        models.InfluxDBClusterInfo.objects.update_or_create(
            host_name=self.influxdb_host_name, cluster_name="test_cluster"
        )
        # ==================== mock end ===============================

        c = models.BCSClusterInfo.register_cluster(
            bk_biz_id=2,
            bk_tenant_id=DEFAULT_TENANT_ID,
            cluster_id="test_cluster_id",
            project_id="test_project",
            creator="system",
            domain_name="test.domain.name",
        )

        for data_id in [c.K8sMetricDataID, c.CustomMetricDataID]:
            rt_name = models.DataSourceResultTable.objects.get(bk_data_id=data_id).table_id
            rt = models.InfluxDBStorage.objects.get(table_id=rt_name)

            assert rt.proxy_cluster_name == "test_cluster"

            ds = models.DataSource.objects.get(bk_data_id=data_id)
            assert ds.transfer_cluster_id == self.transfer_cluster_name


def test_discover_bcs_clusters(
    mocker,
    monkeypatch,
    monkeypatch_cluster_management_fetch_clusters,
    monkeypatch_k8s_node_list_by_cluster,
    monkeypatch_cmdb_get_info_by_ip,
    add_bcs_cluster_info,
):
    """测试周期刷新bcs集群列表 ."""
    monkeypatch.setattr(settings, "BCS_CLUSTER_SOURCE", "cluster-manager")
    monkeypatch.setattr(settings, "BCS_API_GATEWAY_TOKEN", "token")
    monkeypatch.setattr(FetchK8sClusterListResource, "cache_type", None)

    # 测试状态标记为删除
    discover_bcs_clusters()
    cluster_info_model = BCSClusterInfo.objects.get(cluster_id="BCS-K8S-00000")
    assert cluster_info_model.status in [
        BCSClusterInfo.CLUSTER_STATUS_RUNNING,
        BCSClusterInfo.CLUSTER_RAW_STATUS_RUNNING,
    ]
    cluster_info_model = BCSClusterInfo.objects.get(cluster_id="BCS-K8S-00001")
    assert cluster_info_model.status in [
        BCSClusterInfo.CLUSTER_STATUS_DELETED,
        BCSClusterInfo.CLUSTER_RAW_STATUS_DELETED,
    ]

    # 测试状态恢复
    BCSClusterInfo.objects.filter(cluster_id="BCS-K8S-00000").update(status=BCSClusterInfo.CLUSTER_RAW_STATUS_DELETED)
    discover_bcs_clusters()
    cluster_info_model = BCSClusterInfo.objects.get(cluster_id="BCS-K8S-00000")
    assert cluster_info_model.status in [
        BCSClusterInfo.CLUSTER_STATUS_RUNNING,
        BCSClusterInfo.CLUSTER_RAW_STATUS_RUNNING,
    ]


BCS_CLUSTER_ID = "BCS-K8S-00000"
BK_TENANT_ID = "system"


@pytest.fixture
def mock_default_kwargs(monkeypatch):
    def change_kwargs(m, targe_obj, kwargs):
        default_kwargs = list(targe_obj.__defaults__)
        for i, v in kwargs.items():
            i = int(i)
            default_kwargs[i] = v

        default_kwargs = tuple(default_kwargs)
        m.setattr(targe_obj, "__defaults__", default_kwargs)

    with monkeypatch.context() as m:
        m.setattr(settings, "BCS_API_GATEWAY_HOST", "domain_name_1")
        m.setattr(settings, "BCS_API_GATEWAY_PORT", "8000")

        change_kwargs(m, BCSClusterInfo.register_cluster.__wrapped__, {0: "domain_name_1", 1: "8000"})
        change_kwargs(m, ResultTable.create_result_table.__wrapped__, {15: "2_business_alias"})

        yield


@pytest.fixture
def configure_celery():
    # 配置celery为同步执行
    from alarm_backends.service.scheduler.app import app

    app.conf.clear()
    app.conf.task_always_eager = True
    app.conf.task_eager_propagates = True

    yield


@pytest.fixture
def mock_settings(monkeypatch):
    monkeypatch.setattr(FetchK8sClusterListResource, "cache_type", None)
    monkeypatch.setattr(settings, "BCS_CLUSTER_SOURCE", "cluster-manager")
    monkeypatch.setattr(settings, "BCS_API_GATEWAY_TOKEN", "token")
    monkeypatch.setattr(settings, "ENABLE_MULTI_TENANT_MODE", False)
    # 启用influxdb存储
    monkeypatch.setattr(settings, "ENABLE_INFLUXDB_STORAGE", True)
    # 启用VM存储
    monkeypatch.setattr(settings, "ENABLE_V2_VM_DATA_LINK", True)
    # 禁用时区
    monkeypatch.setattr(settings, "USE_TZ", False)

    with patch.object(settings, "BCS_CUSTOM_EVENT_STORAGE_CLUSTER_ID", None, create=True):
        yield


@pytest.fixture
def mock_funcs(monkeypatch):
    def get_data_id(data_name, *args, **kwargs):
        if data_name == f"bcs_{BCS_CLUSTER_ID}_k8s_metric":
            return 100
        elif data_name == f"bcs_{BCS_CLUSTER_ID}_k8s_event":
            return 200
        elif data_name == f"bcs_{BCS_CLUSTER_ID}_custom_metric":
            return 300
        raise ValueError("获取数据源失败")

    with (
        patch("bkmonitor.utils.tenant.get_tenant_datalink_biz_id") as mock_get_tenant_datalink_biz_id,
        patch(
            "metadata.models.data_source.DataSource.apply_for_data_id_from_bkdata"
        ) as mock_apply_for_data_id_from_bkdata,
        patch("metadata.models.data_source.DataSource.apply_for_data_id_from_gse") as mock_apply_for_data_id_from_gse,
        patch("metadata.task.tasks.refresh_custom_report_config") as mock_refresh_custom_report_config,
    ):
        # mock 获取业务ID
        mock_get_tenant_datalink_biz_id.return_value = 2
        # mock 获取数据源
        mock_apply_for_data_id_from_gse.side_effect = [400, 500, 600]

        mock_apply_for_data_id_from_bkdata.side_effect = get_data_id
        mock_refresh_custom_report_config.return_value = MagicMock()

        # mock 同步数据库
        monkeypatch.setattr(InfluxDBStorage, "sync_db", MagicMock())
        monkeypatch.setattr(consul_tools, "HashConsul", MockHashConsul)
        monkeypatch.setattr(consul_tools, "refresh_router_version", MagicMock())
        monkeypatch.setattr(DataLink, "apply_data_link_with_retry", MagicMock())
        monkeypatch.setattr(api.gse, "query_route", MagicMock(return_value={}))
        monkeypatch.setattr(api.gse, "update_route", MagicMock(return_value={}))
        monkeypatch.setattr(dynamic_client, "DynamicClient", MockDynamicClient)
        monkeypatch.setattr(
            api.bk_login,
            "list_tenant",
            MagicMock(return_value=[{"id": "system", "name": "Blueking", "status": "enabled"}]),
        )

        monkeypatch.setattr(tenant, "get_tenant_default_biz_id", MagicMock(return_value=settings.DEFAULT_BK_BIZ_ID))

        space = MagicMock()
        space.bk_tenant_id = BK_TENANT_ID
        monkeypatch.setattr(SpaceApi, "get_space_detail", MagicMock(return_value=space))
        monkeypatch.setattr(ESStorage, "create_es_index", MagicMock(return_value=True))

        yield


# 准备数据
@pytest.fixture()
def prepare_databases(monkeypatch):
    instance_cluster_name = "default"
    proxy_cluster_id = 1001

    InfluxDBProxyStorage.objects.create(
        proxy_cluster_id=proxy_cluster_id,
        instance_cluster_name=instance_cluster_name,
        service_name="influxdb_proxy",
        is_default=True,
    )

    InfluxDBClusterInfo.objects.create(
        host_name="test-influx-host-1", cluster_name=instance_cluster_name, host_readable=True
    )

    ClusterInfo.objects.get_or_create(
        bk_tenant_id=BK_TENANT_ID,
        cluster_type=ClusterInfo.TYPE_INFLUXDB,
        cluster_name="influxdb_cluster",
        domain_name="influxdb_cluster.example.com",
        port=8428,
        is_default_cluster=True,
        cluster_id=proxy_cluster_id,
        defaults={"description": "默认InfluxDB集群", "version": "1.0", "schema": "http"},
    )

    if not ClusterInfo.objects.filter(bk_tenant_id=BK_TENANT_ID, cluster_type=ClusterInfo.TYPE_VM).exists():
        ClusterInfo.objects.get_or_create(
            bk_tenant_id=BK_TENANT_ID,
            cluster_type=ClusterInfo.TYPE_VM,
            cluster_name="default_vm_cluster",
            domain_name="vm.example.com",
            port=8428,
            is_default_cluster=True,
            defaults={"description": "默认VM集群", "version": "1.0", "schema": "http"},
        )

    if not ClusterInfo.objects.filter(bk_tenant_id=BK_TENANT_ID, cluster_type=ClusterInfo.TYPE_ES).exists():
        ClusterInfo.objects.get_or_create(
            bk_tenant_id=BK_TENANT_ID,
            cluster_type=ClusterInfo.TYPE_ES,
            cluster_name="default_es_cluster",
            domain_name="es.example.com",
            port=9200,
            is_default_cluster=True,
            defaults={"description": "默认ES集群", "version": "7.10.0", "schema": "http"},
        )

    if not ClusterInfo.objects.filter(bk_tenant_id=BK_TENANT_ID, cluster_type=ClusterInfo.TYPE_INFLUXDB).exists():
        ClusterInfo.objects.get_or_create(
            bk_tenant_id=BK_TENANT_ID,
            cluster_type=ClusterInfo.TYPE_INFLUXDB,
            cluster_name="default_influxdb_cluster",
            domain_name="influxdb.example.com",
            port=8086,
            is_default_cluster=True,
            defaults={"description": "默认InfluxDB集群", "version": "1.8.0", "schema": "http"},
        )

    mq_cluster = ClusterInfo.objects.filter(bk_tenant_id=BK_TENANT_ID, cluster_type=ClusterInfo.TYPE_KAFKA).first()
    if not mq_cluster:
        mq_cluster = ClusterInfo.objects.get_or_create(
            bk_tenant_id=BK_TENANT_ID,
            cluster_type=ClusterInfo.TYPE_KAFKA,
            cluster_name="default_kafka_cluster",
            domain_name="kafka.example.com",
            port=9092,
            is_default_cluster=True,
            defaults={"description": "默认Kafka集群", "version": "2.8.0", "schema": "http"},
        )

    if not ClusterInfo.objects.filter(bk_tenant_id=BK_TENANT_ID, cluster_type=ClusterInfo.TYPE_VM).exists():
        ClusterInfo.objects.get_or_create(
            bk_tenant_id=BK_TENANT_ID,
            cluster_type=ClusterInfo.TYPE_VM,
            cluster_name="default_vm_cluster",
            domain_name="vm.example.com",
            port=8428,
            is_default_cluster=True,
            defaults={"description": "默认VM集群", "version": "1.0", "schema": "http"},
        )

    changed_gse_stream_to_id = False
    if mq_cluster.gse_stream_to_id == -1:
        mq_cluster.gse_stream_to_id = 12132
        mq_cluster.save()
        changed_gse_stream_to_id = True

    if not Space.objects.filter(space_type_id="bkcc", space_id="2").exists():
        Space.objects.create(
            bk_tenant_id=BK_TENANT_ID,
            space_name="default_space",
            space_id="2",
            space_type_id="bkcc",
        )

    # 创建Kafka 集群
    kafka_cluster = ClusterInfo.objects.filter(
        bk_tenant_id=BK_TENANT_ID, cluster_type=ClusterInfo.TYPE_KAFKA, is_default_cluster=True
    ).first()
    if not kafka_cluster:
        kafka_cluster = ClusterInfo.objects.create(
            bk_tenant_id=BK_TENANT_ID,
            cluster_type=ClusterInfo.TYPE_KAFKA,
            cluster_name="default_kafka_cluster",
            domain_name="kafka.example.com",
            port=9092,
            is_default_cluster=True,
            defaults={"description": "默认Kafka集群", "version": "2.8.0", "schema": "http"},
        )

        # 将其配置为默认 Kafka 存储
        # monkeypatch.setattr(settings, "BCS_KAFKA_STORAGE_CLUSTER_ID", kafka_cluster.cluster_id)
    with patch.object(settings, "BCS_KAFKA_STORAGE_CLUSTER_ID", kafka_cluster.cluster_id, create=True):
        yield

    # 删除创建的库
    InfluxDBProxyStorage.objects.filter(proxy_cluster_id=1001).delete()
    InfluxDBClusterInfo.objects.filter(cluster_name=instance_cluster_name).delete()

    # 还原配置
    if changed_gse_stream_to_id:
        mq_cluster.gse_stream_to_id = -1
        mq_cluster.save()


@pytest.fixture
def delete_databases():
    from metadata.models.data_source import DataSource
    from metadata.models.storage import KafkaTopicInfo
    from metadata.models.data_source import DataSourceOption, DataSourceResultTable
    from metadata.models.custom_report.event import EventGroup
    from metadata.models.custom_report.time_series import TimeSeriesGroup
    from metadata.models.result_table import ResultTable, ResultTableField, ResultTableOption
    from metadata.models.vm.record import AccessVMRecord

    bk_data_ids = [100, 200, 300, 400, 500, 600]
    DataSource.objects.filter(bk_data_id__in=bk_data_ids).delete()
    KafkaTopicInfo.objects.filter(bk_data_id__in=bk_data_ids).delete()
    DataSourceOption.objects.filter(bk_data_id__in=bk_data_ids).delete()

    EventGroup.objects.filter(bk_data_id__in=bk_data_ids).delete()
    TimeSeriesGroup.objects.filter(bk_data_id__in=bk_data_ids).delete()

    rt_ids = []
    for data_id in bk_data_ids:
        rt_ids.append(f"bkmonitor_time_series_{data_id}.{TimeSeriesGroup.DEFAULT_MEASUREMENT}")
        rt_ids.append(f"2_bkmonitor_event_{data_id}")

    # 删除结果表
    ResultTable.objects.filter(table_id__in=rt_ids).delete()
    ResultTableField.objects.filter(table_id__in=rt_ids).delete()
    ResultTableOption.objects.filter(table_id__in=rt_ids).delete()
    DataSourceResultTable.objects.filter(bk_data_id__in=bk_data_ids).delete()
    # 删除influxdb存储
    InfluxDBStorage.objects.filter(table_id__in=rt_ids).delete()
    ESStorage.objects.filter(table_id__in=rt_ids).delete()
    # 删除vm访问记录
    AccessVMRecord.objects.filter(bk_base_data_id__in=bk_data_ids).delete()
    StorageClusterRecord.objects.filter(table_id__in=rt_ids).delete()
    BkBaseResultTable.objects.filter(monitor_table_id__in=rt_ids).delete()

    yield


def test_check_bcs_clusters_status(
    monkeypatch,
    monkeypatch_cluster_management_fetch_clusters,
    monkeypatch_k8s_node_list_by_cluster,
    monkeypatch_cmdb_get_info_by_ip,
    mock_default_kwargs,
    mock_settings,
    mock_funcs,
    prepare_databases,
    delete_databases,
    configure_celery,
):
    """测试周期刷新bcs集群列表 ."""

    # 测试状态标记为删除
    discover_bcs_clusters()

    from metadata.management.commands.check_bcs_cluster_status import Command

    command = Command()
    # command.verbose=True  #
    result = command.check_cluster_status("BCS-K8S-00000")

    assert result
    command.output_summary_report(result)
    # import json
    # print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


def test_update_bcs_cluster_cloud_id_config(
    monkeypatch, monkeypatch_k8s_node_list_by_cluster, monkeypatch_cmdb_get_info_by_ip, add_bcs_cluster_info
):
    """测试补齐云区域ID到集群信息 ."""
    update_bcs_cluster_cloud_id_config()
    cluster_info = BCSClusterInfo.objects.get(cluster_id="BCS-K8S-00000")
    assert cluster_info.bk_cloud_id == 0
    cluster_info = BCSClusterInfo.objects.get(cluster_id="BCS-K8S-00001")
    assert cluster_info.bk_cloud_id == 1

    BCSClusterInfo.objects.filter(cluster_id="BCS-K8S-00000").update(bk_cloud_id=None)
    bk_biz_id = 2
    cluster_id = "BCS-K8S-00000"
    update_bcs_cluster_cloud_id_config(bk_biz_id, cluster_id)
    cluster_info = BCSClusterInfo.objects.get(cluster_id="BCS-K8S-00000")
    assert cluster_info.bk_cloud_id == 0
