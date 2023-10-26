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
import arrow
from django.conf import settings
from django.utils.functional import cached_property
from monitor_web.statistics.v2.base import TIME_RANGE, BaseCollector

from bkmonitor.documents import EventDocument
from bkmonitor.models import EventPlugin
from core.statistics.metric import Metric, register


class EventPluginCollector(BaseCollector):
    """
    告警源
    """

    @cached_property
    def event_plugin(self):
        return EventPlugin.objects.filter(bk_biz_id__in=[0] + list(self.biz_info.keys()))

    @cached_property
    def event_plugin_names_map(self):
        return {
            x["plugin_id"]: x["plugin_display_name"]
            for x in self.event_plugin.values("plugin_id", "plugin_display_name")
        }

    @register(labelnames=("bk_biz_id", "bk_biz_name", "plugin_type", "is_public"))
    def event_plugin_count(self, metric: Metric):
        """
        告警源插件数
        """
        for event_plugin in self.event_plugin:
            is_public = 1 if event_plugin.bk_biz_id == 0 else 0
            metric.labels(
                bk_biz_id=event_plugin.bk_biz_id,
                bk_biz_name=self.get_biz_name(event_plugin.bk_biz_id),
                plugin_type=event_plugin.plugin_type,
                is_public=is_public,
            ).inc()

    @register(labelnames=("bk_biz_id", "bk_biz_name", "time_range", "plugin_id", "plugin_name"))
    def event_plugin_ingest_count(self, metric: Metric):
        """告警源接收条数"""

        now_time = arrow.now()
        for le_en, seconds in TIME_RANGE:
            start_time = int(now_time.replace(seconds=-seconds).timestamp)
            end_time = int(now_time.timestamp)
            search_obj = (
                EventDocument.search()
                .exclude("term", plugin_id=settings.MONITOR_EVENT_PLUGIN_ID)
                .filter("range", create_time={"gte": start_time, "lt": end_time})[:1]
            )
            search_obj.aggs.bucket("bk_biz_id", "terms", field="bk_biz_id", size=10000).bucket(
                "plugin_id", "terms", field="plugin_id", size=10000
            )
            agg_result = search_obj.execute().aggs

            if not agg_result:
                return

            for biz_bucket in agg_result.bk_biz_id.buckets:
                if not self.biz_exists(biz_bucket.key):
                    continue

                for plugin_bucket in biz_bucket.plugin_id.buckets:
                    metric.labels(
                        bk_biz_id=biz_bucket.key,
                        bk_biz_name=self.get_biz_name(biz_bucket.key),
                        time_range=le_en,
                        plugin_id=plugin_bucket.key,
                        plugin_name=self.event_plugin_names_map.get(plugin_bucket.key, plugin_bucket.key),
                    ).inc(plugin_bucket.doc_count)
