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
import logging

from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy
from opentelemetry.semconv.resource import ResourceAttributes
from rest_framework import serializers

from apm.constants import StatisticsProperty
from apm_web.constants import DEFAULT_DIFF_TRACE_MAX_NUM, CategoryEnum, QueryMode
from apm_web.handlers.trace_handler.base import (
    StatisticsHandler,
    StatusCodeAttributePredicate,
    TraceHandler,
)
from apm_web.handlers.trace_handler.dimension_statistics import (
    DimensionStatisticsAPIHandler,
)
from apm_web.handlers.trace_handler.query import (
    QueryHandler,
    SpanQueryTransformer,
    TraceQueryTransformer,
)
from apm_web.handlers.trace_handler.view_config import TraceFieldsHandler
from apm_web.models import Application
from apm_web.models.trace import TraceComparison
from apm_web.trace.constants import EnabledStatisticsDimension, OperatorEnum
from apm_web.trace.serializers import (
    BaseTraceRequestSerializer,
    GetFieldsOptionValuesRequestSerializer,
    QuerySerializer,
    QueryStatisticsSerializer,
    SpanIdInputSerializer,
    TraceFieldStatisticsGraphRequestSerializer,
    TraceFieldStatisticsInfoRequestSerializer,
    TraceFieldsTopkRequestSerializer,
    TraceGenerateQueryStringRequestSerializer,
)
from apm_web.utils import flatten_es_dict_data
from bkmonitor.utils.cache import CacheType, using_cache
from bkmonitor.utils.elasticsearch.handler import QueryStringGenerator
from constants.apm import (
    OperatorGroupRelation,
    OtlpKey,
    PreCalculateSpecificField,
    SpanStandardField,
    TraceListQueryMode,
    TraceWaterFallDisplayKey,
)
from core.drf_resource import Resource, api
from core.drf_resource.exceptions import CustomException
from core.errors.api import BKAPIError
from core.prometheus.base import OPERATION_REGISTRY
from core.prometheus.metrics import safe_push_to_gateway
from monitor_web.statistics.v2.query import unify_query_count

from ..handlers.host_handler import HostHandler
from .diagram import get_diagrammer
from .diagram.service_topo import trace_data_to_service_topo
from .diagram.topo import trace_data_to_topo_data

logger = logging.getLogger(__name__)


class TraceChatsResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")

    def perform_request(self, validated_request_data):
        try:
            app = Application.objects.get(
                bk_biz_id=validated_request_data["bk_biz_id"], app_name=validated_request_data["app_name"]
            )
        except Application.DoesNotExist:
            raise ValueError(_lazy("应用不存在"))
        database, _ = app.metric_result_table_id.split(".")
        return [
            {
                "id": 1,
                "title": "请求数",
                "type": "apm-timeseries-chart",
                "gridPos": {"x": 0, "y": 16, "w": 8, "h": 4},
                "alias": "请求数",
                "targets": [
                    {
                        "data_type": "time_series",
                        "api": "apm_metric.dynamicUnifyQuery",
                        "datasource": "time_series",
                        "alias": "主调",
                        "data": {
                            "app_name": app.app_name,
                            "query_configs": [
                                {
                                    "data_source_label": "custom",
                                    "data_type_label": "time_series",
                                    "table": f"{database}.__default__",
                                    "metrics": [{"field": "bk_apm_count", "method": "SUM", "alias": "A"}],
                                    "group_by": [],
                                    "display": True,
                                    "where": [
                                        {"key": "kind", "method": "eq", "value": ["3"]},
                                        {"condition": "or", "key": "kind", "method": "eq", "value": ["4"]},
                                    ],
                                    "interval_unit": "s",
                                    "time_field": "time",
                                    "filter_dict": {},
                                    "functions": [],
                                }
                            ],
                            "stack": "all",
                            "unify_query_param": {
                                "expression": "A",
                                "query_configs": [
                                    {
                                        "data_source_label": "custom",
                                        "data_type_label": "time_series",
                                        "table": f"{database}.__default__",
                                        "metrics": [{"field": "bk_apm_count", "method": "SUM", "alias": "A"}],
                                        "group_by": [],
                                        "display": True,
                                        "where": [
                                            {"key": "kind", "method": "eq", "value": ["3"]},
                                            {"condition": "or", "key": "kind", "method": "eq", "value": ["4"]},
                                        ],
                                        "interval_unit": "s",
                                        "time_field": "time",
                                        "filter_dict": {},
                                        "functions": [],
                                    }
                                ],
                            },
                            "fill_bar": True,
                        },
                    },
                    {
                        "data_type": "time_series",
                        "api": "apm_metric.dynamicUnifyQuery",
                        "datasource": "time_series",
                        "alias": "被调",
                        "data": {
                            "app_name": app.app_name,
                            "query_configs": [
                                {
                                    "data_source_label": "custom",
                                    "data_type_label": "time_series",
                                    "table": f"{database}.__default__",
                                    "metrics": [{"field": "bk_apm_count", "method": "SUM", "alias": "A"}],
                                    "group_by": [],
                                    "display": True,
                                    "where": [
                                        {"key": "kind", "method": "eq", "value": ["2"]},
                                        {"condition": "or", "key": "kind", "method": "eq", "value": ["5"]},
                                    ],
                                    "interval_unit": "s",
                                    "time_field": "time",
                                    "filter_dict": {},
                                    "functions": [],
                                }
                            ],
                            "stack": "all",
                            "unify_query_param": {
                                "expression": "A",
                                "query_configs": [
                                    {
                                        "data_source_label": "custom",
                                        "data_type_label": "time_series",
                                        "table": f"{database}.__default__",
                                        "metrics": [{"field": "bk_apm_count", "method": "SUM", "alias": "A"}],
                                        "group_by": [],
                                        "display": True,
                                        "where": [
                                            {"key": "kind", "method": "eq", "value": ["2"]},
                                            {"condition": "or", "key": "kind", "method": "eq", "value": ["5"]},
                                        ],
                                        "interval_unit": "s",
                                        "time_field": "time",
                                        "filter_dict": {},
                                        "functions": [],
                                    }
                                ],
                            },
                            "fill_bar": True,
                        },
                    },
                ],
                "options": {
                    "apm_time_series": {
                        "metric": "request_count",
                        "unit": "number",
                    },
                    "time_series": {"type": "bar", "hoverAllTooltips": True},
                },
            },
            {
                "id": 2,
                "title": "错误数",
                "type": "apm-timeseries-chart",
                "gridPos": {"x": 8, "y": 16, "w": 8, "h": 4},
                "targets": [
                    {
                        "data_type": "time_series",
                        "api": "apm_metric.dynamicUnifyQuery",
                        "datasource": "time_series",
                        "alias": "错误数",
                        "data": {
                            "app_name": app.app_name,
                            "query_configs": [
                                {
                                    "data_source_label": "custom",
                                    "data_type_label": "time_series",
                                    "table": f"{database}.__default__",
                                    "metrics": [{"field": "bk_apm_count", "method": "SUM", "alias": "A"}],
                                    "group_by": [],
                                    "display": True,
                                    "where": [
                                        {"key": "status_code", "method": "eq", "value": ["2"], "condition": "and"}
                                    ],
                                    "interval_unit": "s",
                                    "time_field": "time",
                                    "filter_dict": {},
                                    "functions": [],
                                }
                            ],
                            "unify_query_param": {
                                "type": "range",
                                "stack": "all",
                                "expression": "A",
                                "query_configs": [
                                    {
                                        "data_source_label": "custom",
                                        "data_type_label": "time_series",
                                        "table": f"{database}.__default__",
                                        "metrics": [{"field": "bk_apm_count", "method": "SUM", "alias": "A"}],
                                        "group_by": [],
                                        "display": True,
                                        "where": [
                                            {"key": "status_code", "method": "eq", "value": ["2"], "condition": "and"}
                                        ],
                                        "interval_unit": "s",
                                        "time_field": "time",
                                        "filter_dict": {},
                                        "functions": [],
                                    }
                                ],
                            },
                            "fill_bar": True,
                        },
                        "yAxisIndex": 0,
                        "chart_type": "bar",
                    },
                    {
                        "data_type": "time_series",
                        "api": "apm_metric.dynamicUnifyQuery",
                        "datasource": "time_series",
                        "alias": "错误率",
                        "data": {
                            "app_name": app.app_name,
                            "unit": "percentunit",
                            "expression": "a / b",
                            "query_configs": [
                                {
                                    "data_source_label": "custom",
                                    "data_type_label": "time_series",
                                    "metrics": [{"field": "bk_apm_count", "method": "SUM", "alias": "a"}],
                                    "table": f"{database}.__default__",
                                    "data_label": "",
                                    "index_set_id": None,
                                    "group_by": [],
                                    "where": [
                                        {"key": "status_code", "method": "eq", "value": ["2"], "condition": "and"}
                                    ],
                                    "interval_unit": "s",
                                    "time_field": "time",
                                    "filter_dict": {},
                                    "functions": [],
                                },
                                {
                                    "data_source_label": "custom",
                                    "data_type_label": "time_series",
                                    "metrics": [{"field": "bk_apm_count", "method": "SUM", "alias": "b"}],
                                    "table": f"{database}.__default__",
                                    "data_label": "",
                                    "index_set_id": None,
                                    "group_by": [],
                                    "where": [],
                                    "interval_unit": "s",
                                    "time_field": None,
                                    "filter_dict": {},
                                    "functions": [],
                                },
                            ],
                            "unify_query_param": {
                                "expression": "a / b",
                                "query_configs": [
                                    {
                                        "data_source_label": "custom",
                                        "data_type_label": "time_series",
                                        "metrics": [{"field": "bk_apm_count", "method": "SUM", "alias": "a"}],
                                        "table": f"{database}.__default__",
                                        "data_label": "",
                                        "index_set_id": None,
                                        "group_by": [],
                                        "where": [
                                            {"key": "status_code", "method": "eq", "value": ["2"], "condition": "and"}
                                        ],
                                        "interval_unit": "s",
                                        "time_field": "time",
                                        "filter_dict": {},
                                        "functions": [],
                                    },
                                    {
                                        "data_source_label": "custom",
                                        "data_type_label": "time_series",
                                        "metrics": [{"field": "bk_apm_count", "method": "SUM", "alias": "b"}],
                                        "table": f"{database}.__default__",
                                        "data_label": "",
                                        "index_set_id": None,
                                        "group_by": [],
                                        "where": [],
                                        "interval_unit": "s",
                                        "time_field": None,
                                        "filter_dict": {},
                                        "functions": [],
                                    },
                                ],
                            },
                            "fill_bar": True,
                        },
                        "yAxisIndex": 1,
                        "chart_type": "line",
                    },
                ],
                "options": {
                    "apm_time_series": {
                        "metric": "error_count",
                        "unit": "number",
                    },
                    "time_series": {"type": "bar", "hoverAllTooltips": True},
                },
            },
            {
                "id": 3,
                "title": "耗时",
                "gridPos": {"x": 16, "y": 16, "w": 8, "h": 4},
                "type": "apm-timeseries-chart",
                "targets": [
                    {
                        "data_type": "time_series",
                        "api": "apm_metric.dynamicUnifyQuery",
                        "datasource": "time_series",
                        "alias": "AVG",
                        "data": {
                            "app_name": app.app_name,
                            "unit": "ns",
                            "expression": "a / b",
                            "query_configs": [
                                {
                                    "data_source_label": "custom",
                                    "data_type_label": "time_series",
                                    "metrics": [{"field": "bk_apm_duration_sum", "method": "SUM", "alias": "a"}],
                                    "table": f"{database}.__default__",
                                    "data_label": "",
                                    "index_set_id": None,
                                    "group_by": [],
                                    "where": [],
                                    "interval_unit": "s",
                                    "time_field": "time",
                                    "filter_dict": {},
                                    "functions": [{"id": "increase", "params": [{"id": "window", "value": "2m"}]}],
                                },
                                {
                                    "data_source_label": "custom",
                                    "data_type_label": "time_series",
                                    "metrics": [{"field": "bk_apm_total", "method": "SUM", "alias": "b"}],
                                    "table": f"{database}.__default__",
                                    "data_label": "",
                                    "index_set_id": None,
                                    "group_by": [],
                                    "where": [],
                                    "interval_unit": "s",
                                    "time_field": None,
                                    "filter_dict": {},
                                    "functions": [{"id": "increase", "params": [{"id": "window", "value": "2m"}]}],
                                },
                            ],
                            "unify_query_param": {
                                "expression": "a / b",
                                "query_configs": [
                                    {
                                        "data_source_label": "custom",
                                        "data_type_label": "time_series",
                                        "metrics": [{"field": "bk_apm_duration_sum", "method": "SUM", "alias": "a"}],
                                        "table": f"{database}.__default__",
                                        "data_label": "",
                                        "index_set_id": None,
                                        "group_by": [],
                                        "where": [],
                                        "interval_unit": "s",
                                        "time_field": "time",
                                        "filter_dict": {},
                                        "functions": [{"id": "increase", "params": [{"id": "window", "value": "2m"}]}],
                                    },
                                    {
                                        "data_source_label": "custom",
                                        "data_type_label": "time_series",
                                        "metrics": [{"field": "bk_apm_total", "method": "SUM", "alias": "b"}],
                                        "table": f"{database}.__default__",
                                        "data_label": "",
                                        "index_set_id": None,
                                        "group_by": [],
                                        "where": [],
                                        "interval_unit": "s",
                                        "time_field": None,
                                        "filter_dict": {},
                                        "functions": [{"id": "increase", "params": [{"id": "window", "value": "2m"}]}],
                                    },
                                ],
                            },
                            "fill_bar": True,
                        },
                    },
                    {
                        "data_type": "time_series",
                        "api": "apm_metric.dynamicUnifyQuery",
                        "datasource": "time_series",
                        "alias": "P50",
                        "data": {
                            "app_name": app.app_name,
                            "unit": "ns",
                            "query_configs": [
                                {
                                    "data_source_label": "custom",
                                    "data_type_label": "time_series",
                                    "table": f"{database}.__default__",
                                    "metrics": [{"field": "bk_apm_duration_bucket", "method": "SUM", "alias": "A"}],
                                    "group_by": ["le"],
                                    "display": True,
                                    "where": [],
                                    "interval_unit": "s",
                                    "time_field": "time",
                                    "filter_dict": {},
                                    "functions": [
                                        {"id": "rate", "params": [{"id": "window", "value": "2m"}]},
                                        {"id": "histogram_quantile", "params": [{"id": "scalar", "value": 0.5}]},
                                    ],
                                }
                            ],
                            "unify_query_param": {
                                "expression": "A",
                                "query_configs": [
                                    {
                                        "data_source_label": "custom",
                                        "data_type_label": "time_series",
                                        "table": f"{database}.__default__",
                                        "metrics": [{"field": "bk_apm_duration_bucket", "method": "SUM", "alias": "A"}],
                                        "group_by": ["le"],
                                        "display": True,
                                        "where": [],
                                        "interval_unit": "s",
                                        "time_field": "time",
                                        "filter_dict": {},
                                        "functions": [
                                            {"id": "rate", "params": [{"id": "window", "value": "2m"}]},
                                            {"id": "histogram_quantile", "params": [{"id": "scalar", "value": 0.5}]},
                                        ],
                                    }
                                ],
                            },
                            "fill_bar": True,
                        },
                    },
                    {
                        "data_type": "time_series",
                        "api": "apm_metric.dynamicUnifyQuery",
                        "datasource": "time_series",
                        "alias": "P95",
                        "data": {
                            "app_name": app.app_name,
                            "unit": "ns",
                            "query_configs": [
                                {
                                    "data_source_label": "custom",
                                    "data_type_label": "time_series",
                                    "table": f"{database}.__default__",
                                    "metrics": [{"field": "bk_apm_duration_bucket", "method": "SUM", "alias": "A"}],
                                    "group_by": ["le"],
                                    "display": True,
                                    "where": [],
                                    "interval_unit": "s",
                                    "time_field": "time",
                                    "filter_dict": {},
                                    "functions": [
                                        {"id": "rate", "params": [{"id": "window", "value": "2m"}]},
                                        {"id": "histogram_quantile", "params": [{"id": "scalar", "value": 0.95}]},
                                    ],
                                }
                            ],
                            "unify_query_param": {
                                "expression": "A",
                                "query_configs": [
                                    {
                                        "data_source_label": "custom",
                                        "data_type_label": "time_series",
                                        "table": f"{database}.__default__",
                                        "metrics": [{"field": "bk_apm_duration_bucket", "method": "SUM", "alias": "A"}],
                                        "group_by": ["le"],
                                        "display": True,
                                        "where": [],
                                        "interval_unit": "s",
                                        "time_field": "time",
                                        "filter_dict": {},
                                        "functions": [
                                            {"id": "rate", "params": [{"id": "window", "value": "2m"}]},
                                            {"id": "histogram_quantile", "params": [{"id": "scalar", "value": 0.95}]},
                                        ],
                                    }
                                ],
                            },
                            "fill_bar": True,
                        },
                    },
                    {
                        "data_type": "time_series",
                        "api": "apm_metric.dynamicUnifyQuery",
                        "datasource": "time_series",
                        "alias": "P99",
                        "data": {
                            "app_name": app.app_name,
                            "unit": "ns",
                            "query_configs": [
                                {
                                    "data_source_label": "custom",
                                    "data_type_label": "time_series",
                                    "table": f"{database}.__default__",
                                    "metrics": [{"field": "bk_apm_duration_bucket", "method": "SUM", "alias": "A"}],
                                    "group_by": ["le"],
                                    "display": True,
                                    "where": [],
                                    "interval_unit": "s",
                                    "time_field": "time",
                                    "filter_dict": {},
                                    "functions": [
                                        {"id": "rate", "params": [{"id": "window", "value": "2m"}]},
                                        {"id": "histogram_quantile", "params": [{"id": "scalar", "value": 0.99}]},
                                    ],
                                }
                            ],
                            "unify_query_param": {
                                "expression": "A",
                                "query_configs": [
                                    {
                                        "data_source_label": "custom",
                                        "data_type_label": "time_series",
                                        "table": f"{database}.__default__",
                                        "metrics": [{"field": "bk_apm_duration_bucket", "method": "SUM", "alias": "A"}],
                                        "group_by": ["le"],
                                        "display": True,
                                        "where": [],
                                        "interval_unit": "s",
                                        "time_field": "time",
                                        "filter_dict": {},
                                        "functions": [
                                            {"id": "rate", "params": [{"id": "window", "value": "2m"}]},
                                            {"id": "histogram_quantile", "params": [{"id": "scalar", "value": 0.99}]},
                                        ],
                                    }
                                ],
                            },
                            "fill_bar": True,
                        },
                    },
                ],
                "options": {
                    "apm_time_series": {
                        "metric": "avg_duration",
                        "unit": "μs",
                    },
                    "time_series": {"hoverAllTooltips": True},
                },
            },
        ]


class TraceOptionsResource(Resource):
    # class RequestSerializer(serializers.Serializer):
    #     bk_biz_id = serializers.IntegerField(label="业务ID")
    #     app_name = serializers.CharField(label="应用名称")

    many_response_data = True

    class ResponseSerializer(serializers.Serializer):
        id = serializers.CharField(label="id")
        name = serializers.CharField(label="name")
        trace_key = serializers.CharField(label="trace_key")
        metric_key = serializers.CharField(label="metric_key")

    def perform_request(self, validated_request_data):
        return [
            {
                "name": str(_lazy("服务")),
                "id": "service",
                "trace_key": OtlpKey.get_resource_key(ResourceAttributes.SERVICE_NAME),
                "metric_key": OtlpKey.get_metric_dimension_key(
                    OtlpKey.get_resource_key(ResourceAttributes.SERVICE_NAME)
                ),
            },
            {
                "name": str(_lazy("实例")),
                "id": "instance",
                "trace_key": OtlpKey.get_resource_key(OtlpKey.BK_INSTANCE_ID),
                "metric_key": OtlpKey.get_metric_dimension_key(OtlpKey.get_resource_key(OtlpKey.BK_INSTANCE_ID)),
            },
            {
                "name": str(_lazy("接口")),
                "id": "endpoint",
                "trace_key": OtlpKey.SPAN_NAME,
                "metric_key": OtlpKey.get_metric_dimension_key(OtlpKey.SPAN_NAME),
            },
            {
                "name": str(_lazy("类型")),
                "id": "kind",
                "trace_key": OtlpKey.KIND,
                "metric_key": OtlpKey.get_metric_dimension_key(OtlpKey.KIND),
            },
        ]


class ListStandardFilterFieldsResource(Resource):
    def perform_request(self, data):
        return SpanStandardField.list_standard_fields()


class ListSpanResource(Resource):
    RequestSerializer = QuerySerializer

    def perform_request(self, data):
        response = self.get_span_list_api_data(data)

        QueryHandler.handle_span_list(response["data"])
        return response

    def get_span_list_api_data(self, data):
        bk_biz_id: int = data["bk_biz_id"]
        app_name: str = data["app_name"]
        query_string = QueryHandler.process_query_string(SpanQueryTransformer(bk_biz_id, app_name), data["query"])
        params = {
            "bk_biz_id": bk_biz_id,
            "app_name": app_name,
            "start_time": data["start_time"],
            "end_time": data["end_time"],
            "offset": data["offset"],
            "limit": data["limit"],
            "filters": data["filters"],
            "exclude_field": ["bk_app_code"],
            "query_string": query_string,
            "sort": data["sort"],
        }

        try:
            response = api.apm_api.query_span_list(params)
        except BKAPIError as e:
            raise CustomException(_lazy(f"Span列表请求失败: {e.data.get('message')}"))

        self.burial_point(data["bk_biz_id"], data["app_name"])
        return response

    def burial_point(self, bk_biz_id, app_name):
        # 查询指标埋点
        try:
            unify_query_count(data_type_label="trace", bk_biz_id=bk_biz_id, app_name=app_name)
        except Exception:  # noqa
            logger.exception("failed to add trace query count")
        else:
            safe_push_to_gateway(registry=OPERATION_REGISTRY)


class ListTraceResource(Resource):
    RequestSerializer = QuerySerializer

    def perform_request(self, data):
        response = self.get_trace_list_api_data(data)

        QueryHandler.handle_trace_list(response["data"])

        return response

    def get_trace_list_api_data(self, data):
        bk_biz_id: int = data["bk_biz_id"]
        app_name: str = data["app_name"]
        params = {
            "bk_biz_id": bk_biz_id,
            "app_name": app_name,
            "start_time": data["start_time"],
            "end_time": data["end_time"],
            "offset": data["offset"],
            "limit": data["limit"],
            "filters": data["filters"],
            "exclude_field": ["bk_app_code", "biz_name"],
            "sort": data["sort"],
        }

        is_contain_non_standard_fields = QueryHandler.has_field_not_in_fields(
            data["query"],
            data["filters"],
            fields=SpanStandardField.standard_fields() + PreCalculateSpecificField.search_fields(),
        )

        is_has_specific_fields = QueryHandler.has_field_not_in_fields(
            data["query"], data["filters"], fields=PreCalculateSpecificField.specific_fields(), opposite=True
        )

        if is_contain_non_standard_fields:
            # 如果查询包含了非标准字段 -> 走原始表（预计算表无法查询非标准字段）
            qm = TraceListQueryMode.ORIGIN
            params["query_string"] = QueryHandler.process_query_string(
                SpanQueryTransformer(bk_biz_id, app_name), data["query"]
            )
        else:
            qm = TraceListQueryMode.PRE_CALCULATION
            params["query_string"] = QueryHandler.process_query_string(
                TraceQueryTransformer(bk_biz_id, app_name), data["query"]
            )

        params["query_mode"] = qm
        try:
            response = api.apm_api.query_trace_list(params)
            if qm == TraceListQueryMode.PRE_CALCULATION and not response["data"] and not is_has_specific_fields:
                # 如果本次为预计算查询但是无数据时 切换为原始表再次查询 同时 es_dsl 也需要切换为 Span 表的 DSL 转换器
                qm = TraceListQueryMode.ORIGIN
                params["query_mode"] = qm
                params["query_string"] = QueryHandler.process_query_string(
                    SpanQueryTransformer(bk_biz_id, app_name), data["query"]
                )
                response = api.apm_api.query_trace_list(params)
        except BKAPIError as e:
            raise CustomException(_lazy(f"Trace列表请求失败: {e.data.get('message')}"))

        self.burial_point(data["bk_biz_id"], data["app_name"])
        response["type"] = qm
        return response

    def burial_point(self, bk_biz_id, app_name):
        # 查询指标埋点
        try:
            unify_query_count(data_type_label="trace", bk_biz_id=bk_biz_id, app_name=app_name)
        except Exception:  # noqa
            logger.exception("failed to add trace query count")
        else:
            safe_push_to_gateway(registry=OPERATION_REGISTRY)


class TraceStatisticsResource(Resource):
    class RequestSerializer(serializers.Serializer):
        class FilterSerializer(serializers.Serializer):
            filter_types = (
                ("service", _("服务")),
                ("error", _("错误")),
                ("max_duration", _("最大耗时")),
                ("keyword", _("关键词")),
            )
            type = serializers.ChoiceField(label="过滤条件", choices=filter_types)
            value = serializers.CharField(label="过滤值", allow_null=True, allow_blank=True)

        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")
        trace_id = serializers.CharField(label="Trace ID")
        filter = FilterSerializer(label="过滤", required=False, allow_null=True)
        group_fields = serializers.ListField(child=serializers.CharField(), label="分组字段列表")

    def perform_request(self, validated_data):
        trace = api.apm_api.query_trace_detail(
            {
                "bk_biz_id": validated_data["bk_biz_id"],
                "app_name": validated_data["app_name"],
                "trace_id": validated_data["trace_id"],
            }
        )
        if not trace.get("trace_data"):
            raise ValueError(_lazy(f"trace_id: {validated_data['trace_id']} 不存在"))

        return StatisticsHandler.get_trace_statistics(
            trace["trace_data"], validated_data["group_fields"], validated_data.get("filter") or {}
        )


class TraceDetailResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")
        trace_id = serializers.CharField(label="Trace ID")
        displays = serializers.ListField(
            child=serializers.ChoiceField(
                choices=TraceWaterFallDisplayKey.choices(),
                default=TraceWaterFallDisplayKey.SOURCE_CATEGORY_OPENTELEMETRY,
            ),
            default=list,
            allow_empty=True,
            required=False,
        )
        query_trace_relation_app = serializers.BooleanField(required=False, default=False)
        enabled_time_alignment = serializers.BooleanField(required=False, default=False, label="是否开启时间对齐")

    def perform_request(self, validated_request_data):
        data = api.apm_api.query_trace_detail(
            {
                "bk_biz_id": validated_request_data["bk_biz_id"],
                "app_name": validated_request_data["app_name"],
                "trace_id": validated_request_data["trace_id"],
                "displays": validated_request_data["displays"],
                "query_trace_relation_app": validated_request_data["query_trace_relation_app"],
            }
        )
        if not data.get("trace_data"):
            raise CustomException(_lazy(f"trace_id: {validated_request_data['trace_id']} 不存在"))
        handled_data = TraceHandler.handle_trace(
            validated_request_data["app_name"],
            data["trace_data"],
            validated_request_data["trace_id"],
            data["relation_mapping"],
            validated_request_data.get("displays"),
            validated_request_data.get("enabled_time_alignment"),
        )
        if not handled_data.get("original_data", []):
            raise CustomException(
                _lazy("trace_id: {} 没有有效的 trace 数据").format(validated_request_data["trace_id"])
            )

        topo_data = trace_data_to_topo_data(handled_data["original_data"])
        handled_data["topo_relation"] = topo_data["relations"]
        handled_data["topo_nodes"] = topo_data["nodes"]
        service_topo_data = trace_data_to_service_topo(handled_data["original_data"])
        handled_data.update(service_topo_data)
        handled_data.update(data.get("options"))
        return handled_data


class SpanDetailResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")
        span_id = serializers.CharField(label="Span ID")

    def perform_request(self, validated_request_data):
        span = api.apm_api.query_span_detail(**validated_request_data)
        return TraceHandler.handle_span(validated_request_data["app_name"], span)


class TraceDiagramResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")
        trace_id = serializers.CharField(label="Trace ID")

        diagram_type = serializers.ChoiceField(
            label="图表类型", choices=("flamegraph", "sequence", "topo", "statistics")
        )
        displays = serializers.ListField(
            child=serializers.ChoiceField(
                choices=TraceWaterFallDisplayKey.choices(),
                default=TraceWaterFallDisplayKey.SOURCE_CATEGORY_OPENTELEMETRY,
            ),
            default=list,
            allow_empty=True,
            required=False,
        )
        diff_trace_id = serializers.CharField(label="对比 TraceID", required=False, allow_null=True, allow_blank=True)
        prefer_raw = serializers.BooleanField(label="是否优先展示原始数据", required=False, default=False)
        absolute_time_sequence = serializers.BooleanField(label="是否展示绝对时间", required=False, default=False)

        filter = TraceStatisticsResource.RequestSerializer.FilterSerializer(
            label="过滤", required=False, allow_null=True
        )
        group_fields = serializers.ListField(child=serializers.CharField(), label="分组字段列表", required=False)

    def get_comparison_details(self, bk_biz_id: str, app_name: str, trace_id: str, displays: list) -> dict:
        """获取对比详情
        - 先尝试从 DB 中查询已收藏的 Trace
        - 不存在则尝试查询
        """
        starred_comparisons = TraceComparison.objects.filter(trace_id=trace_id)
        if not starred_comparisons:
            diff_trace = api.apm_api.query_trace_detail(
                {"bk_biz_id": bk_biz_id, "app_name": app_name, "trace_id": trace_id, "displays": displays}
            )
            if not diff_trace.get("trace_data"):
                raise ValueError(_lazy("trace_id: {} 不存在").format(trace_id))
            return diff_trace

        starred_comparison = starred_comparisons[0]
        return {"trace_data": starred_comparison.spans, "relation_mapping": {}}

    def perform_request(self, validated_request_data):
        original_data = api.apm_api.query_trace_detail(
            {
                "bk_biz_id": validated_request_data["bk_biz_id"],
                "app_name": validated_request_data["app_name"],
                "trace_id": validated_request_data["trace_id"],
                "displays": validated_request_data["displays"],
            }
        )
        if not original_data.get("trace_data"):
            raise ValueError(_lazy("trace_id: {} 不存在").format(validated_request_data["trace_id"]))

        # TODO: displays would be [] instead of None in GET request
        # and handle_trace will return {} if [] is passed in, which is not clearly defined.
        displays = validated_request_data.get("displays") or []
        if TraceWaterFallDisplayKey.SOURCE_CATEGORY_OPENTELEMETRY not in displays:
            displays.append(TraceWaterFallDisplayKey.SOURCE_CATEGORY_OPENTELEMETRY)

        handled_data = TraceHandler.handle_trace(
            validated_request_data["app_name"],
            original_data["trace_data"],
            validated_request_data["trace_id"],
            original_data["relation_mapping"],
            displays,
        )

        diagrammer = get_diagrammer(validated_request_data["diagram_type"], {})
        # 当有对比 trace_id 时，需要对比两个 trace 的差异
        if validated_request_data.get("diff_trace_id"):
            if validated_request_data.get("diff_trace_id") == validated_request_data["trace_id"]:
                raise ValueError(_lazy("对比 TraceID 不能与原始 TraceID 相同"))

            diff_trace = self.get_comparison_details(
                bk_biz_id=validated_request_data["bk_biz_id"],
                app_name=validated_request_data["app_name"],
                trace_id=validated_request_data["diff_trace_id"],
                displays=displays,
            )

            other_handled_data = TraceHandler.handle_trace(
                validated_request_data["app_name"],
                diff_trace["trace_data"],
                validated_request_data["trace_id"],
                diff_trace["relation_mapping"],
                displays,
            )

            diagram = diagrammer.diff(
                handled_data["original_data"], other_handled_data["original_data"], **validated_request_data
            )
            result = {
                "diagram_data": diagram,
                "original_data": other_handled_data["original_data"],
                "trace_tree": other_handled_data["trace_tree"],
            }
        else:
            diagram = diagrammer.draw(handled_data["original_data"])
            result = {
                "diagram_data": diagram,
                "original_data": handled_data["original_data"],
                "trace_tree": handled_data["trace_tree"],
                "trace_info": handled_data["trace_info"],
            }

        return result


class TraceListByIdResource(Resource):
    TRACE_INFO_URL = (
        "/?bizId={bk_biz_id}#/trace/home?app_name={app_name}&search_id=traceID&search_type=accurate&trace_id={trace_id}"
    )

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        trace_ids = serializers.ListField(child=serializers.CharField(), allow_empty=True)
        start_time = serializers.IntegerField()
        end_time = serializers.IntegerField()

    def generate_url(self, bk_biz_id, app_name, trace_id):
        """生成跳转url"""
        return self.TRACE_INFO_URL.format(bk_biz_id=bk_biz_id, app_name=app_name, trace_id=trace_id)

    def perform_request(self, validated_request_data):
        if not validated_request_data["trace_ids"]:
            return []
        trace_ids_mapping = api.apm_api.query_trace_by_ids(
            trace_ids=validated_request_data["trace_ids"],
            bk_biz_id=validated_request_data["bk_biz_id"],
            start_time=validated_request_data["start_time"],
            end_time=validated_request_data["end_time"],
        )
        res = []
        for trace_id, item in trace_ids_mapping.items():
            app_name = item["app_name"]

            if item["error"]:
                status = {"type": StatusCodeAttributePredicate.STATUS_ERROR, "value": _("异常")}
            else:
                status = {"type": StatusCodeAttributePredicate.STATUS_NORMAL, "value": _("正常")}

            res.append(
                {
                    "url": self.generate_url(validated_request_data["bk_biz_id"], app_name, trace_id),
                    "category": CategoryEnum.get_label_by_key(item["root_service_category"]),
                    "status_code": status,
                    "span_id": item.pop("root_span_id"),
                    **item,
                }
            )

        return res


class TraceListByHostInstanceResource(Resource):
    TRACE_INFO_URL = (
        "/?bizId={bk_biz_id}#/trace/home?app_name={app_name}&search_id=traceID&search_type=accurate&trace_id={trace_id}"
    )

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        ip = serializers.CharField()
        bk_cloud_id = serializers.IntegerField()
        start_time = serializers.IntegerField()
        end_time = serializers.IntegerField()
        offset = serializers.IntegerField(required=False, label="偏移量", default=0)
        limit = serializers.IntegerField(required=False, label="每页数量", default=10)

    def generate_url(self, bk_biz_id, app_name, trace_id):
        """生成跳转url"""
        return self.TRACE_INFO_URL.format(bk_biz_id=bk_biz_id, app_name=app_name, trace_id=trace_id)

    def perform_request(self, validated_request_data):
        traces = api.apm_api.query_trace_by_host_instance(
            bk_biz_id=validated_request_data["bk_biz_id"],
            ip=validated_request_data["ip"],
            bk_cloud_id=validated_request_data["bk_cloud_id"],
            start_time=validated_request_data["start_time"],
            end_time=validated_request_data["end_time"],
            offset=validated_request_data["offset"],
            limit=validated_request_data["limit"],
        )

        if not traces:
            return {}

        bk_biz_id = traces["app_info"]["bk_biz_id"]
        app_name = traces["app_info"]["app_name"]
        total = traces["data"]["total"]

        res = []

        for trace_id, item in traces["data"]["data"].items():
            if item["error"]:
                status = {"type": StatusCodeAttributePredicate.STATUS_ERROR, "value": _("异常")}
            else:
                status = {"type": StatusCodeAttributePredicate.STATUS_NORMAL, "value": _("正常")}
            res.append(
                {
                    "url": self.generate_url(bk_biz_id, app_name, trace_id),
                    "category": CategoryEnum.get_label_by_key(item["root_service_category"]),
                    "status_code": status,
                    "trace_id": item.pop("trace_id")[0],
                    **item,
                }
            )

        return {"total": total, "data": res}


class ListOptionValuesResource(Resource):
    """
    获取Span/Trace表头下拉框候选值
    """

    TRACE_LIST_FIELDS = {
        QueryMode.TRACE: [
            "root_service",
            "root_service_span_name",
            "root_service_status_code",
            "root_service_category",
            "root_span_name",
            "root_span_service",
        ],
        QueryMode.SPAN: [
            "span_name",
            "status.code",
            "kind",
            "resource.telemetry.sdk.version",
            "resource.service.name",
            "resource.bk.instance.id",
        ],
    }

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        app_name = serializers.CharField(label="应用名称")
        start_time = serializers.IntegerField()
        end_time = serializers.IntegerField()
        mode = serializers.ChoiceField(choices=QueryMode.choices(), label="查询模式")

    @using_cache(CacheType.APM(60 * 1))
    def perform_request(self, validated_data):
        validated_data["fields"] = self.TRACE_LIST_FIELDS[validated_data["mode"]]
        return QueryHandler.get_fields_option_values(**validated_data, filters=[], query_string="", limit=500)


class GetFieldOptionValuesResource(Resource):
    """
    获取标准字段下拉框候选值
    """

    class RequestSerializer(serializers.Serializer):
        mode_choices = (
            ("span", "span表查询"),
            ("pre_calculate", "预计算表查询"),
        )

        bk_biz_id = serializers.IntegerField()
        app_name = serializers.CharField(label="应用名称")
        start_time = serializers.IntegerField()
        end_time = serializers.IntegerField()
        fields = serializers.ListField(child=serializers.CharField(), label="查询字段列表")
        # 前端没有传递该值，span 模式下走 unify-query tag values 查询，性能优于 es
        mode = serializers.ChoiceField(label="查询表", choices=mode_choices, default="span")

    @using_cache(CacheType.APM(60 * 1))
    def perform_request(self, validated_request_data):
        return QueryHandler.get_file_option_values(**validated_request_data)


class GetFieldsOptionValuesResource(Resource):
    """获取指定字段列表的候选项值"""

    RequestSerializer = GetFieldsOptionValuesRequestSerializer

    @using_cache(CacheType.APM(60 * 1))
    def perform_request(self, validated_request_data):
        option_values_dict = QueryHandler.get_fields_option_values(**validated_request_data)
        data = {}
        for field_name, option_value_list in option_values_dict.items():
            data[field_name] = [option_value_dict.get("value", "") for option_value_dict in option_value_list]

        return data


class ListSpanStatisticsResource(Resource):
    """
    接口统计
    """

    RequestSerializer = QueryStatisticsSerializer

    def perform_request(self, validated_data):
        bk_biz_id: int = validated_data["bk_biz_id"]
        app_name: str = validated_data["app_name"]
        query_string = QueryHandler.process_query_string(
            SpanQueryTransformer(bk_biz_id, app_name), validated_data["query"]
        )
        params = {
            "bk_biz_id": validated_data["bk_biz_id"],
            "app_name": validated_data["app_name"],
            "start_time": validated_data["start_time"],
            "end_time": validated_data["end_time"],
            "offset": validated_data["offset"],
            "limit": validated_data["limit"],
            "query_string": query_string,
            "filters": validated_data["filters"],
        }

        try:
            response = api.apm_api.query_span_statistics(params)
        except BKAPIError as e:
            raise CustomException(_lazy("获取接口统计失败: {message}").format(message=e.data.get("message")))

        return response


class ListServiceStatisticsResource(Resource):
    """
    服务统计
    """

    RequestSerializer = QueryStatisticsSerializer

    def perform_request(self, validated_data):
        bk_biz_id: int = validated_data["bk_biz_id"]
        app_name: str = validated_data["app_name"]
        query_string = QueryHandler.process_query_string(
            SpanQueryTransformer(bk_biz_id, app_name), validated_data["query"]
        )
        params = {
            "bk_biz_id": validated_data["bk_biz_id"],
            "app_name": validated_data["app_name"],
            "start_time": validated_data["start_time"],
            "end_time": validated_data["end_time"],
            "offset": validated_data["offset"],
            "limit": validated_data["limit"],
            "query_string": query_string,
            "filters": validated_data["filters"],
        }

        try:
            response = api.apm_api.query_service_statistics(params)
        except BKAPIError as e:
            raise CustomException(_lazy("获取服务统计失败: {message}".format(message=e.data.get("message"))))

        return response


class ApplyTraceComparisonResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.CharField(label="应用名称", max_length=50)
        trace_id = serializers.CharField(label="trace ID", max_length=32)
        name = serializers.CharField(label="参照名称", max_length=16)

    class ResponseSerializer(serializers.ModelSerializer):
        class Meta:
            model = TraceComparison
            exclude = ["spans", "is_enabled", "is_deleted"]

    def perform_request(self, validated_data):
        params = dict(bk_biz_id=validated_data["bk_biz_id"], app_name=validated_data["app_name"])
        unique_params = copy.deepcopy(params)
        unique_params["trace_id"] = validated_data["trace_id"]
        comparison = TraceComparison.objects.filter(**unique_params)
        if comparison.exists():
            if (
                TraceComparison.objects.filter(**params, name=validated_data["name"])
                .exclude(trace_id=validated_data["trace_id"])
                .exists()
            ):
                raise ValueError(_lazy("该应用下已有名称为 {} 的常用参照").format(validated_data["name"]))

            update_params = {"name": validated_data["name"]}
            return comparison.update(**update_params)

        if (
            TraceComparison.objects.filter(
                bk_biz_id=validated_data["bk_biz_id"], app_name=validated_data["app_name"]
            ).count()
            >= DEFAULT_DIFF_TRACE_MAX_NUM
        ):
            raise ValueError(_lazy("参照数量已达上限({}), 请删除后再新增").format(DEFAULT_DIFF_TRACE_MAX_NUM))

        # 判断该应用下当前参照是否存在
        params["name"] = validated_data["name"]
        if TraceComparison.objects.filter(**params).exists():
            raise ValueError(_lazy("应用({})下存在重名的参照").format(validated_data["app_name"]))
        # 获取trace详情
        trace = api.apm_api.query_trace_detail(
            {
                "bk_biz_id": validated_data["bk_biz_id"],
                "app_name": validated_data["app_name"],
                "trace_id": validated_data["trace_id"],
            }
        )
        if not trace.get("trace_data"):
            raise ValueError(_lazy("trace_id({})对应的参照不存在或已过期").format(validated_data["trace_id"]))
        # 新建trace参照
        return TraceComparison.objects.create(
            bk_biz_id=validated_data["bk_biz_id"],
            app_name=validated_data["app_name"],
            trace_id=validated_data["trace_id"],
            name=validated_data["name"],
            spans=trace.get("trace_data"),
        )


class DeleteTraceComparisonResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.CharField(label="应用名称", max_length=50)
        trace_id = serializers.CharField(label="trace ID", max_length=32)

    def perform_request(self, validated_data):
        params = {
            "bk_biz_id": validated_data["bk_biz_id"],
            "app_name": validated_data["app_name"],
            "trace_id": validated_data["trace_id"],
        }
        try:
            TraceComparison.objects.get(**params).delete()
            return True
        except TraceComparison.DoesNotExist:
            raise ValueError(_lazy("trace_id({})对应的参照不存在").format(validated_data["trace_id"]))


class ListTraceComparisonResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")

    class TraceComparisonSerializer(serializers.ModelSerializer):
        class Meta:
            model = TraceComparison
            exclude = ["spans", "is_enabled", "is_deleted"]

    def perform_request(self, validated_data):
        filter_params = {"bk_biz_id": validated_data["bk_biz_id"], "app_name": validated_data["app_name"]}
        comparisons = TraceComparison.objects.filter(**filter_params).order_by("-update_time")
        data = self.TraceComparisonSerializer(comparisons, many=True).data
        total = comparisons.count()
        return {"total": total, "data": data}


class ListSpanHostInstancesResource(Resource):
    """
    获取Span中包含的主机实例列表
    """

    RequestSerializer = SpanIdInputSerializer

    def perform_request(self, validated_request_data):
        return HostHandler.find_host_in_span(**validated_request_data)


class ListTraceViewConfigResource(Resource):
    """获取 trace 检索页面的视图配置"""

    RequestSerializer = BaseTraceRequestSerializer

    def perform_request(self, validated_request_data):
        fields_handler = TraceFieldsHandler(validated_request_data["bk_biz_id"], validated_request_data["app_name"])

        return {
            "trace_config": fields_handler.get_fields_by_mode(QueryMode.TRACE),
            "span_config": fields_handler.get_fields_by_mode(QueryMode.SPAN),
        }


class TraceFieldsTopKResource(Resource):
    """获取 trace 字段的 topk 数据"""

    RequestSerializer = TraceFieldsTopkRequestSerializer

    def perform_request(self, validated_data):
        return DimensionStatisticsAPIHandler.get_api_topk_data(validated_data)


class TraceFieldStatisticsInfoResource(Resource):
    """获取 trace 字段的维度统计信息"""

    RequestSerializer = TraceFieldStatisticsInfoRequestSerializer

    def perform_request(self, validated_data):
        if validated_data["field"]["field_name"] in {OtlpKey.ELAPSED_TIME, PreCalculateSpecificField.TRACE_DURATION}:
            validated_data["exclude_property"] = [
                StatisticsProperty.MEDIAN.value,
                StatisticsProperty.TOTAL_COUNT.value,
                StatisticsProperty.FIELD_COUNT.value,
                StatisticsProperty.DISTINCT_COUNT.value,
            ]
        return DimensionStatisticsAPIHandler.get_api_statistics_info_data(validated_data)


class TraceFieldStatisticsGraphResource(Resource):
    """获取 trace 字段的维度统计图表"""

    RequestSerializer = TraceFieldStatisticsGraphRequestSerializer

    EMPTY_DATA = {"series": [{"datapoints": []}]}

    def perform_request(self, validated_data):
        field_info = validated_data["field"]
        # 边界场景，数值字段最小值，最大值为 None 时，直接返回空数据
        if field_info["field_type"] in {
            EnabledStatisticsDimension.INTEGER.value,
            EnabledStatisticsDimension.LONG.value,
            EnabledStatisticsDimension.DOUBLE.value,
        }:
            min_value, max_value, *_ = field_info["values"][:4]
            if min_value is None or max_value is None:
                return self.EMPTY_DATA

        return DimensionStatisticsAPIHandler.get_api_statistics_graph_data(validated_data)


class ListFlattenSpanResource(Resource):
    RequestSerializer = QuerySerializer

    def perform_request(self, data):
        response = ListSpanResource().get_span_list_api_data(data)
        response["data"] = [flatten_es_dict_data(data_dict) for data_dict in response["data"]]
        return response


class ListFlattenTraceResource(Resource):
    RequestSerializer = QuerySerializer

    def perform_request(self, data):
        response = ListTraceResource().get_trace_list_api_data(data)
        data_list = []
        for trace_data_dict in response["data"]:
            data_list.append(flatten_es_dict_data(trace_data_dict))
        response["data"] = data_list
        return response


class TraceGenerateQueryStringResource(Resource):
    RequestSerializer = TraceGenerateQueryStringRequestSerializer

    def perform_request(self, data):
        generator = QueryStringGenerator(OperatorEnum.QueryStringOperatorMapping)
        for f in data["filters"]:
            generator.add_filter(
                f["key"],
                f["operator"],
                f["value"],
                f.get("options", {}).get("is_wildcard", False),
                f.get("options", {}).get("group_relation", OperatorGroupRelation.OR),
            )
        return generator.to_query_string()
