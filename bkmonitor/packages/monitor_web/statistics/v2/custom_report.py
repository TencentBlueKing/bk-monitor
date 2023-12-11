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
from collections import defaultdict

from django.utils.functional import cached_property

from core.statistics.metric import Metric, register
from monitor_web.models import CustomEventGroup, CustomTSTable
from monitor_web.statistics.v2.base import BaseCollector


class CustomReportCollector(BaseCollector):
    """
    自定义上报事件
    """

    @cached_property
    def custom_report_event_group(self):
        return CustomEventGroup.objects.filter(bk_biz_id__in=list(self.biz_info.keys()))

    @cached_property
    def custom_report_metric_table(self):
        return CustomTSTable.objects.filter(bk_biz_id__in=list(self.biz_info.keys()))

    @cached_property
    def custom_report_event(self):
        # TODO: 该采集需要优化
        # event_group_list = api.metadata.query_event_group()
        event_group_list = []
        event_name_dict = defaultdict(int)
        data_id_name_map = {}
        for event_group in event_group_list:
            key = "{bk_biz_id}|{bk_data_id}".format(**event_group)
            event_name_dict[key] += len(event_group.get("event_info_list") or [])
            data_id_name_map[event_group["bk_data_id"]] = event_group["event_group_name"]

        event_metrics = []
        for key, event_count in event_name_dict.items():
            bk_biz_id, bk_data_id = key.split("|")
            bk_biz_id = int(bk_biz_id)
            if self.biz_exists(bk_biz_id):
                event_metrics.append(
                    {
                        "value": event_count,
                        "labels": {
                            "bk_biz_id": bk_biz_id,
                            "bk_biz_name": self.get_biz_name(bk_biz_id),
                            "data_id": bk_data_id,
                            "data_name": data_id_name_map[int(bk_data_id)],
                        },
                    }
                )

        return event_metrics

    @cached_property
    def custom_report_metric(self):
        # 自定义指标上报，指标总量
        # TODO: 该采集需要优化
        # ts_group_list = api.metadata.query_time_series_group()
        ts_group_list = []
        metrics_dict = defaultdict(int)
        data_id_name_map = {}
        for ts_group in ts_group_list:
            key = "{bk_biz_id}|{bk_data_id}".format(**ts_group)
            metrics_dict[key] += len(ts_group.get("metric_info_list") or [])
            data_id_name_map[ts_group["bk_data_id"]] = ts_group["time_series_group_name"]

        ts_metrics = []
        for key, metric_count in metrics_dict.items():
            bk_biz_id, bk_data_id = key.split("|")
            bk_biz_id = int(bk_biz_id)
            if self.biz_exists(bk_biz_id):
                ts_metrics.append(
                    {
                        "value": metric_count,
                        "labels": {
                            "bk_biz_id": bk_biz_id,
                            "bk_biz_name": self.get_biz_name(bk_biz_id),
                            "data_id": bk_data_id,
                            "data_name": data_id_name_map[int(bk_data_id)],
                        },
                    }
                )
        return ts_metrics

    @register(labelnames=("bk_biz_id", "bk_biz_name", "scenario", "is_platform"), run_every=15 * 60)
    def custom_report_event_dataid_count(self, metric: Metric):
        """
        自定义事件组名称数
        """
        for event in self.custom_report_event_group:
            is_platform = 1 if event.is_platform else 0
            metric.labels(
                bk_biz_id=event.bk_biz_id,
                bk_biz_name=self.get_biz_name(event.bk_biz_id),
                scenario=event.scenario,
                is_platform=is_platform,
            ).inc()

    @register(labelnames=("bk_biz_id", "bk_biz_name", "scenario", "is_platform"), run_every=15 * 60)
    def custom_report_metric_dataid_count(self, metric: Metric):
        """
        自定义时序数
        """
        for custom_report_metric in self.custom_report_metric_table:
            is_platform = 1 if custom_report_metric.is_platform else 0
            metric.labels(
                bk_biz_id=custom_report_metric.bk_biz_id,
                bk_biz_name=self.get_biz_name(custom_report_metric.bk_biz_id),
                scenario=custom_report_metric.scenario,
                is_platform=is_platform,
            ).inc()

    @register(labelnames=("bk_biz_id", "bk_biz_name", "data_id", "data_name"), run_every=15 * 60)
    def custom_report_event_name_count(self, metric: Metric):
        """
        自定义事件名称数
        """
        for event in self.custom_report_event:
            if not event["value"]:
                continue

            metric.labels(**event["labels"]).set(event["value"])

    @register(labelnames=("bk_biz_id", "bk_biz_name", "data_id", "data_name"), run_every=15 * 60)
    def custom_report_metric_name_count(self, metric: Metric):
        """
        自定义时序指标数
        """
        for ts in self.custom_report_metric:
            if not ts["value"]:
                continue

            metric.labels(**ts["labels"]).set(ts["value"])
