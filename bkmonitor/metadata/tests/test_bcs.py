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

from api.kubernetes.default import FetchK8sClusterListResource
from metadata import models
from metadata.models.bcs.resource import BCSClusterInfo
from metadata.task.bcs import discover_bcs_clusters, update_bcs_cluster_cloud_id_config
from metadata.tests.common_utils import consul_client
from constants.common import DEFAULT_TENANT_ID

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
