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
import json
import urllib.parse
from collections import defaultdict

from django.utils.translation import gettext_lazy as _
from opentelemetry.semconv.resource import ResourceAttributes

from apm_web.calculation import ErrorRateCalculation
from apm_web.constants import component_where_mapping
from apm_web.handlers.component_handler import ComponentHandler
from apm_web.handlers.service_handler import ServiceHandler
from apm_web.metric_handler import AvgDurationInstance, RequestCountInstance
from apm_web.models import Application
from bkmonitor.utils import group_by
from constants.apm import OtlpKey
from core.unit import load_unit
from monitor_web.scene_view.builtin.apm import ApmBuiltinProcessor

TOP_N_HANDLERS = {}


def load_top_n_handler(query_type: str):
    return TOP_N_HANDLERS.get(query_type)


def get_top_n_query_type():
    return list(TOP_N_HANDLERS.keys())


def register(top_n):
    TOP_N_HANDLERS[top_n.query_type] = top_n
    return top_n


class TopNHandler:
    query_type = None
    # 返回单条数据
    instant = True

    group_by_keys = []

    def __init__(self, application: Application, start_time: int, end_time: int, size: int, filter_dict=None):
        self.application = application
        self.start_time = start_time
        self.end_time = end_time
        self.size = size
        self.filter_dict = filter_dict or {}

        self.service_name_key = OtlpKey.get_metric_dimension_key(ResourceAttributes.SERVICE_NAME)
        self.service_name = self.filter_dict.get(self.service_name_key)
        self.node = ServiceHandler.get_node(
            self.application.bk_biz_id,
            self.application.app_name,
            self.service_name,
            raise_exception=False,
        )

    @property
    def is_service_filter(self):
        return "service_name" in self.filter_dict

    def top_n(self):
        """
        [
                {
                    "total": 1000,
                    "unit": _("次"),
                    "name": "test",
                    "value": 123,
                }
            ]
        """
        pass

    def get_topo_n_data(
        self,
    ):
        if self.filter_dict.get(self.service_name_key) and not self.node:
            # 如果存在服务过滤但是没有查询到节点 说明此服务无数据
            return []

        return self.top_n()[: self.size]

    def get_endpoint_split(self, item):
        return item

    def get_condition(self):
        """如果是组件的话获取查询条件"""
        where_condition = []
        if not self.service_name:
            return self.filter_dict, where_condition

        # 服务页面下
        if ComponentHandler.is_component_by_node(self.node):
            # 在组件类型的服务页面下 需要添加组件的 predicate_value 进行查询
            where_condition.append(
                json.loads(
                    json.dumps(component_where_mapping[self.node["extra_data"]["category"]]).replace(
                        "{predicate_value}", self.node["extra_data"]["predicate_value"]
                    )
                )
            )
            pure_service_name = ComponentHandler.get_component_belong_service(self.filter_dict[self.service_name_key])
            self.filter_dict[self.service_name_key] = pure_service_name

        if ServiceHandler.is_remote_service_by_node(self.node):
            # 自定义服务下 需要加上 peer_service 查询条件
            pure_service_name = ServiceHandler.get_remote_service_origin_name(self.service_name)
            self.filter_dict["peer_service"] = pure_service_name
            self.filter_dict.pop(self.service_name_key, None)

        return self.filter_dict, where_condition

    def collect_sum_metrics(self, metrics, group_keys, group_handler=None):
        if not group_handler:

            def _handler(_metrics):
                return sum(item.get("_result_", 0) for item in _metrics)

            group_handler = _handler

        res = []
        group_key_mapping = group_by(metrics, lambda item: tuple(item.get(g, "") for g in group_keys))
        for k, v in group_key_mapping.items():
            res.append({"_result_": group_handler(v), **{i: k[index] for index, i in enumerate(group_keys)}})

        return res

    def _is_service_view(self):
        # 是否是服务视图下的请求
        return "service_name" in self.filter_dict

    def build_link(self, service_name, span_name):
        """在不同视图下(应用/服务)会有不同的url链接"""
        query_params = {
            "filter-app_name": self.application.app_name,
            "filter-endpoint_name": span_name,
            "filter-service_name": service_name,
            "sceneType": "detail",
        }
        if self._is_service_view():
            query_params["sceneId"] = "apm_service"
            query_params["dashboardId"] = "service-default-endpoint"

            if ComponentHandler.is_component_by_node(self.node):
                predicate_views = f"component-{self.node['extra_data']['predicate_value']}-endpoint"
                if ApmBuiltinProcessor.exists_views(predicate_views):
                    query_params["dashboardId"] = predicate_views
                else:
                    query_params["dashboardId"] = "component-default-endpoint"

            url = f"/service?{urllib.parse.urlencode(query_params)}"
        else:
            query_params["sceneId"] = "apm_application"
            query_params["dashboardId"] = "endpoint"
            url = f"/application?{urllib.parse.urlencode(query_params)}"

        return url

    def agg_data(self, series):
        """数据聚合"""

        aggregated_results = {}
        for i in series:
            result = i["_result_"]

            unique_key = tuple(i.get(key) for key in self.group_by_keys)
            if unique_key in aggregated_results:
                aggregated_results[unique_key] += result
            else:
                aggregated_results[unique_key] = result
        res = []
        for k, v in aggregated_results.items():
            res.append({"_result_": v, **{key: k[index] for index, key in enumerate(self.group_by_keys)}})
        return res


@register
class EndpointCalledCountTopNHandler(TopNHandler):
    query_type = "endpoint_called_count"

    JOIN_CHAR = " | "

    group_by_keys = [
        OtlpKey.SPAN_NAME,
        OtlpKey.get_metric_dimension_key(ResourceAttributes.SERVICE_NAME),
    ]

    def get_endpoint_split(self, item):
        return item["name"].split(self.JOIN_CHAR)[-1]

    def _query_metric(self):
        filter_dict, where_condition = self.get_condition()

        metrics = RequestCountInstance(
            self.application,
            self.start_time,
            self.end_time,
            group_by=self.group_by_keys,
            filter_dict=filter_dict,
            where=where_condition,
        ).origin_query_instance()

        return self.collect_sum_metrics(metrics, self.group_by_keys)

    def top_n(self):
        series = self._query_metric()

        series = self.agg_data(series)

        sum_count = sum([serie["_result_"] for serie in series])
        result = []
        for serie in series:
            if OtlpKey.SPAN_NAME not in serie:
                continue

            service_name = serie.get(OtlpKey.get_metric_dimension_key(ResourceAttributes.SERVICE_NAME), "")
            span_name = serie[OtlpKey.SPAN_NAME]

            result.append(
                {
                    "total": sum_count,
                    "unit": _("次"),
                    "name": service_name + self.JOIN_CHAR + span_name if not self.is_service_filter else span_name,
                    "value": serie["_result_"],
                    "type": "link",
                    "url": self.build_link(service_name, span_name),
                    "target": "event",
                    "key": "switch_scenes_type",
                }
            )
        result = sorted(result, key=lambda item: int(item["value"]), reverse=True)

        return result


@register
class EndpointErrorRateTopNHandler(TopNHandler):
    query_type = "endpoint_error_rate"

    JOIN_CHAR = " | "

    group_by_keys = [
        OtlpKey.SPAN_NAME,
        OtlpKey.get_metric_dimension_key(OtlpKey.STATUS_CODE),
        OtlpKey.get_metric_dimension_key(ResourceAttributes.SERVICE_NAME),
    ]

    def get_endpoint_split(self, item):
        return item["name"].split(self.JOIN_CHAR)[-1]

    def _query_metric(self):
        database_name, _ = self.application.metric_result_table_id.split(".")

        filter_dict, where_condition = self.get_condition()

        group_keys = [
            OtlpKey.SPAN_NAME,
            OtlpKey.get_metric_dimension_key(OtlpKey.STATUS_CODE),
            OtlpKey.get_metric_dimension_key(ResourceAttributes.SERVICE_NAME),
        ]
        metrics = RequestCountInstance(
            self.application,
            self.start_time,
            self.end_time,
            group_by=self.group_by_keys,
            filter_dict=filter_dict,
            where=where_condition,
        ).origin_query_instance()

        return self.collect_sum_metrics(metrics, group_keys)

    def top_n(
        self,
    ):
        series = self._query_metric()
        series = self.agg_data(series)
        endpoint_map = defaultdict(list)
        for serie in series:
            if OtlpKey.SPAN_NAME not in serie:
                continue

            service_name = serie.get(OtlpKey.get_metric_dimension_key(ResourceAttributes.SERVICE_NAME))
            if not service_name:
                continue

            span_name = serie[OtlpKey.SPAN_NAME]

            endpoint_map[(service_name, span_name)].append(serie)
        result = []
        for keys, value in endpoint_map.items():
            error_count, sum_count = ErrorRateCalculation.common_unify_series_cal(value)
            if not error_count:
                # 如果没有错误 则不显示
                continue

            rate = round(ErrorRateCalculation.calculate(error_count, sum_count), 2)

            result.append(
                {
                    "name": self.JOIN_CHAR.join(keys) if not self.is_service_filter else keys[-1],
                    "value": rate,
                    "unit": "%",
                    "total": 100,  # present
                    "target": "event",
                    "type": "link",
                    "url": self.build_link(keys[0], keys[1]),
                    "key": "switch_scenes_type",
                }
            )

        sort_result = sorted(result, key=lambda item: float(item["value"]), reverse=True)

        return sort_result


@register
class EndpointAvgDurationTopNHandler(TopNHandler):
    query_type = "endpoint_avg_duration"

    JOIN_CHAR = " | "

    def get_endpoint_split(self, item):
        return item["name"].split(self.JOIN_CHAR)[-1]

    def _query_metric(self):
        database_name, _ = self.application.metric_result_table_id.split(".")
        group_by_keys = [
            OtlpKey.SPAN_NAME,
            OtlpKey.get_metric_dimension_key(ResourceAttributes.SERVICE_NAME),
        ]

        filter_dict, where_condition = self.get_condition()

        handler = AvgDurationInstance(
            self.application,
            self.start_time,
            self.end_time,
            group_by=group_by_keys,
            where=where_condition,
            filter_dict=filter_dict,
        )

        metrics = handler.origin_query_instance()

        return self.collect_sum_metrics(
            metrics, group_by_keys, lambda l: (sorted(l, key=lambda ii: ii.get("_time_", 0))[0]).get("_result_")
        )

    def top_n(self):
        series = self._query_metric()
        sum_count = sum([serie["_result_"] for serie in series])
        result = []
        for serie in series:
            if OtlpKey.SPAN_NAME not in serie:
                continue
            value, unit = load_unit("ns").auto_convert(serie["_result_"], decimal=2)
            sum_target_value = load_unit("ns").convert(sum_count, decimal=2, target_suffix=unit)
            service_name = serie.get(OtlpKey.get_metric_dimension_key(ResourceAttributes.SERVICE_NAME), "")
            span_name = serie[OtlpKey.SPAN_NAME]

            result.append(
                {
                    "total": sum_target_value,
                    "unit": unit,
                    "name": service_name + self.JOIN_CHAR + span_name if not self.is_service_filter else span_name,
                    "value": value,
                    "actual_value": serie["_result_"],
                    "target": "event",
                    "type": "link",
                    "url": self.build_link(service_name, span_name),
                    "key": "switch_scenes_type",
                }
            )
        result = sorted(result, key=lambda item: int(item["actual_value"]), reverse=True)

        return result


@register
class ServiceCalledCountTopNHandler(TopNHandler):
    """服务调用次数"""

    query_type = "service_called_count"

    group_by_keys = [
        OtlpKey.get_metric_dimension_key(ResourceAttributes.SERVICE_NAME),
    ]

    def _query_metric(self):
        database_name, _ = self.application.metric_result_table_id.split(".")
        return RequestCountInstance(
            self.application,
            self.start_time,
            self.end_time,
            group_by=self.group_by_keys,
            filter_dict=self.filter_dict,
        ).origin_query_instance()

    def top_n(self):
        series = self._query_metric()
        series = self.agg_data(series)
        sum_count = sum([i["_result_"] for i in series])
        result = []

        for i in series:
            service_name = i.get(OtlpKey.get_metric_dimension_key(ResourceAttributes.SERVICE_NAME), "")
            if not service_name:
                continue

            result.append(
                {
                    "total": sum_count,
                    "unit": _("次"),
                    "name": service_name,
                    "value": i["_result_"],
                    "type": "link",
                    "url": f"/service/?filter-service_name={service_name}&filter-app_name={self.application.app_name}",
                    "target": "self",
                }
            )

        result = sorted(result, key=lambda item: int(item["value"]), reverse=True)

        return result


@register
class ServiceErrorCountTopNHandler(TopNHandler):
    """服务错误次数"""

    query_type = "service_error_count"

    group_by_keys = [
        OtlpKey.get_metric_dimension_key(ResourceAttributes.SERVICE_NAME),
    ]

    def _query_metric(self):
        database_name, _ = self.application.metric_result_table_id.split(".")
        return RequestCountInstance(
            self.application,
            self.start_time,
            self.end_time,
            group_by=self.group_by_keys,
            filter_dict=self.filter_dict,
            where=[{"key": "status_code", "method": "eq", "value": ["2"]}],
        ).origin_query_instance()

    def top_n(self):
        series = self._query_metric()
        series = self.agg_data(series)
        sum_count = sum([i["_result_"] for i in series])
        result = []

        for i in series:
            service_name = i.get(OtlpKey.get_metric_dimension_key(ResourceAttributes.SERVICE_NAME), "")
            if not service_name:
                continue

            result.append(
                {
                    "total": sum_count,
                    "unit": _("次"),
                    "name": service_name,
                    "value": i["_result_"],
                    "type": "link",
                    "url": f"/service/?filter-service_name={service_name}"
                    f"&filter-app_name={self.application.app_name}"
                    f"&dashboardId=service-default-error",
                    "target": "self",
                }
            )

        result = sorted(result, key=lambda item: int(item["value"]), reverse=True)

        return result


@register
class ServiceAvgDurationTopNHandler(TopNHandler):
    """服务平均响应耗时"""

    query_type = "service_avg_duration"

    def _query_metric(self):
        database_name, _ = self.application.metric_result_table_id.split(".")

        group_by_keys = [
            OtlpKey.get_metric_dimension_key(ResourceAttributes.SERVICE_NAME),
        ]

        filter_dict, where_condition = self.get_condition()

        handler = AvgDurationInstance(
            self.application,
            self.start_time,
            self.end_time,
            group_by=group_by_keys,
            where=where_condition,
            filter_dict=filter_dict,
        )

        metrics = handler.origin_query_instance()

        return self.collect_sum_metrics(
            metrics, group_by_keys, lambda l: (sorted(l, key=lambda ii: ii.get("_time_", 0))[0]).get("_result_")
        )

    def top_n(self):
        series = self._query_metric()
        sum_count = sum([i["_result_"] for i in series])

        result = []

        for i in series:
            service_name = i.get(OtlpKey.get_metric_dimension_key(ResourceAttributes.SERVICE_NAME), "")
            if not service_name:
                continue

            value, unit = load_unit("ns").auto_convert(i["_result_"], decimal=2)
            sum_target_value = load_unit("ns").convert(sum_count, decimal=2, target_suffix=unit)

            result.append(
                {
                    "total": sum_target_value,
                    "unit": unit,
                    "name": service_name,
                    "value": value,
                    "actual_value": i["_result_"],
                    "type": "link",
                    "url": f"/service/?filter-service_name={service_name}&filter-app_name={self.application.app_name}",
                    "target": "self",
                }
            )

        result = sorted(result, key=lambda item: int(item["actual_value"]), reverse=True)

        return result
