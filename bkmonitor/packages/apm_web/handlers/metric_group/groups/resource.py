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
from typing import Any, Callable, Dict, List, Optional, Tuple

from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
from constants.data_source import DataSourceLabel, DataTypeLabel

from .. import base, define


class ResourceMetricGroup(base.BaseMetricGroup):
    """定义系统容量相关算子"""

    TABLE_ID: str = ""
    USING: Tuple[str, str] = (DataTypeLabel.TIME_SERIES, DataSourceLabel.BK_MONITOR_COLLECTOR)

    DEFAULT_INTERVAL = 60

    def __init__(
        self,
        bk_biz_id: int,
        app_name: str,
        group_by: Optional[List[str]] = None,
        filter_dict: Optional[Dict[str, Any]] = None,
        interval: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(bk_biz_id, app_name, group_by, filter_dict, **kwargs)
        self.interval: int = interval or self.DEFAULT_INTERVAL

    class Meta:
        name = define.GroupEnum.RESOURCE

    def handle(self, calculation_type: str, **kwargs) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def query_config(self, calculation_type: str, **kwargs) -> Dict[str, Any]:
        return self._get_qs(calculation_type).query_config

    def _get_qs(
        self, calculation_type: str, start_time: Optional[int] = None, end_time: Optional[int] = None
    ) -> UnifyQuerySet:
        support_get_qs_methods: Dict[str, Callable[[Optional[int], Optional[int]], UnifyQuerySet]] = {
            define.CalculationType.KUBE_MEMORY_USAGE: self._kube_memory_usage_qs,
            define.CalculationType.KUBE_CPU_USAGE: self._kube_cpu_usage_qs,
            define.CalculationType.KUBE_OOM_KILLED: self._kube_oom_killed_qs,
            define.CalculationType.KUBE_ABNORMAL_RESTART: self._kube_abnormal_restart_qs,
        }
        if calculation_type not in support_get_qs_methods:
            raise ValueError(f"Unsupported calculation type -> {calculation_type}")

        return support_get_qs_methods[calculation_type](start_time, end_time)

    def _q(self, start_time: Optional[int] = None, end_time: Optional[int] = None) -> QueryConfigBuilder:
        q: QueryConfigBuilder = (
            QueryConfigBuilder(self.USING)
            .table(self.TABLE_ID)
            .time_field(self.metric_helper.TIME_FIELD)
            .interval(self.interval)
            .group_by(*self.group_by)
            .filter(self._filter_dict_to_q())
        )
        return q

    def _qs(self, start_time: Optional[int] = None, end_time: Optional[int] = None) -> UnifyQuerySet:
        return self.metric_helper.time_range_qs(start_time, end_time).limit(self.metric_helper.MAX_DATA_LIMIT)

    def _kube_memory_usage_qs(self, start_time: Optional[int] = None, end_time: Optional[int] = None) -> UnifyQuerySet:
        memory_usage_q: QueryConfigBuilder = (
            self._q(start_time, end_time)
            .alias("a")
            .metric(field="container_memory_working_set_bytes", method="sum_without_time", alias="a")
        )
        memory_limit_q: QueryConfigBuilder = (
            self._q(start_time, end_time)
            .alias("b")
            .metric(field="kube_pod_container_resource_limits_memory_bytes", method="sum_without_time", alias="b")
        )
        return (
            self._qs(start_time, end_time)
            .add_query(memory_usage_q)
            .add_query(memory_limit_q)
            .expression("(a / b) * 100")
        )

    def _kube_cpu_usage_qs(self, start_time: Optional[int] = None, end_time: Optional[int] = None) -> UnifyQuerySet:
        cpu_usage_q: QueryConfigBuilder = (
            self._q(start_time, end_time)
            .alias("a")
            .metric(field="container_cpu_usage_seconds_total", method="sum_without_time", alias="a")
            .func(_id="rate", params=[{"id": "window", "value": f"{self.interval}s"}])
        )
        cpu_limit_q: QueryConfigBuilder = (
            self._q(start_time, end_time)
            .alias("b")
            .metric(field="kube_pod_container_resource_requests_cpu_cores", method="sum_without_time", alias="b")
        )
        return self._qs(start_time, end_time).add_query(cpu_usage_q).add_query(cpu_limit_q).expression("(a / b) * 100")

    def _kube_oom_killed_qs(self, start_time: Optional[int] = None, end_time: Optional[int] = None) -> UnifyQuerySet:
        oom_killed_q: QueryConfigBuilder = (
            self._q(start_time, end_time)
            .alias("a")
            .metric(field="kube_pod_container_status_terminated_reason", method="SUM", alias="a")
            .func(_id="increase", params=[{"id": "window", "value": f"{self.interval}s"}])
            .filter(reason__eq="OOMKilled")
        )
        return self._qs(start_time, end_time).add_query(oom_killed_q).expression("a")

    def _kube_abnormal_restart_qs(
        self, start_time: Optional[int] = None, end_time: Optional[int] = None
    ) -> UnifyQuerySet:
        abnormal_restart_q: QueryConfigBuilder = (
            self._q(start_time, end_time)
            .alias("a")
            .metric(field="kube_pod_container_status_restarts_total", method="SUM", alias="a")
            .func(_id="increase", params=[{"id": "window", "value": f"{self.interval}s"}])
        )
        return self._qs(start_time, end_time).add_query(abnormal_restart_q).expression("a")
