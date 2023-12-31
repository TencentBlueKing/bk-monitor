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
from unittest import mock

from django.test import TestCase
from fta_web.event_plugin.resources import (
    CreateEventPluginInstanceResource,
    CreateEventPluginResource,
    DeployEventPluginResource,
    GetEventPluginInstanceResource,
    ListEventPluginResource,
    UpdateEventPluginInstanceResource,
    UpdateEventPluginResource,
)
from fta_web.event_plugin.views import event_plugin_media

from bkmonitor.event_plugin.serializers import HttpPullPluginInstSerializer
from bkmonitor.models import EventPluginInstance, EventPluginV2
from core.drf_resource.exceptions import CustomException
from core.errors.event_plugin import PluginIDExistError

mock.patch(
    "bkmonitor.event_plugin.accessor.EventPluginInstAccessor.access",
    return_value=10001,
).start()

from fta_web.handlers import install_global_event_plugin, register_event_plugin


def get_plugin_info():
    plugin_info = {
        "plugin_id": "rest_pull",
        "version": "1.0.1",
        "plugin_display_name": "REST告警拉取",
        "plugin_type": "http_pull",
        "summary": "接入指定参数格式的REST API告警",
        "author": "蓝鲸智云",
        "tags": ["REST", "PULL"],
        "config_params": [
            {
                "field": "url",
                "value": "",
                "name": "请求url",
                "is_required": True,
                "default_value": "http://www.blueking.com/",
            },
            {
                "field": "begin_time",
                "name": "开始时间",
                "value": "{{begin_time}}",
                "is_required": True,
                "is_hidden": True,
                "default_value": "{{begin_time}}",
            },
            {
                "field": "end_time",
                "name": "结束时间",
                "value": "{{end_time}}",
                "is_required": True,
                "is_hidden": True,
                "default_value": "{{end_time}}",
            },
        ],
        "ingest_config": {
            "source_format": "json",
            "multiple_events": True,
            "events_path": "data",
            "method": "POST",
            "url": "{{url}}",
            "body": {
                "data_type": "raw",
                "content": '{"begin_time__gte": "{{begin_time}}", "begin_time__lte": "{{end_time}}"',
                "content_type": "json",
            },
            "overlap": 60,
            "timeout": 60,
            "time_format": "datetime",
        },
        "normalization_config": [
            {"field": "alert_name", "expr": "alarm_type"},
            {"field": "event_id", "expr": "source_id"},
            {"field": "description", "expr": "alarm_content"},
            {"field": "metric", "expr": "metric"},
            {"field": "category", "expr": "category"},
            {"field": "assignee", "expr": "assignee"},
            {"field": "status", "expr": "status"},
            {"field": "target_type", "expr": "target_type"},
            {"field": "target", "expr": "ip"},
            {"field": "severity", "expr": "severity"},
            {"field": "bk_biz_id", "expr": "bk_biz_id"},
            {"field": "tags", "expr": "alarm_context"},
            {"field": "time", "expr": "time"},
            {"field": "source_time", "expr": "source_time"},
            {"field": "anomaly_time", "expr": "anomaly_time"},
            {"field": "dedupe_md5", "expr": "dedupe_md5"},
        ],
        "alert_config": [
            {"name": "REST默认分类", "rules": [{"key": "alarm_type", "value": ["api_default"], "method": "eq"}]}
        ],
        "description": "这是说明",
        "tutorial": "123",
    }
    return plugin_info


def get_prom_plugin_info():
    plugin_info = {
        "plugin_id": "prom_alerts",
        "version": "1.0.1",
        "plugin_display_name": "Prometheus告警监控日志（PULL）自定义参数",
        "plugin_type": "http_pull",
        "summary": "拉取Prometheus监控告警日志源，自定义渲染参数",
        "author": "蓝鲸智云",
        "tags": ["Restful", "Prometheus ALARM"],
        "config_params": [
            # 拉取日志数据的服务配置
            {
                "field": "url",
                "value": "",
                "name": "请求url",
                "is_required": True,
                "is_sensitive": False,
                "default_value": "http://127.0.0.1:9095/api/v1/alerts",
                "desc": "Prometheus服务的告警数据接口",
            },
            # 以下配置参数为数据清洗配置
            {
                "field": "description",
                "value": "",
                "name": "描述",
                "is_required": True,
                "is_sensitive": False,
                "default_value": "annotations.description",
                "desc:": "描述 - 事件的详细描述及主体内容。作为该项告警的描述内容，此处默认取annotations.description的内容为告警描述",
            },
            {
                "field": "status",
                "value": "",
                "name": "状态",
                "is_required": True,
                "is_sensitive": False,
                "default_value": "get_field({pending: 'ABNORMAL', inactive: 'RECOVERED', firing: 'ABNORMAL'}, state)",
                "desc:": "状态 - 事件状态，用于控制告警状态流转。 不提供则默认为 'ABNORMAL'",
            },
            {
                "field": "target_type",
                "value": "",
                "name": "目标类型",
                "is_required": True,
                "is_sensitive": False,
                "default_value": "labels.target_type",
                "desc": "目标类型 - 产生事件的目标类型。此处默认选择labels.target_type中的字段作为目标类型。如果用户的目标类型不是此字段可做更换",
            },
            {
                "field": "severity",
                "value": "",
                "name": "级别",
                "is_required": True,
                "is_sensitive": False,
                "default_value": "labels.severity",
                "desc": """级别 - 事件的严重程度，默认为：labels.severity
severity取值 1: 致命; 2: 预警; 3: 提醒。
如果Prometheus日志的severity是1、2、3，则使用默认的：labels.severity
如果Prometheus日志的severity不是1、2、3，则使用此表达式：get_field({SEVERITY1: '1', SEVERITY2: '2', SEVERITY3: '3'}, labels.severity)
SEVERITY1、SEVERITY2、SEVERITY3分别替换成Prometheus日志对应的severity""",
            },
        ],
        "ingest_config": {
            "source_format": "json",
            "method": "GET",
            "url": "{{url}}",
            "multiple_events": True,
            "events_path": "data.alerts",
            "interval": 60,
            "overlap": 10,
            "timeout": 60,
            "body": {
                "data_type": "raw",
                "content_type": "json",
            },
            "time_format": "rfc3339",
        },
        "normalization_config": [
            {"field": "alert_name", "expr": "labels.alertname"},
            {"field": "description", "expr": "{{description}}"},
            {"field": "status", "expr": "{{status}}"},
            {"field": "target_type", "expr": "{{target_type}}"},
            {"field": "target", "expr": "labels.instance"},
            {"field": "severity", "expr": "{{severity}}"},
            {"field": "bk_biz_id", "expr": "bk_biz_id || '{{plugin_inst_biz_id}}'"},
            {"field": "tags", "expr": "labels"},
            {"field": "time", "expr": "activeAt"},
            {"field": "anomaly_time", "expr": "activeAt"},
        ],
        "alert_config": [],
        "description": """## 1. 插件说明

拉取（PULL）Prometheus监控告警数据到监控平台。支持用户自定义模板参数渲染方式。
""",
        "tutorial": """1. 安装好插件，系统自动拉取Prometheus的告警日志

2. 拉取Prometheus的数据格式

    ```json
    {
      "status": "success",
      "data": {
        "alerts": [
          {
            "labels": {
              "alertname": "hostCpuUsageAlert",
              "instance": "localhost:10001",
              "severity": "1",
              "target_type": "server"
            },
            "annotations": {
              "description": "localhost:10001 CPU usage above 1% (current value: 0.059166666664774915)",
              "summary": "Instance localhost:10001 CPU usgae high"
            },
            "state": "firing",
            "activeAt": "2023-02-03T08:29:53.485388894Z",
            "value": "5.9166666664774915e-02"
          },
          {
            "labels": {
              "alertname": "hostMemUsageAlert",
              "instance": "localhost:10001",
              "job": "node_exporter",
              "node": "10.0.1.56",
              "severity": "2",
              "target_type": "db"
            },
            "annotations": {
              "description": "localhost:10001 MEM usage above 1% (current value: 0.9329973762988476)",
              "summary": "Instance localhost:10001 MEM usgae high"
            },
            "state": "firing",
            "activeAt": "2023-02-03T08:29:53.485388894Z",
            "value": "9.329973762988476e-01"
          }
        ]
      }
    }
    ```

3. 完成
""",
    }
    return plugin_info


class TestEventPluginMigrate(TestCase):
    def setUp(self) -> None:
        EventPluginV2.objects.all().delete()
        EventPluginInstance.objects.all().delete()

    def tearDown(self) -> None:
        EventPluginV2.objects.all().delete()
        EventPluginInstance.objects.all().delete()

    def test_deploy_event_plugin(self):
        plugin_info = get_plugin_info()
        r = DeployEventPluginResource()
        data = r.request(plugin_info)
        ingest_config = data["ingest_config"]
        self.assertEqual(ingest_config["url"], "http://www.blueking.com/")
        self.assertIsNotNone(data["params_schema"])
        self.assertEqual(int(data["bk_biz_id"]), 0)

        inst_info = {
            "bk_biz_id": 0,
            "plugin_id": data["plugin_id"],
            "version": data["version"],
            "config_params": {param["field"]: "http://www.blueking111.com/" for param in data["config_params"]},
        }

        inst = CreateEventPluginInstanceResource().request(inst_info)
        plugin_info["plugin_display_name"] = f"deploy{plugin_info['plugin_display_name']}"
        r = DeployEventPluginResource()
        data = r.request(plugin_info)
        self.assertEqual(data["plugin_display_name"], plugin_info["plugin_display_name"])
        self.assertEqual(data["updated_instances"]["succeed_instances"], [inst["id"]])

    def test_deploy_event_plugin_inst_force_update(self):
        plugin_info = get_plugin_info()
        r = DeployEventPluginResource()
        data = r.request(plugin_info)
        ingest_config = data["ingest_config"]
        self.assertEqual(ingest_config["url"], "http://www.blueking.com/")
        self.assertIsNotNone(data["params_schema"])
        self.assertEqual(int(data["bk_biz_id"]), 0)

        inst_info = {
            "bk_biz_id": 2,
            "plugin_id": data["plugin_id"],
            "version": data["version"],
            "config_params": {param["field"]: "http://www.blueking111.com/" for param in data["config_params"]},
        }

        inst = CreateEventPluginInstanceResource().request(inst_info)
        plugin_info["plugin_display_name"] = f"deploy{plugin_info['plugin_display_name']}"
        plugin_info["forced_update"] = True
        r = DeployEventPluginResource()
        data = r.request(plugin_info)
        self.assertEqual(data["plugin_display_name"], plugin_info["plugin_display_name"])
        self.assertEqual(data["updated_instances"]["succeed_instances"], [inst["id"]])

    def test_create_event_plugin(self):
        plugin_info = get_plugin_info()
        r = CreateEventPluginResource()
        data = r.request(plugin_info)
        ingest_config = data["ingest_config"]
        self.assertEqual(ingest_config["url"], "http://www.blueking.com/")
        self.assertIsNotNone(data["params_schema"])
        self.assertEqual(int(data["bk_biz_id"]), 0)

        with self.assertRaises(PluginIDExistError):
            r = CreateEventPluginResource()
            r.request(plugin_info)

        plugin_info["plugin_display_name"] = f"update{plugin_info['plugin_display_name']}"
        r = UpdateEventPluginResource()
        data = r.request(plugin_info)
        self.assertEqual(data["plugin_display_name"], plugin_info["plugin_display_name"])

        # 测试创建
        event_plugin = EventPluginV2.objects.get(plugin_id=data["plugin_id"], version=data["version"])
        inst_info = {
            "bk_biz_id": 2,
            "plugin_id": event_plugin.plugin_id,
            "version": event_plugin.version,
            "config_params": {param["field"]: "http://www.blueking111.com/" for param in event_plugin.config_params},
        }
        inst_r = CreateEventPluginInstanceResource()
        inst_data = inst_r.request(inst_info)
        self.assertEqual(inst_data["data_id"], 10001)
        p_inst = EventPluginInstance.objects.get(id=inst_data["id"])
        data = HttpPullPluginInstSerializer(p_inst).data
        self.assertEqual(data["ingest_config"]["url"], "http://www.blueking111.com/")
        p_inst.id = None
        p_inst.save()

        # 测试获取
        rsp_data = ListEventPluginResource().request({"bk_biz_id": 2})
        print("list: ", json.dumps(rsp_data))

        # 测试获取
        rsp_data = GetEventPluginInstanceResource().request(
            {"plugin_id": p_inst.plugin_id, "version": p_inst.version, "bk_biz_id": 2}
        )
        print(json.dumps(rsp_data))
        self.assertEqual(len(rsp_data["instances"]), 2)
        self.assertTrue(rsp_data["is_installed"])

        # 测试更新
        inst_info["id"] = p_inst.id
        inst_info["config_params"]["url"] = "http://www.blueking123.com/"
        u_req = UpdateEventPluginInstanceResource()
        u_req.request(inst_info)
        p_inst.refresh_from_db()
        data = HttpPullPluginInstSerializer(p_inst).data
        self.assertEqual(data["ingest_config"]["url"], "http://www.blueking123.com/")

        inst_info["config_params"] = {param["field"]: "随便写的一个url" for param in event_plugin.config_params}
        with self.assertRaises(CustomException):
            inst_r.request(inst_info)

    def test_register_by_file(self):
        pull_config_params = [
            {
                "field": "url",
                "value": "",
                "name": "请求url",
                "is_required": True,
                "default_value": "http://127.0.0.1:8009",
            },
            {
                "field": "method",
                "value": "",
                "name": "请求方法",
                "is_required": True,
                "default_value": "PUT",
            },
            {
                "field": "begin_time",
                "name": "开始时间",
                "value": "{{begin_time}}",
                "is_required": True,
                "is_hidden": True,
                "default_value": "{{begin_time}}",
            },
            {
                "field": "end_time",
                "name": "结束时间",
                "value": "{{end_time}}",
                "is_required": True,
                "is_hidden": True,
                "default_value": "{{end_time}}",
            },
        ]
        plugins = register_event_plugin(pull_config_params)
        for p_id in ["rest_api", "rest_pull"]:
            install_global_event_plugin(plugins[p_id])

        self.assertEqual(EventPluginV2.objects.all().count(), 4)
        self.assertEqual(EventPluginInstance.objects.filter(bk_biz_id=0).count(), 2)

        pull_inst = EventPluginInstance.objects.get(plugin_id="rest_pull")
        data = HttpPullPluginInstSerializer(pull_inst).data
        self.assertEqual(data["ingest_config"]["url"], "http://127.0.0.1:8009")
        self.assertEqual(data["ingest_config"]["method"], "PUT")

        EventPluginV2.objects.get(plugin_id="tencent_cloud_alert")
        inst_info = {
            "bk_biz_id": 2,
            "plugin_id": "tencent_cloud_alert",
            "version": "1.0.0",
            "config_params": {},
        }
        inst_info["config_params"]["method"] = "POST"
        inst_r = CreateEventPluginInstanceResource().request(inst_info)
        tencent_cloud_inst = EventPluginInstance.objects.get(id=inst_r["id"])
        data = HttpPullPluginInstSerializer(tencent_cloud_inst).data
        normalization_config = {item["field"]: item for item in data["normalization_config"]}
        self.assertEqual(normalization_config["bk_biz_id"]["expr"], "bk_biz_id || '2'")
        self.assertEqual("https://monitor.tencentcloudapi.com", data["ingest_config"]["url"])
        self.assertEqual(
            '{"PageNumber":{{page}},"PageSize":{{page_size}},"Module":"monitor","EndTime":{{end_time}}}',
            data["ingest_config"]["body"]["content"],
        )

    def test_register_prom_pull_event_plugin(self):
        # test install plugin
        plugins = get_prom_plugin_info()
        r = CreateEventPluginResource()
        data = r.request(plugins)
        ingest_config = data["ingest_config"]
        self.assertEqual(ingest_config["url"], "http://127.0.0.1:9095/api/v1/alerts")
        self.assertIsNotNone(data["params_schema"])
        self.assertIsNotNone(data["normalization_config"])
        self.assertEqual(int(data["bk_biz_id"]), 0)
        self.assertEqual("data.alerts", ingest_config["events_path"])
        self.assertEqual("GET", ingest_config["method"])
        self.assertEqual(EventPluginV2.objects.all().count(), 1)
        self.assertIsNotNone(EventPluginV2.objects.filter(plugin_id="prom_alerts").count())

        # test plugin instance for normalization_config and ingest_config
        inst_info = {
            "bk_biz_id": 2,
            "plugin_id": "prom_alerts",
            "version": "1.0.1",
            "config_params": {
                "url": "http://127.0.0.1:9095/api/v1/alerts",
                "description": "annotations.description",
                "status": "get_field({pending: 'ABNORMAL', inactive: 'RECOVERED', firing: 'ABNORMAL'}, state)",
                "target_type": "labels.target_type",
                "severity": "labels.severity",
            },
        }
        inst_r = CreateEventPluginInstanceResource().request(inst_info)
        prom_plugin_inst = EventPluginInstance.objects.get(id=inst_r["id"])
        data = HttpPullPluginInstSerializer(prom_plugin_inst).data
        normalization_config = {item["field"]: item for item in data["normalization_config"]}

        self.assertEqual(data["ingest_config"]["url"], "http://127.0.0.1:9095/api/v1/alerts")
        self.assertEqual(data["ingest_config"]["method"], "GET")
        self.assertEqual(normalization_config["alert_name"]["expr"], "labels.alertname")
        self.assertEqual(normalization_config["description"]["expr"], "annotations.description")
        self.assertEqual(normalization_config["target_type"]["expr"], "labels.target_type")
        self.assertEqual(normalization_config["target"]["expr"], "labels.instance")
        self.assertEqual(
            normalization_config["status"]["expr"],
            "get_field({pending: 'ABNORMAL', inactive: 'RECOVERED', firing: 'ABNORMAL'}, state)",
        )
        self.assertEqual(normalization_config["severity"]["expr"], "labels.severity")
        self.assertEqual(normalization_config["bk_biz_id"]["expr"], "bk_biz_id || '2'")

        # test update plugin
        update_info = {
            "id": inst_r["id"],
            "bk_biz_id": 2,
            "config_params": {
                "url": "http://0.0.0.0:9000/api/v1/alerts",
                "description": "test_description",
                "status": "test_status",
                "target_type": "test_target_type",
                "severity": "test_severity",
            },
        }
        update_inst = UpdateEventPluginInstanceResource().request(update_info)
        new_prom_plugin = EventPluginInstance.objects.get(id=update_inst["id"])
        new_data = HttpPullPluginInstSerializer(new_prom_plugin).data
        new_normalization_config = {item["field"]: item for item in new_data["normalization_config"]}
        self.assertEqual(new_data["ingest_config"]["url"], "http://0.0.0.0:9000/api/v1/alerts")
        self.assertEqual(new_normalization_config["description"]["expr"], "test_description")
        self.assertEqual(new_normalization_config["status"]["expr"], "test_status")
        self.assertEqual(new_normalization_config["target_type"]["expr"], "test_target_type")
        self.assertEqual(new_normalization_config["severity"]["expr"], "test_severity")
        self.assertEqual(new_normalization_config["bk_biz_id"]["expr"], "bk_biz_id || '2'")

        plugin_id = "zabbix"
        version = "1.0.0"
        bk_biz_id = 0
        register_event_plugin()
        inst_info = {"bk_biz_id": bk_biz_id, "plugin_id": plugin_id, "version": version, "config_params": {}}
        inst_r = CreateEventPluginInstanceResource().request(inst_info)

        plugin_instances = GetEventPluginInstanceResource().request(
            plugin_id=plugin_id, version="1.0.0", bk_biz_id=bk_biz_id
        )
        self.assertEqual(
            plugin_instances["ingest_config"].get("ingester_host"), "http://ingester.bkmonitorv3.service.consul"
        )
        self.assertIsNotNone(plugin_instances["ingest_config"].get("push_url", None))

        plugin_infos = EventPluginV2.objects.get(plugin_id=plugin_id)
        plugin_kwargs = {"plugin_id": plugin_id, "package_dir": plugin_infos.package_dir}

        event_plugin_media(**plugin_kwargs)
