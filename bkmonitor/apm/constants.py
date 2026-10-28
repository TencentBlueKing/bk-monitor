"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.conf import settings
from django.db.models import TextChoices
from django.utils.translation import gettext as _

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
APM_GLOBAL_CONFIG_KEY = "APM_GLOBAL"
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
        return [
            (cls.ASYNC, _("异步")),
            (cls.SYNC, _("同步")),
            (cls.INTERNAL, _("内部")),
            (cls.UNSPECIFIED, _("未指定")),
        ]

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

DEFAULT_APM_APPLICATION_LOGS_ATTRIBUTE_CONFIG = {"name": "attribute_filter/logs"}

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

DEFAULT_APM_PLATFORM_ATTRIBUTE_CONFIG = {
    "as_int": ["attributes.http.status_code"],
    "as_string": [
        "attributes.trpc.status_type",
        "attributes.trpc.status_code",
    ],
}


class ConfigTypes:
    """
    可以配置的类型
    """

    QUEUE_METRIC_BATCH_SIZE = "metrics_batch_size"
    QUEUE_TRACES_BATCH_SIZE = "traces_batch_size"
    QUEUE_LOGS_BATCH_SIZE = "logs_batch_size"
    QUEUE_PROFILES_BATCH_SIZE = "profiles_batch_size"

    DB_SLOW_COMMAND_CONFIG = "db_slow_command_config"
    DB_CONFIG = "db_config"
    DROP_FIELDS_CONFIG = "drop_fields_config"
    ATTRIBUTES_CONFIG_LOGS = "attributes_config_logs"
    CODE_RELABEL_CONFIG = "code_relabel_config"

    ALL_APP_CONFIG = "all_app_config"
    ALL_SERVICE_CONFIG = "all_service_config"
    ALL_INSTANCE_CONFIG = "all_instance_config"

    @classmethod
    def choices(cls):
        return [
            (cls.QUEUE_METRIC_BATCH_SIZE, _("每批Metric发送大小")),
            (cls.QUEUE_TRACES_BATCH_SIZE, _("每批Trace发送大小")),
            (cls.QUEUE_LOGS_BATCH_SIZE, _("每批Log发送大小")),
            (cls.QUEUE_PROFILES_BATCH_SIZE, _("每批Profile发送大小")),
            (cls.DB_SLOW_COMMAND_CONFIG, _("db慢命令配置")),
            (cls.DB_CONFIG, _("db配置")),
            (cls.DROP_FIELDS_CONFIG, _("后台 drop 字段配置")),
            (cls.ATTRIBUTES_CONFIG_LOGS, _("attributes 配置(logs)")),
            (cls.CODE_RELABEL_CONFIG, _("返回码重定义配置")),
            (cls.ALL_APP_CONFIG, _("app全量配置")),
            (cls.ALL_SERVICE_CONFIG, _("service全量配置")),
            (cls.ALL_INSTANCE_CONFIG, _("instance全量配置")),
        ]


PLATFORM_METRIC_DIMENSION_FILED = [
    "attributes.net.peer.name",
    "attributes.api_name",
    "attributes.db.is_slow",
    "attributes.net.host.ip",
]


class ApmCacheType:
    """APM 缓存类型枚举"""

    TOPO_INSTANCE = "topo_instance"
    ENDPOINT = "endpoint"
    HOST = "host"
    ROOT_ENDPOINT = "root_endpoint"
    RELATION = "relation"
    REMOTE_SERVICE_RELATION = "remote_service_relation"


class ApmCacheConfig:
    """
    APM 缓存配置容器
    统一管理所有 APM 相关的缓存配置，包括 key 模板和过期时间
    """

    # 缓存 key 模板
    _KEY_TEMPLATES = {
        ApmCacheType.TOPO_INSTANCE: "BKMONITOR_{}_{}_APM_TOPO_INSTANCE_HEARTBEAT_{}_{}",
        ApmCacheType.ENDPOINT: "BKMONITOR_{}_{}_APM_ENDPOINT_HEARTBEAT_{}_{}",
        ApmCacheType.HOST: "BKMONITOR_{}_{}_APM_HOST_HEARTBEAT_{}_{}",
        ApmCacheType.ROOT_ENDPOINT: "BKMONITOR_{}_{}_APM_ROOT_ENDPOINT_HEARTBEAT_{}_{}",
        ApmCacheType.RELATION: "BKMONITOR_{}_{}_APM_RELATION_HEARTBEAT_{}_{}",
        ApmCacheType.REMOTE_SERVICE_RELATION: "BKMONITOR_{}_{}_APM_REMOTE_SERVICE_RELATION_HEARTBEAT_{}_{}",
    }

    # 缓存过期时间（秒）
    _EXPIRE_TIMES = {
        ApmCacheType.TOPO_INSTANCE: 7 * 24 * 60 * 60,  # 7天
        ApmCacheType.ENDPOINT: 7 * 24 * 60 * 60,  # 7天
        ApmCacheType.HOST: 7 * 24 * 60 * 60,  # 7天
        ApmCacheType.ROOT_ENDPOINT: 7 * 24 * 60 * 60,  # 7天
        ApmCacheType.RELATION: 7 * 24 * 60 * 60,  # 7天
        ApmCacheType.REMOTE_SERVICE_RELATION: 7 * 24 * 60 * 60,  # 7天
    }

    @classmethod
    def get_key_template(cls, cache_type: str) -> str:
        """
        获取缓存 key 模板
        :param cache_type: 缓存类型
        :return: key 模板
        """
        if cache_type not in cls._KEY_TEMPLATES:
            raise ValueError(f"Unknown cache type: {cache_type}")
        return cls._KEY_TEMPLATES[cache_type]

    @classmethod
    def get_expire_time(cls, cache_type: str) -> int:
        """
        获取缓存过期时间
        :param cache_type: 缓存类型
        :return: 过期时间（秒）
        """
        if cache_type not in cls._EXPIRE_TIMES:
            raise ValueError(f"Unknown cache type: {cache_type}")
        return cls._EXPIRE_TIMES[cache_type]


class ProfileApiType:
    """Profile查询api_type参数枚举值"""

    # service_name查询
    SERVICE_NAME = "service_name"

    # sampler查询
    SAMPLE = "query_sample_by_json"

    # type查询
    COL_TYPE = "col_type"

    # 复杂查询
    AGGREGATE = "select_aggregate"


class ProfileQueryType:
    """Profile查询中api_params.type参数枚举值"""

    # cpu查询
    CPU = "cpu"


# 主动 Profiling 执行状态；outdate 不落库，查询时由成功类终态按 Profiling 保留期派生
ACTIVE_PROFILING_STATUSES = (
    "running",
    "succeed",
    "partial_succeed",
    "failed",
    "timeout",
    "cancelled",
    "unknown",
    "outdate",
)
ACTIVE_PROFILING_SUCCEED_STATUSES = ("succeed", "partial_succeed")
# 成功类主机执行结束后 Profiling 数据还要解析入库，这段时间内主机行显示为 parsing；
# parsing 只是主机行的展示状态，不落库、不参与执行汇总，也不提供筛选
ACTIVE_PROFILING_PARSING_MS = 30 * 1000
# 搜索框候选字段与前端协议同名，target 对应主机执行时 IP；process_names 按进程名去重，
# process_pids 显示与取值都是 进程名:PID，点选后按同一进程的进程名与 PID 精确筛选
ACTIVE_PROFILING_TOPK_FIELDS = (
    "target",
    "task_name",
    "collection_method",
    "collection_type",
    "schedule_type",
    "process_names",
    "process_pids",
)
# 进程候选按最近出现排序，只读最近的这么多行主机执行，全量分组计数的开销随主机执行数增长
ACTIVE_PROFILING_PROCESS_TOPK_RECENT_ROWS = 1000

# 计划的部署状态；outdate 不落库，计划时间已过时列表展示为 outdate，过期停用成功后才写入
ACTIVE_PROFILING_DEPLOYMENT_DEPLOYING = "deploying"
ACTIVE_PROFILING_DEPLOYMENT_SUCCESS = "success"
ACTIVE_PROFILING_DEPLOYMENT_FAILED = "failed"
ACTIVE_PROFILING_DEPLOYMENT_EXPIRED = "outdate"
ACTIVE_PROFILING_TASK_STATUS_BY_ENABLED = {True: "enabled", False: "disabled"}
# 计划最后一次执行过去 1 天后才停用并移除主机上的子配置，执行时离线的主机上线后仍能收到配置、上报配置晚到的失败
ACTIVE_PROFILING_EXPIRED_TASK_STOP_DELAY_MS = 24 * 3600 * 1000

# 子配置模板随 bkmonitorbeat 插件包发布，context 结构由模板约定
ACTIVE_PROFILING_SUBSCRIPTION_STEP_ID = "bkmonitorbeat_active_profile"
ACTIVE_PROFILING_CONFIG_TEMPLATE_NAME = "bkmonitorbeat_active_profile.conf"
# TODO: 测试包写死 0.0.5，正式发布前改回 latest
ACTIVE_PROFILING_PLUGIN_VERSION = "0.0.5"
ACTIVE_PROFILING_PROFILE_SERVICE_NAME = "active_allocation"

ACTIVE_PROFILING_BEAT_RELATIVE_PATH = "plugins/bin/bkmonitorbeat"
ACTIVE_PROFILING_BEAT_MAIN_CONF_RELATIVE_PATH = "plugins/etc/bkmonitorbeat.conf"
# 运行目录由主配置的 path.data 推导，取消命令靠它定位采集进程，因此必须显式传 -c
ACTIVE_PROFILING_IMMEDIATE_SCRIPT = 'echo "$1" | base64 -d | {beat_path} -c {main_conf} -active-profile-run\n'
ACTIVE_PROFILING_CANCEL_SCRIPT = 'echo "$1" | base64 -d | {beat_path} -c {main_conf} -active-profile-cancel\n'

# 作业平台没有执行成功由 SaaS 归类，其余 error_type 由采集端上报
ACTIVE_PROFILING_ERROR_TYPE_DISPATCH_FAILED = "dispatch_failed"
# 只有 started 的主机执行超过“采集时长 + 300 秒”仍没有 finished，视为 unknown
ACTIVE_PROFILING_UNKNOWN_GRACE_SEC = 300

# 查询默认读 MySQL 执行表，es 保留一期按 Event 聚合的查询能力
ACTIVE_PROFILING_QUERY_SOURCES = ("mysql", "es")
ACTIVE_PROFILING_STARTED_EVENT = "active_profiling_started"
ACTIVE_PROFILING_FINISHED_EVENT = "active_profiling_finished"
# SaaS 先按 5 分钟封顶，采集器另有自身上限
ACTIVE_PROFILING_COLLECTOR_MAX_DURATION_SEC = 300
# 开始后超过采集时长上限 + 300 秒仍无 finished 即为 unknown，running 行和 finished 事件都落在这个窗口内
ACTIVE_PROFILING_RUNNING_WINDOW_MS = (
    ACTIVE_PROFILING_COLLECTOR_MAX_DURATION_SEC + ACTIVE_PROFILING_UNKNOWN_GRACE_SEC
) * 1000
# unify-query 单次最多返回 1 万条，ES 的 from + size 默认也不能超过 1 万
ACTIVE_PROFILING_ES_QUERY_BATCH_SIZE = 200
ACTIVE_PROFILING_ES_QUERY_MAX_SIZE = 10000
# 一次执行可能覆盖很多主机，任务历史每批多读一些，减少续读请求
ACTIVE_PROFILING_ES_EXECUTION_BATCH_SIZE = 500


class ApmBmwTaskStatus:
    """APM 预计算任务状态"""

    # 正常运行
    RUNNING = "running"
    # 未开启
    UNOPENED = "unopened"


class DiscoverRuleType(TextChoices):
    """拓扑发现规则类型"""

    CATEGORY = "category", _("分类规则")
    SYSTEM = "system", _("系统类型规则")
    PLATFORM = "platform", _("平台规则")
    SDK = "sdk", _("SDK 规则")


class QueryMode:
    """查询视角 Trace/Span"""

    TRACE = "trace"
    SPAN = "span"

    @classmethod
    def choices(cls):
        return [
            (cls.TRACE, "Trace视角"),
            (cls.SPAN, "span视角"),
        ]
