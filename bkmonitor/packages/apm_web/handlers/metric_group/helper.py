# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import datetime
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

import arrow
from django.db.models import Q

from apm_web.models import Application
from bkmonitor.data_source import dict_to_q
from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
from bkmonitor.utils.thread_backend import ThreadPool
from bkmonitor.utils.time_tools import time_interval_align
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import resource

logger = logging.getLogger(__name__)


class MetricHelper:
    TIME_FIELD_ACCURACY = 1000

    # 默认查询近 1h 的数据
    DEFAULT_TIME_DURATION: datetime.timedelta = datetime.timedelta(hours=1)

    # 最多查询近 30d 的数据
    MAX_TIME_DURATION: datetime.timedelta = datetime.timedelta(days=30)

    MAX_OPTION_LIMIT: int = 9999

    MAX_DATA_LIMIT: int = 24 * 60 * 30

    USING: Tuple[str, str] = (DataTypeLabel.TIME_SERIES, DataSourceLabel.CUSTOM)

    TIME_FIELD: str = "time"

    def __init__(self, bk_biz_id: int, app_name: str):
        self.table_id: str = Application.get_metric_table_id(bk_biz_id, app_name)

    @property
    def q(self) -> QueryConfigBuilder:
        return QueryConfigBuilder(self.USING).table(self.table_id).time_field(self.TIME_FIELD)

    def time_range_qs(self, start_time: Optional[int] = None, end_time: Optional[int] = None) -> UnifyQuerySet:
        start_time, end_time = self._get_time_range(start_time, end_time)
        return UnifyQuerySet().start_time(start_time).end_time(end_time)

    def get_field_option_values(
        self,
        metric_field: str,
        field: str,
        filter_dict: Optional[Dict[str, Any]] = None,
        limit: int = MAX_OPTION_LIMIT,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> List[str]:
        q: QueryConfigBuilder = (
            self.q.filter(dict_to_q(filter_dict or {}) or Q())
            .metric(field=metric_field, method="count")
            .tag_values(field)
        )

        option_values: Set[str] = set()
        qs: UnifyQuerySet = self.time_range_qs(start_time, end_time).add_query(q).limit(limit)
        try:
            for bucket in qs:
                value: Optional[str] = bucket.get(field)
                if value:
                    option_values.add(value)
        except Exception:  # noqa
            logger.exception("[get_field_option_values] failed to get option values")
            pass

        return list(option_values)

    def fetch_field_option_values(
        self, params_list: List[Dict[str, Any]], start_time: Optional[int] = None, end_time: Optional[int] = None
    ) -> Dict[Tuple[str, str], List[str]]:
        def _collect(_metric_field: str, _field: str, _filter_dict: Optional[Dict[str, Any]] = None):
            group_option_values_map[(_metric_field, _field)] = self.get_field_option_values(
                _metric_field, _field, filter_dict=_filter_dict, start_time=start_time, end_time=end_time
            )

        group_option_values_map: Dict[Tuple[str, str], List[str]] = {}
        ThreadPool().map_ignore_exception(
            _collect, [(params["metric_field"], params["field"], params.get("filter_dict")) for params in params_list]
        )
        return group_option_values_map

    def get_field_option_values_by_groups(
        self, params_list: List[Dict[str, Any]], start_time: Optional[int] = None, end_time: Optional[int] = None
    ) -> List[str]:
        option_values: Set[str] = set()
        group_option_values_map: Dict[Tuple[str, str], List[str]] = self.fetch_field_option_values(
            params_list, start_time, end_time
        )
        for params in params_list:
            option_values |= set(group_option_values_map.get((params["metric_field"], params["field"])) or [])
        return list(option_values)

    @classmethod
    def _get_time_range(cls, start_time: Optional[int] = None, end_time: Optional[int] = None):
        now: int = int(datetime.datetime.now().timestamp())
        # 最早查询起始时间
        earliest_start_time: int = now - int(cls.MAX_TIME_DURATION.total_seconds())
        # 默认查询起始时间
        default_start_time: int = now - int(cls.DEFAULT_TIME_DURATION.total_seconds())

        # 开始时间不能小于 earliest_start_time
        start_time = max(earliest_start_time, start_time or default_start_time)

        # 结束时间不能大于 now
        end_time = min(now, end_time or now)

        # 省略未完成的一分钟，避免数据不准确引起误解
        interval: int = 60
        start_time = time_interval_align(start_time, interval) * cls.TIME_FIELD_ACCURACY
        end_time = time_interval_align(end_time, interval) * cls.TIME_FIELD_ACCURACY

        return start_time, end_time

    @classmethod
    def get_interval(cls, start_time: Optional[int] = None, end_time: Optional[int] = None):
        start_time, end_time = cls._get_time_range(start_time, end_time)
        return (end_time - start_time) // cls.TIME_FIELD_ACCURACY

    @classmethod
    def get_monitor_info(
        cls,
        bk_biz_id,
        result_table_id,
        service_name=None,
        monitor_name_key="scope_name",
        service_name_key="service_name",
        count: int = 3000,
        start_time=None,
        end_time=None,
        count_win: str = "5m",
        **kwargs,
    ) -> dict:
        """
        获取自定义指标的监控信息
        :param bk_biz_id: 业务ID
        :param result_table_id: 结果表ID
        :param service_name: 服务名
        :param monitor_name_key: 监控项维度名
        :param service_name_key: 服务维度名
        :param count: 查询数量
        :param start_time: 开始时间
        :param end_time: 结束时间
        :param count_win: 统计时间窗口
        """

        if not start_time or not end_time:
            end_time = int(arrow.now().timestamp)
            start_time = int(end_time - 300)

        request_params = {
            "bk_biz_id": bk_biz_id,
            "query_configs": [
                {
                    "data_source_label": DataSourceLabel.PROMETHEUS,
                    "data_type_label": DataTypeLabel.TIME_SERIES,
                    "promql": "",
                    "interval": "auto",
                    "alias": "a",
                    "filter_dict": {},
                }
            ],
            "slimit": count,
            "expression": "",
            "alias": "a",
            "start_time": start_time,
            "end_time": end_time,
        }
        metric_table_id = result_table_id.replace('.', ':')
        monitor_info_mapping = {}
        try:
            # 指定service_name
            if service_name is not None:
                promql = (
                    f"count by (metric_name, {monitor_name_key}) (count_over_time(label_replace("
                    f"{{__name__=~\"custom:{metric_table_id}:.*\", "
                    f"__name__!~\"^(rpc_server_|rpc_client_|bk_apm_|apm_).*\", "
                    f"{service_name_key}=\"{service_name}\"}}, "
                    f"\"metric_name\", \"$1\", \"__name__\", \"(.*)\")[{count_win}:]))"
                )

            else:
                promql = (
                    f"count by (metric_name, {monitor_name_key}, {service_name_key}) (count_over_time(label_replace("
                    f"{{__name__=~\"custom:{metric_table_id}:.*\", "
                    f"__name__!~\"^(rpc_server_|rpc_client_|bk_apm_|apm_).*\"}}, "
                    f"\"metric_name\", \"$1\", \"__name__\", \"(.*)\")[{count_win}:]))"
                )

            request_params["query_configs"][0]["promql"] = promql
            series = resource.grafana.graph_unify_query(request_params)["series"]
            for metric in series:
                metric_field = metric.get("dimensions", {}).get("metric_name")
                metric_service_name = service_name or metric.get("dimensions", {}).get(service_name_key)
                if metric_service_name and metric_field:
                    if metric_service_name not in monitor_info_mapping:
                        monitor_info_mapping[metric_service_name] = {}
                    if metric_field not in monitor_info_mapping[metric_service_name]:
                        monitor_info_mapping[metric_service_name][metric_field] = {"monitor_name_list": []}
                    monitor_name = metric["dimensions"].get(monitor_name_key) or "default"
                    if monitor_name not in monitor_info_mapping[metric_service_name][metric_field]["monitor_name_list"]:
                        monitor_info_mapping[metric_service_name][metric_field]["monitor_name_list"].append(
                            monitor_name
                        )
        except Exception as e:  # pylint: disable=broad-except
            logger.warning(f"查询自定义指标关键维度信息失败: {e} ")

        return monitor_info_mapping
