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


import json

import mock
from django.core.cache import caches
from django.test import TestCase

from alarm_backends.core.cache.cmdb import (
    BusinessManager,
    HostIDManager,
    HostManager,
    ModuleManager,
    ServiceInstanceManager,
    TopoManager,
)
from alarm_backends.tests.utils.cmdb_data import (
    ALL_HOSTS,
    ALL_MODULES,
    ALL_SERVICE_INSTANCES,
    TOPO_TREE,
)
from api.cmdb.define import Business, Host, Module, ServiceInstance, TopoNode
from bkmonitor.utils.local import local

BIZ_IDS = [2, 3, 4, 5, 6, 10, 20, 21]

ALL_BUSINESS = [Business(bk_biz_id=i) for i in BIZ_IDS]

mock.patch("alarm_backends.core.cache.cmdb.business.api.cmdb.get_business", return_value=ALL_BUSINESS).start()

get_hosts = mock.patch("alarm_backends.core.cache.cmdb.host.api.cmdb.get_host_by_topo_node").start()
get_hosts.side_effect = lambda bk_biz_id, **kwargs: [host for host in ALL_HOSTS if host.bk_biz_id == bk_biz_id]

get_modules = mock.patch("alarm_backends.core.cache.cmdb.module.api.cmdb.get_module").start()
get_modules.side_effect = lambda bk_biz_id: [module for module in ALL_MODULES if module.bk_biz_id == bk_biz_id]


get_service_instances = mock.patch(
    "alarm_backends.core.cache.cmdb." "service_instance.api.cmdb.get_service_instance_by_topo_node"
).start()
get_service_instances.side_effect = lambda bk_biz_id: [
    instance for instance in ALL_SERVICE_INSTANCES if instance.bk_biz_id == bk_biz_id
]

mock.patch("alarm_backends.core.cache.cmdb.host.api.cmdb.get_topo_tree", return_value=TOPO_TREE).start()
mock.patch("alarm_backends.core.cache.cmdb.service_instance.api.cmdb.get_topo_tree", return_value=TOPO_TREE).start()
mock.patch("alarm_backends.core.cache.cmdb.service_instance.api.cmdb.get_set", return_value=[]).start()


class TestBusinessManager(TestCase):
    def setUp(self):
        BusinessManager.clear()

    def tearDown(self):
        BusinessManager.clear()

    def test_serialize(self):
        biz_obj = Business(bk_biz_id=2)
        obj_bin = BusinessManager.serialize(biz_obj)
        new_biz_obj = BusinessManager.deserialize(obj_bin)
        self.assertEqual(biz_obj, new_biz_obj)

    def test_key_convert(self):
        self.assertEqual("2", BusinessManager.key_to_internal_value(2))
        self.assertEqual("2", BusinessManager.key_to_internal_value("2"))
        self.assertEqual(2, BusinessManager.key_to_representation(2))
        self.assertEqual(2, BusinessManager.key_to_representation("2"))

    def test_refresh(self):
        # TODO: mock redis cache
        BusinessManager.refresh()
        all_business_ids = BusinessManager.cache.hkeys(BusinessManager.CACHE_KEY)
        all_business_ids = [BusinessManager.key_to_representation(biz_id) for biz_id in all_business_ids]
        self.assertSetEqual(set(BIZ_IDS), set(all_business_ids))

    def test_keys(self):
        BusinessManager.refresh()
        biz_ids = list(BusinessManager.keys())
        self.assertEqual(len(biz_ids), len(BIZ_IDS))
        self.assertSetEqual(set(biz_ids), set(BIZ_IDS))

    def test_get(self):
        BusinessManager.refresh()
        for bk_biz_id in BIZ_IDS:
            biz_obj = BusinessManager.get(bk_biz_id=bk_biz_id)
            self.assertEqual(bk_biz_id, biz_obj.bk_biz_id)

    def test_all(self):
        BusinessManager.refresh()
        business_list = BusinessManager.all()
        self.assertEqual(len(ALL_BUSINESS), len(business_list))
        self.assertSetEqual(set(ALL_BUSINESS), set(business_list))

    def test_clear(self):
        BusinessManager.refresh()
        keys = BusinessManager.cache.hkeys(BusinessManager.CACHE_KEY)
        self.assertEqual(len(keys), len(BIZ_IDS))
        BusinessManager.clear()
        keys = BusinessManager.cache.hkeys(BusinessManager.CACHE_KEY)
        self.assertEqual(len(keys), 0)

    @mock.patch("alarm_backends.core.cache.cmdb.business.api.cmdb.get_business")
    def test_remove_biz(self, get_business):
        get_business.return_value = ALL_BUSINESS
        BusinessManager.refresh()
        self.assertSetEqual(set(ALL_BUSINESS), set(BusinessManager.all()))
        new_business_list = ALL_BUSINESS[:3]
        get_business.return_value = new_business_list
        BusinessManager.refresh()
        self.assertSetEqual(set(new_business_list), set(BusinessManager.all()))


class TestHostManager(TestCase):
    def setUp(self):
        caches["locmem"].clear()
        HostManager.clear()
        local.host_cache = {}

    def tearDown(self):
        HostManager.clear()

    def test_serialize(self):
        host_obj = Host(bk_host_innerip="10.0.0.1", bk_cloud_id=0, bk_host_id=1, bk_biz_id=2)
        obj_bin = HostManager.serialize(host_obj)
        new_host_obj = HostManager.deserialize(obj_bin)
        self.assertEqual(host_obj, new_host_obj)

    def test_key_convert(self):
        self.assertEqual("10.0.0.1|0", HostManager.key_to_internal_value(ip="10.0.0.1", bk_cloud_id=0))
        self.assertEqual("10.0.0.1|0", HostManager.key_to_representation("10.0.0.1|0"))

    def test_refresh(self):
        # TODO: mock redis cache
        HostManager.refresh()
        host_ids = HostManager.cache.hkeys(HostManager.CACHE_KEY)
        excepted_host_ids = [HostManager.key_to_internal_value(host.ip, host.bk_cloud_id) for host in ALL_HOSTS]
        for host in ALL_HOSTS:
            excepted_host_ids.append(str(host.bk_host_id))
        self.assertSetEqual(set(excepted_host_ids), set(host_ids))

    def test_keys(self):
        HostManager.refresh()
        host_ids = list(HostManager.keys())
        excepted_host_ids = [HostManager.key_to_internal_value(host.ip, host.bk_cloud_id) for host in ALL_HOSTS]
        for host in ALL_HOSTS:
            excepted_host_ids.append(str(host.bk_host_id))
        self.assertSetEqual(set(excepted_host_ids), set(host_ids))

    def test_get(self):
        HostManager.refresh()
        for host in ALL_HOSTS:
            actual_host = HostManager.get(ip=host.ip, bk_cloud_id=host.bk_cloud_id)
            self.assertEqual(host, actual_host)

        # test get topo link
        host = HostManager.get("10.0.0.1", 1)
        self.assertSetEqual(set(host.topo_link.keys()), {"module|5", "module|6"})
        self.assertEqual(len(host.topo_link["module|5"]), 3)
        self.assertEqual(HostManager.get("10.0.0.2", 2).topo_link, {})

    def test_mget(self):
        HostManager.refresh()
        hosts = HostManager.multi_get_with_dict(
            [
                HostManager.key_to_internal_value("10.0.0.1", 1),
                HostManager.key_to_internal_value("10.0.0.2", 0),
                HostManager.key_to_internal_value("10.0.0.3", 3),
            ]
        )
        self.assertEqual(3, len(hosts))
        self.assertEqual("10.0.0.1", hosts["10.0.0.1|1"].ip)
        self.assertIsNone(hosts["10.0.0.2|0"])
        self.assertEqual("10.0.0.3", hosts["10.0.0.3|3"].ip)

    def test_all(self):
        HostManager.refresh()
        hosts = HostManager.all()
        self.assertSetEqual(set(ALL_HOSTS), set(hosts))

    def test_clear(self):

        HostManager.refresh()
        keys = HostManager.cache.hkeys(HostManager.CACHE_KEY)
        biz_keys = HostManager.cache.hkeys(HostManager.get_biz_cache_key())
        biz_keys = [int(key) for key in biz_keys]
        self.assertEqual(len(keys), len(ALL_HOSTS) * 2)
        self.assertSetEqual(set(biz_keys), set(BIZ_IDS))

        HostManager.clear()
        self.assertEqual(len(HostManager.cache.hkeys(HostManager.CACHE_KEY)), 0)
        self.assertEqual(len(HostManager.cache.hkeys(HostManager.get_biz_cache_key())), 0)

    @mock.patch("alarm_backends.core.cache.cmdb.host.api.cmdb.get_host_by_topo_node")
    def test_refresh_exception(self, get_host_by_topo_node):
        get_host_by_topo_node.side_effect = lambda bk_biz_id, **kwargs: [
            host for host in ALL_HOSTS if host.bk_biz_id == bk_biz_id
        ]
        HostManager.refresh()

        self.assertEqual(3, HostManager.get(ip="10.0.0.3", bk_cloud_id=3).bk_biz_id)

        all_host_id_list = HostManager.cache.hgetall(HostManager.get_biz_cache_key())
        self.assertSetEqual({"10.0.0.1|1", "10.0.0.2|2", "1", "2"}, set(json.loads(all_host_id_list["2"])))
        self.assertSetEqual({"10.0.0.3|3", "10.0.0.4|4", "3", "4"}, set(json.loads(all_host_id_list["3"])))
        self.assertSetEqual({"10.0.0.5|5", "10.0.0.6|6", "5", "6"}, set(json.loads(all_host_id_list["4"])))

        NEW_HOSTS = [
            Host(bk_host_innerip="10.0.0.1", bk_cloud_id=1, bk_host_id=1, bk_biz_id=2),
            Host(bk_host_innerip="10.0.0.3", bk_cloud_id=3, bk_host_id=3, bk_biz_id=2),
            Host(bk_host_innerip="10.0.0.4", bk_cloud_id=4, bk_host_id=4, bk_biz_id=2),
        ]

        def mocked_get_host_by_topo_node(bk_biz_id, **kwargs):
            # 业务3的机器挪到业务2中，业务3当前机器列表为空，业务4请求失败
            if bk_biz_id == 4:
                raise Exception
            return [host for host in NEW_HOSTS if host.bk_biz_id == bk_biz_id]

        get_host_by_topo_node.side_effect = mocked_get_host_by_topo_node

        HostManager.refresh()
        hosts = HostManager.all()

        # 删除了一台业务2的机器
        excepted_hosts_result = [
            Host(bk_host_innerip="10.0.0.1", bk_cloud_id=1, bk_host_id=1, bk_biz_id=2),
            Host(bk_host_innerip="10.0.0.3", bk_cloud_id=3, bk_host_id=3, bk_biz_id=2),
            Host(bk_host_innerip="10.0.0.4", bk_cloud_id=4, bk_host_id=4, bk_biz_id=2),
            Host(bk_host_innerip="10.0.0.5", bk_cloud_id=5, bk_host_id=5, bk_biz_id=4),
            Host(bk_host_innerip="10.0.0.6", bk_cloud_id=6, bk_host_id=6, bk_biz_id=4),
        ]
        self.assertSetEqual(set(excepted_hosts_result), set(hosts))

        # 业务迁移
        # 清理本地缓存
        caches["locmem"].clear()

        self.assertEqual(2, HostManager.get(ip="10.0.0.3", bk_cloud_id=3).bk_biz_id)
        self.assertIsNone(HostManager.get(ip="10.0.0.2", bk_cloud_id=2))

        all_host_id_list = HostManager.cache.hgetall(HostManager.get_biz_cache_key())
        self.assertSetEqual(
            {"10.0.0.1|1", "10.0.0.3|3", "10.0.0.4|4", "1", "3", "4"}, set(json.loads(all_host_id_list["2"]))
        )
        self.assertSetEqual(set(), set(json.loads(all_host_id_list["3"])))
        self.assertSetEqual({"10.0.0.5|5", "10.0.0.6|6", "5", "6"}, set(json.loads(all_host_id_list["4"])))

        # 业务拉取异常
        self.assertEqual(4, HostManager.get(ip="10.0.0.5", bk_cloud_id=5).bk_biz_id)

    @mock.patch("alarm_backends.core.cache.cmdb.business.api.cmdb.get_business")
    def test_remove_biz(self, get_business):
        get_business.return_value = ALL_BUSINESS
        HostManager.refresh()
        self.assertEqual(12, len(HostManager.all()))
        new_business_list = ALL_BUSINESS[:2]
        get_business.return_value = new_business_list
        # 删除业务4，减少2台主机
        HostManager.refresh()
        self.assertEqual(8, len(HostManager.all()))

    @mock.patch("alarm_backends.core.cache.cmdb.host.api.cmdb.get_host_without_biz_v2")
    def test_get_using_api(self, get_host_without_biz_v2):
        HostManager.refresh()
        ip, bk_cloud_id = "127.0.0.1", 0
        get_host_without_biz_v2.side_effect = lambda *args, **kwargs: {
            "count": 1,
            "hosts": [Host(bk_host_innerip=ip, bk_cloud_id=bk_cloud_id, bk_host_id=7, bk_biz_id=3).get_attrs()],
        }
        # 没有设置调用 API，拉不到数据
        self.assertIsNone(HostManager.get(ip=ip, bk_cloud_id=bk_cloud_id))
        get_host_without_biz_v2.assert_not_called()

        # 主机已存在，不写 local / 不查 API
        self.assertEqual(HostManager.get(ip="10.0.0.3", bk_cloud_id=3, using_api=True, using_mem=True).bk_biz_id, 3)
        get_host_without_biz_v2.assert_not_called()
        self.assertTrue(HostManager.key_to_internal_value(ip, bk_cloud_id) not in local.host_cache)
        get_host_without_biz_v2.assert_not_called()

        # 穿透缓存走 API 查询
        self.assertEqual(HostManager.get(ip=ip, bk_cloud_id=bk_cloud_id, using_api=True).bk_host_id, 7)
        get_host_without_biz_v2.assert_called_once_with(ips=[ip], bk_cloud_id=[bk_cloud_id], limit=1)
        # 只是实时获取，但没有更新 local
        self.assertTrue(HostManager.key_to_internal_value(ip, bk_cloud_id) not in local.host_cache)

        # 穿透缓存走 API 查询，并设置到 local
        self.assertEqual(HostManager.get(ip=ip, bk_cloud_id=bk_cloud_id, using_api=True, using_mem=True).bk_host_id, 7)

        self.assertTrue(HostManager.key_to_internal_value(ip, bk_cloud_id) in local.host_cache)


class TestHostIDManager(TestCase):
    def setUp(self):
        HostIDManager.clear()

    def tearDown(self):
        HostIDManager.clear()

    def test_serialize(self):
        obj_bin = HostManager.serialize("10.0.0.1|0")
        new_host_obj = HostManager.deserialize(obj_bin)
        self.assertEqual("10.0.0.1|0", new_host_obj)

    def test_key_convert(self):
        self.assertEqual("1", HostIDManager.key_to_internal_value(1))
        self.assertEqual("1", HostIDManager.key_to_internal_value("1"))
        self.assertEqual("1", HostIDManager.key_to_representation("1"))

    def test_refresh(self):
        HostIDManager.refresh()
        host_ids = HostIDManager.cache.hkeys(HostIDManager.CACHE_KEY)
        excepted_host_ids = [HostIDManager.key_to_internal_value(host.bk_host_id) for host in ALL_HOSTS]
        self.assertSetEqual(set(excepted_host_ids), set(host_ids))

    def test_keys(self):
        HostIDManager.refresh()
        host_ids = list(HostIDManager.keys())
        excepted_host_ids = [HostIDManager.key_to_internal_value(host.bk_host_id) for host in ALL_HOSTS]
        self.assertSetEqual(set(excepted_host_ids), set(host_ids))

    def test_get(self):
        HostIDManager.refresh()
        for host in ALL_HOSTS:
            actual_host = HostIDManager.get(host.bk_host_id)
            self.assertEqual("{}|{}".format(host.ip, host.bk_cloud_id), actual_host)

    def test_all(self):
        HostIDManager.refresh()
        host_keys = HostIDManager.all()
        self.assertSetEqual({"{}|{}".format(host.ip, host.bk_cloud_id) for host in ALL_HOSTS}, set(host_keys))


class TestModuleManager(TestCase):
    def setUp(self):
        ModuleManager.clear()

    def tearDown(self):
        ModuleManager.clear()

    def test_serialize(self):
        module_obj = Module(bk_module_id=1, bk_module_name="test_module")
        obj_bin = ModuleManager.serialize(module_obj)
        actual_module_obj = ModuleManager.deserialize(obj_bin)
        self.assertEqual(module_obj, actual_module_obj)

    def test_key_convert(self):
        self.assertEqual("123", ModuleManager.key_to_internal_value(bk_module_id=123))
        self.assertEqual("123", ModuleManager.key_to_internal_value(bk_module_id="123"))
        self.assertEqual(123, ModuleManager.key_to_representation("123"))
        self.assertEqual(123, ModuleManager.key_to_representation(123))

    def test_refresh(self):
        # TODO: mock redis cache
        ModuleManager.refresh()
        module_ids = ModuleManager.cache.hkeys(ModuleManager.CACHE_KEY)
        excepted_module_ids = [ModuleManager.key_to_internal_value(module.bk_module_id) for module in ALL_MODULES]
        self.assertSetEqual(set(module_ids), set(excepted_module_ids))

    def test_keys(self):
        ModuleManager.refresh()
        module_ids = list(ModuleManager.keys())
        excepted_module_ids = [module.bk_module_id for module in ALL_MODULES]
        self.assertSetEqual(set(module_ids), set(excepted_module_ids))

    def test_get(self):
        ModuleManager.refresh()
        for module in ALL_MODULES:
            actual_module = ModuleManager.get(module.bk_module_id)
            self.assertEqual(module, actual_module)

    def test_all(self):
        ModuleManager.refresh()
        modules = ModuleManager.all()
        self.assertSetEqual(set(ALL_MODULES), set(modules))

    def test_clear(self):

        ModuleManager.refresh()
        keys = ModuleManager.cache.hkeys(ModuleManager.CACHE_KEY)
        biz_keys = ModuleManager.cache.hkeys(ModuleManager.get_biz_cache_key())
        biz_keys = [int(key) for key in biz_keys]
        self.assertEqual(len(keys), len(ALL_MODULES))
        self.assertSetEqual(set(biz_keys), set(BIZ_IDS))

        ModuleManager.clear()
        self.assertEqual(len(ModuleManager.cache.hkeys(ModuleManager.CACHE_KEY)), 0)
        self.assertEqual(len(ModuleManager.cache.hkeys(ModuleManager.get_biz_cache_key())), 0)


class TestServiceInstanceManager(TestCase):
    def setUp(self):
        ServiceInstanceManager.clear()

    def tearDown(self):
        ServiceInstanceManager.clear()

    def test_serialize(self):
        instance_obj = ServiceInstance(service_instance_id=1, name="s1", bk_host_id=1, bk_module_id=1)
        obj_bin = ServiceInstanceManager.serialize(instance_obj)
        actual_instance_obj = ServiceInstanceManager.deserialize(obj_bin)
        self.assertEqual(instance_obj, actual_instance_obj)

    def test_key_convert(self):
        self.assertEqual("123", ServiceInstanceManager.key_to_internal_value(service_instance_id=123))
        self.assertEqual("123", ServiceInstanceManager.key_to_internal_value(service_instance_id="123"))
        self.assertEqual(123, ServiceInstanceManager.key_to_representation("123"))
        self.assertEqual(123, ServiceInstanceManager.key_to_representation(123))

    def test_refresh(self):
        # TODO: mock redis cache
        ServiceInstanceManager.refresh()
        instance_ids = ServiceInstanceManager.cache.hkeys(ServiceInstanceManager.CACHE_KEY)
        excepted_instance_ids = [
            ServiceInstanceManager.key_to_internal_value(instance.service_instance_id)
            for instance in ALL_SERVICE_INSTANCES
        ]
        self.assertSetEqual(set(instance_ids), set(excepted_instance_ids))

    def test_keys(self):
        ServiceInstanceManager.refresh()
        instance_ids = list(ServiceInstanceManager.keys())
        excepted_instance_ids = [instance.service_instance_id for instance in ALL_SERVICE_INSTANCES]
        self.assertSetEqual(set(instance_ids), set(excepted_instance_ids))

    def test_get(self):
        ServiceInstanceManager.refresh()
        for instance in ALL_SERVICE_INSTANCES:
            actual_instance = ServiceInstanceManager.get(instance.service_instance_id)
            self.assertEqual(instance, actual_instance)
        # test get topo link
        instance = ServiceInstanceManager.get(1)
        self.assertEqual(instance.topo_link["module|5"][0].id, "module|5")
        self.assertEqual(instance.topo_link["module|5"][1].id, "set|3")
        self.assertEqual(instance.topo_link["module|5"][2].id, "biz|2")
        self.assertEqual(ServiceInstanceManager.get(2).topo_link, {"module|2": []})

    def test_all(self):
        ServiceInstanceManager.refresh()
        instances = ServiceInstanceManager.all()
        self.assertSetEqual(set(ALL_SERVICE_INSTANCES), set(instances))

    def test_clear(self):
        ServiceInstanceManager.refresh()
        keys = ServiceInstanceManager.cache.hkeys(ServiceInstanceManager.CACHE_KEY)
        biz_keys = ServiceInstanceManager.cache.hkeys(ServiceInstanceManager.get_biz_cache_key())
        biz_keys = [int(key) for key in biz_keys]
        self.assertEqual(len(keys), len(ALL_SERVICE_INSTANCES))
        self.assertSetEqual(set(biz_keys), set(BIZ_IDS))

        ServiceInstanceManager.clear()
        self.assertEqual(len(ServiceInstanceManager.cache.hkeys(ServiceInstanceManager.CACHE_KEY)), 0)
        self.assertEqual(len(ServiceInstanceManager.cache.hkeys(ServiceInstanceManager.get_biz_cache_key())), 0)


class TestTopoManager(TestCase):
    def setUp(self):
        TopoManager.clear()
        TopoManager.refresh()

    def tearDown(self):
        TopoManager.clear()

    def test_serialize(self):
        excepted_node = TopoNode(
            bk_inst_id=3,
            bk_inst_name="job",
            bk_obj_id="set",
            bk_obj_name="set",
        )
        obj_bin = TopoManager.serialize(excepted_node)
        node = TopoManager.deserialize(obj_bin)
        self.assertEqual(excepted_node, node)

    def test_key_convert(self):
        self.assertEqual("set|5", TopoManager.key_to_internal_value("set", 5))
        self.assertEqual("set|5", TopoManager.key_to_internal_value("set", "5"))
        self.assertEqual("set|5", TopoManager.key_to_representation("set|5"))

    def test_keys(self):
        keys = list(TopoManager.keys())
        expected_keys = set()
        for node in TOPO_TREE.convert_to_flat_nodes():
            expected_keys.add("{}|{}".format(node.bk_obj_id, node.bk_inst_id))
        self.assertSetEqual(set(keys), set(expected_keys))

    def test_get(self):
        for node in TOPO_TREE.convert_to_flat_nodes():
            actual_node = TopoManager.get(node.bk_obj_id, node.bk_inst_id)
            self.assertEqual(node, actual_node)

    def test_all(self):
        nodes = TopoManager.all()
        self.assertSetEqual(set(TOPO_TREE.convert_to_flat_nodes()), set(nodes))

    def test_clear(self):
        keys = TopoManager.cache.hkeys(TopoManager.CACHE_KEY)
        biz_keys = TopoManager.cache.hkeys(TopoManager.get_biz_cache_key())
        biz_keys = [int(key) for key in biz_keys]
        self.assertEqual(len(keys), len(TOPO_TREE.convert_to_flat_nodes()))
        self.assertSetEqual(set(biz_keys), set(BIZ_IDS))

        TopoManager.clear()
        self.assertEqual(len(TopoManager.cache.hkeys(TopoManager.CACHE_KEY)), 0)
        self.assertEqual(len(TopoManager.cache.hkeys(TopoManager.get_biz_cache_key())), 0)
