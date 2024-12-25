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

from django.conf import settings
from django.utils.translation import gettext as _

from alarm_backends.core.cache.models.uptimecheck import UptimecheckCacheManager
from alarm_backends.service.alert.enricher.translator.base import BaseTranslator
from constants.data_source import DataSourceLabel


class UptimecheckConfigTranslator(BaseTranslator):
    """
    拨测配置翻译
    """

    TABLE_ID_PREFIX = "uptimecheck."

    def is_enabled(self):
        return self.data_source_label == DataSourceLabel.BK_MONITOR_COLLECTOR and self.result_table_id.startswith(
            self.TABLE_ID_PREFIX
        )

    def translate(self, data):
        node_field = data.get("node_id")
        if node_field:
            try:
                # 若还是数字ID, 则说明为旧格式
                node_id = int(node_field.value)
                node_keys = [node for node in UptimecheckCacheManager.cache.keys() if "uptimecheck_node" in node]
                nodes = [json.loads(node) for node in UptimecheckCacheManager.cache.mget(node_keys)]
                node_field.display_name = _("节点名称")
                if node_id == 0 and len(nodes) > 1:
                    node_field.display_value = _(
                        _("bkmonitorbeat(版本低于{}, 请升级)").format(settings.BKMONITORBEAT_SUPPORT_NEW_NODE_ID_VERSION)
                    )
                elif node_id == 0 and len(nodes) == 1:
                    node_field.display_value = nodes[0]["name"]
                elif node_id != 0:
                    for node in nodes:
                        if node["id"] == node_id:
                            node_field.display_value = node["name"]
            except ValueError:
                # 说明是新格式(bk_cloud_id:ip)，直接取即可
                node = UptimecheckCacheManager.get_node(node_field.value)
                node_field.display_name = _("节点名称")
                if node:
                    node_field.display_value = node["name"]

        task_field = data.get("task_id")
        if not task_field:
            return data

        task = UptimecheckCacheManager.get_task(task_field.value)
        if not task:
            task_field.display_name = _("任务ID")
            task_field.display_value = _("{} (任务不存在)").format(task_field.value)
            return data

        task_field.display_name = _("任务名称")
        task_field.display_value = task["name"]

        # 特殊逻辑：根据错误码转换拨测任务配置信息
        error_code_field = data.get("error_code")
        if not error_code_field:
            return data

        if error_code_field.value == "3303":
            error_code_field.display_name = _("响应状态码")
            error_code_field.display_value = task["config"]["response_code"]
        elif error_code_field.value == "3302":
            error_code_field.display_name = _("响应消息")
            error_code_field.display_value = task["config"]["response"]
        return data
