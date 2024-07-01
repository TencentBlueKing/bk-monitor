# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import pytest
from django.conf import settings
from django.forms.models import model_to_dict

from api.bcs_storage.default import FetchResource
from api.kubernetes.default import FetchK8sClusterListResource
from bkmonitor.models.bcs_cluster import BCSCluster
from core.testing import assert_list_contains

DEFAULT_CLUSTER = "BCS-K8S-00000"
pytestmark = pytest.mark.django_db(databases=["default", "monitor_api"])


@pytest.fixture
def mock_bulk_fetch_usage_ratios(mocker, request):
    usages = {
        DEFAULT_CLUSTER: {
            "cpu_usage_ratio": 0.2,
            "memory_usage_ratio": 0.3,
            "disk_usage_ratio": 0.4,
        }
    }
    # 模拟无数据返回
    for k in request.param:
        del usages[DEFAULT_CLUSTER][k]

    return mocker.patch(
        "core.drf_resource.api.kubernetes.bulk_fetch_usage_ratios",
        return_value=usages,
    )


class TestBCSCluster:
    def test_load_list_from_api(
        self,
        monkeypatch,
        monkeypatch_cluster_management_fetch_clusters,
        monkeypatch_bcs_storage_fetch_node_and_endpoints,
        monkeypatch_unify_query_query_data,
        monkeypatch_list_spaces,
    ):
        monkeypatch.setattr(settings, "BCS_CLUSTER_SOURCE", "cluster-manager")
        monkeypatch.setattr(FetchK8sClusterListResource, "cache_type", None)
        monkeypatch.setattr(FetchResource, "cache_type", None)

        models = BCSCluster.load_list_from_api(
            {
                "data_type": "simple",
            }
        )
        actual = [model_to_dict(model) for model in models]
        expect = [
            {
                'alert_status': 'enabled',
                'area_name': '',
                'bcs_cluster_id': 'BCS-K8S-00000',
                'bcs_monitor_data_source': 'prometheus',
                'bk_biz_id': 2,
                'bkmonitor_operator_deployed': False,
                'bkmonitor_operator_first_deployed': None,
                'bkmonitor_operator_last_deployed': None,
                'bkmonitor_operator_version': None,
                'cpu_usage_ratio': 0,
                'created_at': '2022-01-01T00:00:00+08:00',
                'data_source': 'api',
                'deleted_at': None,
                'disk_usage_ratio': 0,
                'environment': 'prod',
                'gray_status': False,
                'id': None,
                'labels': [],
                'memory_usage_ratio': 0,
                'monitor_status': '',
                'name': '蓝鲸社区版7.0',
                'node_count': 1,
                'project_name': '',
                'status': 'RUNNING',
                'updated_at': '2022-01-01T00:00:00+08:00',
                'space_uid': 'bkci__test_bcs_project',
            },
            {
                'alert_status': 'enabled',
                'area_name': '',
                'bcs_cluster_id': 'BCS-K8S-00002',
                'bcs_monitor_data_source': 'prometheus',
                'bk_biz_id': 100,
                'bkmonitor_operator_deployed': False,
                'bkmonitor_operator_first_deployed': None,
                'bkmonitor_operator_last_deployed': None,
                'bkmonitor_operator_version': None,
                'cpu_usage_ratio': 0,
                'created_at': '2022-01-01T00:00:00+08:00',
                'data_source': 'api',
                'deleted_at': None,
                'disk_usage_ratio': 0,
                'environment': 'prod',
                'gray_status': False,
                'labels': [],
                'memory_usage_ratio': 0,
                'monitor_status': '',
                'name': '共享集群',
                'node_count': 1,
                'project_name': '',
                'space_uid': 'bkci__test_shared_bcs_project',
                'status': 'RUNNING',
            },
        ]
        assert_list_contains(actual, expect)

    def test_fetch_usage_ratio(
        self,
        monkeypatch,
        monkeypatch_cluster_management_fetch_clusters,
        monkeypatch_bcs_storage_fetch_node_and_endpoints,
        monkeypatch_bcs_kubernetes_fetch_usage_radio,
    ):
        monkeypatch.setattr(settings, "BCS_CLUSTER_SOURCE", "cluster-manager")
        monkeypatch.setattr(FetchK8sClusterListResource, "cache_type", None)
        monkeypatch.setattr(FetchResource, "cache_type", None)

        bcs_cluster_id = "BCS-K8S-00000"
        bk_biz_id = 2
        actual = BCSCluster.fetch_usage_ratio(bk_biz_id, bcs_cluster_id)
        expect = {'cpu': 2.46, 'disk': 7.82, 'memory': 27.74}
        assert actual == expect

    def test_get_cluster_ids(self, add_bcs_cluster_item_for_update_and_delete):
        bk_biz_id = 2
        actual = BCSCluster.objects.get_cluster_ids(bk_biz_id)
        expect = ['BCS-K8S-00000', 'BCS-K8S-00001']
        assert actual == expect

    @pytest.mark.parametrize(
        "mock_bulk_fetch_usage_ratios, expected_usages, expected_monitor_status",
        [
            pytest.param([], (0.2, 0.3, 0.4), "success"),
            pytest.param(["disk_usage_ratio"], (0.2, 0.3, 0), "success"),
            pytest.param(["cpu_usage_ratio"], (0, 0.3, 0.4), "disabled"),
        ],
        indirect=["mock_bulk_fetch_usage_ratios"],
    )
    def test_sync_resource_usage(
        self,
        add_bcs_cluster_item_for_update_and_delete,
        mock_bulk_fetch_usage_ratios,
        expected_usages,
        expected_monitor_status,
    ):
        bk_biz_id = 2
        BCSCluster.sync_resource_usage(bk_biz_id)
        for cluster in BCSCluster.objects.filter(bk_biz_id=bk_biz_id):
            actual_usages = cluster.cpu_usage_ratio, cluster.memory_usage_ratio, cluster.disk_usage_ratio
            if cluster.bcs_cluster_id == DEFAULT_CLUSTER:
                # 跟据线上数据更新
                assert actual_usages == expected_usages
                assert cluster.monitor_status == expected_monitor_status
            else:
                # 整个集群都无数据
                assert actual_usages == (0, 0, 0)
                assert cluster.monitor_status == BCSCluster.METRICS_STATE_DISABLED
