"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from copy import deepcopy

import pytest

from api.cmdb.default import GetHostByIP, GetHostByTopoNode, GetModule, GetServiceInstanceByTopoNode
from api.cmdb.define import Host, Module, ServiceInstance
from bkmonitor.models import ItemModel, StrategyModel
from core.drf_resource import resource
from monitor_web.commons.cc.utils.service_category import ServiceCategorySearcher
from monitor_web.strategies.resources.v2 import GetTargetDetail, GetTargetDetailWithCache

BK_BIZ_ID = 2

# 拓扑：biz 2 -> set 10 (module 100, 101) / set 11 (module 102)
MOCK_TOPO_TREE = {
    "bk_obj_id": "biz",
    "bk_inst_id": BK_BIZ_ID,
    "bk_inst_name": "biz-2",
    "child": [
        {
            "bk_obj_id": "set",
            "bk_inst_id": 10,
            "bk_inst_name": "set-10",
            "child": [
                {"bk_obj_id": "module", "bk_inst_id": 100, "bk_inst_name": "module-100", "child": []},
                {"bk_obj_id": "module", "bk_inst_id": 101, "bk_inst_name": "module-101", "child": []},
            ],
        },
        {
            "bk_obj_id": "set",
            "bk_inst_id": 11,
            "bk_inst_name": "set-11",
            "child": [
                {"bk_obj_id": "module", "bk_inst_id": 102, "bk_inst_name": "module-102", "child": []},
            ],
        },
    ],
}


def make_hosts():
    common = {"bk_biz_id": BK_BIZ_ID, "bk_cloud_id": 0, "bk_cloud_name": "default area"}
    return [
        Host(bk_host_innerip="127.0.0.1", bk_host_id=1, bk_module_ids=[100], **common),
        Host(bk_host_innerip="127.0.0.2", bk_host_id=2, bk_module_ids=[101], **common),
        Host(bk_host_innerip="127.0.0.3", bk_host_id=3, bk_module_ids=[100, 102], **common),
    ]


def make_services():
    return [
        ServiceInstance(service_instance_id=201, name="svc-201", bk_host_id=3, bk_module_id=102),
        ServiceInstance(service_instance_id=202, name="svc-202", bk_host_id=1, bk_module_id=100),
    ]


def make_modules():
    return [
        Module(bk_module_id=100, bk_module_name="module-100", service_category_id=5, service_template_id=1000),
        Module(bk_module_id=101, bk_module_name="module-101", service_category_id=6, service_template_id=1001),
        Module(bk_module_id=102, bk_module_name="module-102", service_category_id=7, service_template_id=1002),
    ]


# Agent 状态冻结值（时敏字段，逐策略与批量两条路径必须看到同一份）
MOCK_AGENT_STATUS = {1: 0, 2: -1, 3: 2}

HOST_TOPO_TARGET_SET10 = [
    [{"field": "host_topo_node", "method": "eq", "value": [{"bk_obj_id": "set", "bk_inst_id": 10}]}]
]
HOST_TOPO_TARGET_MIXED = [
    [
        {
            "field": "host_topo_node",
            "method": "eq",
            "value": [
                {"bk_obj_id": "module", "bk_inst_id": 102},
                {"bk_obj_id": "set", "bk_inst_id": 10},
            ],
        }
    ]
]
SERVICE_TOPO_TARGET_SET11 = [
    [{"field": "service_topo_node", "method": "eq", "value": [{"bk_obj_id": "set", "bk_inst_id": 11}]}]
]
HOST_IP_TARGET = [
    [
        {
            "field": "ip",
            "method": "eq",
            "value": [
                {"ip": "127.0.0.1", "bk_cloud_id": 0, "bk_supplier_id": 0},
                {"ip": "127.0.0.2", "bk_cloud_id": 0, "bk_supplier_id": 0},
            ],
        }
    ]
]
EMPTY_TARGET = [[]]


@pytest.fixture
def mock_cmdb(monkeypatch):
    """冻结 resolver 的全部下游：拓扑树 / 整业务主机 / Agent状态 / 服务实例 / 模块 / 服务分类"""
    counters = {"get_host_by_topo_node": 0, "get_service_instance_by_topo_node": 0, "topo_tree": 0}

    def fake_topo_tree(bk_biz_id):
        counters["topo_tree"] += 1
        return deepcopy(MOCK_TOPO_TREE)

    def fake_get_agent_status(bk_biz_id, hosts):
        return {host.bk_host_id: MOCK_AGENT_STATUS.get(host.bk_host_id, -1) for host in hosts}

    def fake_get_host_by_topo_node(_self, params):
        counters["get_host_by_topo_node"] += 1
        return make_hosts()

    def fake_get_service_instance_by_topo_node(_self, params):
        counters["get_service_instance_by_topo_node"] += 1
        return make_services()

    monkeypatch.setattr(resource.cc, "topo_tree", fake_topo_tree)
    monkeypatch.setattr(resource.cc, "get_agent_status", fake_get_agent_status)
    monkeypatch.setattr(GetHostByIP, "perform_request", lambda _self, params: make_hosts()[:2])
    monkeypatch.setattr(GetHostByTopoNode, "perform_request", fake_get_host_by_topo_node)
    monkeypatch.setattr(GetServiceInstanceByTopoNode, "perform_request", fake_get_service_instance_by_topo_node)
    monkeypatch.setattr(GetModule, "perform_request", lambda _self, params: make_modules())
    monkeypatch.setattr(
        ServiceCategorySearcher,
        "search",
        lambda _self, bk_biz_id, category_id: {"first": "cat", "second": f"cat-{category_id}"},
    )
    return counters


def create_strategy(name, scenario, target):
    strategy = StrategyModel.objects.create(
        name=name,
        bk_biz_id=BK_BIZ_ID,
        source="bk_monitorv3",
        scenario=scenario,
        type="monitor",
        is_enabled=True,
        is_invalid=False,
        invalid_type="",
        create_user="admin",
        update_user="admin",
        app="",
        path="",
        hash="",
        snippet="",
    )
    ItemModel.objects.create(
        strategy_id=strategy.id,
        name=name,
        expression="a",
        origin_sql="",
        no_data_config={},
        target=target,
        meta=[],
    )
    return strategy.id


@pytest.mark.django_db(databases="__all__")
class TestGetTargetDetailBatch:
    """GetTargetDetail 批量路径与逐策略路径的对拍测试"""

    def test_batch_equals_per_strategy(self, mock_cmdb):
        """批量解析结果与逐策略 get_target_detail 完全一致（results-preserving，含混合目标）"""
        sid1 = create_strategy("s1-host-topo", "os", deepcopy(HOST_TOPO_TARGET_SET10))
        sid2 = create_strategy("s2-host-topo", "os", deepcopy(HOST_TOPO_TARGET_MIXED))
        sid3 = create_strategy("s3-service-topo", "service_module", deepcopy(SERVICE_TOPO_TARGET_SET11))
        sid4 = create_strategy("s4-host-ip", "os", deepcopy(HOST_IP_TARGET))

        actual = GetTargetDetail().request({"bk_biz_id": BK_BIZ_ID, "strategy_ids": [sid1, sid2, sid3, sid4]})

        expected = {
            sid: GetTargetDetailWithCache.get_target_detail(BK_BIZ_ID, deepcopy(target))
            for sid, target in [
                (sid1, HOST_TOPO_TARGET_SET10),
                (sid2, HOST_TOPO_TARGET_MIXED),
                (sid3, SERVICE_TOPO_TARGET_SET11),
                (sid4, HOST_IP_TARGET),
            ]
        }

        assert actual == expected

    def test_empty_target_falls_back(self, mock_cmdb):
        """空 target 策略不进批量路径，仍走原 fallback（bk_target_detail=None）"""
        sid = create_strategy("s-empty-target", "os", deepcopy(EMPTY_TARGET))

        result = GetTargetDetail().request({"bk_biz_id": BK_BIZ_ID, "strategy_ids": [sid]})

        assert result == {
            sid: {
                "bk_target_type": None,
                "bk_obj_type": None,
                "bk_target_detail": None,
                "instance_type": None,
            }
        }

    def test_batch_reduces_biz_level_fetches(self, mock_cmdb):
        """业务级取数（整业务主机拉取）由每策略一次降为每目标类型一次"""
        sid1 = create_strategy("s1-host-topo", "os", deepcopy(HOST_TOPO_TARGET_SET10))
        sid2 = create_strategy("s2-host-topo", "os", deepcopy(HOST_TOPO_TARGET_MIXED))
        sid3 = create_strategy("s3-service-topo", "service_module", deepcopy(SERVICE_TOPO_TARGET_SET11))

        GetTargetDetail().request({"bk_biz_id": BK_BIZ_ID, "strategy_ids": [sid1, sid2, sid3]})

        # host_topo（2 个策略合并 1 次）+ service_topo（1 次，其 get_instance_count 也拉整业务主机）
        assert mock_cmdb["get_host_by_topo_node"] == 2
        assert mock_cmdb["get_service_instance_by_topo_node"] == 1
        assert mock_cmdb["topo_tree"] == 2

    def test_target_not_mutated(self, mock_cmdb):
        """批量路径不得改写 ItemModel.target 原始数据（resolver 会原地改节点字典）"""
        sid1 = create_strategy("s1-host-topo", "os", deepcopy(HOST_TOPO_TARGET_SET10))

        GetTargetDetail().request({"bk_biz_id": BK_BIZ_ID, "strategy_ids": [sid1]})

        item = ItemModel.objects.get(strategy_id=sid1)
        assert item.target == HOST_TOPO_TARGET_SET10


@pytest.mark.django_db(databases="__all__")
class TestGetTargetDetailCacheProbe:
    """cache-probe-then-batch 接线测试：探缓存命中短路 / refresh 旁路并回写"""

    @pytest.fixture
    def prod_cache_env(self, monkeypatch):
        # development 下缓存读写被 UsingCache 关闭，切到 production 语义以验证探测/回写
        from django.conf import settings

        monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    def test_probe_hit_short_circuits_and_refresh_bypasses(self, prod_cache_env, mock_cmdb, monkeypatch):
        sid1 = create_strategy("s1-host-topo", "os", deepcopy(HOST_TOPO_TARGET_SET10))
        sid2 = create_strategy("s2-service-topo", "service_module", deepcopy(SERVICE_TOPO_TARGET_SET11))

        miss_counts = []
        real_batch = GetTargetDetail.batch_get_node_target_details.__func__

        def spy_batch(cls, bk_biz_id, items):
            miss_counts.append(len(items))
            return real_batch(cls, bk_biz_id, items)

        monkeypatch.setattr(GetTargetDetail, "batch_get_node_target_details", classmethod(spy_batch))

        params = {"bk_biz_id": BK_BIZ_ID, "strategy_ids": [sid1, sid2]}

        # 冷启动：全部未命中，批量解析 + 回写策略级缓存
        run1 = GetTargetDetail().request(dict(params))
        assert miss_counts == [2]

        # 暖缓存：探测全部命中，批量解析零输入，结果与冷启动一致
        run2 = GetTargetDetail().request(dict(params))
        assert miss_counts == [2, 0]
        assert run2 == run1

        # refresh：跳过探测、全部重算并重写缓存
        run3 = GetTargetDetail().request(dict(params, refresh=True))
        assert miss_counts == [2, 0, 2]
        assert run3 == run1

        # refresh 重写后的缓存仍可命中
        run4 = GetTargetDetail().request(dict(params))
        assert miss_counts == [2, 0, 2, 0]
        assert run4 == run1

        # set_cached 写的 key 必须能被原生 request() 读到（celery 预热任务等旧路径的消费方式）
        fresh = GetTargetDetailWithCache()
        monkeypatch.setattr(
            GetTargetDetailWithCache,
            "get_target_detail",
            classmethod(lambda *args, **kwargs: pytest.fail("cache miss: set_cached 的 key 与 request() 不兼容")),
        )
        fresh.set_mapping({sid1: (BK_BIZ_ID, deepcopy(HOST_TOPO_TARGET_SET10))})
        assert fresh.request({"strategy_id": sid1}) == run1[sid1]
