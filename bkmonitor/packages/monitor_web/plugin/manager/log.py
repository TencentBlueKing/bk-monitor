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


import re

from django.db import transaction
from django.utils.translation import ugettext as _

from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import api
from monitor_web.commons.data_access import EventDataAccessor
from monitor_web.models.custom_report import CustomEventGroup, CustomEventItem
from monitor_web.models.plugin import CollectorPluginMeta, PluginVersionHistory
from monitor_web.plugin.constant import PluginType
from monitor_web.plugin.manager import BuiltInPluginManager
from monitor_web.plugin.serializers import LogSerializer
from monitor_web.tasks import append_event_metric_list_cache


class LogPluginManager(BuiltInPluginManager):
    serializer_class = LogSerializer
    DEFAULT_DIMENSIONS = [
        "event_name",
        "file_path",
        "bk_target_ip",
        "bk_target_cloud_id",
        "bk_biz_id",
        "bk_set_id",
        "bk_module_id",
    ]

    @staticmethod
    def get_params(plugin_id, bk_biz_id, label, **kwargs):
        params = {
            "plugin_id": plugin_id,
            "bk_biz_id": bk_biz_id,
            "plugin_type": PluginType.LOG,
            "label": label,
            "plugin_display_name": _("日志关键字采集"),
            "description_md": "",
            "logo": "",
            "version_log": "",
            "metric_json": [],
        }
        params.update(kwargs)
        return params

    @staticmethod
    def full_request_data(data, event_list):
        dimension_set = []
        for dimension in event_list:
            dimension_set.extend(dimension["dimension_list"])
        metric_json = [
            {
                "fields": [
                    {
                        "type": "double",
                        "monitor_type": "metric",
                        "name": "event.count",
                        "unit": "",
                        "description": "event_count",
                        "is_active": True,
                        "is_diff_metric": False,
                    },
                ],
                "table_name": "base",
                "table_desc": _("默认分类"),
            }
        ]
        for dimension in set(dimension_set):
            metric_json[0]["fields"].append(
                {
                    "type": "string",
                    "monitor_type": "dimension",
                    "name": dimension,
                    "description": dimension,
                    "is_active": True,
                    "unit": "",
                }
            )
        data["metric_json"] = metric_json

    def create_version(self, data):
        event_list = self.get_dimensions(data["rules"], data["label"])
        self.full_request_data(data, event_list)
        return self._create_version(data, event_list)

    def _create_version(self, data, event_list):
        version, need_debug = super(LogPluginManager, self).create_version(data)
        plugin = CollectorPluginMeta.objects.get(plugin_id=version.plugin.plugin_id)
        plugin_manager = self.__class__(plugin, self.operator)
        plugin_manager.release_collector_plugin(version)
        plugin_manager.create_result_table(
            plugin.release_version, DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.LOG, event_list
        )
        return version, need_debug

    def update_version(self, data, target_config_version: int = None, target_info_version: int = None):
        event_list = self.get_dimensions(data["rules"])
        self.full_request_data(data, event_list)
        return self._update_version(data, event_list)

    def _update_version(self, data, event_list):
        version, need_debug = super(LogPluginManager, self).update_version(data)
        self.release_collector_plugin(version)
        self.modify_result_table(version, event_list)
        return version, need_debug

    def get_dimensions(self, rules, label=None):
        dimensions = []
        pattern = re.compile("(?<=<)[^<>]+(?=>)")
        default_dimensions = self.DEFAULT_DIMENSIONS
        if label in ["component", "service_module"]:
            default_dimensions = self.DEFAULT_DIMENSIONS + ["bk_service_instance_id"]

        for rule in rules:
            dimensions.append(
                {
                    "event_name": rule["name"],
                    "dimension_list": pattern.findall(rule["pattern"]) + default_dimensions,
                }
            )
        return dimensions

    def create_result_table(self, current_version, source_label, type_label, event_info_list):
        access = EventDataAccessor(current_version, self.operator)
        data_id = access.create_data_id(source_label, type_label)
        group_info = access.create_result_table(data_id, event_info_list)
        CustomEventGroup.objects.create(
            bk_biz_id=group_info["bk_biz_id"],
            bk_event_group_id=group_info["event_group_id"],
            scenario=group_info["label"],
            name=group_info["event_group_name"],
            bk_data_id=group_info["bk_data_id"],
            table_id=group_info["table_id"],
            type="keywords",
        )
        event_items = []
        for event in group_info["event_info_list"]:
            event_items.append(
                CustomEventItem(
                    custom_event_id=event["event_id"],
                    bk_event_group_id=group_info["event_group_id"],
                    custom_event_name=event["event_name"],
                    dimension_list=[{"dimension_name": dimension} for dimension in event["dimension_list"]],
                )
            )
        CustomEventItem.objects.bulk_create(event_items)
        # 修改或更新指标缓存表
        append_event_metric_list_cache.delay(group_info["event_group_id"])
        return group_info

    def modify_result_table(self, current_version, event_info_list):
        access = EventDataAccessor(current_version, self.operator)
        group_info = access.modify_result_table(event_info_list)
        event_items = []
        for event in group_info["event_info_list"]:
            event_items.append(
                CustomEventItem(
                    custom_event_id=event["event_id"],
                    bk_event_group_id=group_info["event_group_id"],
                    custom_event_name=event["event_name"],
                    dimension_list=[{"dimension_name": dimension} for dimension in event["dimension_list"]],
                )
            )
        CustomEventItem.objects.filter(bk_event_group_id=group_info["event_group_id"]).delete()
        CustomEventItem.objects.bulk_create(event_items)
        # 修改或更新指标缓存表
        append_event_metric_list_cache.delay(group_info["event_group_id"])
        return group_info

    def delete_result_table(self, current_version):
        with transaction.atomic():
            access = EventDataAccessor(current_version, self.operator)
            event_group_id = access.delete_result_table()
            CustomEventGroup.objects.filter(bk_event_group_id=event_group_id).delete()
            CustomEventItem.objects.filter(bk_event_group_id=event_group_id).delete()
            PluginVersionHistory.origin_objects.filter(plugin=current_version.plugin).delete()
            current_version.plugin.delete()

    def _get_debug_config_context(self, config_version, info_version, param, target_nodes):
        return {}

    @staticmethod
    def release_collector_plugin(current_version):
        current_version.stage = "release"
        current_version.is_packaged = True
        current_version.save()

    def get_deploy_steps_params(self, plugin_version, param, target_nodes):
        collector_params = {
            "tasks": [
                {
                    "task_id": param["collector"]["task_id"],
                    "bk_biz_id": param["collector"]["bk_biz_id"],
                    "dataid": param["collector"]["dataid"],
                    "type": "keyword",
                    "close_inactive": "86400s",
                    "path_list": param["log"]["log_path"],
                    "report_period": param["collector"]["period"],
                    "encoding": param["log"]["charset"],
                    "filter_patterns": param["log"].get("filter_patterns", []),
                    "task_list": [{"name": rule["name"], "pattern": rule["pattern"]} for rule in param["log"]["rules"]],
                    "target": self.get_target(param["target_object_type"]),
                    "labels": param["collector"]["labels"],
                }
            ]
        }
        step_id = "bkmonitorlog"
        subscription_id = param.pop("subscription_id", "")
        if subscription_id:
            subscription_info = api.node_man.subscription_info(subscription_id_list=[subscription_id])
            if subscription_info:
                step_id = subscription_info[0]["steps"][0]["id"]

        deploy_steps = [
            self._get_bkmonitorbeat_deploy_step(
                "bkmonitorbeat_keyword.conf", {"context": collector_params}, step_id=step_id
            ),
        ]
        return deploy_steps

    def _get_collector_json(self, plugin_params):
        return {}

    @staticmethod
    def get_target(object_type):
        if object_type == "SERVICE":
            target = "{{ cmdb_instance.service.id }}"
        else:
            target = (
                "{{ '{}:{}'.format(cmdb_instance.host.bk_cloud_id[0].id, cmdb_instance.host.bk_host_innerip) "
                "if cmdb_instance.host.bk_cloud_id is iterable and cmdb_instance.host.bk_cloud_id is not string "
                "else '{}:{}'.format(cmdb_instance.host.bk_cloud_id, cmdb_instance.host.bk_host_innerip) }}"
            )
        return target
