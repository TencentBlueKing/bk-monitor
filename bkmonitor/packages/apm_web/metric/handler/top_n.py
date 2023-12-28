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

from apm_web.calculation import ErrorRateCalculation
from apm_web.constants import component_where_mapping
from apm_web.handlers.component_handler import ComponentHandler
from apm_web.handlers.service_handler import ServiceHandler
from apm_web.metric_handler import AvgDurationInstance, MetricHandler
from apm_web.models import Application
from apm_web.utils import group_by
from django.utils.translation import ugettext_lazy as _
from monitor_web.scene_view.builtin.apm import ApmBuiltinProcessor
from opentelemetry.semconv.resource import ResourceAttributes

from constants.apm import OtlpKey
from core.drf_resource import api
from core.unit import load_unit

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

    def __init__(
        self, application: Application, start_time: int, end_time: int, size: int, filter_dict=None, service_params=None
    ):
        self.application = application
        self.start_time = start_time
        self.end_time = end_time
        self.size = size
        self.filter_dict = filter_dict or {}
        self.service_params = service_params

    def top_n(self, override_filter_dict=None):
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

        if self.filter_dict.get("service_name"):
            service_name = self.filter_dict["service_name"]
            bk_biz_id = self.application.bk_biz_id
            app_name = self.application.app_name
            # 判断是否查询的是自定义服务 是 -> 显示所有主调方数据并过滤
            if ServiceHandler.is_remote_service(bk_biz_id, app_name, service_name):

                res = []
                # step1: 查询被调所有服务
                response = api.apm_api.query_topo_relation(
                    bk_biz_id=bk_biz_id, app_name=app_name, to_topo_key=service_name
                )
                from_service_names = {i["from_topo_key"] for i in response}
                for from_service in from_service_names:
                    override_filter_dict = dict(self.filter_dict)
                    override_filter_dict["service_name"] = from_service

                    res += self.top_n(override_filter_dict)

                # step2: 查询被调接口
                query_params = {"bk_biz_id": bk_biz_id, "app_name": app_name, "topo_node_key": service_name}
                from_endpoints = [
                    i["from_endpoint_name"] for i in api.apm_api.query_remote_service_relation(**query_params)
                ]

                return [r for r in res if self.get_endpoint_split(r) in from_endpoints][: self.size]

        return self.top_n()[: self.size]

    def get_endpoint_split(self, item):
        return item

    def get_condition(self, override_filter_dict):
        """如果是组件的话获取查询条件"""
        where_condition = []
        filter_dict = self.filter_dict if not override_filter_dict else override_filter_dict

        if ComponentHandler.is_component(self.service_params):
            # 组件获取TopN时
            where_condition.append(
                json.loads(
                    json.dumps(component_where_mapping[self.service_params["category"]]).replace(
                        "{predicate_value}", self.service_params["predicate_value"]
                    )
                )
            )
            if OtlpKey.get_metric_dimension_key(ResourceAttributes.SERVICE_NAME) in self.filter_dict:
                pure_service_name = ComponentHandler.get_component_belong_service(
                    self.filter_dict[OtlpKey.get_metric_dimension_key(ResourceAttributes.SERVICE_NAME)],
                    self.service_params["predicate_value"],
                )
                filter_dict[OtlpKey.get_metric_dimension_key(ResourceAttributes.SERVICE_NAME)] = pure_service_name

        return filter_dict, where_condition

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

            if ComponentHandler.is_component(self.service_params):
                query_params["filter-category"] = self.service_params["category"]
                query_params["filter-kind"] = self.service_params["kind"]
                query_params["filter-predicate_value"] = self.service_params["predicate_value"]

                predicate_views = f"component-{self.service_params['predicate_value']}-endpoint"
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


@register
class EndpointCalledCountTopNHandler(TopNHandler):
    query_type = "endpoint_called_count"

    JOIN_CHAR = " | "

    def get_endpoint_split(self, item):
        return item["name"].split(self.JOIN_CHAR)[-1]

    def _query_metric(self, override_filter_dict):
        database_name, _ = self.application.metric_result_table_id.split(".")
        filter_dict, where_condition = self.get_condition(override_filter_dict)

        handler = MetricHandler(self.application, self.start_time, self.end_time)
        group_by_keys = [
            OtlpKey.SPAN_NAME,
            OtlpKey.get_metric_dimension_key(ResourceAttributes.SERVICE_NAME),
        ]
        metrics = handler.instance_unify_query(
            {
                "data_source_label": "custom",
                "data_type_label": "time_series",
                "metrics": [{"field": "bk_apm_count", "method": "SUM", "alias": "a"}],
                "table": f"{database_name}.__default__",
                "group_by": group_by_keys,
                "display": True,
                "interval": self.end_time - self.start_time,
                "interval_unit": "s",
                "time_field": "time",
                "filter_dict": filter_dict,
                "functions": [],
                "where": where_condition,
            }
        )

        return self.collect_sum_metrics(metrics, group_by_keys)

    def top_n(self, override_filter_dict=None):
        series = self._query_metric(override_filter_dict)

        sum_count = sum([serie["_result_"] for serie in series])
        result = []
        for serie in series:
            if OtlpKey.SPAN_NAME not in serie:
                continue

            service_name = serie.get(OtlpKey.get_metric_dimension_key(ResourceAttributes.SERVICE_NAME), "")
            span_name = serie[OtlpKey.SPAN_NAME]

            result.append(
                {
                    # TODO 未补充kind等新的参数
                    "total": sum_count,
                    "unit": _("次"),
                    "name": service_name + self.JOIN_CHAR + span_name,
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

    def get_endpoint_split(self, item):
        return item["name"].split(self.JOIN_CHAR)[-1]

    def _query_metric(self, override_filter_dict):
        database_name, _ = self.application.metric_result_table_id.split(".")
        handler = MetricHandler(self.application, self.start_time, self.end_time)

        filter_dict, where_condition = self.get_condition(override_filter_dict)

        group_keys = [
            OtlpKey.SPAN_NAME,
            OtlpKey.get_metric_dimension_key(OtlpKey.STATUS_CODE),
            OtlpKey.get_metric_dimension_key(ResourceAttributes.SERVICE_NAME),
        ]
        metrics = handler.instance_unify_query(
            {
                "data_source_label": "custom",
                "data_type_label": "time_series",
                "metrics": [{"field": "bk_apm_count", "method": "SUM", "alias": "a"}],
                "table": f"{database_name}.__default__",
                "group_by": group_keys,
                "display": True,
                "interval": self.end_time - self.start_time,
                "interval_unit": "s",
                "time_field": "time",
                "filter_dict": filter_dict,
                "functions": [],
                "where": where_condition,
            }
        )

        return self.collect_sum_metrics(metrics, group_keys)

    def top_n(self, override_filter_dict=None):
        series = self._query_metric(override_filter_dict)
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
            rate = round(ErrorRateCalculation.calculate(error_count, sum_count), 2)

            result.append(
                {
                    "name": self.JOIN_CHAR.join(keys),
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

    def _query_metric(self, override_filter_dict):
        database_name, _ = self.application.metric_result_table_id.split(".")
        group_by_keys = [
            OtlpKey.SPAN_NAME,
            OtlpKey.get_metric_dimension_key(ResourceAttributes.SERVICE_NAME),
        ]

        filter_dict, where_condition = self.get_condition(override_filter_dict)

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

    def top_n(self, override_filter_dict=None):

        series = self._query_metric(override_filter_dict)
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
                    "name": service_name + self.JOIN_CHAR + span_name,
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

    def _query_metric(self, override_filter_dict):
        database_name, _ = self.application.metric_result_table_id.split(".")
        handler = MetricHandler(self.application, self.start_time, self.end_time)
        return handler.instance_unify_query(
            {
                "data_source_label": "custom",
                "data_type_label": "time_series",
                "metrics": [{"field": "bk_apm_count", "method": "SUM", "alias": "a"}],
                "table": f"{database_name}.__default__",
                "group_by": [
                    OtlpKey.get_metric_dimension_key(ResourceAttributes.SERVICE_NAME),
                ],
                "display": True,
                "interval": self.end_time - self.start_time,
                "interval_unit": "s",
                "time_field": "time",
                "filter_dict": self.filter_dict if not override_filter_dict else override_filter_dict,
                "functions": [],
                "where": [],
            }
        )

    def top_n(self, override_filter_dict=None):
        series = self._query_metric(override_filter_dict)
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

    def _query_metric(self, override_filter_dict):
        database_name, _ = self.application.metric_result_table_id.split(".")
        handler = MetricHandler(self.application, self.start_time, self.end_time)
        return handler.instance_unify_query(
            {
                "data_source_label": "custom",
                "data_type_label": "time_series",
                "metrics": [{"field": "bk_apm_count", "method": "SUM", "alias": "a"}],
                "table": f"{database_name}.__default__",
                "group_by": [
                    OtlpKey.get_metric_dimension_key(ResourceAttributes.SERVICE_NAME),
                ],
                "display": True,
                "interval": self.end_time - self.start_time,
                "interval_unit": "s",
                "time_field": "time",
                "filter_dict": self.filter_dict if not override_filter_dict else override_filter_dict,
                "functions": [],
                "where": [{"key": "status_code", "method": "eq", "value": ["2"]}],
            }
        )

    def top_n(self, override_filter_dict=None):
        series = self._query_metric(override_filter_dict)
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

    def _query_metric(self, override_filter_dict):
        database_name, _ = self.application.metric_result_table_id.split(".")

        group_by_keys = [
            OtlpKey.get_metric_dimension_key(ResourceAttributes.SERVICE_NAME),
        ]

        filter_dict, where_condition = self.get_condition(override_filter_dict)

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

    def top_n(self, override_filter_dict=None):
        series = self._query_metric(override_filter_dict)
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
