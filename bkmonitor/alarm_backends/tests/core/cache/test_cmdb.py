"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
from unittest import mock

from django.core.cache import caches
from django.test import TestCase

from alarm_backends.core.cache.cmdb import (
    BusinessManager,
    HostManager,
    ModuleManager,
    ServiceInstanceManager,
    SetManager,
    TopoManager,
)
from api.cmdb.define import Business, Host
from bkmonitor.utils.local import local
from constants.common import DEFAULT_TENANT_ID

BIZ_IDS = [2, 3, 4, 5, 6, 10, 20, 21]

ALL_BUSINESS = [Business(bk_biz_id=i) for i in BIZ_IDS]


class TestBusinessManager(TestCase):
    def setUp(self):
        # 初始化测试数据
        test_business = {
            "2": {
                "bk_tenant_id": "test",
                "bk_biz_developer": [],
                "bk_biz_id": 2,
                "bk_biz_maintainer": ["user1", "user2"],
                "bk_biz_name": "蓝鲸",
                "bk_biz_productor": ["admin"],
                "bk_biz_tester": [],
                "bk_created_at": "2019-09-25T14:34:26.49+08:00",
                "bk_supplier_account": "0",
                "bk_updated_at": "2024-11-26T17:43:28.454+08:00",
                "bk_updated_by": ["user1"],
                "create_time": "2019-09-25T14:34:26.49+08:00",
                "default": 0,
                "language": "1",
                "last_time": "2024-11-26T17:43:28.454+08:00",
                "life_cycle": "2",
                "operator": [],
                "time_zone": "Asia/Shanghai",
            },
            "3": {
                "bk_tenant_id": "test",
                "bk_biz_developer": [],
                "bk_biz_id": 3,
                "bk_biz_maintainer": ["user1", "user2"],
                "bk_biz_name": "测试业务1",
                "bk_biz_productor": ["admin"],
                "bk_biz_tester": [],
                "bk_created_at": "2019-09-25T14:34:26.49+08:00",
                "bk_supplier_account": "0",
                "bk_updated_at": "2024-11-26T17:43:28.454+08:00",
                "bk_updated_by": ["user1"],
                "create_time": "2019-09-25T14:34:26.49+08:00",
                "default": 0,
                "language": "1",
                "last_time": "2024-11-26T17:43:28.454+08:00",
                "life_cycle": "2",
                "operator": [],
                "time_zone": "Asia/Shanghai",
            },
            "4": {
                "bk_biz_developer": [],
                "bk_biz_id": 4,
                "bk_biz_maintainer": ["user1", "user2"],
                "bk_biz_name": "无租户业务",
                "bk_biz_productor": ["admin"],
                "bk_biz_tester": [],
                "bk_created_at": "2019-09-25T14:34:26.49+08:00",
                "bk_supplier_account": "0",
                "bk_updated_at": "2024-11-26T17:43:28.454+08:00",
                "bk_updated_by": ["user1"],
                "create_time": "2019-09-25T14:34:26.49+08:00",
                "default": 0,
                "language": "1",
                "last_time": "2024-11-26T17:43:28.454+08:00",
                "life_cycle": "2",
                "operator": [],
                "time_zone": "Asia/Shanghai",
            },
        }
        BusinessManager.cache.delete(BusinessManager.get_cache_key("test"))
        BusinessManager.cache.hmset(
            BusinessManager.get_cache_key("test"),
            {key: json.dumps(biz_data, ensure_ascii=False) for key, biz_data in test_business.items()},
        )

    def tearDown(self):
        super().tearDown()
        BusinessManager.cache.delete(BusinessManager.get_cache_key("test"))

    def test_get(self):
        """测试获取单个业务信息"""
        # 测试获取存在的业务
        business = BusinessManager.get(2)
        assert business is not None  # 类型检查提示
        self.assertEqual(business.bk_biz_id, 2)
        self.assertEqual(business.bk_biz_name, "蓝鲸")
        self.assertEqual(business.bk_tenant_id, "test")
        self.assertEqual(business.bk_biz_maintainer, ["user1", "user2"])
        self.assertEqual(business.bk_biz_developer, [])

        # 测试获取不存在的业务
        self.assertIsNone(BusinessManager.get(999))

    def test_keys(self):
        """测试获取业务ID列表"""
        biz_ids = BusinessManager.keys()
        self.assertSetEqual(set(biz_ids), {2, 3, 4})

    def test_all(self):
        """测试获取所有业务信息"""
        businesses = BusinessManager.all()
        self.assertEqual(len(businesses), 3)

        # 验证业务数据
        biz_dict = {biz.bk_biz_id: biz for biz in businesses}
        self.assertEqual(biz_dict[2].bk_biz_name, "蓝鲸")
        self.assertEqual(biz_dict[3].bk_biz_name, "测试业务1")
        self.assertEqual(biz_dict[4].bk_biz_name, "无租户业务")

    def test_default_tenant_id(self):
        """测试默认租户ID"""
        business = BusinessManager.get(4)
        assert business is not None  # 类型检查提示
        self.assertEqual(business.bk_biz_id, 4)
        self.assertEqual(business.bk_biz_name, "无租户业务")
        self.assertEqual(business.bk_tenant_id, DEFAULT_TENANT_ID)


class TestHostManager(TestCase):
    test_hosts = {
        DEFAULT_TENANT_ID: {
            "127.0.0.1|0": dict(
                bk_host_innerip="127.0.0.1", bk_cloud_id=0, bk_host_id=1, bk_biz_id=2, bk_host_name="default1"
            ),
            "10.0.0.1|1": dict(
                bk_host_innerip="10.0.0.1", bk_cloud_id=1, bk_host_id=2, bk_biz_id=2, bk_host_name="default2"
            ),
        },
        "test": {
            "127.0.0.1|0": dict(
                bk_host_innerip="127.0.0.1", bk_cloud_id=0, bk_host_id=1, bk_biz_id=2, bk_host_name="test1"
            ),
            "10.0.0.2|0": dict(
                bk_host_innerip="10.0.0.2", bk_cloud_id=0, bk_host_id=3, bk_biz_id=2, bk_host_name="test2"
            ),
            "10.0.0.3|3": dict(
                bk_host_innerip="10.0.0.3", bk_cloud_id=3, bk_host_id=4, bk_biz_id=3, bk_host_name="test3"
            ),
        },
    }

    @classmethod
    def setUpClass(cls):
        caches["locmem"].clear()
        local.host_cache = {}

        for tenant_id, hosts in cls.test_hosts.items():
            HostManager.cache.hmset(
                HostManager.get_cache_key(tenant_id),
                {key: json.dumps(host, ensure_ascii=False) for key, host in hosts.items()},
            )

    @classmethod
    def tearDownClass(cls):
        for tenant_id in cls.test_hosts.keys():
            HostManager.cache.delete(HostManager.get_cache_key(tenant_id))

    def test_get_host_key(self):
        self.assertEqual("10.0.0.1|0", HostManager.get_host_key("10.0.0.1", 0))
        self.assertEqual("10.0.0.1|0", HostManager.get_host_key("10.0.0.1", "0"))

    def test_get(self):
        test_tables = [
            (DEFAULT_TENANT_ID, "10.0.0.1", 1, "default2"),
            ("test", "127.0.0.1", 0, "test1"),
            ("test", "10.0.0.2", 0, "test2"),
            ("test", "10.0.0.3", 3, "test3"),
            ("test", "10.0.0.4", 4, None),
        ]

        for bk_tenant_id, ip, bk_cloud_id, bk_host_name in test_tables:
            host = HostManager.get(bk_tenant_id=bk_tenant_id, ip=ip, bk_cloud_id=bk_cloud_id)
            if host is None:
                if bk_host_name is not None:
                    self.fail(
                        f"HostManager.get(bk_tenant_id={bk_tenant_id}, ip={ip}, bk_cloud_id={bk_cloud_id}) is None"
                    )
            else:
                self.assertEqual(host.bk_host_name, bk_host_name)

        # test mem cache
        self.assertEqual(local.host_cache, {})
        for bk_tenant_id, ip, bk_cloud_id, bk_host_name in test_tables:
            host = HostManager.get(bk_tenant_id=bk_tenant_id, ip=ip, bk_cloud_id=bk_cloud_id, using_mem=True)
            if host is None:
                if bk_host_name is not None:
                    self.fail(
                        f"HostManager.get(bk_tenant_id={bk_tenant_id}, ip={ip}, bk_cloud_id={bk_cloud_id}) is None"
                    )
            else:
                self.assertEqual(host.bk_host_name, bk_host_name)
                self.assertIn(f"{bk_tenant_id}.{HostManager.get_host_key(ip, bk_cloud_id)}", local.host_cache)

    def test_mget(self):
        test_tables = [
            (DEFAULT_TENANT_ID, ["10.0.0.1|1", "10.0.0.2|0", "10.0.0.3|3"], ["default2"]),
            ("test", ["127.0.0.1|0", "10.0.0.2|0", "10.0.0.3|3"], ["test1", "test2", "test3"]),
        ]

        for bk_tenant_id, host_keys, bk_host_names in test_tables:
            hosts = HostManager.mget(bk_tenant_id=bk_tenant_id, host_keys=host_keys)
            self.assertEqual(len(hosts), len(bk_host_names))

            for host_key, bk_host_name in zip(host_keys, bk_host_names):
                self.assertEqual(hosts[host_key].bk_host_name, bk_host_name)

    def test_all(self):
        test_tables = [
            (DEFAULT_TENANT_ID, ["127.0.0.1|0", "10.0.0.1|1"]),
            ("test", ["127.0.0.1|0", "10.0.0.2|0", "10.0.0.3|3"]),
        ]
        for bk_tenant_id, host_keys in test_tables:
            hosts = HostManager.all(bk_tenant_id=bk_tenant_id)
            self.assertEqual(len(hosts), len(host_keys))
            for host, host_key in zip(hosts, host_keys):
                self.assertEqual(HostManager.get_host_key(host.ip, host.bk_cloud_id), host_key)

    @mock.patch("alarm_backends.core.cache.cmdb.host.api.cmdb.get_host_without_biz_v2")
    def test_get_using_api(self, get_host_without_biz_v2):
        ip, bk_cloud_id = "10.0.0.4", 4
        get_host_without_biz_v2.side_effect = lambda *args, **kwargs: {
            "count": 1,
            "hosts": [Host(bk_host_innerip=ip, bk_cloud_id=bk_cloud_id, bk_host_id=7, bk_biz_id=3).get_attrs()],
        }
        # 没有设置调用 API，拉不到数据
        self.assertIsNone(HostManager.get(bk_tenant_id=DEFAULT_TENANT_ID, ip=ip, bk_cloud_id=bk_cloud_id))
        get_host_without_biz_v2.assert_not_called()

        # 主机已存在，不写 local / 不查 API
        host = HostManager.get(
            bk_tenant_id=DEFAULT_TENANT_ID, ip="10.0.0.1", bk_cloud_id=1, using_api=True, using_mem=True
        )
        if host is None:
            self.fail(f"HostManager.get(bk_tenant_id={DEFAULT_TENANT_ID}, ip={ip}, bk_cloud_id={bk_cloud_id}) is None")
        self.assertEqual(host.bk_biz_id, 2)
        get_host_without_biz_v2.assert_not_called()

        # 穿透缓存走 API 查询
        host = HostManager.get(bk_tenant_id=DEFAULT_TENANT_ID, ip=ip, bk_cloud_id=bk_cloud_id, using_api=True)
        if host is None:
            self.fail(f"HostManager.get(bk_tenant_id={DEFAULT_TENANT_ID}, ip={ip}, bk_cloud_id={bk_cloud_id}) is None")
        self.assertEqual(host.bk_host_id, 7)
        get_host_without_biz_v2.assert_called_once_with(ips=[ip], bk_cloud_id=[bk_cloud_id], limit=1)
        # 只是实时获取，但没有更新 local
        self.assertTrue(HostManager.get_host_key(ip, bk_cloud_id) not in local.host_cache)

        # 穿透缓存走 API 查询，并设置到 local
        host = HostManager.get(
            bk_tenant_id=DEFAULT_TENANT_ID, ip=ip, bk_cloud_id=bk_cloud_id, using_api=True, using_mem=True
        )
        if host is None:
            self.fail(f"HostManager.get(bk_tenant_id={DEFAULT_TENANT_ID}, ip={ip}, bk_cloud_id={bk_cloud_id}) is None")
        self.assertEqual(host.bk_host_id, 7)
        self.assertTrue(f"{DEFAULT_TENANT_ID}.{HostManager.get_host_key(ip, bk_cloud_id)}" in local.host_cache)


class TestModuleManager(TestCase):
    test_modules = {
        DEFAULT_TENANT_ID: {
            "1": {
                "bk_bak_operator": [],
                "bk_biz_id": 2,
                "bk_created_at": "2019-09-25T14:34:26.559+08:00",
                "bk_module_id": 1,
                "bk_module_name": "zookeeper",
                "bk_module_type": "1",
                "bk_parent_id": 1,
                "bk_set_id": 1,
                "bk_supplier_account": "0",
                "bk_updated_at": "2021-07-01T10:09:25.878+08:00",
                "create_time": "2019-09-25T14:34:26.559+08:00",
                "default": 0,
                "host_apply_enabled": True,
                "last_time": "2021-07-01T10:09:25.878+08:00",
                "operator": [],
                "service_category_id": 2,
                "service_template_id": 44,
                "set_template_id": 0,
            },
            "2": {
                "bk_bak_operator": [],
                "bk_biz_id": 2,
                "bk_created_at": "2019-09-25T14:34:26.559+08:00",
                "bk_module_id": 2,
                "bk_module_name": "kafka",
                "bk_module_type": "1",
                "bk_parent_id": 2,
                "bk_set_id": 2,
                "bk_supplier_account": "0",
                "bk_updated_at": "2021-07-01T10:09:25.878+08:00",
                "create_time": "2019-09-25T14:34:26.559+08:00",
                "default": 0,
                "host_apply_enabled": True,
                "last_time": "2021-07-01T10:09:25.878+08:00",
                "operator": [],
                "service_category_id": 2,
                "service_template_id": 44,
                "set_template_id": 0,
            },
        },
        "test": {
            "3": {
                "bk_bak_operator": [],
                "bk_biz_id": 3,
                "bk_created_at": "2019-09-25T14:34:26.559+08:00",
                "bk_module_id": 3,
                "bk_module_name": "test3",
                "bk_module_type": "1",
                "bk_parent_id": 3,
                "bk_set_id": 3,
                "bk_supplier_account": "0",
                "bk_updated_at": "2021-07-01T10:09:25.878+08:00",
                "create_time": "2019-09-25T14:34:26.559+08:00",
                "default": 0,
                "host_apply_enabled": True,
                "last_time": "2021-07-01T10:09:25.878+08:00",
                "operator": [],
                "service_category_id": 2,
            },
        },
    }

    @classmethod
    def setUpClass(cls):
        for tenant_id, modules in cls.test_modules.items():
            ModuleManager.cache.hmset(
                ModuleManager.get_cache_key(tenant_id),
                {key: json.dumps(module, ensure_ascii=False) for key, module in modules.items()},
            )

    @classmethod
    def tearDownClass(cls):
        for tenant_id in cls.test_modules.keys():
            ModuleManager.cache.delete(ModuleManager.get_cache_key(tenant_id))

    def test_get(self):
        test_tables = [
            (DEFAULT_TENANT_ID, 1, "zookeeper"),
            (DEFAULT_TENANT_ID, 2, "kafka"),
            ("test", 3, "test3"),
            ("test", 4, None),
        ]
        for bk_tenant_id, bk_module_id, bk_module_name in test_tables:
            module = ModuleManager.get(bk_tenant_id=bk_tenant_id, bk_module_id=bk_module_id)
            if module is None:
                if bk_module_name is not None:
                    self.fail(f"ModuleManager.get(bk_tenant_id={bk_tenant_id}, bk_module_id={bk_module_id}) is None")
            else:
                self.assertEqual(module.bk_module_name, bk_module_name)

    def test_mget(self):
        test_tables = [
            (DEFAULT_TENANT_ID, [1, 2], ["zookeeper", "kafka"]),
            ("test", [3, 4], ["test3"]),
        ]
        for bk_tenant_id, bk_module_ids, bk_module_names in test_tables:
            modules = ModuleManager.mget(bk_tenant_id=bk_tenant_id, bk_module_ids=bk_module_ids)
            self.assertEqual(len(modules), len(bk_module_names))
            for bk_module_id, bk_module_name in zip(bk_module_ids, bk_module_names):
                self.assertEqual(modules[bk_module_id].bk_module_name, bk_module_name)


class TestSetManager(TestCase):
    test_sets = {
        DEFAULT_TENANT_ID: {
            "1": {
                "bk_biz_id": 2,
                "bk_capacity": None,
                "bk_created_at": "2019-10-23T10:47:41.411+08:00",
                "bk_parent_id": 2,
                "bk_service_status": "1",
                "bk_set_desc": "",
                "bk_set_env": "1",
                "bk_set_id": 1,
                "bk_set_name": "test1",
                "bk_supplier_account": "0",
                "bk_updated_at": "2019-10-23T10:47:41.411+08:00",
                "create_time": "2019-10-23T10:47:41.411+08:00",
                "default": 1,
                "description": "",
                "last_time": "2019-10-23T10:47:41.411+08:00",
                "set_template_id": 0,
            },
            "2": {
                "bk_biz_id": 2,
                "bk_capacity": None,
                "bk_created_at": "2019-10-23T10:47:41.411+08:00",
                "bk_parent_id": 2,
                "bk_service_status": "1",
                "bk_set_desc": "",
                "bk_set_env": "1",
                "bk_set_id": 2,
                "bk_set_name": "test2",
                "bk_supplier_account": "0",
                "bk_updated_at": "2019-10-23T10:47:41.411+08:00",
                "create_time": "2019-10-23T10:47:41.411+08:00",
                "default": 1,
                "description": "",
                "last_time": "2019-10-23T10:47:41.411+08:00",
                "set_template_id": 0,
            },
        },
        "test": {
            "3": {
                "bk_biz_id": 3,
                "bk_capacity": None,
                "bk_created_at": "2019-10-23T10:47:41.411+08:00",
                "bk_parent_id": 3,
                "bk_service_status": "1",
                "bk_set_desc": "",
                "bk_set_env": "1",
                "bk_set_id": 3,
                "bk_set_name": "test3",
                "bk_supplier_account": "0",
                "bk_updated_at": "2019-10-23T10:47:41.411+08:00",
                "create_time": "2019-10-23T10:47:41.411+08:00",
                "default": 1,
                "description": "",
                "last_time": "2019-10-23T10:47:41.411+08:00",
                "set_template_id": 0,
            },
        },
    }

    @classmethod
    def setUpClass(cls):
        for tenant_id, sets in cls.test_sets.items():
            SetManager.cache.hmset(
                SetManager.get_cache_key(tenant_id),
                {key: json.dumps(set_data, ensure_ascii=False) for key, set_data in sets.items()},
            )

    @classmethod
    def tearDownClass(cls):
        for tenant_id in cls.test_sets.keys():
            SetManager.cache.delete(SetManager.get_cache_key(tenant_id))

    def test_get(self):
        test_tables = [
            (DEFAULT_TENANT_ID, 1, "test1"),
            (DEFAULT_TENANT_ID, 2, "test2"),
            ("test", 3, "test3"),
            ("test", 4, None),
        ]
        for bk_tenant_id, bk_set_id, bk_set_name in test_tables:
            set_obj = SetManager.get(bk_tenant_id=bk_tenant_id, bk_set_id=bk_set_id)
            if set_obj is None:
                if bk_set_name is not None:
                    self.fail(f"SetManager.get(bk_tenant_id={bk_tenant_id}, bk_set_id={bk_set_id}) is None")
            else:
                self.assertEqual(set_obj.bk_set_name, bk_set_name)

    def test_mget(self):
        test_tables = [
            (DEFAULT_TENANT_ID, [1, 2], ["test1", "test2"]),
            ("test", [3, 4], ["test3"]),
        ]
        for bk_tenant_id, bk_set_ids, bk_set_names in test_tables:
            sets = SetManager.mget(bk_tenant_id=bk_tenant_id, bk_set_ids=bk_set_ids)
            self.assertEqual(len(sets), len(bk_set_names))
            for bk_set_id, bk_set_name in zip(bk_set_ids, bk_set_names):
                self.assertEqual(sets[bk_set_id].bk_set_name, bk_set_name)


class TestServiceInstanceManager(TestCase):
    test_service_instances = {
        DEFAULT_TENANT_ID: {
            "1": {
                "service_instance_id": 1,
                "name": "127.0.0.1_kafka_broker_9092",
                "bk_host_id": 1,
                "bk_module_id": 1,
                "service_category_id": 0,
                "labels": {},
                "ip": "127.0.0.1",
                "bk_cloud_id": 0,
                "bk_biz_id": 2,
                "id": 1,
                "service_template_id": 1,
                "creator": "admin",
                "modifier": "admin",
                "create_time": "2023-12-14T15:00:16.835Z",
                "last_time": "2023-12-14T15:00:16.835Z",
                "bk_supplier_account": "0",
                "process_instances": [
                    {
                        "process": {
                            "proc_num": None,
                            "stop_cmd": "",
                            "restart_cmd": "",
                            "face_stop_cmd": "",
                            "bk_process_id": 1,
                            "bk_func_name": "java",
                            "work_path": "",
                            "priority": None,
                            "reload_cmd": "",
                            "bk_process_name": "kafka_broker",
                            "pid_file": "",
                            "auto_start": None,
                            "bk_start_check_secs": None,
                            "last_time": "2023-12-14T15:00:17.023Z",
                            "create_time": "2023-12-14T15:00:17.023Z",
                            "bk_biz_id": 2,
                            "start_cmd": "",
                            "user": "",
                            "timeout": None,
                            "description": "",
                            "bk_supplier_account": "0",
                            "bk_start_param_regex": "/data/kafka/broker/bin/",
                            "service_instance_id": 1,
                            "bind_info": [
                                {
                                    "enable": False,
                                    "ip": "127.0.0.1",
                                    "port": "9092",
                                    "protocol": "1",
                                    "template_row_id": 1,
                                }
                            ],
                        },
                        "relation": {
                            "bk_biz_id": 2,
                            "bk_process_id": 1,
                            "service_instance_id": 1,
                            "process_template_id": 1,
                            "bk_host_id": 1,
                            "bk_supplier_account": "0",
                        },
                    }
                ],
                "topo_link": {
                    "module|1": [
                        {"bk_obj_id": "module", "bk_inst_id": 1, "bk_obj_name": "zookeeper"},
                        {"bk_obj_id": "set", "bk_inst_id": 1, "bk_obj_name": "test1"},
                        {"bk_obj_id": "biz", "bk_inst_id": 2, "bk_obj_name": "test2"},
                    ]
                },
            },
        },
        "test": {
            "2": {
                "service_instance_id": 2,
                "name": "127.0.0.2_kafka_broker_9092",
                "bk_host_id": 2,
                "bk_module_id": 2,
                "service_category_id": 0,
                "labels": {},
                "ip": "127.0.0.2",
                "bk_cloud_id": 0,
                "bk_biz_id": 3,
                "id": 2,
                "service_template_id": 2,
                "creator": "admin",
                "modifier": "admin",
                "create_time": "2023-12-14T15:00:16.835Z",
                "last_time": "2023-12-14T15:00:16.835Z",
                "bk_supplier_account": "0",
                "process_instances": [],
                "topo_link": {
                    "module|2": [
                        {"bk_obj_id": "module", "bk_inst_id": 2, "bk_obj_name": "kafka"},
                        {"bk_obj_id": "set", "bk_inst_id": 2, "bk_obj_name": "test2"},
                        {"bk_obj_id": "biz", "bk_inst_id": 3, "bk_obj_name": "test3"},
                    ]
                },
            },
        },
    }

    @classmethod
    def setUpClass(cls):
        for tenant_id, service_instances in cls.test_service_instances.items():
            host_to_service_instance_id_cache = {}
            ServiceInstanceManager.cache.hmset(
                ServiceInstanceManager.get_cache_key(tenant_id),
                {
                    key: json.dumps(service_instance, ensure_ascii=False)
                    for key, service_instance in service_instances.items()
                },
            )
            for service_instance in service_instances.values():
                host_to_service_instance_id_cache[service_instance["bk_host_id"]] = [
                    service_instance["service_instance_id"]
                ]

            ServiceInstanceManager.cache.hmset(
                ServiceInstanceManager.get_host_to_service_instance_id_cache_key(tenant_id),
                {
                    str(host_id): json.dumps(service_instance_ids, ensure_ascii=False)
                    for host_id, service_instance_ids in host_to_service_instance_id_cache.items()
                },
            )

    @classmethod
    def tearDownClass(cls):
        for tenant_id in cls.test_service_instances.keys():
            ServiceInstanceManager.cache.delete(ServiceInstanceManager.get_cache_key(tenant_id))
            ServiceInstanceManager.cache.delete(
                ServiceInstanceManager.get_host_to_service_instance_id_cache_key(tenant_id)
            )

    def test_get_service_instance_id_by_host(self):
        self.assertEqual(
            ServiceInstanceManager.get_service_instance_id_by_host(bk_tenant_id=DEFAULT_TENANT_ID, bk_host_id=1), [1]
        )
        self.assertEqual(
            ServiceInstanceManager.get_service_instance_id_by_host(bk_tenant_id=DEFAULT_TENANT_ID, bk_host_id=2), []
        )
        self.assertEqual(ServiceInstanceManager.get_service_instance_id_by_host(bk_tenant_id="test", bk_host_id=2), [2])

    def test_get(self):
        instance = ServiceInstanceManager.get(bk_tenant_id=DEFAULT_TENANT_ID, service_instance_id=1)
        if instance is None:
            self.fail(f"ServiceInstanceManager.get(bk_tenant_id={DEFAULT_TENANT_ID}, service_instance_id=1) is None")
        else:
            self.assertEqual(instance.name, "127.0.0.1_kafka_broker_9092")
            self.assertEqual(instance.bk_host_id, 1)
            self.assertEqual(instance.bk_module_id, 1)
            self.assertEqual(instance.service_category_id, 0)
            self.assertEqual(instance.topo_link["module|1"][0].id, "module|1")

    def test_mget(self):
        instances = ServiceInstanceManager.mget(bk_tenant_id=DEFAULT_TENANT_ID, service_instance_ids=[1])
        self.assertEqual(len(instances), 1)
        self.assertEqual(instances[1].name, "127.0.0.1_kafka_broker_9092")
        instances = ServiceInstanceManager.mget(bk_tenant_id="test", service_instance_ids=[2])
        self.assertEqual(len(instances), 1)
        self.assertEqual(instances[2].name, "127.0.0.2_kafka_broker_9092")


class TestTopoManager(TestCase):
    test_topo_nodes = {
        DEFAULT_TENANT_ID: {
            "module|1": {
                "bk_obj_id": "module",
                "bk_inst_id": 1,
                "bk_obj_name": "模块",
                "bk_inst_name": "zookeeper",
            },
            "set|1": {
                "bk_obj_id": "set",
                "bk_inst_id": 1,
                "bk_obj_name": "集群",
                "bk_inst_name": "test1",
            },
            "biz|2": {
                "bk_obj_id": "biz",
                "bk_inst_id": 2,
                "bk_obj_name": "业务",
                "bk_inst_name": "蓝鲸",
            },
        },
        "test": {
            "module|2": {
                "bk_obj_id": "module",
                "bk_inst_id": 2,
                "bk_obj_name": "模块",
                "bk_inst_name": "kafka",
            },
            "set|2": {
                "bk_obj_id": "set",
                "bk_inst_id": 2,
                "bk_obj_name": "集群",
                "bk_inst_name": "test2",
            },
            "biz|3": {
                "bk_obj_id": "biz",
                "bk_inst_id": 3,
                "bk_obj_name": "业务",
                "bk_inst_name": "测试业务",
            },
        },
    }

    @classmethod
    def setUpClass(cls):
        for tenant_id, topo_nodes in cls.test_topo_nodes.items():
            TopoManager.cache.hmset(
                TopoManager.get_cache_key(tenant_id),
                {key: json.dumps(topo_node, ensure_ascii=False) for key, topo_node in topo_nodes.items()},
            )

    @classmethod
    def tearDownClass(cls):
        for tenant_id in cls.test_topo_nodes.keys():
            TopoManager.cache.delete(TopoManager.get_cache_key(tenant_id))

    def test_get(self):
        test_tables = [
            (DEFAULT_TENANT_ID, "module", 1, "zookeeper"),
            (DEFAULT_TENANT_ID, "set", 1, "test1"),
            (DEFAULT_TENANT_ID, "biz", 2, "蓝鲸"),
            ("test", "module", 2, "kafka"),
            ("test", "set", 2, "test2"),
            ("test", "biz", 3, "测试业务"),
        ]
        for bk_tenant_id, bk_obj_id, bk_inst_id, bk_inst_name in test_tables:
            node = TopoManager.get(bk_tenant_id=bk_tenant_id, bk_obj_id=bk_obj_id, bk_inst_id=bk_inst_id)
            if node is None:
                if bk_inst_name is not None:
                    self.fail(
                        f"TopoManager.get(bk_tenant_id={bk_tenant_id}, bk_obj_id={bk_obj_id}, bk_inst_id={bk_inst_id}) is None"
                    )
            else:
                self.assertEqual(node.bk_obj_id, bk_obj_id)
                self.assertEqual(node.bk_inst_id, bk_inst_id)
                self.assertEqual(node.bk_inst_name, bk_inst_name)
