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
import math
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import arrow
from django.db.models import Q

from apm_web.models import Application
from bkmonitor.data_source import dict_to_q
from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
from bkmonitor.utils.thread_backend import ThreadPool
from bkmonitor.utils.time_format import parse_duration
from bkmonitor.utils.time_tools import (
    parse_time_compare_abbreviation,
    time_interval_align,
)
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
        start_time, end_time = self.get_time_range(start_time, end_time)
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
    def get_time_range(
        cls, start_time: Optional[int] = None, end_time: Optional[int] = None, with_accuracy: bool = True
    ):
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
        start_time, end_time = time_interval_align(start_time, interval), time_interval_align(end_time, interval)

        if not with_accuracy:
            return start_time, end_time

        return start_time * cls.TIME_FIELD_ACCURACY, end_time * cls.TIME_FIELD_ACCURACY

    @classmethod
    def get_interval(cls, start_time: Optional[int] = None, end_time: Optional[int] = None):
        start_time, end_time = cls.get_time_range(start_time, end_time)
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
                    f"__name__!=\"rpc_client_handled_total\", "
                    f"__name__!=\"rpc_client_handled_seconds_sum\", "
                    f"__name__!=\"rpc_client_handled_seconds_count\", "
                    f"__name__!=\"rpc_client_handled_seconds_bucket\", "
                    f"__name__!=\"rpc_server_handled_total\", "
                    f"__name__!=\"rpc_server_handled_seconds_sum\", "
                    f"__name__!=\"rpc_server_handled_seconds_count\", "
                    f"__name__!=\"rpc_server_handled_seconds_bucket\", "
                    f"__name__!~\"^(bk_apm_|apm_).*\", "
                    f"{service_name_key}=\"{service_name}\"}}, "
                    f"\"metric_name\", \"$1\", \"__name__\", \"(.*)\")[{count_win}:]))"
                )

            else:
                promql = (
                    f"count by (metric_name, {monitor_name_key}, {service_name_key}) (count_over_time(label_replace("
                    f"{{__name__=~\"custom:{metric_table_id}:.*\", "
                    f"__name__!=\"rpc_client_handled_total\", "
                    f"__name__!=\"rpc_client_handled_seconds_sum\", "
                    f"__name__!=\"rpc_client_handled_seconds_count\", "
                    f"__name__!=\"rpc_client_handled_seconds_bucket\", "
                    f"__name__!=\"rpc_server_handled_total\", "
                    f"__name__!=\"rpc_server_handled_seconds_sum\", "
                    f"__name__!=\"rpc_server_handled_seconds_count\", "
                    f"__name__!=\"rpc_server_handled_seconds_bucket\", "
                    f"__name__!~\"^(bk_apm_|apm_).*\"}}, "
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


class PreCalculateHelper:
    """指标预计算工具类，配置示例：
    {
        "enabled": true,
        # 数据延迟
        "data_delay": "3m",
        # 数据偏移，用于对齐原指标数据
        "time_shift": "-1m"
        # 最小查询时长
        "min_duration": "1h",
        "metrics": {
            "rpc_client_handled_seconds_bucket": [
                {
                    # 屏蔽维度
                    "drop_labels": [
                        "callee_ip",
                        "caller_ip",
                        "instance"
                    ],
                    # 预计算指标名
                    "metric": "sum_without_ip_rpc_client_handled_seconds_bucket",
                    # 最小查询时长，优先级高于外层
                    "min_duration": "30m"
                }
            ]
        },
        # 查询屏蔽时间，为空表示无穷远，比如 (start_time, nil) 表示屏蔽 >= start_time
        "shield_time_ranges": [{"start_time": 1740405600}],
        # 预计算结果表 ID
        "table_id": "xxx"
    }
    """

    def __init__(self, config: Dict[str, Any]):
        self._config: Dict[str, Any] = config

    def _is_enabled(self) -> bool:
        """启用预计算时返回 True，默认启用"""
        return self._config.get("enabled", True)

    def adjust_time_shift(self, origin_time_shift: Optional[str]) -> str:
        """指标时间戳对齐"""
        time_shift: str = self._config.get("time_shift", "-1m")
        if origin_time_shift is None:
            return time_shift

        sec_time_shift: int = -1 * parse_time_compare_abbreviation(time_shift)
        origin_sec_time_shift: int = -1 * parse_time_compare_abbreviation(origin_time_shift)
        return f"{sec_time_shift + origin_sec_time_shift}s"

    def adjust_time_range(self, start_time: int, end_time: int) -> Tuple[int, int]:
        """调整查询数据范围
        背景：预计算存在一定的数据延迟，如果查询时间临近当前时间，按数据延迟进行截断，避免最后一个点数据存在较大误差影响观测
        """
        data_delay_sec: int = parse_duration(self._config.get("data_delay", "0s"))
        is_near_to_now: bool = abs(end_time - int(datetime.datetime.now().timestamp())) < 60
        if end_time - start_time > data_delay_sec and is_near_to_now:
            logger.info("[adjust_time_range] adjust end_time -> %s, data_delay_sec -> %s", end_time, data_delay_sec)
            end_time -= data_delay_sec

        return start_time, end_time

    def _is_time_shield(
        self,
        metric_info: Dict[str, Any],
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        time_shift: Optional[str] = None,
    ) -> bool:
        """判断是否屏蔽预计算
        - 规则-1：查询时长 >= min_duration
        - 规则-2: 查询时间范围不在屏蔽时间范围内
        """
        min_duration: Optional[str] = metric_info.get("min_duration") or self._config.get("min_duration")
        start_time, end_time = self.shift_time_range(start_time, end_time, time_shift)
        duration: int = end_time - start_time
        # 判断查询时间是否小于等于最小路由间隔
        if min_duration and duration <= parse_duration(min_duration):
            logger.info(
                "[is_time_shield] shield due to duration: metric -> %s, duration -> %s, min_duration -> %s",
                metric_info["metric"],
                duration,
                min_duration,
            )
            return True

        for shield_time_range in self._config.get("shield_time_ranges") or []:
            # 为空表示无穷远，比如 (start_time, nil) 表示屏蔽 >= start_time
            shield_start_time: float = shield_time_range.get("start_time", 0)
            shield_end_time: float = shield_time_range.get("end_time", math.inf)

            # 判断查询时间范围是否与屏蔽范围有交集
            if start_time <= shield_end_time and end_time >= shield_start_time:
                logger.info(
                    "[is_time_shield] shield due to range: metric -> %s, time_range(%s, %s), query_range(%s, %s)",
                    metric_info["metric"],
                    shield_start_time,
                    shield_end_time,
                    start_time,
                    end_time,
                )
                return True

        logger.info(
            "[is_time_shield] not shield: metric -> %s, query_range -> (%s, %s), duration -> %s, min_duration -> %s",
            metric_info["metric"],
            start_time,
            end_time,
            duration,
            min_duration,
        )
        return False

    def router(
        self,
        table_id: str,
        metric: str,
        used_labels: Iterable[str],
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        time_shift: Optional[str] = None,
    ) -> Dict[str, Any]:
        """将原始指标路由到预计算指标
        :param table_id: 原结果表
        :param metric: 原指标
        :param used_labels: 本次计算使用到的维度
        :param end_time: 开始时间
        :param start_time: 结束时间
        :param time_shift: 时间偏移
        :return:
        """
        result: Dict[str, Any] = {"table_id": table_id, "metric": metric, "is_hit": False}
        if not self._is_enabled():
            return result

        try:
            pre_cal_metric_infos: List[Dict[str, Any]] = self._config["metrics"][metric]
        except KeyError:
            return result

        used_labels: Set[str] = set(used_labels)
        for metric_info in pre_cal_metric_infos:
            drop_labels: Set[str] = set(metric_info.get("drop_labels") or [])
            if used_labels & drop_labels:
                continue

            if "table_id" in self._config and "metric" in metric_info:
                if self._is_time_shield(metric_info, start_time, end_time, time_shift):
                    continue

                result["is_hit"] = True
                result["metric"] = metric_info["metric"]
                # 支持 metric 单独定义 table_id，优先级比外层高。
                result["table_id"] = metric_info.get("table_id") or self._config["table_id"]
                break

        return result

    @classmethod
    def shift_time_range(
        cls, start_time: Optional[int] = None, end_time: Optional[int] = None, time_shift: Optional[str] = None
    ) -> Tuple[int, int]:
        start_time, end_time = MetricHelper.get_time_range(start_time, end_time, with_accuracy=False)
        if not time_shift:
            return start_time, end_time

        start_time += parse_time_compare_abbreviation(time_shift)
        end_time += parse_time_compare_abbreviation(time_shift)
        return start_time, end_time
