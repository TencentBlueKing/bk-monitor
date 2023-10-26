"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import logging
from collections import defaultdict
from typing import List, Optional, Tuple, Union

import arrow
from django.utils.functional import cached_property
from monitor_web.models import CustomEventGroup, CustomTSTable
from monitor_web.statistics.v2.base import BaseCollector

from bkmonitor.data_source import UnifyQuery, load_data_source
from core.statistics.metric import Metric, register

logger = logging.getLogger(__name__)


class BkCollectorCollector(BaseCollector):
    """采集器指标收集器"""

    DEFAULT_QUERY_PERIOD = 600

    def _query(self, table: str, group_by: Optional[List[str]] = None) -> dict:
        group_by = group_by or ["bk_biz_id", "bk_cloud_id", "bk_host_innerip"]

        alias = "a"
        method = "SUM"
        query = [
            {
                "data_source_label": "custom",
                "data_type_label": "time_series",
                "metrics": [{"field": table, "method": method, "alias": alias}],
                "table": "datalink_stats.__default__",
                "group_by": group_by,
                "where": [],
                "interval": 60,
                "interval_unit": "s",
                "filter_dict": {},
                "functions": [],
            }
        ]

        now_ts = arrow.now().timestamp
        data_sources = []
        for query_config in query:
            data_source_class = load_data_source(query_config["data_source_label"], query_config["data_type_label"])
            data_source = data_source_class(bk_biz_id=0, **query_config)
            query_config["group_by"] = data_source.group_by
            data_sources.append(data_source)

        query = UnifyQuery(
            bk_biz_id=0,
            data_sources=data_sources,
            expression=alias,
            functions=[],
        )
        points = query.query_data(
            start_time=(now_ts - self.DEFAULT_QUERY_PERIOD) * 1000,
            end_time=now_ts * 1000,
            slimit=500,
            down_sample_range="3s",
        )
        biz_count = defaultdict(int)

        # 获取时间段内最大值
        for p in points:
            try:
                key = tuple([p[group] for group in group_by])
            except KeyError as e:
                logger.warning("point<%s> missing dimension: %s", p, e)
                continue

            if p["_result_"] > biz_count[key]:
                biz_count[key] = p["_result_"]

        return biz_count

    @cached_property
    def custom_report_data_id_map(self) -> dict:
        data_id_name_map = {}
        for ts_group in CustomEventGroup.objects.values("bk_data_id", "name", "data_label"):
            data_id_name_map[ts_group["bk_data_id"]] = (ts_group["name"], ts_group["data_label"])

        for ts_table in CustomTSTable.objects.values("bk_data_id", "name", "data_label"):
            data_id_name_map[ts_table["bk_data_id"]] = (ts_table["name"], ts_table["data_label"])

        return data_id_name_map

    def get_data_names(self, data_id: Union[str, int]) -> Tuple[str, str]:
        return self.custom_report_data_id_map.get(int(data_id), (str(data_id), str(data_id)))

    @register(labelnames=("bk_biz_id", "bk_biz_name", "bk_cloud_id", "bk_host_innerip"))
    def bkmonitorbeat_records_count(self, metric: Metric):
        """bkmonitorbeat 采集器的采集记录数量"""
        for biz_info, count in self._query(table="bkmonitorbeat_global_events_sent_total").items():
            biz_id, cloud_id, host_innerip = biz_info
            metric.labels(
                bk_biz_id=biz_id,
                bk_biz_name=self.get_biz_name(biz_id),
                bk_cloud_id=cloud_id,
                bk_host_innerip=host_innerip,
            ).inc(count)

    @register(labelnames=("bk_biz_id", "bk_biz_name", "bk_cloud_id", "bk_host_innerip"))
    def bkmonitorbeat_instances_count(self, metric: Metric):
        """bkmonitorbeat 实例数"""
        for biz_info, count in self._query(table="bkmonitorbeat_global_build_info").items():
            biz_id, cloud_id, host_innerip = biz_info
            metric.labels(
                bk_biz_id=biz_id,
                bk_biz_name=self.get_biz_name(biz_id),
                bk_cloud_id=cloud_id,
                bk_host_innerip=host_innerip,
            ).inc(count)

    @register(
        labelnames=(
            "bk_biz_id",
            "bk_biz_name",
            "bk_cloud_id",
            "bk_host_innerip",
            "data_id",
            "data_name",
            "data_display_name",
            "record_type",
        )
    )
    def bk_collector_records_count(self, metric: Metric):
        """bk-collector 采集器的采集记录数量"""
        group_by = ["bk_biz_id", "bk_cloud_id", "bk_host_innerip", "id", "record_type"]
        for biz_info, count in self._query(table="bk_collector_pipeline_handled_total", group_by=group_by).items():
            biz_id, cloud_id, host_innerip, data_id, record_type = biz_info
            data_name, data_display_name = self.get_data_names(data_id)
            metric.labels(
                bk_biz_id=biz_id,
                bk_biz_name=self.get_biz_name(biz_id),
                bk_cloud_id=cloud_id,
                bk_host_innerip=host_innerip,
                data_id=data_id,
                data_name=data_name,
                data_display_name=data_display_name,
                record_type=record_type,
            ).inc(count)

    @register(labelnames=("bk_biz_id", "bk_biz_name", "bk_cloud_id", "bk_host_innerip"))
    def bk_collector_instances_count(self, metric: Metric):
        """bk-collector 实例数"""
        for biz_info, count in self._query(table="bk_collector_app_build_info").items():
            biz_id, cloud_id, host_innerip = biz_info
            metric.labels(
                bk_biz_id=biz_id,
                bk_biz_name=self.get_biz_name(biz_id),
                bk_cloud_id=cloud_id,
                bk_host_innerip=host_innerip,
            ).inc(count)

    @register(labelnames=("bk_biz_id", "bk_biz_name", "bk_cloud_id", "data_id", "data_name", "data_display_name"))
    def bk_collector_receiver_metrics_count(self, metric: Metric):
        """自定义事件接收上报数"""
        for biz_info, count in self._query(
            table="bk_collector_exporter_handled_event_total",
            group_by=["bk_biz_id", "bk_cloud_id", "id"],
        ).items():
            biz_id, cloud_id, data_id = biz_info
            data_name, data_display_name = self.get_data_names(data_id)
            metric.labels(
                bk_biz_id=biz_id,
                bk_biz_name=self.get_biz_name(biz_id),
                bk_cloud_id=cloud_id,
                data_id=data_id,
                data_name=data_name,
                data_display_name=data_display_name,
            ).inc(count)

    @register(labelnames=("bk_biz_id", "bk_biz_name", "bk_cloud_id", "data_id", "data_name", "data_display_name"))
    def bk_collector_receiver_events_count(self, metric: Metric):
        """自定义指标接收上报数"""
        for biz_info, count in self._query(
            table="bk_collector_exporter_handled_event_total", group_by=["bk_biz_id", "bk_cloud_id", "id"]
        ).items():
            biz_id, cloud_id, data_id = biz_info
            data_name, data_display_name = self.get_data_names(data_id)
            metric.labels(
                bk_biz_id=biz_id,
                bk_biz_name=self.get_biz_name(biz_id),
                bk_cloud_id=cloud_id,
                data_id=data_id,
                data_name=data_name,
                data_display_name=data_display_name,
            ).inc(count)
