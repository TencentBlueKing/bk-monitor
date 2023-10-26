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
from django.db.models import Count
from monitor_web.statistics.v2.base import BaseCollector

from bkmonitor.models import MetricListCache
from core.statistics.metric import Metric, register


class MonitorMetricCollector(BaseCollector):
    """
    监控指标
    """

    @register(labelnames=("bk_biz_id", "bk_biz_name", "data_source_label", "data_type_label", "scenario"))
    def monitor_metric_count(self, metric: Metric):
        """
        监控指标数
        """

        monitor_metrics = (
            MetricListCache.objects.values("bk_biz_id", "data_source_label", "data_type_label", "result_table_label")
            .annotate(count=Count("id"))
            .order_by()
        )
        for monitor_metric in monitor_metrics:
            bk_biz_id = monitor_metric["bk_biz_id"]
            if not self.biz_exists(bk_biz_id):
                continue
            metric.labels(
                bk_biz_id=bk_biz_id,
                bk_biz_name=self.get_biz_name(bk_biz_id),
                data_source_label=monitor_metric["data_source_label"],
                data_type_label=monitor_metric["data_type_label"],
                scenario=monitor_metric["result_table_label"],
            ).set(monitor_metric["count"])
