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
from django.utils.functional import cached_property

from bkmonitor.models import ActionConfig, ActionPlugin
from core.statistics.metric import Metric, register
from monitor_web.statistics.v2.base import BaseCollector


class ActionConfigCollector(BaseCollector):
    """
    故障自愈-处理套餐
    """

    @cached_property
    def action_config(self):
        return ActionConfig.objects.filter(bk_biz_id__in=list(self.biz_info.keys())).exclude(
            plugin_id=ActionConfig.NOTICE_PLUGIN_ID
        )

    @register(labelnames=("bk_biz_id", "bk_biz_name", "plugin_type_name", "status"))
    def action_config_count(self, metric: Metric):
        """
        处理套餐配置数
        """
        action_plugin_mapping = {str(plugin.id): plugin.plugin_key for plugin in ActionPlugin.objects.all()}
        for action_config in self.action_config:
            status = "enabled" if action_config.is_enabled else "disabled"
            metric.labels(
                bk_biz_id=action_config.bk_biz_id,
                bk_biz_name=self.get_biz_name(action_config.bk_biz_id),
                plugin_type_name=action_plugin_mapping.get(str(action_config.plugin_id), "Deleted"),
                status=status,
            ).inc()
