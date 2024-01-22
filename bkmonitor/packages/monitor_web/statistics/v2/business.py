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
from django.utils.functional import cached_property

from apm_ebpf.models import DeepflowWorkload
from apm_web.constants import DataStatus
from apm_web.models import Application
from bkmonitor.data_source import UnifyQuery, load_data_source
from bkmonitor.models import (
    AlgorithmModel,
    BCSCluster,
    QueryConfigModel,
    StrategyActionConfigRelation,
    StrategyModel,
)
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.statistics.metric import Metric, register
from metadata.models import TimeSeriesGroup
from monitor.models import UptimeCheckTask
from monitor_web.models.custom_report import CustomEventGroup
from monitor_web.statistics.v2.base import TIME_RANGE, BaseCollector
from utils.business import ACTIVE_BIZ_LAST_VISIT_TIME
from utils.redis_client import redis_cli


class BusinessCollector(BaseCollector):
    """
    业务数
    """

    DEFAULT_TS_DATA_DURATION = "3m"

    @cached_property
    def uptime_check_biz_count(self) -> int:
        return (
            UptimeCheckTask.objects.filter(bk_biz_id__in=list(self.biz_info.keys()))
            .values("bk_biz_id")
            .distinct()
            .count()
        )

    @cached_property
    def custom_time_series_biz_count(self) -> int:
        return (
            TimeSeriesGroup.objects.filter(bk_biz_id__in=list(self.biz_info.keys()))
            .values("bk_biz_id")
            .distinct()
            .count()
        )

    @cached_property
    def custom_event_biz_count(self) -> int:
        return (
            CustomEventGroup.objects.filter(bk_biz_id__in=list(self.biz_info.keys()))
            .values("bk_biz_id")
            .distinct()
            .count()
        )

    @cached_property
    def strategies(self):
        return StrategyModel.objects.filter(is_enabled=True, is_invalid=False, bk_biz_id__in=list(self.biz_info.keys()))

    @cached_property
    def valid_strategies_biz_count(self):
        return self.strategies.values("bk_biz_id").distinct().count()

    @cached_property
    def action_strategies_biz_count(self):
        return (
            self.strategies.filter(
                pk__in=StrategyActionConfigRelation.objects.filter(
                    relate_type=StrategyActionConfigRelation.RelateType.ACTION
                ).values_list("strategy_id", flat=True)
            )
            .values("bk_biz_id")
            .distinct()
            .count()
        )

    @cached_property
    def log_strategies_biz_count(self):
        return (
            self.strategies.filter(
                pk__in=QueryConfigModel.objects.filter(data_type_label="log").values_list("strategy_id", flat=True)
            )
            .values("bk_biz_id")
            .distinct()
            .count()
        )

    @cached_property
    def host_biz_count(self):
        now_ts = arrow.now()
        data_source = load_data_source(DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES)(
            table="system.cpu_summary",
            metrics=[{"field": "idle", "method": "COUNT", "alias": "a"}],
            interval=60,
            group_by=["bk_biz_id"],
        )
        query = UnifyQuery(bk_biz_id=None, data_sources=[data_source], expression="")
        try:
            records = query.query_data(
                start_time=now_ts.replace(minutes=-3).timestamp * 1000, end_time=now_ts.timestamp * 1000
            )
        except Exception:
            # 由于全业务数据量级过大，可能会在 bk_biz_id 上增加路由，从而无法直接一口气拉取到全业务数据
            # 暂时没有太轻量的方法解决，为了保证整体指标的可用性，返回一个错误值标记
            return -1

        biz_info = set()
        for item in records:
            if not item["bk_biz_id"]:
                continue

            biz_info.add(item["bk_biz_id"])

        return len(biz_info)

    @cached_property
    def process_biz_count(self):
        now_ts = arrow.now()
        data_source = load_data_source(DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES)(
            table="system.proc",
            metrics=[{"field": "uptime", "method": "COUNT", "alias": "a"}],
            interval=60,
            group_by=["bk_biz_id"],
        )
        query = UnifyQuery(bk_biz_id=None, data_sources=[data_source], expression="")
        try:
            records = query.query_data(
                start_time=now_ts.replace(minutes=-3).timestamp * 1000, end_time=now_ts.timestamp * 1000
            )
        except Exception:
            # 由于全业务数据量级过大，可能会在 bk_biz_id 上增加路由，从而无法直接一口气拉取到全业务数据
            # 暂时没有太轻量的方法解决，为了保证整体指标的可用性，返回一个错误值标记
            # TODO: 找到一个足够轻量的方法统计进程业务使用数
            return -1

        biz_info = set()
        for item in records:
            if not item["bk_biz_id"]:
                continue

            biz_info.add(item["bk_biz_id"])

        return len(biz_info)

    @cached_property
    def k8s_biz_count(self):
        return BCSCluster.objects.filter().values_list("bk_biz_id", flat=True).distinct().count()

    @cached_property
    def apm_biz_count(self):
        return (
            Application.objects.filter(
                bk_biz_id__in=list(self.biz_info.keys()), is_enabled=True, data_status=DataStatus.NORMAL
            )
            .values_list("bk_biz_id", flat=True)
            .distinct()
            .count()
        )

    @cached_property
    def ebpf_biz_count(self):
        """
        ebpf 使用业务数
        目前只有K8S集群部署模式，统计的时候只统计CC的业务数(bk_biz_id>0)，不然会重复统计
        """
        return DeepflowWorkload.objects.filter(bk_biz_id__gt=0).values_list("bk_biz_id", flat=True).distinct().count()

    @cached_property
    def aiops_strategy_biz_count(self):
        algorithm_strategy_ids = list(
            AlgorithmModel.objects.filter(type__in=AlgorithmModel.AIOPS_ALGORITHMS).values_list(
                "strategy_id", flat=True
            )
        )
        return self.strategies.filter(pk__in=algorithm_strategy_ids).values("bk_biz_id").distinct().count()

    @register(labelnames=("time_range",))
    def business_active_count(self, metric: Metric):
        """
        业务数
        """
        now = arrow.now()
        for le_en, seconds in TIME_RANGE:
            start_time = now.replace(seconds=-seconds)
            active_business_list = redis_cli.zrevrangebyscore(
                ACTIVE_BIZ_LAST_VISIT_TIME, now.timestamp, start_time.timestamp
            )

            metric.labels(time_range=le_en).set(len(active_business_list))

    @register(labelnames=("function",))
    def biz_usage_count(self, metric: Metric):
        """功能使用的业务数"""

        metric.labels(function="uptimecheck").inc(self.uptime_check_biz_count)
        metric.labels(function="custom_time_series").inc(self.custom_time_series_biz_count)
        metric.labels(function="custom_event").inc(self.custom_event_biz_count)

        metric.labels(function="has_valid_strategy").inc(self.valid_strategies_biz_count)
        metric.labels(function="has_aiops_strategy").inc(self.aiops_strategy_biz_count)
        metric.labels(function="has_action_strategy").inc(self.action_strategies_biz_count)
        metric.labels(function="has_log_strategy").inc(self.log_strategies_biz_count)
        metric.labels(function="host").inc(self.host_biz_count)
        metric.labels(function="process").inc(self.process_biz_count)
        metric.labels(function="k8s").inc(self.k8s_biz_count)
        metric.labels(function="apm").inc(self.apm_biz_count)
        metric.labels(function="ebpf").inc(self.ebpf_biz_count)
