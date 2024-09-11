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
from collections import defaultdict

from opentelemetry.trace import StatusCode

from apm_web.constants import AlertLevel, Apdex, CategoryEnum
from apm_web.handlers.component_handler import ComponentHandler
from apm_web.handlers.service_handler import ServiceHandler
from apm_web.metric_handler import ApdexInstance, RequestCountInstance
from apm_web.models import Application
from apm_web.topo.constants import BarChartDataType
from apm_web.topo.handle.graph_plugin import NodeColor
from constants.apm import OtlpKey, SpanKind
from core.drf_resource import api, resource


class EndpointList:
    id: str = None

    def __init__(self, bk_biz_id, app_name, start_time, end_time, service_name, size):
        self.bk_biz_id = bk_biz_id
        self.app_name = app_name
        self.start_time = start_time
        self.end_time = end_time
        self.service_name = service_name
        self.size = size
        self.application = Application.objects.get(bk_biz_id=bk_biz_id, app_name=app_name)

    @property
    def common_params(self):
        return {
            "application": self.application,
            "start_time": self.start_time,
            "end_time": self.end_time,
        }

    def get_filter_dict(self):
        node = ServiceHandler.get_node(self.bk_biz_id, self.app_name, self.service_name)
        if ComponentHandler.is_component_by_node(node):
            category = node.get("extra_data", {}).get("category")
            if category == CategoryEnum.DB:
                filter_dict = {
                    "db_system": ComponentHandler.get_component_predicate_value(node),
                    "service_name": ComponentHandler.get_component_belong_service(self.service_name),
                }
            elif category == CategoryEnum.MESSAGING:
                filter_dict = {
                    "messaging_system": ComponentHandler.get_component_predicate_value(node),
                    "service_name": ComponentHandler.get_component_belong_service(self.service_name),
                }
            else:
                filter_dict = {"service_name": ComponentHandler.get_component_belong_service(self.service_name)}

            return filter_dict
        elif ServiceHandler.is_remote_service_by_node(node):
            return {
                "peer_service": ServiceHandler.get_remote_service_origin_name(self.service_name),
            }
        else:
            return {"service_name": self.service_name}

    def fill_endpoints(self, res, endpoint_names):

        node = ServiceHandler.get_node(self.bk_biz_id, self.app_name, self.service_name)
        if ComponentHandler.is_component_by_node(node):
            service_name = ComponentHandler.get_component_belong_service(self.service_name)
        elif ServiceHandler.is_remote_service_by_node(node):
            service_name = ServiceHandler.get_remote_service_origin_name(self.service_name)
        else:
            service_name = self.service_name

        # 数量可能不够 用接口列表进行凑数
        endpoints = api.apm_api.query_endpoint(
            **{
                "bk_biz_id": self.bk_biz_id,
                "app_name": self.app_name,
                "service_name": service_name,
            }
        )

        for index, item in enumerate(endpoints, len(res) + 1):
            if len(res) >= self.size:
                break
            if item["endpoint_name"] not in endpoint_names:
                res.append({"id": index, "name": item["endpoint_name"], "color": NodeColor.Color.GREEN, "value": 0})

        return sorted(res, key=lambda j: j["value"], reverse=True)


class ErrorRateMixin(EndpointList):
    @classmethod
    def get_mapping(cls, metric):
        response = metric.get_instance_values_mapping()

        total_mapping = {}
        error_mapping = {}
        endpoint_names = set()

        for k, v in response.items():
            span, status_code = k
            value = v.get(metric.metric_id, 0)

            total_mapping.setdefault(span, 0)
            total_mapping[span] += value

            if status_code == str(StatusCode.ERROR.value):
                error_mapping.setdefault(span, 0)
                error_mapping[span] += value

            endpoint_names.add(span)

        return total_mapping, error_mapping, endpoint_names

    def convert_mapping_to_list(self, total_mapping, error_mapping, endpoint_names):
        res = []
        for index, name in enumerate(endpoint_names, 1):

            error_rate = round(error_mapping[name] / total_mapping[name], 2) if total_mapping[name] else 0
            if error_rate == 0:
                color = NodeColor.Color.GREEN
            elif error_rate < 0.1:
                color = NodeColor.Color.YELLOW
            else:
                color = NodeColor.Color.RED

            res.append(
                {
                    "id": index,
                    "name": name,
                    "color": color,
                    "value": error_rate,
                }
            )

        return sorted(res, key=lambda i: i["value"], reverse=True)[: self.size]

    def get_where_kinds(self, call_type):
        node = ServiceHandler.get_node(self.bk_biz_id, self.app_name, self.service_name)
        if ComponentHandler.is_component_by_node(node) or ServiceHandler.is_remote_service_by_node(node):
            if call_type == "caller":
                return [SpanKind.SPAN_KIND_SERVER, SpanKind.SPAN_KIND_CONSUMER]
            else:
                return [SpanKind.SPAN_KIND_CLIENT, SpanKind.SPAN_KIND_PRODUCER]
        else:
            if call_type == "caller":
                return [SpanKind.SPAN_KIND_CLIENT, SpanKind.SPAN_KIND_PRODUCER]
            else:
                return [SpanKind.SPAN_KIND_SERVER, SpanKind.SPAN_KIND_CONSUMER]


class ErrorRateList(ErrorRateMixin):
    id: str = BarChartDataType.ErrorRate.value
    metric = RequestCountInstance

    def list(self):
        return self.convert_mapping_to_list(
            *self.get_mapping(
                self.metric(
                    **self.common_params,
                    **{
                        "filter_dict": self.get_filter_dict(),
                        "group_by": ["span_name", "status_code"],
                    },
                )
            )
        )


class ErrorRateCalleeList(ErrorRateMixin):
    id: str = BarChartDataType.ErrorRateCallee.value
    metric = RequestCountInstance

    def list(self):
        return self.convert_mapping_to_list(
            *self.get_mapping(
                self.metric(
                    **self.common_params,
                    **{
                        "filter_dict": self.get_filter_dict(),
                        "where": [
                            {
                                "key": "kind",
                                "method": "eq",
                                "value": self.get_where_kinds("callee"),
                            }
                        ],
                        "group_by": ["span_name", "status_code"],
                    },
                )
            )
        )


class ErrorRateCallerList(ErrorRateMixin):
    id: str = BarChartDataType.ErrorRateCaller.value
    metric = RequestCountInstance

    def list(self):
        return self.convert_mapping_to_list(
            *self.get_mapping(
                self.metric(
                    **self.common_params,
                    **{
                        "filter_dict": self.get_filter_dict(),
                        "where": [
                            {
                                "key": "kind",
                                "method": "eq",
                                "value": self.get_where_kinds("caller"),
                            }
                        ],
                        "group_by": ["span_name", "status_code"],
                    },
                )
            )
        )


class ApdexList(EndpointList):
    id: str = BarChartDataType.Apdex.value
    metric = ApdexInstance

    def list(self):

        response = self.metric(
            **self.common_params, **{"filter_dict": self.get_filter_dict(), "group_by": ["span_name"]}
        ).get_instance_calculate_values_mapping(
            ignore_keys=[OtlpKey.get_metric_dimension_key(OtlpKey.STATUS_CODE), Apdex.DIMENSION_KEY]
        )

        res = []
        for index, item in enumerate(response.items(), 1):
            span = item[0][0]
            apdex = item[1].get(self.metric.metric_id, None)
            if not apdex:
                color = NodeColor.Color.WHITE
            elif apdex == Apdex.FRUSTRATED:
                color = NodeColor.Color.RED
            elif apdex == Apdex.TOLERATING:
                color = NodeColor.Color.YELLOW
            else:
                color = NodeColor.Color.GREEN

            res.append(
                {
                    "id": index,
                    "name": span,
                    "color": color,
                    "value": apdex,
                }
            )

        def _sort(i):
            if i["color"] == NodeColor.Color.RED:
                return 0
            if i["color"] == NodeColor.Color.YELLOW:
                return 1
            return 2

        return sorted(res, key=_sort)[: self.size]


class AlertList(EndpointList):
    id: str = BarChartDataType.Alert.value

    def list(self):
        # 查看出维度满足 filter_dict 条件的告警 同时需要要求告警维度中包含 span_name 维度 才认为这个接口产生了告警
        filter_dict = self.get_filter_dict()
        query_strings = []
        for f, v in filter_dict.items():
            query_strings.append(f"tags.{f}: {v}")
        alert_infos = resource.fta_web.alert.search_alert(
            **{
                "bk_biz_ids": [self.bk_biz_id],
                "query_string": " AND ".join(query_strings),
                "start_time": self.start_time,
                "end_time": self.end_time,
                "page_size": 1000,
            }
        ).get("alerts", [])

        count_mapping = defaultdict(list)
        res = []
        endpoint_names = []
        for i in alert_infos:
            span = next((i["value"] for i in i["tags"] if i["key"] == "span_name"), None)
            level = i.get("severity")
            if span and level:
                count_mapping[span].append(level)

        for index, item in enumerate(count_mapping.items(), 1):
            res.append(
                {
                    "id": index,
                    "name": item[0],
                    "color": NodeColor.Color.RED
                    if any(i == AlertLevel.ERROR for i in item[1])
                    else NodeColor.Color.YELLOW,
                    "value": len(item[1]),
                }
            )
            endpoint_names.append(item[0])

        if len(res) >= self.size:
            return res[: self.size]

        return self.fill_endpoints(res, endpoint_names)
