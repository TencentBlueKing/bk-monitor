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
from monitor_web.models import CollectorPluginMeta
from monitor_web.statistics.v2.base import BaseCollector

from core.statistics.metric import Metric, register


class CollectPluginCollector(BaseCollector):
    """
    采集插件
    """

    @cached_property
    def collect_plugin(self):
        return CollectorPluginMeta.objects.filter(bk_biz_id__in=list(self.biz_info.keys())).prefetch_related("versions")

    @register(labelnames=("bk_biz_id", "bk_biz_name", "label", "plugin_type", "is_public", "is_support_remote"))
    def collect_plugin_count(self, metric: Metric):
        """
        插件数
        """
        for collect_plugin in self.collect_plugin:
            is_public = 0 if collect_plugin.is_internal else 1
            metric.labels(
                bk_biz_id=collect_plugin.bk_biz_id,
                bk_biz_name=self.get_biz_name(collect_plugin.bk_biz_id),
                label=collect_plugin.label,
                plugin_type=collect_plugin.plugin_type,
                is_public=is_public,
                is_support_remote=collect_plugin.current_version.config.is_support_remote,
            ).inc()

    @register(labelnames=("bk_biz_id", "bk_biz_name", "plugin_type", "env"))
    def collect_plugin_env_count(self, metric: Metric):
        """
        各环境插件数
        """
        for collect_plugin in self.collect_plugin:
            for env in collect_plugin.current_version.os_type_list:
                metric.labels(
                    bk_biz_id=collect_plugin.bk_biz_id,
                    bk_biz_name=self.get_biz_name(collect_plugin.bk_biz_id),
                    plugin_type=collect_plugin.plugin_type,
                    env=env,
                ).inc()
