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


import copy
import json
import os

import mock
from django.conf import settings
from django.test import TestCase, override_settings
from django.utils.translation import gettext as _

from core.drf_resource import APIResource
from monitor_web.models import (
    CollectorPluginConfig,
    CollectorPluginInfo,
    PluginVersionHistory,
)
from monitor_web.models.plugin import CollectorPluginMeta
from monitor_web.plugin.constant import DebugStatus, PluginType

metric_json = [
    {
        "fields": [
            {
                "type": "double",  # 字段类型
                "monitor_type": "metric",  # 指标类型（metric or dimension）
                "unit": "none",  # 单位
                "name": "disk_usage",  # 字段名（指标或维度名）
                "source_name": "",  # 原指标名
                "description": "disk_usage_1",  # 描述（别名）
                "is_active": True,  # 是否启用
                "is_diff_metric": False,  # 是否差值指标
                "dimensions": ["disk_name"],
            },
            {
                "type": "string",
                "monitor_type": "dimension",
                "unit": "none",
                "name": "disk_name",
                "source_name": "",
                "description": "disk_name_1",
                "is_active": True,
            },
        ],
        "table_name": "base",
        "table_desc": "123",
    }
]


# class TestPluginViewSet(TestCase):
#     def setUp(self):
#         settings.CELERY_ALWAYS_EAGER = True
#
#     def tearDown(self):
#         CollectorPluginMeta.objects.all().delete()
#         CollectorPluginConfig.objects.all().delete()
#         CollectorPluginInfo.objects.all().delete()
#         PluginVersionHistory.objects.all().delete()
#         settings.CELERY_ALWAYS_EAGER = False
#
#     def create_models(self):
#         metrics = copy.deepcopy(metric_json)
#         metrics[0]["fields"][1]["is_diff_metric"] = False
#         plugin = CollectorPluginMeta.objects.create(plugin_id="test_r", plugin_type=PluginType.DATADOG, label="test")
#         config = CollectorPluginConfig.objects.create(
#             config_json=[],
#             collector_json={
#                 "linux": {"filename": "test.sh", "type": "shell", "script_content_base64": "IyEvYmluL3NoCmVja"}
#             },
#         )
#         info = CollectorPluginInfo.objects.create(plugin_display_name="test", metric_json=metrics)
#         PluginVersionHistory.objects.create(
#             plugin=plugin, config=config, info=info, config_version=1, info_version=1, stage="release", is_packaged=True
#         )
#         PluginVersionHistory.objects.create(
#             plugin=plugin,
#             config=config,
#             info=info,
#             config_version=1,
#             info_version=2,
#             stage="release",
#             is_packaged=False,
#         )
#
#     @override_settings(MIDDLEWARE=("monitor_web.tests.middlewares.OverrideMiddleware",))
#     def test_data_dog_plugin(self):
#         path = "/rest/v2/data_dog_plugin/"
#         file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_file", "bkplugin_consul-1.1.tgz")
#         with open(file_path, "rb") as fp:
#             post_data = {"file_data": fp, "os": "linux"}
#             response = self.client.post(path=path, data=post_data)
#             content = json.loads(response.content)
#             self.assertEqual(response.status_code, 200)
#             self.assertEqual(content["data"]["datadog_check_name"], "consul")
#
#     @override_settings(MIDDLEWARE=("monitor_web.tests.middlewares.OverrideMiddleware",))
#     @mock.patch.object(APIResource, "perform_request")
#     def test_metric_plugin_no_change(self, mock_api):
#         def mock_request(*args, **kwargs):
#             if "data_name" in args[0]:
#                 return {"data_id": "123"}
#             elif "datasource_type" in args[0]:
#                 return [{"table_id": "datadog_test_r.base", "table_name_zh": "base"}]
#             return {"result": "success"}
#
#         mock_api.side_effect = mock_request
#         path = "/rest/v2/metric_plugin/save/"
#
#         post_data = {
#             "plugin_id": "test_r",
#             "plugin_type": PluginType.DATADOG,
#             "config_version": 1,
#             "info_version": 1,
#             "need_upgrade": False,
#             "metric_json": metric_json,
#         }
#         self.create_models()
#         response = self.client.post(path=path, data=json.dumps(post_data), content_type="application/json")
#         content = json.loads(response.content)
#         self.assertEqual(response.status_code, 200)
#         self.assertEqual(content["data"]["config_version"], 1)
#         self.assertEqual(content["data"]["info_version"], 1)
#
#     @override_settings(MIDDLEWARE=("monitor_web.tests.middlewares.OverrideMiddleware",))
#     @mock.patch.object(APIResource, "perform_request")
#     def test_metric_plugin_info_change(self, mock_api):
#         def mock_request(*args, **kwargs):
#             if "data_name" in args[0]:
#                 return {"data_id": "123"}
#             elif "datasource_type" in args[0]:
#                 return [{"table_id": "datadog_test_r.base", "table_name_zh": "base"}]
#             return {"result": "success"}
#
#         mock_api.side_effect = mock_request
#         path = "/rest/v2/metric_plugin/save/"
#
#         metric_data = copy.deepcopy(metric_json)
#         metric_data[0]["fields"][0]["description"] = "disk_usage_2"
#         post_data = {
#             "plugin_id": "test_r",
#             "plugin_type": PluginType.DATADOG,
#             "config_version": 1,
#             "info_version": 1,
#             "need_upgrade": False,
#             "metric_json": metric_data,
#         }
#         self.create_models()
#         response = self.client.post(path=path, data=json.dumps(post_data), content_type="application/json")
#         content = json.loads(response.content)
#         self.assertEqual(response.status_code, 200)
#         self.assertEqual(content["data"]["config_version"], 1)
#         self.assertEqual(content["data"]["info_version"], 2)
#
#     @override_settings(MIDDLEWARE=("monitor_web.tests.middlewares.OverrideMiddleware",))
#     @mock.patch.object(APIResource, "perform_request")
#     def test_metric_plugin_need_upgrade(self, mock_api):
#         def mock_request(*args, **kwargs):
#             if "data_name" in args[0]:
#                 return {"data_id": "123"}
#             elif "datasource_type" in args[0]:
#                 return [{"table_id": "datadog_test_r.base", "table_name_zh": "base"}]
#             return {"result": "success"}
#
#         mock_api.side_effect = mock_request
#
#         path = "/rest/v2/metric_plugin/save/"
#
#         metric_data = copy.deepcopy(metric_json)
#         metric_data[0]["fields"][0]["description"] = "disk_usage_2"
#         post_data = {
#             "plugin_id": "test_r",
#             "plugin_type": PluginType.DATADOG,
#             "config_version": 1,
#             "info_version": 1,
#             "need_upgrade": True,
#             "metric_json": metric_data,
#         }
#         self.create_models()
#         response = self.client.post(path=path, data=json.dumps(post_data), content_type="application/json")
#         print(response.content)
#         content = json.loads(response.content)
#         self.assertEqual(response.status_code, 200)
#         self.assertEqual(content["data"]["config_version"], 1)
#         self.assertEqual(content["data"]["info_version"], 2)
#
#     @override_settings(MIDDLEWARE=("monitor_web.tests.middlewares.OverrideMiddleware",))
#     def test_operate_system(self):
#         path = "/rest/v2/collector_plugin/operator_system/"
#         response = self.client.get(path=path)
#         content = json.loads(response.content)
#         self.assertEqual(response.status_code, 200)
#         expected_value = [{"os_type": "linux", "os_type_id": "1"}, {"os_type": "windows", "os_type_id": "2"}]
#         self.assertEqual(content["data"], expected_value)
#
#     @override_settings(MIDDLEWARE=("monitor_web.tests.middlewares.OverrideMiddleware",))
#     @mock.patch.object(APIResource, "perform_request")
#     def test_debug_log_comm(self, mock_api):
#         file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_file", "log_content_comm.json")
#         with open(file_path, "r") as fp:
#             message = json.load(fp)["data"]["log_content"]
#             mock_api.return_value = {"message": message, "step": "DEBUG_PROCESS", "status": DebugStatus.SUCCESS}
#         path = "/rest/v2/collector_plugin/test_r/fetch_debug_log/"
#         self.create_models()
#         response = self.client.get(path=path, data={"task_id": "12345"})
#         content = json.loads(response.content)
#         self.assertEqual(response.status_code, 200)
#         expected_value = [
#             {
#                 "metric_name": "disk_usage",
#                 "metric_value": 0.75,
#                 "dimensions": [{"dimension_name": "disk_name", "dimension_value": "disk01"}],
#             }
#         ]
#         self.assertEqual(content["data"]["metric_json"], expected_value)
#
#     @override_settings(MIDDLEWARE=("monitor_web.tests.middlewares.OverrideMiddleware",))
#     @mock.patch.object(APIResource, "perform_request")
#     def test_debug_log_error(self, mock_api):
#         file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_file", "log_content_comm.json")
#         with open(file_path, "r") as fp:
#             message = json.load(fp)["data"]["log_content"]
#             mock_api.return_value = {"message": message, "step": "DEBUG_PROCESS", "status": DebugStatus.SUCCESS}
#         path = "/rest/v2/collector_plugin/test_r/fetch_debug_log/"
#         self.create_models()
#         response = self.client.get(path=path, data={"task_id": "12345"})
#         content = json.loads(response.content)
#         self.assertEqual(response.status_code, 200)
#         error_desc = content["data"]["log_content"].split("\n")[-1]
#         self.assertEqual(error_desc, _("脚本运行报错,原因是[run script timeout]"))
#
#     @override_settings(MIDDLEWARE=("monitor_web.tests.middlewares.OverrideMiddleware",))
#     @mock.patch.object(APIResource, "perform_request")
#     def test_debug_log_exporter(self, mock_api):
#         file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_file", "log_content_exporter.json")
#         with open(file_path, "r") as fp:
#             message = json.load(fp)["data"]["log_content"]
#             mock_api.return_value = {"message": message, "step": "DEBUG_PROCESS", "status": DebugStatus.SUCCESS}
#         path = "/rest/v2/collector_plugin/test_r/fetch_debug_log/"
#         self.create_models()
#         response = self.client.get(path=path, data={"task_id": "12345"})
#         content = json.loads(response.content)
#         self.assertEqual(response.status_code, 200)
#         expected_value = [
#             {
#                 "metric_name": "go_gc_duration_seconds",
#                 "metric_value": 0,
#                 "dimensions": [{"dimension_name": "quantile", "dimension_value": "0"}],
#             },
#             {"metric_name": "go_gc_duration_seconds_sum", "metric_value": 0, "dimensions": []},
#             {"metric_name": "go_gc_duration_seconds_count", "metric_value": 0, "dimensions": []},
#             {"metric_name": "go_goroutines", "metric_value": 8, "dimensions": []},
#             {
#                 "metric_name": "go_info",
#                 "metric_value": 1,
#                 "dimensions": [{"dimension_name": "version", "dimension_value": "go1.12.7"}],
#             },
#             {"metric_name": "go_memstats_alloc_bytes", "metric_value": 518144, "dimensions": []},
#             {"metric_name": "go_memstats_alloc_bytes_total", "metric_value": 518144, "dimensions": []},
#             {"metric_name": "go_memstats_buck_hash_sys_bytes", "metric_value": 2740, "dimensions": []},
#             {"metric_name": "go_memstats_frees_total", "metric_value": 150, "dimensions": []},
#             {"metric_name": "go_memstats_gc_cpu_fraction", "metric_value": 0, "dimensions": []},
#             {"metric_name": "go_memstats_gc_sys_bytes", "metric_value": 2240512.0, "dimensions": []},
#             {"metric_name": "go_memstats_heap_alloc_bytes", "metric_value": 518144, "dimensions": []},
#             {"metric_name": "go_memstats_heap_idle_bytes", "metric_value": 65101824.0, "dimensions": []},
#             {"metric_name": "go_memstats_heap_inuse_bytes", "metric_value": 1515520.0, "dimensions": []},
#             {"metric_name": "go_memstats_heap_objects", "metric_value": 2226, "dimensions": []},
#             {"metric_name": "go_memstats_heap_released_bytes", "metric_value": 0, "dimensions": []},
#             {"metric_name": "go_memstats_heap_sys_bytes", "metric_value": 66617344.0, "dimensions": []},
#             {"metric_name": "go_memstats_last_gc_time_seconds", "metric_value": 0, "dimensions": []},
#             {"metric_name": "go_memstats_lookups_total", "metric_value": 0, "dimensions": []},
#             {"metric_name": "go_memstats_mallocs_total", "metric_value": 2376, "dimensions": []},
#             {"metric_name": "go_memstats_mcache_inuse_bytes", "metric_value": 13888, "dimensions": []},
#             {"metric_name": "go_memstats_mcache_sys_bytes", "metric_value": 16384, "dimensions": []},
#             {"metric_name": "go_memstats_mspan_inuse_bytes", "metric_value": 21888, "dimensions": []},
#             {"metric_name": "go_memstats_mspan_sys_bytes", "metric_value": 32768, "dimensions": []},
#             {"metric_name": "go_memstats_next_gc_bytes", "metric_value": 4473924.0, "dimensions": []},
#             {"metric_name": "go_memstats_other_sys_bytes", "metric_value": 789836, "dimensions": []},
#             {"metric_name": "go_memstats_stack_inuse_bytes", "metric_value": 491520, "dimensions": []},
#             {"metric_name": "go_memstats_stack_sys_bytes", "metric_value": 491520, "dimensions": []},
#             {"metric_name": "go_memstats_sys_bytes", "metric_value": 70191104.0, "dimensions": []},
#             {"metric_name": "go_threads", "metric_value": 8, "dimensions": []},
#             {"metric_name": "nginx_exporter_scrape_failures_total", "metric_value": 1, "dimensions": []},
#             {"metric_name": "nginx_up", "metric_value": 0, "dimensions": []},
#             {"metric_name": "process_cpu_seconds_total", "metric_value": 0, "dimensions": []},
#             {"metric_name": "process_max_fds", "metric_value": 102400, "dimensions": []},
#             {"metric_name": "process_open_fds", "metric_value": 7, "dimensions": []},
#             {"metric_name": "process_resident_memory_bytes", "metric_value": 4726784.0, "dimensions": []},
#             {"metric_name": "process_start_time_seconds", "metric_value": 1581562110.71, "dimensions": []},
#             {"metric_name": "process_virtual_memory_bytes", "metric_value": 237633536.0, "dimensions": []},
#             {"metric_name": "process_virtual_memory_max_bytes", "metric_value": -1, "dimensions": []},
#             {"metric_name": "promhttp_metric_handler_requests_in_flight", "metric_value": 1, "dimensions": []},
#             {
#                 "metric_name": "promhttp_metric_handler_requests_total",
#                 "metric_value": 0,
#                 "dimensions": [{"dimension_name": "code", "dimension_value": "200"}],
#             },
#         ]
#         self.assertEqual(content["data"]["metric_json"], expected_value)
#
#     @override_settings(MIDDLEWARE=("monitor_web.tests.middlewares.OverrideMiddleware",))
#     def test_create_plugin(self):
#         file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_file", "collector_info")
#         with open(file_path, "r", encoding="utf-8") as fp:
#             collector_info = fp.read()
#         config_info = [
#             {
#                 "description": "111",
#                 "default": "python",
#                 "visible": False,
#                 "mode": "collector",
#                 "type": "text",
#                 "name": "python_path",
#             },
#             {
#                 "default": "http://localhost:8500",
#                 "mode": "opt_cmd",
#                 "type": "text",
#                 "description": "111",
#                 "name": "instance_url",
#             },
#         ]
#         post_data = {
#             "bk_biz_id": 2,
#             "plugin_id": "aaz",
#             "plugin_display_name": "aaz",
#             "plugin_type": "DataDog",
#             "logo": "",
#             "collector_json": {
#                 "windows": {"file_id": "123", "file_name": "aaz.sh", "md5": "12345"},
#                 "datadog_check_name": "consul",
#                 "config_yaml": collector_info,
#                 "linux": {"file_id": "345", "file_name": "aaz.sh", "md5": "54321"},
#             },
#             "config_json": config_info,
#             "metric_json": [
#                 {
#                     "fields": [
#                         {
#                             "type": "double",
#                             "monitor_type": "metric",
#                             "unit": "",
#                             "name": "disk_usage",
#                             "source_name": "",
#                             "description": "disk_usage",
#                             "is_active": True,
#                             "is_diff_metric": False,
#                         },
#                         {
#                             "type": "string",
#                             "monitor_type": "dimension",
#                             "unit": "",
#                             "name": "disk_name",
#                             "source_name": "",
#                             "description": "disk_name",
#                         },
#                     ],
#                     "table_name": "base",
#                     "table_desc": "123",
#                 }
#             ],
#             "label": "os",
#             "version_log": "",
#             "signature": "",
#             "is_support_remote": False,
#             "description_md": "test_content",
#         }
#         path = "/rest/v2/collector_plugin/"
#         result_data = self.client.post(path=path, data=json.dumps(post_data), content_type="application/json")
#         content = json.loads(result_data.content)
#         self.assertEqual(content["data"]["config_version"], 1)
#         self.assertEqual(content["data"]["info_version"], 1)
#
#     @override_settings(MIDDLEWARE=("monitor_web.tests.middlewares.OverrideMiddleware",))
#     @mock.patch.object(APIResource, "perform_request")
#     def test_start_debug(self, mock_api):
#         def mock_request(*args, **kwargs):
#             if "plugin_version" in args[0]:
#                 return {"id": 1, "md5": "456"}
#             else:
#                 return {"task_id": "123"}
#
#         mock_api.side_effect = mock_request
#
#         data = {
#             "config_version": 1,
#             "info_version": 1,
#             "param": {"collector": {"period": "10"}, "plugin": {}},
#             "host_info": {"bk_cloud_id": 0, "ip": "10.0.1.10", "bk_biz_id": 2},
#         }
#         self.create_models()
#         path = "/rest/v2/collector_plugin/test_r/start_debug/"
#         result_data = self.client.post(path=path, data=json.dumps(data), content_type="application/json")
#         content = json.loads(result_data.content)
#         self.assertEqual(content["data"]["task_id"], "123")
#
#     @override_settings(MIDDLEWARE=("monitor_web.tests.middlewares.OverrideMiddleware",))
#     def test_datadog_check(self):
#         file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_file", "collector_info")
#         with open(file_path, "r", encoding="utf-8") as fp:
#             collector_info = fp.read()
#         config_info = [
#             {
#                 "description": "",
#                 "default": "python",
#                 "visible": False,
#                 "mode": "collector",
#                 "type": "text",
#                 "name": "python_path",
#             }
#         ]
#         post_data = {
#             "bk_biz_id": 2,
#             "plugin_id": "aaz",
#             "plugin_display_name": "aaz",
#             "plugin_type": "DataDog",
#             "logo": "",
#             "collector_json": {
#                 "windows": {"file_id": "123", "file_name": "aaz.sh", "md5": "12345"},
#                 "datadog_check_name": "consul",
#                 "config_yaml": collector_info,
#                 "linux": {"file_id": "345", "file_name": "aaz.sh", "md5": "54321"},
#             },
#             "config_json": config_info,
#             "metric_json": [
#                 {
#                     "fields": [
#                         {
#                             "type": "double",
#                             "monitor_type": "metric",
#                             "unit": "",
#                             "name": "disk_usage",
#                             "source_name": "",
#                             "description": "disk_usage",
#                             "is_active": True,
#                             "is_diff_metric": False,
#                         },
#                         {
#                             "type": "string",
#                             "monitor_type": "dimension",
#                             "unit": "",
#                             "name": "disk_name",
#                             "source_name": "",
#                             "description": "disk_name",
#                         },
#                     ],
#                     "table_name": "base",
#                     "table_desc": "123",
#                 }
#             ],
#             "label": "os",
#             "version_log": "",
#             "signature": "",
#             "is_support_remote": False,
#             "description_md": "test_content",
#         }
#         path = "/rest/v2/collector_plugin/"
#         result = self.client.post(path=path, data=json.dumps(post_data), content_type="application/json")
#         content = json.loads(result.content)
#         self.assertEqual(content["message"], "插件包解析错误: 采集配置中配置的参数 ['instance_url'] 未定义")
