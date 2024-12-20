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
from functools import partial

from django.utils.translation import gettext_lazy as _
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.semconv.trace import SpanAttributes

from apm_web.constants import CalculationMethod
from apm_web.metric_handler import (
    ApdexInstance,
    AvgDurationInstance,
    ErrorCountInstance,
    ErrorRateInstance,
    RequestCountInstance,
    cache_batch_metric_query,
    cache_batch_metric_query_group,
)
from constants.apm import OtlpKey
from core.unit import load_unit


def application_id_get(application):
    return application["application_id"]


APPLICATION_LIST = partial(
    cache_batch_metric_query,
    metric_handler_cls=[
        RequestCountInstance,
        ApdexInstance,
        ErrorCountInstance,
        ErrorRateInstance,
        AvgDurationInstance,
    ],
    id_get=application_id_get,
    period="day",
    distance=1,
)

APPLICATION_LIST_REFRESH = partial(
    cache_batch_metric_query.refresh,
    metric_handler_cls=[
        RequestCountInstance,
        ApdexInstance,
        ErrorCountInstance,
        ErrorRateInstance,
        AvgDurationInstance,
    ],
    id_get=application_id_get,
    period="day",
    distance=1,
)

SERVICE_LIST = partial(
    cache_batch_metric_query_group,
    period="day",
    distance=1,
    group_key=[OtlpKey.get_metric_dimension_key(ResourceAttributes.SERVICE_NAME)],
    metric_handler_cls=[RequestCountInstance, ErrorCountInstance, AvgDurationInstance, ErrorRateInstance],
)

SERVICE_DATA_STATUS = partial(
    cache_batch_metric_query_group,
    period="day",
    distance=1,
    group_key=[OtlpKey.get_metric_dimension_key(ResourceAttributes.SERVICE_NAME)],
    metric_handler_cls=[RequestCountInstance],
)

REMOTE_SERVICE_DATA_STATUS = partial(
    cache_batch_metric_query_group,
    period="day",
    distance=1,
    group_key=[OtlpKey.get_metric_dimension_key(SpanAttributes.PEER_SERVICE)],
    metric_handler_cls=[RequestCountInstance],
)

COMPONENT_DATA_STATUS = partial(
    cache_batch_metric_query_group,
    period="day",
    distance=1,
    group_key=[
        OtlpKey.get_metric_dimension_key(key)
        for key in [
            ResourceAttributes.SERVICE_NAME,
            SpanAttributes.DB_SYSTEM,
            SpanAttributes.MESSAGING_SYSTEM,
        ]
    ],
    metric_handler_cls=[
        RequestCountInstance,
    ],
)

REMOTE_SERVICE_LIST = partial(
    cache_batch_metric_query_group,
    period="day",
    distance=1,
    group_key=[OtlpKey.get_metric_dimension_key(SpanAttributes.PEER_SERVICE)],
    metric_handler_cls=[RequestCountInstance, ErrorCountInstance, AvgDurationInstance, ErrorRateInstance],
)

SERVICE_LIST_REFRESH = partial(
    cache_batch_metric_query_group.refresh,
    period="day",
    distance=1,
    group_key=[OtlpKey.get_metric_dimension_key(ResourceAttributes.SERVICE_NAME)],
    metric_handler_cls=[RequestCountInstance, ErrorCountInstance, AvgDurationInstance, ErrorRateInstance],
)

ENDPOINT_LIST = partial(
    cache_batch_metric_query_group,
    period="day",
    distance=1,
    group_key=[OtlpKey.SPAN_NAME, OtlpKey.KIND, OtlpKey.get_metric_dimension_key(ResourceAttributes.SERVICE_NAME)]
    + [
        OtlpKey.get_metric_dimension_key(k)
        for k in [
            SpanAttributes.DB_SYSTEM,
            SpanAttributes.MESSAGING_SYSTEM,
            SpanAttributes.RPC_SYSTEM,
            SpanAttributes.HTTP_METHOD,
            SpanAttributes.MESSAGING_DESTINATION,
        ]
    ],
    metric_handler_cls=[
        RequestCountInstance,
        ApdexInstance,
        ErrorCountInstance,
        ErrorRateInstance,
        AvgDurationInstance,
    ],
)

ENDPOINT_LIST_REFRESH = partial(
    cache_batch_metric_query_group.refresh,
    period="day",
    distance=1,
    group_key=[OtlpKey.SPAN_NAME, OtlpKey.KIND, OtlpKey.get_metric_dimension_key(ResourceAttributes.SERVICE_NAME)]
    + [
        OtlpKey.get_metric_dimension_key(k)
        for k in [
            SpanAttributes.DB_SYSTEM,
            SpanAttributes.MESSAGING_SYSTEM,
            SpanAttributes.RPC_SYSTEM,
            SpanAttributes.HTTP_METHOD,
            SpanAttributes.MESSAGING_DESTINATION,
        ]
    ],
    metric_handler_cls=[
        RequestCountInstance,
        ApdexInstance,
        ErrorCountInstance,
        ErrorRateInstance,
        AvgDurationInstance,
    ],
)

ENDPOINT_DETAIL_LIST = partial(
    cache_batch_metric_query_group,
    period="hour",
    distance=1,
    group_key=[OtlpKey.SPAN_NAME, OtlpKey.get_metric_dimension_key(ResourceAttributes.SERVICE_NAME)],
    metric_handler_cls=[RequestCountInstance, ErrorCountInstance, AvgDurationInstance],
)

ENDPOINT_DETAIL_LIST_REFRESH = partial(
    cache_batch_metric_query_group.refresh,
    period="hour",
    distance=1,
    group_key=[OtlpKey.SPAN_NAME, OtlpKey.get_metric_dimension_key(ResourceAttributes.SERVICE_NAME)],
    metric_handler_cls=[RequestCountInstance, ErrorCountInstance],
)

INSTANCE_LIST_REFRESH = partial(
    cache_batch_metric_query_group.refresh,
    period="day",
    distance=1,
    group_key=[OtlpKey.get_metric_dimension_key(OtlpKey.BK_INSTANCE_ID)],
    metric_handler_cls=[
        RequestCountInstance,
        ApdexInstance,
        ErrorRateInstance,
        AvgDurationInstance,
    ],
)

INSTANCE_LIST = partial(
    cache_batch_metric_query_group,
    period="day",
    distance=1,
    group_key=[OtlpKey.get_metric_dimension_key(OtlpKey.BK_INSTANCE_ID)],
    metric_handler_cls=[
        RequestCountInstance,
        ApdexInstance,
        ErrorRateInstance,
        AvgDurationInstance,
    ],
)


def default_value_format(name="", id="", unit="short", decimal=5):
    def _format(value):
        original_value = value
        value = load_unit(unit).auto_convert(value, decimal=decimal)
        return {
            "name": str(name),
            "id": id,
            "value": "".join([str(i) for i in value]),
            "original_value": original_value,
        }

    return _format


TOPO_SERVICE_METRIC_REFRESH = partial(
    cache_batch_metric_query_group.refresh,
    period="day",
    distance=1,
    group_key=[
        OtlpKey.get_metric_dimension_key(key)
        for key in [
            ResourceAttributes.SERVICE_NAME,
            OtlpKey.KIND,
        ]
    ],
    metric_handler_cls=[
        partial(
            AvgDurationInstance,
            result_map=default_value_format(name=_("平均耗时"), id=CalculationMethod.AVG_DURATION, unit="ns"),
        ),
        partial(
            RequestCountInstance,
            result_map=default_value_format(name=_("请求数"), id=CalculationMethod.REQUEST_COUNT, unit="short"),
        ),
        partial(
            ErrorRateInstance,
            result_map=default_value_format(name=_("错误率"), id=CalculationMethod.ERROR_RATE, unit="percent", decimal=2),
        ),
    ],
)

TOPO_SERVICE_METRIC = partial(
    cache_batch_metric_query_group,
    period="day",
    distance=1,
    group_key=[
        OtlpKey.get_metric_dimension_key(key)
        for key in [
            ResourceAttributes.SERVICE_NAME,
        ]
    ],
    metric_handler_cls=[
        partial(
            AvgDurationInstance,
            result_map=default_value_format(name=_("平均耗时"), id=CalculationMethod.AVG_DURATION, unit="ns"),
        ),
        partial(
            RequestCountInstance,
            result_map=default_value_format(name=_("请求数"), id=CalculationMethod.REQUEST_COUNT, unit="short"),
        ),
        partial(
            ErrorRateInstance,
            result_map=default_value_format(name=_("错误率"), id=CalculationMethod.ERROR_RATE, unit="percent", decimal=2),
        ),
    ],
)

TOPO_REMOTE_SERVICE_METRIC = partial(
    cache_batch_metric_query_group,
    period="day",
    distance=1,
    group_key=[
        OtlpKey.get_metric_dimension_key(key)
        for key in [
            SpanAttributes.PEER_SERVICE,
            OtlpKey.KIND,
        ]
    ],
    metric_handler_cls=[
        partial(
            AvgDurationInstance,
            result_map=default_value_format(name=_("平均耗时"), id=CalculationMethod.AVG_DURATION, unit="ns"),
        ),
        partial(
            RequestCountInstance,
            result_map=default_value_format(name=_("请求数"), id=CalculationMethod.REQUEST_COUNT, unit="short"),
        ),
        partial(
            ErrorRateInstance,
            result_map=default_value_format(name=_("错误率"), id=CalculationMethod.ERROR_RATE, unit="percent", decimal=2),
        ),
    ],
)

TOPO_REMOTE_SERVICE_METRIC_REFRESH = partial(
    cache_batch_metric_query_group.refresh,
    period="day",
    distance=1,
    group_key=[
        OtlpKey.get_metric_dimension_key(key)
        for key in [
            SpanAttributes.PEER_SERVICE,
            OtlpKey.KIND,
        ]
    ],
    metric_handler_cls=[
        partial(
            AvgDurationInstance,
            result_map=default_value_format(name=_("平均耗时"), id=CalculationMethod.AVG_DURATION, unit="ns"),
        ),
        partial(
            RequestCountInstance,
            result_map=default_value_format(name=_("请求数"), id=CalculationMethod.REQUEST_COUNT, unit="short"),
        ),
        partial(
            ErrorRateInstance,
            result_map=default_value_format(name=_("错误率"), id=CalculationMethod.ERROR_RATE, unit="percent", decimal=2),
        ),
    ],
)

TOPO_COMPONENT_METRIC_REFRESH = partial(
    cache_batch_metric_query_group.refresh,
    period="day",
    distance=1,
    group_key=[
        OtlpKey.get_metric_dimension_key(key)
        for key in [
            SpanAttributes.DB_SYSTEM,
            SpanAttributes.MESSAGING_SYSTEM,
            SpanAttributes.NET_PEER_NAME,
            SpanAttributes.NET_PEER_IP,
            SpanAttributes.NET_PEER_PORT,
        ]
    ],
    metric_handler_cls=[
        partial(
            AvgDurationInstance,
            result_map=default_value_format(name=_("平均耗时"), id=CalculationMethod.AVG_DURATION, unit="ns"),
        ),
        partial(
            RequestCountInstance,
            result_map=default_value_format(name=_("请求数"), id=CalculationMethod.REQUEST_COUNT, unit="short"),
        ),
        partial(
            ErrorRateInstance,
            result_map=default_value_format(name=_("错误率"), id=CalculationMethod.ERROR_RATE, unit="percent", decimal=2),
        ),
    ],
)

TOPO_COMPONENT_METRIC = partial(
    cache_batch_metric_query_group,
    period="day",
    distance=1,
    group_key=[
        OtlpKey.get_metric_dimension_key(key)
        for key in [
            ResourceAttributes.SERVICE_NAME,
            SpanAttributes.DB_SYSTEM,
            SpanAttributes.MESSAGING_SYSTEM,
        ]
    ],
    metric_handler_cls=[
        partial(
            AvgDurationInstance,
            result_map=default_value_format(name=_("平均耗时"), id=CalculationMethod.AVG_DURATION, unit="ns"),
        ),
        partial(
            RequestCountInstance,
            result_map=default_value_format(name=_("请求数"), id=CalculationMethod.REQUEST_COUNT, unit="short"),
        ),
        partial(
            ErrorRateInstance,
            result_map=default_value_format(name=_("错误率"), id=CalculationMethod.ERROR_RATE, unit="percent", decimal=2),
        ),
    ],
)

COMPONENT_LIST = partial(
    cache_batch_metric_query_group,
    period="day",
    distance=1,
    group_key=[
        OtlpKey.get_metric_dimension_key(key)
        for key in [
            ResourceAttributes.SERVICE_NAME,
            SpanAttributes.DB_SYSTEM,
            SpanAttributes.MESSAGING_SYSTEM,
        ]
    ],
    metric_handler_cls=[
        RequestCountInstance,
        ErrorCountInstance,
        AvgDurationInstance,
        ErrorRateInstance,
        ApdexInstance,
        ErrorRateInstance,
    ],
)

TOPO_LIST_REFRESH = partial(
    cache_batch_metric_query_group.refresh,
    period="hour",
    distance=24,
    group_key=[
        OtlpKey.get_metric_dimension_key(ResourceAttributes.SERVICE_NAME),
        OtlpKey.get_metric_dimension_key(OtlpKey.KIND),
    ],
    metric_handler_cls=[
        RequestCountInstance,
        ErrorRateInstance,
        AvgDurationInstance,
    ],
)

TOPO_LIST = partial(
    cache_batch_metric_query_group,
    period="hour",
    distance=24,
    group_key=[
        OtlpKey.get_metric_dimension_key(ResourceAttributes.SERVICE_NAME),
        OtlpKey.get_metric_dimension_key(OtlpKey.KIND),
    ],
    metric_handler_cls=[
        RequestCountInstance,
        ErrorRateInstance,
        AvgDurationInstance,
    ],
)
