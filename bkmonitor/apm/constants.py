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
from django.conf import settings
from django.utils.translation import ugettext as _

from constants.apm import SpanKind


class ApdexEnum:
    Satisfied = "satisfied"
    Tolerating = "tolerating"
    Frustrated = "frustrated"


class VisibleEnum:
    # 当前业务可见
    CURRENT_BIZ = "current_biz"
    # 多业务可见
    MULTI_BIZ = "multi_biz"
    # 全业务
    ALL_BIZ = "all_biz"
    # 业务属性可见
    BIZ_ATTR = "biz_attr"


GLOBAL_CONFIG_BK_BIZ_ID = 0
# 获取需要增加事务的DB链接名
DATABASE_CONNECTION_NAME = getattr(settings, "METADATA_DEFAULT_DATABASE_NAME", "monitor_api")


############################################################################
# Topo Discover Constants
#############################################################################
DISCOVER_TIME_RANGE = "10m"
DISCOVER_BATCH_SIZE = 10000


############################################################################
# 计算平台清洗规则
#############################################################################
databus_cleans_fields = [
    {"field_name": "target", "field_type": "string", "field_alias": "target", "is_dimension": True, "field_index": 1},
    {"field_name": "time", "field_type": "long", "field_alias": "time", "is_dimension": False, "field_index": 2},
    {
        "field_name": "bk_apm_duration",
        "field_type": "long",
        "field_alias": "bk_apm_duration",
        "is_dimension": False,
        "field_index": 3,
    },
    {
        "field_name": "apdex_type",
        "field_type": "string",
        "field_alias": "apdex_type",
        "is_dimension": True,
        "field_index": 4,
    },
    {
        "field_name": "bk_instance_id",
        "field_type": "string",
        "field_alias": "bk_instance_id",
        "is_dimension": True,
        "field_index": 5,
    },
    {"field_name": "kind", "field_type": "string", "field_alias": "kind", "is_dimension": True, "field_index": 6},
    {
        "field_name": "service_name",
        "field_type": "string",
        "field_alias": "service_name",
        "is_dimension": True,
        "field_index": 7,
    },
    {
        "field_name": "span_name",
        "field_type": "string",
        "field_alias": "span_name",
        "is_dimension": True,
        "field_index": 8,
    },
    {
        "field_name": "status_code",
        "field_type": "string",
        "field_alias": "status_code",
        "is_dimension": True,
        "field_index": 9,
    },
    {
        "field_name": "telemetry_sdk_language",
        "field_type": "string",
        "field_alias": "telemetry_sdk_language",
        "is_dimension": True,
        "field_index": 10,
    },
    {
        "field_name": "telemetry_sdk_name",
        "field_type": "string",
        "field_alias": "telemetry_sdk_name",
        "is_dimension": True,
        "field_index": 11,
    },
    {
        "field_name": "telemetry_sdk_version",
        "field_type": "string",
        "field_alias": "telemetry_sdk_version",
        "is_dimension": True,
        "field_index": 12,
    },
    {
        "field_name": "peer_service",
        "field_type": "string",
        "field_alias": "peer_service",
        "is_dimension": True,
        "field_index": 13,
    },
    {
        "field_name": "http_server_name",
        "field_type": "string",
        "field_alias": "http_server_name",
        "is_dimension": True,
        "field_index": 14,
    },
    {
        "field_name": "http_method",
        "field_type": "string",
        "field_alias": "http_method",
        "is_dimension": True,
        "field_index": 15,
    },
    {
        "field_name": "http_scheme",
        "field_type": "string",
        "field_alias": "http_scheme",
        "is_dimension": True,
        "field_index": 16,
    },
    {
        "field_name": "http_flavor",
        "field_type": "string",
        "field_alias": "http_flavor",
        "is_dimension": True,
        "field_index": 17,
    },
    {
        "field_name": "http_status_code",
        "field_type": "string",
        "field_alias": "http_status_code",
        "is_dimension": True,
        "field_index": 18,
    },
    {
        "field_name": "rpc_method",
        "field_type": "string",
        "field_alias": "rpc_method",
        "is_dimension": True,
        "field_index": 19,
    },
    {
        "field_name": "rpc_service",
        "field_type": "string",
        "field_alias": "rpc_service",
        "is_dimension": True,
        "field_index": 20,
    },
    {
        "field_name": "rpc_system",
        "field_type": "string",
        "field_alias": "rpc_system",
        "is_dimension": True,
        "field_index": 21,
    },
    {
        "field_name": "rpc_grpc_status_code",
        "field_type": "string",
        "field_alias": "rpc_grpc_status_code",
        "is_dimension": True,
        "field_index": 22,
    },
    {
        "field_name": "db_name",
        "field_type": "string",
        "field_alias": "db_name",
        "is_dimension": True,
        "field_index": 23,
    },
    {
        "field_name": "db_operation",
        "field_type": "string",
        "field_alias": "db_operation",
        "is_dimension": True,
        "field_index": 24,
    },
    {
        "field_name": "db_system",
        "field_type": "string",
        "field_alias": "db_system",
        "is_dimension": True,
        "field_index": 25,
    },
    {
        "field_name": "messaging_system",
        "field_type": "string",
        "field_alias": "messaging_system",
        "is_dimension": True,
        "field_index": 26,
    },
    {
        "field_name": "messaging_destination",
        "field_type": "string",
        "field_alias": "messaging_destination",
        "is_dimension": True,
        "field_index": 27,
    },
    {
        "field_name": "messaging_destination_kind",
        "field_type": "string",
        "field_alias": "messaging_destination_kind",
        "is_dimension": True,
        "field_index": 28,
    },
    {
        "field_name": "celery_action",
        "field_type": "string",
        "field_alias": "celery_action",
        "is_dimension": True,
        "field_index": 29,
    },
    {
        "field_name": "celery_task_name",
        "field_type": "string",
        "field_alias": "celery_task_name",
        "is_dimension": True,
        "field_index": 30,
    },
]

databus_cleans_json_config = {
    "extract": {
        "type": "fun",
        "method": "from_json",
        "result": "json_data",
        "label": "label9ddd92",
        "args": [],
        "next": {
            "type": "access",
            "subtype": "access_obj",
            "label": "label19fada",
            "key": "data",
            "result": "data_list",
            "default_type": "null",
            "default_value": "",
            "next": {
                "type": "fun",
                "label": "label990256",
                "result": "item",
                "args": [],
                "method": "iterate",
                "next": {
                    "type": "branch",
                    "name": "",
                    "label": None,
                    "next": [
                        {
                            "type": "assign",
                            "subtype": "assign_obj",
                            "label": "label522123",
                            "assign": [
                                {"type": "string", "assign_to": "target", "key": "target"},
                                {"type": "long", "assign_to": "time", "key": "timestamp"},
                            ],
                            "next": None,
                        },
                        {
                            "type": "access",
                            "subtype": "access_obj",
                            "label": "label70361d",
                            "key": "metrics",
                            "result": "item_metrics",
                            "default_type": "null",
                            "default_value": "",
                            "next": {
                                "type": "assign",
                                "subtype": "assign_obj",
                                "label": "labele1de9b",
                                "assign": [{"type": "long", "assign_to": "bk_apm_duration", "key": "bk_apm_duration"}],
                                "next": None,
                            },
                        },
                        {
                            "type": "access",
                            "subtype": "access_obj",
                            "label": "labela74674",
                            "key": "dimension",
                            "result": "item_dimension",
                            "default_type": "null",
                            "default_value": "",
                            "next": {
                                "type": "assign",
                                "subtype": "assign_obj",
                                "label": "labela4d53c",
                                "assign": [
                                    {"type": "string", "assign_to": "apdex_type", "key": "apdex_type"},
                                    {"type": "string", "assign_to": "bk_instance_id", "key": "bk_instance_id"},
                                    {"type": "string", "assign_to": "kind", "key": "kind"},
                                    {"type": "string", "assign_to": "service_name", "key": "service_name"},
                                    {"type": "string", "assign_to": "span_name", "key": "span_name"},
                                    {"type": "string", "assign_to": "status_code", "key": "status_code"},
                                    {
                                        "type": "string",
                                        "assign_to": "telemetry_sdk_language",
                                        "key": "telemetry_sdk_language",
                                    },
                                    {"type": "string", "assign_to": "telemetry_sdk_name", "key": "telemetry_sdk_name"},
                                    {
                                        "type": "string",
                                        "assign_to": "telemetry_sdk_version",
                                        "key": "telemetry_sdk_version",
                                    },
                                    {"type": "string", "assign_to": "peer_service", "key": "peer_service"},
                                    {"type": "string", "assign_to": "http_server_name", "key": "http_server_name"},
                                    {"type": "string", "assign_to": "http_method", "key": "http_method"},
                                    {"type": "string", "assign_to": "http_scheme", "key": "http_scheme"},
                                    {"type": "string", "assign_to": "http_flavor", "key": "http_flavor"},
                                    {"type": "string", "assign_to": "http_status_code", "key": "http_status_code"},
                                    {"type": "string", "assign_to": "rpc_method", "key": "rpc_method"},
                                    {"type": "string", "assign_to": "rpc_service", "key": "rpc_service"},
                                    {"type": "string", "assign_to": "rpc_system", "key": "rpc_system"},
                                    {
                                        "type": "string",
                                        "assign_to": "rpc_grpc_status_code",
                                        "key": "rpc_grpc_status_code",
                                    },
                                    {"type": "string", "assign_to": "db_name", "key": "db_name"},
                                    {"type": "string", "assign_to": "db_operation", "key": "db_operation"},
                                    {"type": "string", "assign_to": "db_system", "key": "db_system"},
                                    {"type": "string", "assign_to": "messaging_system", "key": "messaging_system"},
                                    {
                                        "type": "string",
                                        "assign_to": "messaging_destination",
                                        "key": "messaging_destination",
                                    },
                                    {
                                        "type": "string",
                                        "assign_to": "messaging_destination_kind",
                                        "key": "messaging_destination_kind",
                                    },
                                    {"type": "string", "assign_to": "celery_action", "key": "celery_action"},
                                    {"type": "string", "assign_to": "celery_task_name", "key": "celery_task_name"},
                                ],
                                "next": None,
                            },
                        },
                    ],
                },
            },
        },
    },
    "conf": {
        "time_format": "Unix Time Stamp(milliseconds)",
        "timezone": 8,
        "time_field_name": "time",
        "output_field_name": "timestamp",
        "timestamp_len": 13,
        "encoding": "UTF-8",
    },
}


class EsTraceQueryMode:
    """
    trace查询模式
    减少查询返回数据量
    """

    ALL = "all"
    TRACE_INFO = "trace_info"

    @classmethod
    def choices(cls):
        return [(cls.ALL, _("全量查询")), (cls.TRACE_INFO, _("trace信息查询"))]


class KindCategory:
    """类型大类"""

    ASYNC = "async"
    SYNC = "sync"
    INTERNAL = "interval"
    UNSPECIFIED = "unspecified"

    KIND_MAPPING = {
        SpanKind.SPAN_KIND_UNSPECIFIED: UNSPECIFIED,
        SpanKind.SPAN_KIND_INTERNAL: INTERNAL,
        SpanKind.SPAN_KIND_SERVER: SYNC,
        SpanKind.SPAN_KIND_CLIENT: SYNC,
        SpanKind.SPAN_KIND_PRODUCER: ASYNC,
        SpanKind.SPAN_KIND_CONSUMER: ASYNC,
    }

    @classmethod
    def choices(cls):
        return [(cls.ASYNC, _("异步")), (cls.SYNC, _("同步")), (cls.INTERNAL, _("内部")), (cls.UNSPECIFIED, _("未指定"))]

    @classmethod
    def get_category(cls, kind):
        return cls.KIND_MAPPING[kind]


# 默认APM热数据存储天数系数
DEFAULT_APM_ES_WARM_RETENTION_RATIO = 0.3

DEFAULT_PLATFORM_LICENSE_CONFIG = {
    "enabled": False,
    # license证书过期时间2099-12-31 00:00:00
    "expire_time": 4102329600,
    "number_nodes": 1000000,
    "tolerable_expire": "1h",
    "tolerable_num_ratio": 1.0,
}

DEFAULT_APM_ATTRIBUTE_CONFIG = {"name": "attribute_filter/common"}


DEFAULT_APM_APPLICATION_ATTRIBUTE_CONFIG = {"name": "attribute_filter/app"}


DEFAULT_APM_APPLICATION_DB_SLOW_COMMAND_CONFIG = {"name": "db_filter/common"}

DEFAULT_PLATFORM_API_NAME_CONFIG = {
    "assemble": [
        {
            "destination": "api_name",
            "predicate_key": "attributes.http.scheme",
            "default_from": "span_name",
            "rules": [
                {
                    "kind": "SPAN_KIND_CLIENT",
                    "separator": ":",
                    "placeholder": "Unknown",
                    "keys": ["attributes.http.method", "attributes.http.host", "attributes.http.target"],
                },
                {
                    "kind": "SPAN_KIND_SERVER",
                    "separator": ":",
                    "placeholder": "Unknown",
                    "keys": [
                        "attributes.http.method",
                        "attributes.http.route",
                    ],
                },
            ],
        },
        {
            "destination": "api_name",
            "predicate_key": "attributes.rpc.system",
            "default_from": "span_name",
            "rules": [
                {
                    "kind": "",
                    "separator": ":",
                    "placeholder": "Unknown",
                    "keys": [
                        "attributes.rpc.method",
                    ],
                }
            ],
        },
        {
            "destination": "api_name",
            "predicate_key": "attributes.db.system",
            "default_from": "span_name",
            "rules": [
                {
                    "kind": "",
                    "separator": ":",
                    "placeholder": "Unknown",
                    "first_upper": ["attributes.db.system"],
                    "keys": [
                        "attributes.db.system",
                        "attributes.db.operation",
                        "attributes.db.name",
                    ],
                }
            ],
        },
        {
            "destination": "api_name",
            "predicate_key": "attributes.messaging.system",
            "default_from": "span_name",
            "rules": [
                {
                    "kind": "SPAN_KIND_PRODUCER",
                    "separator": ":",
                    "placeholder": "Unknown",
                    "first_upper": ["attributes.messaging.system"],
                    "keys": [
                        "attributes.messaging.system",
                        "const.producer",
                        "attributes.topic",
                    ],
                },
                {
                    "kind": "SPAN_KIND_CONSUMER",
                    "separator": ":",
                    "placeholder": "Unknown",
                    "first_upper": ["attributes.messaging.system"],
                    "keys": [
                        "attributes.messaging.system",
                        "const.consumer",
                        "attributes.topic",
                    ],
                },
            ],
        },
    ],
}

DEFAULT_APM_PLATFORM_AS_INT_CONFIG = {"as_int": ["attributes.http.status_code"]}


class ConfigTypes:
    """
    可以配置的类型
    """

    QUEUE_METRIC_BATCH_SIZE = "metrics_batch_size"
    QUEUE_TRACES_BATCH_SIZE = "traces_batch_size"
    QUEUE_LOGS_BATCH_SIZE = "logs_batch_size"
    DB_SLOW_COMMAND_CONFIG = "db_slow_command_config"
    DB_CONFIG = "db_config"

    @classmethod
    def choices(cls):
        return [
            (cls.QUEUE_METRIC_BATCH_SIZE, _("每批Metric发送大小")),
            (cls.QUEUE_TRACES_BATCH_SIZE, _("每批Trace发送大小")),
            (cls.QUEUE_LOGS_BATCH_SIZE, _("每批Log发送大小")),
            (cls.DB_SLOW_COMMAND_CONFIG, _("db慢命令配置")),
            (cls.DB_CONFIG, _("db配置")),
        ]


PLATFORM_METRIC_DIMENSION_FILED = [
    "attributes.net.peer.name",
    "attributes.api_name",
    "attributes.db.is_slow",
    "attributes.net.host.ip",
]

APM_TOPO_INSTANCE = "BKMONITOR_{}_{}_APM_TOPO_INSTANCE_HEARTBEAT_{}_{}"

DEFAULT_TOPO_INSTANCE_EXPIRE = 7 * 24 * 60 * 60


class ProfileApiType:
    """Profile查询api_type参数枚举值"""

    # service_name查询
    SERVICE_NAME = "service_name"

    # sampler查询
    SAMPLE = "query_sample_by_json"

    # type查询
    COL_TYPE = "col_type"


class ProfileQueryType:
    """Profile查询中api_params.type参数枚举值"""

    # cpu查询
    CPU = "cpu"
