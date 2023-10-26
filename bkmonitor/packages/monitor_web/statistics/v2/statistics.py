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
from monitor_web.statistics.v2.base import BaseCollector, MySQLStorage

from bkmonitor.models import StatisticsMetric
from core.statistics.metric import Metric, register


class StatisticCollector(BaseCollector):
    STORAGE_BACKEND = MySQLStorage

    @register(labelnames=("metric_name", "updated_time"))
    def outdated_statistic_metrics_count(self, metric: Metric):
        """超过一天未更新的运营指标"""
        now_ts = arrow.now()
        last_day = now_ts.replace(days=-1)

        for statistic in StatisticsMetric.objects.filter(update_time__lte=last_day.timestamp):
            metric.labels(metric_name=statistic.name, updated_time=arrow.get(statistic.update_time).humanize()).inc()

    @register(labelnames=("domain_name", "bk_biz_id", "bk_biz_name"))
    def last_update_timestamp(self, metric: Metric):
        """最近更新时间"""
        for bk_biz_id in self.biz_info:
            metric.labels(
                domain_name=settings.BK_MONITOR_HOST, bk_biz_id=bk_biz_id, bk_biz_name=self.get_biz_name(bk_biz_id)
            ).set(arrow.now().timestamp)
