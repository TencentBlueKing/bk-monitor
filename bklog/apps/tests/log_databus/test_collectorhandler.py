"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

import copy
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings

from apps.exceptions import ApiResultError
from apps.log_databus.constants import DORIS_CLUSTER_TYPE, STORAGE_CLUSTER_TYPE, LogPluginInfo
from apps.log_databus.handlers.collector.base import CollectorHandler
from apps.log_databus.handlers.collector.host import HostCollectorHandler
from apps.log_databus.models import CollectorConfig

BK_DATA_ID = 1
BK_DATA_NAME = "2_log_test_collector"
TABLE_ID = "2_log.test_table"
SUBSCRIPTION_ID = 2
TASK_ID = 3
NEW_TASK_ID = 4
LAST_TASK_ID = 5
CLUSTER_INFO = [{"cluster_config": {"cluster_id": 1, "cluster_name": "", "port": 123, "domain_name": ""}}]
PARAMS = {
    "bk_biz_id": 706,
    "collector_config_name": "采集项名称",
    "collector_config_name_en": "test_collector",
    "collector_scenario_id": "row",
    "category_id": "application",
    "target_object_type": "HOST",
    "target_node_type": "TOPO",
    "target_nodes": [{"bk_inst_id": 33, "bk_obj_id": "module"}],
    "data_encoding": "UTF-8",
    "bk_data_name": "abc",
    "description": "这是一个描述",
    "params": {
        "paths": ["/log/abc"],
        "exclude_files": ["app"],
        "conditions": {
            "type": "match",
            "match_type": "include",
            "match_content": "delete",
            "separator": "|",
            "separator_filters": [
                {"fieldindex": 1, "word": "val1", "op": "eq", "logic_op": "or"},
                {"fieldindex": 2, "word": "val2", "op": "eq", "logic_op": "or"},
            ],
        },
        "tail_files": True,
        "ignore_older": 1,
        "max_bytes": 1,
    },
    "storage_cluster_id": "default",
    "storage_expires": 1,
}

PART_FAILED_INSTANCE_DATA = {
    "instances": [
        {
            "status": "FAILED",
            "host_statuses": [
                {"status": "UNKNOWN", "version": "3.0.10", "name": "unifytlogc"},
                {"status": "UNKNOWN", "version": "3.0.10", "name": "unifytlogc"},
            ],
            "running_task": None,
            "instance_id": "host|instance|host|127.0.0.1-0-0",
            "create_time": "2019-09-19T20:32:19.957883",
            "instance_info": {
                "host": {
                    "bk_host_name": "rbtnode1",
                    "bk_supplier_account": "0",
                    "bk_cloud_id": [
                        {
                            "bk_obj_name": "",
                            "id": "0",
                            "bk_obj_id": "plat",
                            "bk_obj_icon": "",
                            "bk_inst_id": 0,
                            "bk_inst_name": "default area",
                        }
                    ],
                    "bk_host_innerip": "127.0.0.1",
                },
                "service": {},
            },
        },
        {
            "status": "SUCCESS",
            "host_statuses": [
                {"status": "RUNNING", "version": "3.0.10", "name": "unifytlogc"},
                {"status": "RUNNING", "version": "3.0.10", "name": "unifytlogc"},
            ],
            "running_task": None,
            "instance_id": "host|instance|host|127.0.0.1-0-0",
            "create_time": "2019-09-19T20:32:19.957883",
            "instance_info": {
                "host": {
                    "bk_host_name": "rbtnode1",
                    "bk_supplier_account": "0",
                    "bk_cloud_id": [
                        {
                            "bk_obj_name": "",
                            "id": "0",
                            "bk_obj_id": "plat",
                            "bk_obj_icon": "",
                            "bk_inst_id": 0,
                            "bk_inst_name": "default area",
                        }
                    ],
                    "bk_host_innerip": "127.0.0.1",
                },
                "service": {},
            },
        },
    ],
    "subscription_id": SUBSCRIPTION_ID,
}

CONFIG_DATA = {
    "data_id_config": {"option": {"encoding": "encoding data"}, "data_name": "data name"},
    "result_table_config": "",
    "subscription_config": [
        {
            "steps": [
                {
                    "config": {"plugin_name": LogPluginInfo.NAME, "plugin_version": LogPluginInfo.VERSION},
                    "type": "PLUGIN",
                    "id": LogPluginInfo.NAME,
                    "params": {
                        "context": {
                            "dataid": BK_DATA_ID,
                            "local": [
                                {
                                    "paths": ["testlogic_op"],
                                    "delimiter": "|",
                                    "filters": [
                                        {"conditions": [{"index": 1, "key": "val1", "op": "eq"}]},
                                        {"conditions": [{"index": 1, "key": "val1", "op": "eq"}]},
                                    ],
                                    "encoding": "UTF-8",
                                }
                            ],
                        }
                    },
                }
            ]
        }
    ],
}


class CCModuleTest:
    """
    mock CCApi.search_module
    """

    def bulk_request(self, params=None):
        return []


class CCBizHostsTest:
    """
    mock CCApi.list_biz_hosts
    """

    def bulk_request(self, params=None):
        return []


class CCSetTest:
    """
    mock CCApi.list_biz_hosts
    """

    def bulk_request(self, params=None):
        return []


class CCBizHostsFilterTest:
    """
    mock CCApi.list_biz_hosts
    """

    def bulk_request(self, params=None):
        return [
            {
                "bk_os_name": "",
                "bk_host_id": 2000006651,
                "bk_cloud_id": 0,
                "bk_supplier_account": "tencent",
                "bk_host_innerip": "127.0.0.2",
                "bk_os_type": "1",
            },
        ]


FILTER_ILLEGAL_IPS_BIZ_ID = 215
FILTER_ILLEGAL_IPS_IP_LIST = ["127.0.0.1"]


def subscription_statistic(params):
    return [
        {
            "subscription_id": SUBSCRIPTION_ID,
            "status": [
                {"status": "SUCCESS", "count": 0},
                {"status": "PENDING", "count": 0},
                {"status": "FAILED", "count": 0},
                {"status": "RUNNING", "count": 0},
            ],
            "versions": [],
            "instances": 0,
        }
    ]


def get_data_id(x):
    if x["data_name"] != BK_DATA_NAME:
        raise ApiResultError()
    return {"data_name": BK_DATA_NAME, "bk_data_id": BK_DATA_ID}


@patch("apps.log_databus.tasks.bkdata.async_create_bkdata_data_id.delay", return_value=None)
class TestCollectorHandler(TestCase):
    @staticmethod
    @patch(
        "apps.api.TransferApi.get_data_id",
        get_data_id,
    )
    @patch(
        "apps.api.TransferApi.get_result_table",
        lambda x: {"result_table_id": TABLE_ID} if x["table_id"] == TABLE_ID else {},
    )
    @patch("apps.api.TransferApi.create_data_id", lambda _: {"bk_data_id": BK_DATA_ID})
    @patch("apps.api.NodeApi.create_subscription", lambda _: {"subscription_id": SUBSCRIPTION_ID})
    @patch("apps.api.NodeApi.run_subscription_task", lambda _: {"task_id": TASK_ID})
    def create(params=None, *args, **kwargs):
        """
        创建 CollectorHandler实例对象，并创建一个采集配置
        """

        if params:
            result = HostCollectorHandler().update_or_create(params=params)
        else:
            params = copy.deepcopy(PARAMS)
            params["params"]["conditions"]["type"] = "separator"
            result = HostCollectorHandler().update_or_create(params=params)
        return params, result

    @patch("apps.api.NodeApi.switch_subscription", lambda _: {})
    @patch("apps.decorators.user_operation_record.delay", return_value=None)
    @patch("apps.api.NodeApi.subscription_statistic", subscription_statistic)
    def test_update_or_create(self, *args, **kwargs):
        """
        测试'创建采集配置'函数 CollectorHandler.update_or_create
        """
        params, result = self.create()

        self.assertEqual(result["bk_data_id"], BK_DATA_ID)
        self.assertEqual(result["collector_config_name"], params["collector_config_name"])
        self.assertEqual(result["subscription_id"], SUBSCRIPTION_ID)
        self.assertEqual(result["task_id_list"], [str(TASK_ID)])

    @patch("apps.api.TransferApi.get_cluster_info")
    @patch("apps.utils.thread.MultiExecuteFunc.append")
    @patch("apps.utils.thread.MultiExecuteFunc.run")
    @patch("apps.api.NodeApi.switch_subscription", lambda _: {})
    @patch("apps.api.CCApi.search_biz_inst_topo", lambda _: [])
    @patch("apps.api.CCApi.search_module", CCModuleTest())
    @patch("apps.api.CCApi.search_set", CCSetTest())
    @patch("apps.api.CCApi.list_biz_hosts", CCBizHostsTest())
    @patch("apps.decorators.user_operation_record.delay", return_value=None)
    def test_retrieve(self, mock_run, mock_append, mock_get_cluster_info, *args, **kwargs):
        """
        测试'获取采集配置'函数 CollectorHandler.retrieve
        """
        _, result = self.create()

        mock_append.return_value = ""
        mock_run.return_value = CONFIG_DATA
        mock_get_cluster_info.return_value = CLUSTER_INFO

        collector_config_id = result["collector_config_id"]
        collector = HostCollectorHandler(collector_config_id=collector_config_id)

        res = collector.retrieve()

        self.assertEqual(res.get("data_encoding"), "UTF-8")
        self.assertIsNone(res.get("storage_cluster_id"))
        self.assertIsNone(res.get("retention"))
        self.assertEqual(res.get("collector_config_id"), collector_config_id)
        self.assertEqual(res.get("collector_scenario_id"), "row")
        self.assertEqual(res.get("log_access_type"), "linux")

    @patch("apps.api.CCApi.list_biz_hosts", CCBizHostsFilterTest())
    def test_filter_illegal_ips(self, *args, **kwargs):
        self.assertEqual(
            HostCollectorHandler._filter_illegal_ip_and_host_id(
                bk_biz_id=FILTER_ILLEGAL_IPS_BIZ_ID, ips=FILTER_ILLEGAL_IPS_IP_LIST
            )[0],
            ["127.0.0.1"],
        )


class TestCollectorClusterInfo(TestCase):
    """
    列表补充集群信息时的过期天数映射：ES 存 retention，doris 存 expire_days，对外统一暴露 retention
    """

    ES_TABLE_ID = "2_bklog.retention_es"
    DORIS_TABLE_ID = "2_bklog.retention_doris"
    MISSING_TABLE_ID = "2_bklog.retention_missing"

    @staticmethod
    def _make_row(table_id, storage_cluster_type=STORAGE_CLUSTER_TYPE):
        return {
            "table_id": table_id,
            "storage_cluster_type": storage_cluster_type,
            "category_id": "application",
            "custom_type": "log",
            "created_at": "2026-08-19 10:00:00",
            "updated_at": "2026-08-19 10:00:00",
        }

    @staticmethod
    def _make_cluster_info(cluster_type, storage_config):
        return {
            "cluster_config": {"cluster_id": 1, "cluster_name": "test", "display_name": "test"},
            "storage_config": storage_config,
            "cluster_type": cluster_type,
        }

    # add_cluster_info 内部取时区后做 arrow 转换，独立运行时 get_local_param 返回 None 会抛 TypeError，
    # 不能依赖其它用例残留的线程本地时区
    @patch("apps.log_databus.handlers.collector.base.get_local_param", return_value="Asia/Shanghai")
    @patch.object(CollectorHandler, "bulk_cluster_infos")
    def test_add_cluster_info_maps_storage_expiration_to_retention(self, mock_bulk_cluster_infos, *args, **kwargs):
        mock_bulk_cluster_infos.return_value = {
            self.ES_TABLE_ID: self._make_cluster_info(STORAGE_CLUSTER_TYPE, {"retention": 7}),
            self.DORIS_TABLE_ID: self._make_cluster_info(DORIS_CLUSTER_TYPE, {"expire_days": 30}),
        }

        data = CollectorHandler.add_cluster_info(
            [
                self._make_row(self.ES_TABLE_ID),
                self._make_row(self.DORIS_TABLE_ID, DORIS_CLUSTER_TYPE),
            ]
        )

        self.assertEqual(data[0]["retention"], 7)
        self.assertEqual(data[1]["retention"], 30)

    @patch("apps.log_databus.handlers.collector.base.get_local_param", return_value="Asia/Shanghai")
    @patch.object(CollectorHandler, "bulk_cluster_infos")
    def test_add_cluster_info_doris_ignores_es_retention_field(self, mock_bulk_cluster_infos, *args, **kwargs):
        """doris 结果表即便同时带了 ES 的 retention，也应以 expire_days 为准"""
        mock_bulk_cluster_infos.return_value = {
            self.DORIS_TABLE_ID: self._make_cluster_info(
                DORIS_CLUSTER_TYPE, {"expire_days": 30, "retention": 0}
            ),
        }

        data = CollectorHandler.add_cluster_info([self._make_row(self.DORIS_TABLE_ID, DORIS_CLUSTER_TYPE)])

        self.assertEqual(data[0]["retention"], 30)

    @patch("apps.log_databus.handlers.collector.base.get_local_param", return_value="Asia/Shanghai")
    @patch.object(CollectorHandler, "bulk_cluster_infos")
    def test_add_cluster_info_missing_cluster_info_falls_back_to_zero(self, mock_bulk_cluster_infos, *args, **kwargs):
        """Metadata 未返回集群信息时保持原有兜底行为"""
        mock_bulk_cluster_infos.return_value = {}

        data = CollectorHandler.add_cluster_info([self._make_row(self.MISSING_TABLE_ID, DORIS_CLUSTER_TYPE)])

        self.assertEqual(data[0]["retention"], 0)
        self.assertEqual(data[0]["storage_cluster_id"], -1)


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class TestBulkClusterInfos(TestCase):
    """bulk_cluster_infos 需要把实际使用的存储类型回传给调用方"""

    ES_TABLE_ID = "2_bklog.bulk_es"
    DORIS_TABLE_ID = "2_bklog.bulk_doris"
    UNKNOWN_TABLE_ID = "2_bklog.bulk_unknown"

    def setUp(self):
        cache.clear()
        for table_id, storage_cluster_type in (
            (self.ES_TABLE_ID, STORAGE_CLUSTER_TYPE),
            (self.DORIS_TABLE_ID, DORIS_CLUSTER_TYPE),
        ):
            CollectorConfig.objects.create(
                collector_config_name=table_id,
                collector_config_name_en=table_id.replace(".", "_"),
                collector_scenario_id="row",
                category_id="application",
                bk_biz_id=706,
                table_id=table_id,
                storage_cluster_type=storage_cluster_type,
            )

    @patch("apps.api.TransferApi.get_result_table_storage")
    def test_returns_cluster_type_per_result_table(self, mock_get_result_table_storage):
        def _get_result_table_storage(params):
            return {
                table_id: {"cluster_config": {"cluster_id": 1, "cluster_name": "c"}, "storage_config": {}}
                for table_id in params["result_table_list"].split(",")
            }

        mock_get_result_table_storage.side_effect = _get_result_table_storage

        cluster_infos = CollectorHandler.bulk_cluster_infos(
            result_table_list=[self.ES_TABLE_ID, self.DORIS_TABLE_ID]
        )

        self.assertEqual(cluster_infos[self.ES_TABLE_ID]["cluster_type"], STORAGE_CLUSTER_TYPE)
        self.assertEqual(cluster_infos[self.DORIS_TABLE_ID]["cluster_type"], DORIS_CLUSTER_TYPE)

    @patch("apps.api.TransferApi.get_result_table_storage")
    def test_missing_result_table_still_gets_cluster_type(self, mock_get_result_table_storage):
        """Metadata 查询失败走兜底时，兜底条目同样需要带上存储类型"""
        mock_get_result_table_storage.side_effect = Exception("metadata unavailable")

        cluster_infos = CollectorHandler.bulk_cluster_infos(
            result_table_list=[self.DORIS_TABLE_ID, self.UNKNOWN_TABLE_ID]
        )

        self.assertEqual(cluster_infos[self.DORIS_TABLE_ID]["cluster_type"], DORIS_CLUSTER_TYPE)
        # 未登记的结果表默认按 ES 处理，与 _get_table_id_to_cluster_type_map 保持一致
        self.assertEqual(cluster_infos[self.UNKNOWN_TABLE_ID]["cluster_type"], STORAGE_CLUSTER_TYPE)
