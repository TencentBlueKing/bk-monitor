"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
import json
import time

from unittest import mock
import pytest
from django.core.cache import caches

from alarm_backends.core.alert import Alert, Event
from alarm_backends.core.cache.cmdb.host import HostIPManager, HostManager
from alarm_backends.core.storage.redis_cluster import get_node_by_strategy_id
from alarm_backends.service.alert.enricher import KubernetesCMDBEnricher
from alarm_backends.service.converge.shield.shielder.saas_config import HostShielder
from alarm_backends.tests.utils.cmdb_data import ALL_HOSTS, TOPO_TREE
from api.cmdb.define import Business, Host
from bkmonitor.models import CacheNode
from bkmonitor.utils.local import local
from constants.common import DEFAULT_TENANT_ID
from constants.data_source import KubernetesResultTableLabel

pytestmark = pytest.mark.django_db

BK_BIZ_ID = 2
BK_CLOUD_ID = 0
IP = "127.0.0.1"

IP__HOST_ID_MAP = {"127.0.0.1": 100, "127.0.0.2": 200, "10.0.0.1": 1}
IP__BIZ_MAP = {"127.0.0.1": 2, "127.0.0.2": 3, "10.0.0.1": 2}

POD__IP_MAP = {"backend-test-1": "127.0.0.1", "backend-test-2": "127.0.0.2", "backend-test-3": "10.0.0.1"}


def _init():
    get_node_by_strategy_id(0)
    CacheNode.refresh_from_settings()


@pytest.fixture()
def init():
    _init()

    with mock.patch(
        "alarm_backends.service.alert.enricher.kubernetes_cmdb.settings.KUBERNETES_CMDB_ENRICH_BIZ_WHITE_LIST",
        [BK_BIZ_ID, 3],
    ) as p:
        yield p


@pytest.fixture()
def mock_get_kubernetes_relation():
    with mock.patch(
        "alarm_backends.service.alert.enricher.kubernetes_cmdb.api.unify_query.get_kubernetes_relation"
    ) as get_kubernetes_relation:
        get_kubernetes_relation.side_effect = lambda query_params: {
            "data": [
                {
                    "code": 200,
                    "source_type": "pod",
                    "source_info": {**query_params["source_info_list"][0]},
                    "target_list": [{"bk_target_ip": POD__IP_MAP[query_params["source_info_list"][0]["pod"]]}],
                }
            ]
        }

        yield get_kubernetes_relation


@pytest.fixture()
def mock_get_host_by_ip():
    with mock.patch("alarm_backends.service.alert.enricher.kubernetes_cmdb.api.cmdb.get_host_by_ip") as get_host_by_ip:
        get_host_by_ip.side_effect = lambda **query_params: [
            Host(
                bk_host_innerip=query_params["ips"][0]["ip"],
                bk_cloud_id=BK_CLOUD_ID,
                bk_host_id=IP__HOST_ID_MAP[query_params["ips"][0]["ip"]],
                bk_biz_id=query_params["bk_biz_id"],
                bk_state="运营中[无告警]",
            )
        ]
        yield get_host_by_ip


@pytest.fixture()
def mock_get_host_without_biz_v2():
    with mock.patch("alarm_backends.core.cache.cmdb.host.api.cmdb.get_host_without_biz_v2") as get_host_without_biz_v2:
        get_host_without_biz_v2.side_effect = lambda **query_params: {
            "count": 1,
            "hosts": [
                Host(
                    bk_host_innerip=query_params["ips"][0],
                    bk_cloud_id=BK_CLOUD_ID,
                    bk_host_id=IP__HOST_ID_MAP[query_params["ips"][0]],
                    bk_biz_id=IP__BIZ_MAP[query_params["ips"][0]],
                    bk_state="运营中[无告警]",
                ).get_attrs()
            ],
        }
        yield get_host_without_biz_v2


@pytest.fixture()
def init_host_cache():
    def _clear():
        caches["locmem"].clear()
        local.host_cache = {}
        HostManager.cache.delete(HostManager.get_cache_key(DEFAULT_TENANT_ID))
        HostIPManager.cache.delete(HostIPManager.get_cache_key(DEFAULT_TENANT_ID))

    _clear()

    def _refresh():
        hosts = copy.deepcopy(ALL_HOSTS)
        HostManager.fill_attr_to_hosts(bk_biz_id=BK_BIZ_ID, hosts=hosts, with_world_ids=True)
        for host in hosts:
            host_dict = host.get_attrs()
            host_dict["topo_link"] = {
                key: [
                    {
                        "bk_obj_id": node.bk_obj_id,
                        "bk_obj_name": node.bk_obj_name,
                        "bk_inst_id": node.bk_inst_id,
                        "bk_inst_name": node.bk_inst_name,
                    }
                    for node in nodes
                ]
                for key, nodes in TOPO_TREE.convert_to_topo_link().items()
            }
            HostManager.cache.hset(
                HostManager.get_cache_key(DEFAULT_TENANT_ID),
                HostManager.get_host_key(host.bk_host_innerip, host.bk_cloud_id),
                json.dumps(host_dict),
            )
        HostIPManager.cache.hmset(
            HostIPManager.get_cache_key(DEFAULT_TENANT_ID),
            {
                host.bk_host_innerip: json.dumps([HostManager.get_host_key(host.bk_host_innerip, host.bk_cloud_id)])
                for host in hosts
            },
        )

    get_business = mock.patch(
        "alarm_backends.service.alert.enricher.kubernetes_cmdb.api.cmdb.get_business",
        return_value=[Business(bk_biz_id=i) for i in [2, 3, 4, 5, 6, 10, 20, 21]],
    )

    get_topo_tree = mock.patch("alarm_backends.core.cache.cmdb.host.api.cmdb.get_topo_tree", return_value=TOPO_TREE)

    get_set = mock.patch("alarm_backends.core.cache.cmdb.host.api.cmdb.get_set", return_value=[])

    get_set.start()
    get_business.start()
    get_topo_tree.start()
    _refresh()

    yield

    get_set.stop()
    get_business.stop()
    get_topo_tree.stop()

    _clear()


@pytest.fixture()
def event_data():
    event = {
        "strategy_id": 1,
        "id": "1",
        "event_id": "1",
        "bk_biz_id": BK_BIZ_ID,
        "plugin_id": "bkmonitor",
        "alert_name": "[kube pod] 容器状态异常",
        "status": "ABNORMAL",
        "time": int(time.time()),
        "severity": 1,
        "target_type": "",
        "target": None,
        "category": KubernetesResultTableLabel.kubernetes,
        "tags": [
            {"key": "pod", "value": "backend-test-1"},
            {"key": "container", "value": "backend-test-operator"},
            {"key": "bcs_cluster_id", "value": "TEST-K8S-1"},
            {"key": "namespace", "value": "bcs-system"},
        ],
        "dedupe_keys": [
            "strategy_id",
            "target_type",
            "target",
            "bk_biz_id",
            "tags.pod",
            "tags.container",
            "tags.bcs_cluster_id",
            "tags.namespace",
        ],
        "extra_info": {
            "agg_dimensions": {"bcs_cluster_id", "container", "pod", "namespace"},
            "origin_alarm": {
                "data": {
                    "dimensions": {
                        "pod": "backend-test-1",
                        "container": "backend-test-operator",
                        "bcs_cluster_id": "TEST-K8S-1",
                        "namespace": "bcs-system",
                    }
                }
            },
        },
    }

    yield event


class TestKubernetesCMDBEnricher:
    def test_k8s_enricher__increment(
        self,
        init,
        init_host_cache,
        event_data,
        mock_get_kubernetes_relation,
        mock_get_host_by_ip,
        mock_get_host_without_biz_v2,
    ):
        alert = Alert.from_event(Event(event_data))
        alert._is_new = True
        KubernetesCMDBEnricher([alert]).enrich()

        mock_get_host_by_ip.assert_called_once()
        mock_get_kubernetes_relation.assert_called_once()
        mock_get_host_without_biz_v2.assert_not_called()

        assert alert.dimensions[4]["key"] == "target_type" and alert.dimensions[4]["value"] == "pod"
        assert alert.dimensions[5]["key"] == "bk_host_id" and alert.dimensions[5]["value"] == 100
        assert alert.dimensions[6]["key"] == "ip" and alert.dimensions[6]["value"] == "127.0.0.1"
        assert alert.dimensions[7]["key"] == "bk_cloud_id" and alert.dimensions[7]["value"] == 0

    def test_k8s_enricher__multi_biz_increment(
        self,
        init,
        init_host_cache,
        event_data: dict,
        mock_get_kubernetes_relation,
        mock_get_host_by_ip,
        mock_get_host_without_biz_v2,
    ):
        event1 = copy.deepcopy(event_data)
        event2 = copy.deepcopy(event_data)
        event2["bk_biz_id"] = 3
        event2["event_id"] = event2["id"] = 2
        event2["tags"][1]["value"] = "backend-test-2"
        event2["extra_info"]["origin_alarm"]["data"]["dimensions"]["pod"] = "backend-test-2"

        alert1 = Alert.from_event(Event(event1))
        alert1._is_new = True

        alert2 = Alert.from_event(Event(event2))
        alert2._is_new = True

        KubernetesCMDBEnricher([alert1, alert2]).enrich()

        assert alert1.dimensions[4]["key"] == "target_type" and alert1.dimensions[4]["value"] == "pod"
        assert alert1.dimensions[5]["key"] == "bk_host_id" and alert1.dimensions[5]["value"] == 100
        assert alert1.dimensions[6]["key"] == "ip" and alert1.dimensions[6]["value"] == "127.0.0.1"
        assert alert1.dimensions[7]["key"] == "bk_cloud_id" and alert1.dimensions[7]["value"] == 0

        assert alert2.dimensions[4]["key"] == "target_type" and alert2.dimensions[4]["value"] == "pod"
        assert alert2.dimensions[5]["key"] == "bk_host_id" and alert2.dimensions[5]["value"] == 200
        assert alert2.dimensions[6]["key"] == "ip" and alert2.dimensions[6]["value"] == "127.0.0.2"
        assert alert2.dimensions[7]["key"] == "bk_cloud_id" and alert2.dimensions[7]["value"] == 0

    def test_k8s_enricher__host_exists(
        self,
        init,
        init_host_cache,
        event_data: dict,
        mock_get_kubernetes_relation,
        mock_get_host_by_ip,
        mock_get_host_without_biz_v2,
    ):
        event_data = copy.deepcopy(event_data)
        event_data["tags"][1]["value"] = "backend-test-3"
        event_data["extra_info"]["origin_alarm"]["data"]["dimensions"]["pod"] = "backend-test-3"

        alert = Alert.from_event(Event(event_data))
        alert._is_new = True
        KubernetesCMDBEnricher([alert]).enrich()

        mock_get_host_by_ip.assert_not_called()
        mock_get_host_without_biz_v2.assert_not_called()

        assert alert.dimensions[4]["key"] == "target_type" and alert.dimensions[4]["value"] == "pod"
        assert alert.dimensions[5]["key"] == "bk_host_id" and alert.dimensions[5]["value"] == 1
        assert alert.dimensions[6]["key"] == "ip" and alert.dimensions[6]["value"] == "10.0.0.1"
        assert alert.dimensions[7]["key"] == "bk_cloud_id" and alert.dimensions[7]["value"] == 1


class TestHostShielder:
    def test_is_matched__host_not_exists(
        self,
        init,
        init_host_cache,
        event_data,
        mock_get_kubernetes_relation,
        mock_get_host_by_ip,
        mock_get_host_without_biz_v2,
    ):
        alert = Alert.from_event(Event(event_data))
        alert._is_new = True
        KubernetesCMDBEnricher([alert]).enrich()

        shielder = HostShielder(alert.to_document())

        mock_get_host_without_biz_v2.assert_not_called()
        assert shielder.is_matched()
        mock_get_host_without_biz_v2.assert_called_once()

    def test_is_matched__host_exists(
        self,
        init,
        init_host_cache,
        event_data: dict,
        mock_get_kubernetes_relation,
        mock_get_host_by_ip,
        mock_get_host_without_biz_v2,
    ):
        event_data = copy.deepcopy(event_data)
        event_data["tags"][1]["value"] = "backend-test-3"
        event_data["extra_info"]["origin_alarm"]["data"]["dimensions"]["pod"] = "backend-test-3"

        alert = Alert.from_event(Event(event_data))
        alert._is_new = True
        KubernetesCMDBEnricher([alert]).enrich()

        shielder = HostShielder(alert.to_document())

        assert shielder.is_matched()
        mock_get_host_without_biz_v2.assert_not_called()
