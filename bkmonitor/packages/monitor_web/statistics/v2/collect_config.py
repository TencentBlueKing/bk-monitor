# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import logging

from django.utils.functional import cached_property
from monitor_web.models import CollectConfigMeta
from monitor_web.statistics.v2.base import BaseCollector

from core.drf_resource import resource
from core.statistics.metric import Metric, register

logger = logging.getLogger(__name__)


class CollectConfigCollector(BaseCollector):
    """
    采集配置
    """

    @cached_property
    def collect_configs(self):
        return CollectConfigMeta.objects.filter(bk_biz_id__in=list(self.biz_info.keys()))

    @register(labelnames=("bk_biz_id", "bk_biz_name", "label", "plugin_type", "plugin_id"))
    def collect_config_count(self, metric: Metric):
        """
        采集任务数
        """
        for collect_config in self.collect_configs:
            metric.labels(
                bk_biz_id=collect_config.bk_biz_id,
                bk_biz_name=self.get_biz_name(collect_config.bk_biz_id),
                label=collect_config.label,
                plugin_type=collect_config.collect_type,
                plugin_id=collect_config.plugin_id,
            ).inc()

    @register(labelnames=("bk_biz_id", "bk_biz_name"))
    def legacy_subscription_count(self, metric: Metric):
        """野订阅数量"""
        try:
            list_legacy_subscriptions = resource.collecting.list_legacy_subscription()
        except Exception:
            logger.exception("failed get list_legacy_subscriptions")
            list_legacy_subscriptions = {"detail": []}

        for subscription in list_legacy_subscriptions.get("detail"):
            metric.labels(
                bk_biz_id=subscription["bk_biz_id"], bk_biz_name=self.get_biz_name(subscription["bk_biz_id"])
            ).inc()

    @register(
        labelnames=(
            "bk_biz_id",
            "bk_biz_name",
            "plugin_id",
            "plugin_name",
            "collect_config_id",
            "collect_config_name",
        )
    )
    def collect_config_instance_count(self, metric: Metric):
        """采集实例/主机数"""

        for collect_config in self.collect_configs:
            if collect_config.cache_data is None:
                instances_count = 0
            else:
                instances_count = collect_config.cache_data.get("total_instance_count", 0)

            plugin_latest_version = collect_config.plugin.packaged_release_version
            metric.labels(
                bk_biz_id=collect_config.bk_biz_id,
                bk_biz_name=self.get_biz_name(collect_config.bk_biz_id),
                plugin_id=collect_config.plugin_id,
                plugin_name=plugin_latest_version.info.plugin_display_name
                if plugin_latest_version
                else collect_config.plugin_id,
                collect_config_id=collect_config.pk,
                collect_config_name=collect_config.name,
            ).set(instances_count)
