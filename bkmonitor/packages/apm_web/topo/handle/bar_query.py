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
import copy
import itertools
from dataclasses import asdict, dataclass, field
from typing import Dict, List

from apm_web.constants import AlertLevel, DataStatus
from apm_web.metric_handler import (
    ApdexRange,
    ServiceFlowErrorRate,
    ServiceFlowErrorRateCallee,
    ServiceFlowErrorRateCaller,
)
from apm_web.models import Application
from apm_web.topo.constants import BarChartDataType
from apm_web.topo.handle import BaseQuery
from core.drf_resource import resource


@dataclass
class BarSeries:
    datapoints: List = field(default_factory=list)
    dimensions: Dict = field(default_factory=dict)
    target: str = ""
    type: str = "bar"
    unit: str = ""


@dataclass
class BarResponse:
    metrics: List = field(default_factory=list)
    series: List[BarSeries] = field(default_factory=list)


class BarQuery(BaseQuery):
    def execute(self) -> dict:
        if "endpoint_name" not in self.params:
            if self.application.data_status == DataStatus.NO_DATA and self.data_type != BarChartDataType.Alert.value:
                # 如果应用无数据 则柱状图显示为无数据
                return asdict(BarResponse())

            return getattr(self, f"get_{self.data_type}_series")()
        else:
            if not self.service_name:
                raise ValueError(f"[柱状图] 查询接口: {self.params['endpoint_name']} 的告警数据时需要传递服务名称")
            if self.data_type == BarChartDataType.Alert.value:
                return self.get_alert_series()
            if self.data_type == BarChartDataType.Apdex.value:
                return self.get_apdex_series()

            raise ValueError(f"[柱状图] 不支持查询接口: {self.params['endpoint_name']} 的 {self.data_type} 数据")

    def get_alert_series(self) -> Dict:
        ts_mapping = {AlertLevel.INFO: {}, AlertLevel.WARN: {}, AlertLevel.ERROR: {}}
        all_ts = []
        common_params = {
            "bk_biz_ids": [self.bk_biz_id],
            "start_time": self.start_time,
            "end_time": self.end_time,
            "interval": self.delta // 30,
            "query_string": f"metric: custom.{self.metrics_table}.*",
            "conditions": [],
        }
        if self.service_name:
            common_params["query_string"] += f' AND tags.service_name: "{self.service_name}"'

        if "endpoint_name" in self.params:
            endpoint_name = self.params["endpoint_name"]
            common_params["query_string"] += f' AND tags.span_name: "{endpoint_name}"'

        if self.params.get("strategy_ids", []):
            common_params["conditions"].append({"key": "strategy_id", "value": self.params["strategy_ids"]})

        for level in [AlertLevel.INFO, AlertLevel.WARN, AlertLevel.ERROR]:
            params = copy.deepcopy(common_params)
            params["conditions"].append({"key": "severity", "value": [level]})
            alert_series = resource.fta_web.alert.alert_date_histogram(params)
            if not all_ts and alert_series.get("series", []):
                all_ts = sorted(
                    set(itertools.chain(*[[j[0] for j in i.get("data", [])] for i in alert_series["series"]]))
                )

            ts_mapping[level] = {
                j[0]: j[1]
                for i in alert_series.get("series", [])
                if i.get("name") == "ABNORMAL"
                for j in i.get("data", [])
            }

        res = []
        for t in all_ts:
            info_count = ts_mapping[AlertLevel.INFO].get(t, 0)
            warn_count = ts_mapping[AlertLevel.WARN].get(t, 0)
            error_count = ts_mapping[AlertLevel.ERROR].get(t, 0)
            if error_count > 0:
                # 致命级别优先级最高
                res.append([[1, error_count], t])
            elif info_count > 0 or warn_count > 0:
                res.append([[2, info_count + warn_count], t])
            else:
                res.append([[3, 0], t])

        return asdict(BarResponse(series=[BarSeries(datapoints=[res])]))

    def get_apdex_series(self) -> Dict:
        wheres = self.convert_metric_to_condition()
        if "endpoint_name" in self.params:
            wheres.append({"key": "span_name", "method": "eq", "value": [self.params["endpoint_name"]]})
        return self.get_metric(
            ApdexRange,
            interval=self._get_metric_interval(),
            where=wheres,
        ).query_range()

    def get_error_rate_series(self) -> Dict:
        return self.get_metric(
            ServiceFlowErrorRate,
            interval=self._get_metric_interval(),
            where=self.convert_flow_metric_to_condition(),
        ).query_range()

    def get_error_rate_caller_series(self) -> Dict:
        return self.get_metric(
            ServiceFlowErrorRateCaller,
            interval=self._get_metric_interval(),
            where=self.convert_flow_metric_to_condition(),
        ).query_range()

    def get_error_rate_callee_series(self) -> Dict:
        return self.get_metric(
            ServiceFlowErrorRateCallee,
            interval=self._get_metric_interval(),
            where=self.convert_flow_metric_to_condition(),
        ).query_range()

    def _get_metric_interval(self):
        """
        计算 flow 指标的聚合周期
        需要保持柱状图最大柱子数量为 30
        """

        if self.end_time - self.start_time > 1800:
            return int((self.end_time - self.start_time) / 30)
        # 如果小于 30分钟 按照一分钟进行聚合
        return 60

    def convert_flow_metric_to_condition(self):
        """转换为 APM Flow 指标的 where 条件"""
        # 服务页面中获取柱状图不需要固定 caller / callee 视角 因为某服务的拓扑图反应的是所有和这个服务有关的数据 所以用 or 条件来查询
        return (
            [
                {"key": "from_apm_service_name", "method": "eq", "value": [self.service_name]},
                {"key": "to_apm_service_name", "method": "eq", "value": [self.service_name], "condition": "or"},
            ]
            if self.service_name
            else []
        )


class LinkHelper:
    @classmethod
    def get_service_alert_link(cls, bk_biz_id, app_name, service_name, start_time, end_time):
        """获取服务的告警中心链接"""
        table_id = Application.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).get().metric_result_table_id
        return (
            f"/?bizId={bk_biz_id}#/event-center?"
            f"queryString=tags.service_name: {service_name} AND metric: custom.{table_id}.*&"
            f"from={start_time * 1000}&to={end_time * 1000}"
        )

    @classmethod
    def get_endpoint_alert_link(cls, bk_biz_id, app_name, service_name, endpoint_name, start_time, end_time):
        """获取接口得告警中心链接"""
        table_id = Application.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).get().metric_result_table_id
        return (
            f"/?bizId={bk_biz_id}#/event-center?"
            f"queryString=metric: custom.{table_id}.* "
            f"AND tags.service_name: {service_name} "
            f"AND tags.span_name: {endpoint_name}&"
            f"from={start_time * 1000}&to={end_time * 1000}"
        )
