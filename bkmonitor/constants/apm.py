import base64
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache, cache
from typing import Any

from django.db.models import TextChoices
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.utils.translation import gettext_lazy as _lazy
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.semconv.trace import SpanAttributes

from constants.result_table import ResultTableField


FIVE_MIN_SECONDS = 5 * 60


class TraceDataSourceConfig:
    """Trace数据源配置常量"""

    ES_KEYWORD_OPTION = {"es_type": "keyword"}

    # object 字段配置
    ES_OBJECT_OPTION = {"es_type": "object", "es_dynamic": True}

    # NESTED 配置
    ES_NESTED_OPTION = {"es_type": "nested"}

    # OTLP events 配置
    TRACE_EVENT_OPTION = {
        **ES_NESTED_OPTION,
        "es_properties": {
            "attributes": {
                "properties": {
                    "exception": {"properties": {"message": {"type": "text"}, "stacktrace": {"type": "text"}}},
                    "message": {"type": "object"},
                }
            },
            "timestamp": {"type": "long"},
        },
    }

    # OTLP status 配置
    TRACE_STATUS_OPTION = {
        **ES_OBJECT_OPTION,
        "es_properties": {"message": {"type": "text"}, "code": {"type": "integer"}},
    }

    TRACE_FIELD_LIST = [
        {
            "field_name": "attributes",
            "field_type": ResultTableField.FIELD_TYPE_OBJECT,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": ES_OBJECT_OPTION,
            "is_config_by_user": True,
            "description": "Span Attributes",
        },
        {
            "field_name": "resource",
            "field_type": ResultTableField.FIELD_TYPE_OBJECT,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": ES_OBJECT_OPTION,
            "is_config_by_user": True,
            "description": "Span Resources",
        },
        {
            "field_name": "events",
            "field_type": ResultTableField.FIELD_TYPE_NESTED,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": TRACE_EVENT_OPTION,
            "is_config_by_user": True,
            "description": "Span Events",
        },
        {
            "field_name": "elapsed_time",
            "field_type": ResultTableField.FIELD_TYPE_LONG,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "long"},
            "is_config_by_user": True,
            "description": "Span Elapsed Time",
        },
        {
            "field_name": "end_time",
            "field_type": ResultTableField.FIELD_TYPE_LONG,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "long"},
            "is_config_by_user": True,
            "description": "Span End Time",
        },
        {
            "field_name": "start_time",
            "field_type": ResultTableField.FIELD_TYPE_LONG,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "long"},
            "is_config_by_user": True,
            "description": "Span Start Time",
        },
        {
            "field_name": "kind",
            "field_type": ResultTableField.FIELD_TYPE_INT,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "integer"},
            "is_config_by_user": True,
            "description": "Span Kind",
        },
        {
            "field_name": "links",
            "field_type": ResultTableField.FIELD_TYPE_NESTED,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": ES_NESTED_OPTION,
            "is_config_by_user": True,
            "description": "Span Links",
        },
        {
            "field_name": "parent_span_id",
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": ES_KEYWORD_OPTION,
            "is_config_by_user": True,
            "description": "Parent Span ID",
        },
        {
            "field_name": "span_id",
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": ES_KEYWORD_OPTION,
            "is_config_by_user": True,
            "description": "Span ID",
        },
        {
            "field_name": "span_name",
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": ES_KEYWORD_OPTION,
            "is_config_by_user": True,
            "description": "Span Name",
        },
        {
            "field_name": "status",
            "field_type": ResultTableField.FIELD_TYPE_OBJECT,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": TRACE_STATUS_OPTION,
            "is_config_by_user": True,
            "description": "Span Status",
        },
        {
            "field_name": "trace_id",
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": ES_KEYWORD_OPTION,
            "is_config_by_user": True,
            "description": "Trace ID",
        },
        {
            "field_name": "trace_state",
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": ES_KEYWORD_OPTION,
            "is_config_by_user": True,
            "description": "Trace State",
        },
    ]


class SpanKind:
    SPAN_KIND_UNSPECIFIED = 0
    SPAN_KIND_INTERNAL = 1
    SPAN_KIND_SERVER = 2
    SPAN_KIND_CLIENT = 3
    SPAN_KIND_PRODUCER = 4
    SPAN_KIND_CONSUMER = 5

    @classmethod
    def get_label_by_key(cls, key):
        return {
            cls.SPAN_KIND_UNSPECIFIED: "未指定(unspecified)",
            cls.SPAN_KIND_INTERNAL: "内部(internal)",
            cls.SPAN_KIND_SERVER: _("被调"),
            cls.SPAN_KIND_CLIENT: _("主调"),
            cls.SPAN_KIND_PRODUCER: _("异步主调"),
            cls.SPAN_KIND_CONSUMER: _("异步被调"),
        }.get(key, key)

    @classmethod
    def list(cls):
        return [
            {"value": cls.SPAN_KIND_UNSPECIFIED, "text": cls.get_label_by_key(cls.SPAN_KIND_UNSPECIFIED)},
            {"value": cls.SPAN_KIND_INTERNAL, "text": cls.get_label_by_key(cls.SPAN_KIND_INTERNAL)},
            {"value": cls.SPAN_KIND_SERVER, "text": cls.get_label_by_key(cls.SPAN_KIND_SERVER)},
            {"value": cls.SPAN_KIND_CLIENT, "text": cls.get_label_by_key(cls.SPAN_KIND_CLIENT)},
            {"value": cls.SPAN_KIND_PRODUCER, "text": cls.get_label_by_key(cls.SPAN_KIND_PRODUCER)},
            {"value": cls.SPAN_KIND_CONSUMER, "text": cls.get_label_by_key(cls.SPAN_KIND_CONSUMER)},
        ]

    @classmethod
    def called_kinds(cls):
        """被调类型"""
        return [cls.SPAN_KIND_SERVER, cls.SPAN_KIND_CONSUMER]

    @classmethod
    def calling_kinds(cls):
        """主调类型"""
        return [cls.SPAN_KIND_CLIENT, cls.SPAN_KIND_PRODUCER]

    @classmethod
    def async_kinds(cls):
        """异步类型"""
        return [cls.SPAN_KIND_CONSUMER, cls.SPAN_KIND_PRODUCER]


class OtlpKey:
    ELAPSED_TIME = "elapsed_time"
    LINKS = "links"
    EVENTS = "events"
    START_TIME = "start_time"
    END_TIME = "end_time"
    PARENT_SPAN_ID = "parent_span_id"
    TRACE_ID = "trace_id"
    TRACE_STATE = "trace_state"
    SPAN_ID = "span_id"
    ATTRIBUTES = "attributes"
    SPAN_NAME = "span_name"
    KIND = "kind"
    STATUS = "status"
    STATUS_CODE = "status.code"
    STATUS_MESSAGE = "status.message"
    RESOURCE = "resource"
    BK_INSTANCE_ID = "bk.instance.id"
    UNKNOWN_SERVICE = "unknown.service"
    UNKNOWN_COMPONENT = "unknown.service-component"

    # apdex_type自身维度
    APDEX_TYPE = "apdex_type"

    @classmethod
    def get_resource_key(cls, key: str) -> str:
        return f"{cls.RESOURCE}.{key}"

    @classmethod
    def get_attributes_key(cls, key: str) -> str:
        return f"{cls.ATTRIBUTES}.{key}"

    @classmethod
    def get_metric_dimension_key(cls, key: str):
        if key.startswith(cls.ATTRIBUTES):
            key = key.replace(f"{cls.ATTRIBUTES}.", "")
        if key.startswith(cls.RESOURCE):
            key = key.replace(f"{cls.RESOURCE}.", "")
        return key.replace(".", "_")


# ==============================================================================
# Span标准字段枚举
# ==============================================================================
class ValueSource:
    """数据来源"""

    METHOD = "method"
    TRACE = "trace"
    METRIC = "metric"


class StandardFieldCategory:
    BASE = "base"
    HTTP = "http"
    RPC = "rpc"
    DB = "db"
    MESSAGING = "messaging"
    ASYNC_BACKEND = "async_backend"

    OTHER = "other"

    @classmethod
    def get_label_by_key(cls, key: str):
        return {
            cls.BASE: _("基础信息"),
            cls.HTTP: _("网页"),
            cls.RPC: _("远程调用"),
            cls.DB: _("数据库"),
            cls.MESSAGING: _("消息队列"),
            cls.ASYNC_BACKEND: _("后台任务"),
            cls.OTHER: _("其他"),
        }.get(key, key)


@dataclass
class StandardField:
    source: str
    key: str
    value: str
    display_level: str
    category: str
    value_source: str
    is_hidden: bool = False

    @property
    def field(self) -> str:
        return [f"{self.source}.{self.key}", self.source][self.source == self.key]

    @property
    def metric_dimension(self) -> str:
        return OtlpKey.get_metric_dimension_key(self.field)


class StandardFieldDisplayLevel:
    """标准字段显示层级"""

    BASE = "base"
    ADVANCES = "advances"

    @classmethod
    def get_label_by_key(cls, key):
        return {
            cls.BASE: _("基础信息"),
            cls.ADVANCES: _("高级(Advances)"),
        }.get(key, key)


class SpanStandardField:
    """
    常见的Span标准字段
    会影响:
    1. 预计算中存储的collections的数据
    2. Trace检索侧边栏查询条件
    """

    COMMON_STANDARD_FIELDS = [
        StandardField(
            OtlpKey.ATTRIBUTES,
            SpanAttributes.HTTP_HOST,
            "HTTP Host",
            StandardFieldDisplayLevel.ADVANCES,
            StandardFieldCategory.HTTP,
            ValueSource.TRACE,
        ),
        StandardField(
            OtlpKey.ATTRIBUTES,
            SpanAttributes.HTTP_URL,
            "HTTP URL",
            StandardFieldDisplayLevel.ADVANCES,
            StandardFieldCategory.HTTP,
            ValueSource.TRACE,
        ),
        StandardField(
            OtlpKey.ATTRIBUTES,
            "server.address",
            _("服务地址"),
            StandardFieldDisplayLevel.ADVANCES,
            StandardFieldCategory.HTTP,
            ValueSource.TRACE,
        ),
        StandardField(
            OtlpKey.ATTRIBUTES,
            SpanAttributes.HTTP_SCHEME,
            _("HTTP协议"),
            StandardFieldDisplayLevel.ADVANCES,
            StandardFieldCategory.HTTP,
            ValueSource.METRIC,
        ),
        StandardField(
            OtlpKey.ATTRIBUTES,
            SpanAttributes.HTTP_FLAVOR,
            _("HTTP服务名称"),
            StandardFieldDisplayLevel.ADVANCES,
            StandardFieldCategory.HTTP,
            ValueSource.METRIC,
        ),
        StandardField(
            OtlpKey.ATTRIBUTES,
            SpanAttributes.HTTP_METHOD,
            _("HTTP方法"),
            StandardFieldDisplayLevel.ADVANCES,
            StandardFieldCategory.HTTP,
            ValueSource.METRIC,
        ),
        StandardField(
            OtlpKey.ATTRIBUTES,
            SpanAttributes.HTTP_STATUS_CODE,
            _("HTTP状态码"),
            StandardFieldDisplayLevel.ADVANCES,
            StandardFieldCategory.HTTP,
            ValueSource.METRIC,
        ),
        StandardField(
            OtlpKey.ATTRIBUTES,
            SpanAttributes.RPC_METHOD,
            _("RPC方法"),
            StandardFieldDisplayLevel.ADVANCES,
            StandardFieldCategory.RPC,
            ValueSource.TRACE,
        ),
        StandardField(
            OtlpKey.ATTRIBUTES,
            SpanAttributes.RPC_SERVICE,
            _("RPC服务"),
            StandardFieldDisplayLevel.ADVANCES,
            StandardFieldCategory.RPC,
            ValueSource.TRACE,
        ),
        StandardField(
            OtlpKey.ATTRIBUTES,
            SpanAttributes.RPC_SYSTEM,
            _("RPC系统名"),
            StandardFieldDisplayLevel.ADVANCES,
            StandardFieldCategory.RPC,
            ValueSource.TRACE,
        ),
        StandardField(
            OtlpKey.ATTRIBUTES,
            SpanAttributes.RPC_GRPC_STATUS_CODE,
            _("gRPC状态码"),
            StandardFieldDisplayLevel.ADVANCES,
            StandardFieldCategory.RPC,
            ValueSource.TRACE,
        ),
        StandardField(
            OtlpKey.ATTRIBUTES,
            SpanAttributes.DB_NAME,
            _("数据库名称"),
            StandardFieldDisplayLevel.ADVANCES,
            StandardFieldCategory.DB,
            ValueSource.METRIC,
        ),
        StandardField(
            OtlpKey.ATTRIBUTES,
            SpanAttributes.DB_OPERATION,
            _("数据库操作"),
            StandardFieldDisplayLevel.ADVANCES,
            StandardFieldCategory.DB,
            ValueSource.METRIC,
        ),
        StandardField(
            OtlpKey.ATTRIBUTES,
            SpanAttributes.DB_SYSTEM,
            _("数据库类型"),
            StandardFieldDisplayLevel.ADVANCES,
            StandardFieldCategory.DB,
            ValueSource.METRIC,
        ),
        StandardField(
            OtlpKey.ATTRIBUTES,
            SpanAttributes.DB_STATEMENT,
            _("数据库语句"),
            StandardFieldDisplayLevel.ADVANCES,
            StandardFieldCategory.DB,
            ValueSource.TRACE,
        ),
        StandardField(
            OtlpKey.ATTRIBUTES,
            "db.instance",
            _("数据库实例ID"),
            StandardFieldDisplayLevel.ADVANCES,
            StandardFieldCategory.DB,
            ValueSource.TRACE,
        ),
        StandardField(
            OtlpKey.ATTRIBUTES,
            SpanAttributes.MESSAGING_SYSTEM,
            _("消息系统"),
            StandardFieldDisplayLevel.ADVANCES,
            StandardFieldCategory.MESSAGING,
            ValueSource.TRACE,
        ),
        StandardField(
            OtlpKey.ATTRIBUTES,
            SpanAttributes.MESSAGING_DESTINATION,
            _("消息目的地"),
            StandardFieldDisplayLevel.ADVANCES,
            StandardFieldCategory.MESSAGING,
            ValueSource.TRACE,
        ),
        StandardField(
            OtlpKey.ATTRIBUTES,
            SpanAttributes.MESSAGING_DESTINATION_KIND,
            _("消息目的地类型"),
            StandardFieldDisplayLevel.ADVANCES,
            StandardFieldCategory.MESSAGING,
            ValueSource.TRACE,
        ),
        StandardField(
            OtlpKey.ATTRIBUTES,
            "celery.action",
            _("Celery操作名称"),
            StandardFieldDisplayLevel.ADVANCES,
            StandardFieldCategory.MESSAGING,
            ValueSource.TRACE,
        ),
        StandardField(
            OtlpKey.ATTRIBUTES,
            "celery.task_name",
            _("Celery任务名称"),
            StandardFieldDisplayLevel.ADVANCES,
            StandardFieldCategory.MESSAGING,
            ValueSource.TRACE,
        ),
        StandardField(
            OtlpKey.ATTRIBUTES,
            SpanAttributes.NET_PEER_NAME,
            _("远程服务器名称"),
            StandardFieldDisplayLevel.ADVANCES,
            StandardFieldCategory.HTTP,
            ValueSource.METRIC,
        ),
        StandardField(
            OtlpKey.ATTRIBUTES,
            SpanAttributes.PEER_SERVICE,
            _("远程服务名"),
            StandardFieldDisplayLevel.ADVANCES,
            StandardFieldCategory.HTTP,
            ValueSource.METRIC,
        ),
        StandardField(
            OtlpKey.RESOURCE,
            ResourceAttributes.SERVICE_NAME,
            _("服务名"),
            StandardFieldDisplayLevel.BASE,
            StandardFieldCategory.BASE,
            ValueSource.METRIC,
        ),
        StandardField(
            OtlpKey.RESOURCE,
            ResourceAttributes.SERVICE_VERSION,
            _("服务版本"),
            StandardFieldDisplayLevel.BASE,
            StandardFieldCategory.BASE,
            ValueSource.METRIC,
        ),
        StandardField(
            OtlpKey.RESOURCE,
            ResourceAttributes.TELEMETRY_SDK_LANGUAGE,
            _("SDK语言"),
            StandardFieldDisplayLevel.BASE,
            StandardFieldCategory.BASE,
            ValueSource.METRIC,
        ),
        StandardField(
            OtlpKey.RESOURCE,
            ResourceAttributes.TELEMETRY_SDK_NAME,
            _("SDK名称"),
            StandardFieldDisplayLevel.BASE,
            StandardFieldCategory.BASE,
            ValueSource.METRIC,
        ),
        StandardField(
            OtlpKey.RESOURCE,
            ResourceAttributes.TELEMETRY_SDK_VERSION,
            _("SDK版本"),
            StandardFieldDisplayLevel.BASE,
            StandardFieldCategory.BASE,
            ValueSource.METRIC,
        ),
        StandardField(
            OtlpKey.RESOURCE,
            ResourceAttributes.SERVICE_NAMESPACE,
            _("服务命名空间"),
            StandardFieldDisplayLevel.BASE,
            StandardFieldCategory.BASE,
            ValueSource.TRACE,
        ),
        StandardField(
            OtlpKey.RESOURCE,
            ResourceAttributes.SERVICE_INSTANCE_ID,
            _("服务实例ID"),
            StandardFieldDisplayLevel.BASE,
            StandardFieldCategory.BASE,
            ValueSource.TRACE,
        ),
        StandardField(
            OtlpKey.RESOURCE,
            "net.host.ip",
            _("主机IP(net.host.ip)"),
            StandardFieldDisplayLevel.BASE,
            StandardFieldCategory.BASE,
            ValueSource.TRACE,
        ),
        StandardField(
            OtlpKey.RESOURCE,
            "host.ip",
            _("主机IP(host.ip)"),
            StandardFieldDisplayLevel.BASE,
            StandardFieldCategory.BASE,
            ValueSource.TRACE,
        ),
        StandardField(
            OtlpKey.RESOURCE,
            "k8s.bcs.cluster.id",
            _("K8S BCS 集群 ID"),
            StandardFieldDisplayLevel.BASE,
            StandardFieldCategory.BASE,
            ValueSource.TRACE,
        ),
        StandardField(
            OtlpKey.RESOURCE,
            "k8s.namespace.name",
            _("K8S 命名空间"),
            StandardFieldDisplayLevel.BASE,
            StandardFieldCategory.BASE,
            ValueSource.TRACE,
        ),
        StandardField(
            OtlpKey.RESOURCE,
            "k8s.pod.ip",
            _("K8S Pod Ip"),
            StandardFieldDisplayLevel.BASE,
            StandardFieldCategory.BASE,
            ValueSource.TRACE,
        ),
        StandardField(
            OtlpKey.RESOURCE,
            "k8s.pod.name",
            _("K8S Pod 名称"),
            StandardFieldDisplayLevel.BASE,
            StandardFieldCategory.BASE,
            ValueSource.TRACE,
        ),
        StandardField(
            OtlpKey.RESOURCE,
            "net.host.port",
            _("主机端口"),
            StandardFieldDisplayLevel.BASE,
            StandardFieldCategory.BASE,
            ValueSource.TRACE,
        ),
        StandardField(
            OtlpKey.RESOURCE,
            "net.host.name",
            _("主机名称"),
            StandardFieldDisplayLevel.BASE,
            StandardFieldCategory.BASE,
            ValueSource.TRACE,
        ),
        StandardField(
            OtlpKey.RESOURCE,
            "bk.instance.id",
            _("实例"),
            StandardFieldDisplayLevel.BASE,
            StandardFieldCategory.BASE,
            ValueSource.METRIC,
        ),
        StandardField(
            OtlpKey.KIND,
            OtlpKey.KIND,
            _("类型"),
            StandardFieldDisplayLevel.BASE,
            StandardFieldCategory.BASE,
            ValueSource.METHOD,
        ),
        StandardField(
            OtlpKey.SPAN_NAME,
            OtlpKey.SPAN_NAME,
            _("接口名称"),
            StandardFieldDisplayLevel.BASE,
            StandardFieldCategory.BASE,
            ValueSource.TRACE,
        ),
        StandardField(
            OtlpKey.STATUS,
            "code",
            _("状态"),
            StandardFieldDisplayLevel.BASE,
            StandardFieldCategory.BASE,
            ValueSource.METHOD,
            is_hidden=True,
        ),
    ]

    @classmethod
    def standard_fields(cls) -> list[str]:
        """获取标准字段"""
        return [field_info.field for field_info in cls.COMMON_STANDARD_FIELDS if not field_info.is_hidden]

    @classmethod
    def list_standard_fields(cls):
        """按照层级获取标准字段"""
        base_fields = []
        advances_fields = []

        for i in cls.COMMON_STANDARD_FIELDS:
            if i.is_hidden:
                continue

            if i.display_level == StandardFieldDisplayLevel.BASE:
                base_fields.append({"name": i.value, "id": i.field})
            else:
                advances_fields.append({"name": i.value, "id": i.field, "category": i.category})

        res = []
        for i in base_fields:
            res.append({"id": i["id"], "name": i["name"], "children": []})

        child_mapping = {}

        for i in advances_fields:
            child_mapping.setdefault(i["category"], []).append({"id": i["id"], "name": i["name"], "children": []})

        advances_child = []
        for category, items in child_mapping.items():
            advances_child.append(
                {"id": category, "name": StandardFieldCategory.get_label_by_key(category), "children": items}
            )

        res.append(
            {
                "id": StandardFieldDisplayLevel.ADVANCES,
                "name": StandardFieldDisplayLevel.get_label_by_key(StandardFieldDisplayLevel.ADVANCES),
                "children": advances_child,
            }
        )

        return res

    @classmethod
    def flat_list(cls):
        """获取打平的标准字段列表"""

        res = []
        # 基础字段放在前面 高级字段放在后面
        base_fields = [
            i
            for i in cls.COMMON_STANDARD_FIELDS
            if i.display_level == StandardFieldDisplayLevel.BASE and not i.is_hidden
        ]
        ad_fields = [
            i
            for i in cls.COMMON_STANDARD_FIELDS
            if i.display_level == StandardFieldDisplayLevel.ADVANCES and not i.is_hidden
        ]

        for item in base_fields + ad_fields:
            res.append({"name": f"{item.value}({item.field})", "key": item.field, "type": "string"})

        return res


class PreCalculateSpecificField(TextChoices):
    """
    预计算存储字段
    """

    # 下面字段的顺序调整，会影响页面展示，需尽可能把最常用的字段放最前面
    BK_TENANT_ID = "bk_tenant_id"
    BIZ_ID = "biz_id"
    BIZ_NAME = "biz_name"
    APP_ID = "app_id"
    APP_NAME = "app_name"
    TRACE_ID = "trace_id"
    TRACE_DURATION = "trace_duration"
    SERVICE_COUNT = "service_count"
    SPAN_COUNT = "span_count"
    HIERARCHY_COUNT = "hierarchy_count"
    ERROR = "error"
    ERROR_COUNT = "error_count"
    MIN_START_TIME = "min_start_time"
    MAX_END_TIME = "max_end_time"
    SPAN_MAX_DURATION = "span_max_duration"
    SPAN_MIN_DURATION = "span_min_duration"
    ROOT_SERVICE = "root_service"
    ROOT_SERVICE_SPAN_ID = "root_service_span_id"
    ROOT_SERVICE_SPAN_NAME = "root_service_span_name"
    ROOT_SERVICE_STATUS_CODE = "root_service_status_code"
    ROOT_SERVICE_CATEGORY = "root_service_category"
    ROOT_SERVICE_KIND = "root_service_kind"
    ROOT_SPAN_ID = "root_span_id"
    ROOT_SPAN_NAME = "root_span_name"
    ROOT_SPAN_SERVICE = "root_span_service"
    ROOT_SPAN_KIND = "root_span_kind"
    TIME = "time"
    CATEGORY_STATISTICS = "category_statistics"
    KIND_STATISTICS = "kind_statistics"
    COLLECTIONS = "collections"

    @classmethod
    def search_fields(cls):
        """获取可供搜索的字段"""
        return [v for v in cls.values if v not in cls.hidden_fields()]

    @classmethod
    def hidden_fields(cls):
        """获取隐藏字段"""
        return [cls.BK_TENANT_ID, cls.BIZ_ID, cls.BIZ_NAME, cls.APP_ID, cls.APP_NAME, cls.TIME, cls.COLLECTIONS]

    @classmethod
    def specific_fields(cls):
        """获取可供搜索的字段中预计算表特有的字段"""
        # span 表的顶层字段
        trace_top_fields = {field_dict["field_name"] for field_dict in TraceDataSourceConfig.TRACE_FIELD_LIST}
        return list(set(cls.search_fields()) - trace_top_fields)


class TraceListQueryMode:
    """trace检索查询模式"""

    ORIGIN = "origin"
    PRE_CALCULATION = "pre_calculation"

    @classmethod
    def choices(cls):
        return [
            (cls.ORIGIN, _("原始查询")),
            (cls.PRE_CALCULATION, _("预计算查询")),
        ]


class TraceWaterFallDisplayKey:
    """trace瀑布列表显示勾选项"""

    # 来源: OT
    SOURCE_CATEGORY_OPENTELEMETRY = "source_category_opentelemetry"
    # 来源: EBPF
    SOURCE_CATEGORY_EBPF = "source_category_ebpf"

    # 虚拟节点
    VIRTUAL_SPAN = "virtual_span"

    @classmethod
    def choices(cls):
        return [
            (cls.SOURCE_CATEGORY_OPENTELEMETRY, "OT"),
            (cls.SOURCE_CATEGORY_EBPF, "EBPF"),
            (cls.VIRTUAL_SPAN, _("虚拟节点")),
        ]


class SpanKindKey:
    """Span类型标识(用于collector处识别)"""

    UNSPECIFIED = "SPAN_KIND_UNSPECIFIED"
    INTERNAL = "SPAN_KIND_INTERNAL"
    SERVER = "SPAN_KIND_SERVER"
    CLIENT = "SPAN_KIND_CLIENT"
    PRODUCER = "SPAN_KIND_PRODUCER"
    CONSUMER = "SPAN_KIND_CONSUMER"


class TrpcAttributes:
    """for trpc"""

    TRPC_ENV_NAME = "trpc.envname"
    TRPC_NAMESPACE = "trpc.namespace"
    TRPC_CALLER_SERVICE = "trpc.caller_service"
    TRPC_CALLEE_SERVICE = "trpc.callee_service"
    TRPC_CALLER_METHOD = "trpc.caller_method"
    TRPC_CALLEE_METHOD = "trpc.callee_method"
    TRPC_STATUS_TYPE = "trpc.status_type"
    TRPC_STATUS_CODE = "trpc.status_code"


class TRPCMetricTag:
    # 通用
    REGION = "region"
    ENV_NAME = "env_name"
    NAMESPACE = "namespace"
    VERSION = "version"
    CANARY = "canary"
    USER_EXT1 = "user_ext1"
    USER_EXT2 = "user_ext2"
    USER_EXT3 = "user_ext3"
    CODE = "code"

    # 主调
    CALLER_SERVER: str = "caller_server"
    CALLER_SERVICE: str = "caller_service"
    CALLER_METHOD: str = "caller_method"
    CALLER_IP: str = "caller_ip"
    CALLER_CONTAINER: str = "caller_container"
    CALLER_CON_SETID: str = "caller_con_setid"
    CALLER_GROUP: str = "caller_group"

    # 被调
    CALLEE_SERVER: str = "callee_server"
    CALLEE_SERVICE: str = "callee_service"
    CALLEE_METHOD: str = "callee_method"
    CALLEE_IP: str = "callee_ip"
    CALLEE_CONTAINER: str = "callee_container"
    CALLEE_CON_SETID: str = "callee_con_setid"

    TARGET: str = "target"
    # 后续不同上报端都会使用该字段唯一标识一个 RPC 服务
    SERVICE_NAME: str = "service_name"
    # 特殊维度
    APP: str = "server"

    @classmethod
    def tags(cls) -> list[dict[str, str]]:
        return [
            {"value": cls.CALLER_SERVER, "text": _("主调服务")},
            {"value": cls.CALLER_SERVICE, "text": _("主调 Service")},
            {"value": cls.CALLER_METHOD, "text": _("主调接口")},
            {"value": cls.CALLER_IP, "text": _("主调 IP")},
            {"value": cls.CALLER_CONTAINER, "text": _("主调容器")},
            {"value": cls.CALLER_CON_SETID, "text": _("主调 SetID")},
            {"value": cls.CALLER_GROUP, "text": _("主调流量组")},
            {"value": cls.CALLEE_SERVER, "text": _("被调服务")},
            {"value": cls.CALLEE_SERVICE, "text": _("被调 Service")},
            {"value": cls.CALLEE_METHOD, "text": _("被调接口"), "default_group_by_field": True},
            {"value": cls.CALLEE_IP, "text": _("被调 IP")},
            {"value": cls.CALLEE_CONTAINER, "text": _("被调容器")},
            {"value": cls.CALLEE_CON_SETID, "text": _("被调 SetID")},
            {"value": cls.NAMESPACE, "text": _("物理环境")},
            {"value": cls.ENV_NAME, "text": _("用户环境")},
            {"value": cls.CODE, "text": _("返回码")},
            {"value": cls.VERSION, "text": _("版本")},
            {"value": cls.REGION, "text": _("地域")},
            {"value": cls.CANARY, "text": _("金丝雀")},
            {"value": cls.USER_EXT1, "text": _("预留字段1")},
            {"value": cls.USER_EXT2, "text": _("预留字段2")},
            {"value": cls.USER_EXT3, "text": _("预留字段3")},
        ]

    @classmethod
    def callee_tags(cls) -> list[dict[str, str]]:
        # 被调已经固定「被调服务」，不需要展示
        return [tag for tag in cls.tags() if tag["value"] != cls.CALLEE_SERVER]

    @classmethod
    def caller_tags(cls) -> list[dict[str, str]]:
        # 主调已经固定「主调服务」，不需要展示
        return [tag for tag in cls.tags() if tag["value"] != cls.CALLER_SERVER]

    @classmethod
    def tag_trace_mapping(cls) -> dict[str, dict[str, Any]]:
        return {
            "caller": {"field": "kind", "value": [SpanKind.SPAN_KIND_CLIENT, SpanKind.SPAN_KIND_CONSUMER]},
            cls.CALLER_SERVER: {"field": ResourceAttributes.SERVICE_NAME},
            cls.CALLER_SERVICE: {"field": f"{OtlpKey.ATTRIBUTES}.{TrpcAttributes.TRPC_CALLER_SERVICE}"},
            cls.CALLER_METHOD: {"field": f"{OtlpKey.ATTRIBUTES}.{TrpcAttributes.TRPC_CALLER_METHOD}"},
            cls.CALLER_IP: {"field": f"{OtlpKey.ATTRIBUTES}.{SpanAttributes.NET_HOST_IP}"},
            "callee": {"field": "kind", "value": [SpanKind.SPAN_KIND_SERVER, SpanKind.SPAN_KIND_PRODUCER]},
            cls.CALLEE_SERVER: {"field": ResourceAttributes.SERVICE_NAME},
            cls.CALLEE_SERVICE: {"field": f"{OtlpKey.ATTRIBUTES}.{TrpcAttributes.TRPC_CALLEE_SERVICE}"},
            cls.CALLEE_METHOD: {"field": f"{OtlpKey.ATTRIBUTES}.{TrpcAttributes.TRPC_CALLEE_METHOD}"},
            cls.CALLEE_IP: {"field": f"{OtlpKey.ATTRIBUTES}.{SpanAttributes.NET_PEER_IP}"},
            cls.NAMESPACE: {"field": f"{OtlpKey.ATTRIBUTES}.{TrpcAttributes.TRPC_NAMESPACE}"},
            cls.ENV_NAME: {"field": f"{OtlpKey.ATTRIBUTES}.{TrpcAttributes.TRPC_ENV_NAME}"},
            cls.CODE: {"field": f"{OtlpKey.ATTRIBUTES}.{TrpcAttributes.TRPC_STATUS_CODE}"},
        }

    @classmethod
    def caller_tag_trace_mapping(cls) -> dict[str, dict[str, Any]]:
        return {tag: trace_tag_info for tag, trace_tag_info in cls.tag_trace_mapping().items() if tag not in ["callee"]}

    @classmethod
    def callee_tag_trace_mapping(cls) -> dict[str, dict[str, Any]]:
        return {tag: trace_tag_info for tag, trace_tag_info in cls.tag_trace_mapping().items() if tag not in ["caller"]}


class TrpcTagDrillOperation:
    CALLER = "caller"
    CALLEE = "callee"
    TRACE = "trace"
    TOPO = "topo"
    SERVICE = "service"

    @classmethod
    def caller_support_operations(cls) -> list[dict[str, Any]]:
        tag_trace_mapping: dict[str, dict[str, Any]] = TRPCMetricTag.caller_tag_trace_mapping()
        return [
            {
                "text": _("主调"),
                "value": cls.CALLEE,
                "tags": [
                    TRPCMetricTag.CALLER_SERVICE,
                    TRPCMetricTag.CALLER_METHOD,
                    TRPCMetricTag.CALLEE_SERVICE,
                    TRPCMetricTag.CALLEE_METHOD,
                ],
            },
            {
                "text": _("Trace"),
                "value": cls.TRACE,
                "tags": list(tag_trace_mapping.keys()),
                "tag_trace_mapping": tag_trace_mapping,
            },
            # 主调视图下，第一个 group by 字段为「被调服务」时，可以跳转到拓扑页
            {"text": _("拓扑"), "value": cls.TOPO, "tags": [TRPCMetricTag.CALLEE_SERVER]},
            # 主调视图下，跳转到该服务的主被调界面，默认展示「被调」
            {"text": _("查看"), "value": cls.SERVICE, "tags": [TRPCMetricTag.CALLEE_SERVER]},
        ]

    @classmethod
    def callee_support_operations(cls) -> list[dict[str, Any]]:
        tag_trace_mapping: dict[str, dict[str, Any]] = TRPCMetricTag.callee_tag_trace_mapping()
        return [
            {
                "text": _("被调"),
                "value": cls.CALLEE,
                "tags": [
                    TRPCMetricTag.CALLER_SERVICE,
                    TRPCMetricTag.CALLER_METHOD,
                    TRPCMetricTag.CALLEE_SERVICE,
                    TRPCMetricTag.CALLEE_METHOD,
                ],
            },
            {
                "text": _("Trace"),
                "value": cls.TRACE,
                "tags": list(tag_trace_mapping.keys()),
                "tag_trace_mapping": tag_trace_mapping,
            },
            # TODO：需要检查下服务在不在，不在的话最好是有另外的交互提示
            # 被调视图下，第一个 group by 字段为「主调服务」时，可以跳转到拓扑页
            {"text": _("拓扑"), "value": cls.TOPO, "tags": [TRPCMetricTag.CALLER_SERVER]},
            # 被调视图下，跳转到该服务的主被调界面，默认展示「被调」
            {"text": _("查看"), "value": cls.SERVICE, "tags": [TRPCMetricTag.CALLER_SERVER]},
        ]


class IndexSetSource(TextChoices):
    """日志索引集来源类型"""

    HOST_COLLECT = "host_collect", _("主机采集项")
    SERVICE_RELATED = "service_related", _("服务关联")


class FlowType(TextChoices):
    """Flow类型"""

    TAIL_SAMPLING = "tail_sampling", _("尾部采样Flow")


class TailSamplingSupportMethod(TextChoices):
    """计算平台-尾部采样中采样规则支持配置的操作符"""

    GT = "gt", "gt"
    GTE = "gte", "gte"
    LT = "lt", "lt"
    LTE = "lte", "lte"
    EQ = (
        "eq",
        "eq",
    )
    NEQ = "neq", "neq"
    REG = "reg", "reg"
    NREG = "nreg", "nreg"


class DataSamplingLogTypeChoices:
    """走datalink的数据采样类型"""

    TRACE = "trace"
    METRIC = "metric"

    @classmethod
    def choices(cls):
        return [
            (cls.TRACE, cls.TRACE),
            (cls.METRIC, cls.METRIC),
        ]


class ApmMetrics:
    """
    APM内置指标
    格式: (指标名，描述，单位)
    """

    BK_APM_DURATION = "bk_apm_duration", _("trace请求耗时"), "ns"
    BK_APM_COUNT = "bk_apm_count", _("trace分钟请求数"), ""
    BK_APM_TOTAL = "bk_apm_total", _("trace总请求数"), ""
    BK_APM_DURATION_MAX = "bk_apm_duration_max", _("trace分钟请求最大耗时"), "ns"
    BK_APM_DURATION_MIN = "bk_apm_duration_min", _("trace分钟请求最小耗时"), "ns"
    BK_APM_DURATION_SUM = "bk_apm_duration_sum", _("trace总请求耗时"), "ns"
    BK_APM_DURATION_DELTA = "bk_apm_duration_delta", _("trace分钟总请求耗时"), "ns"
    BK_APM_DURATION_BUCKET = "bk_apm_duration_bucket", _("trace总请求耗时bucket"), "ns"

    @classmethod
    def all(cls):
        return [
            cls.BK_APM_DURATION,
            cls.BK_APM_COUNT,
            cls.BK_APM_TOTAL,
            cls.BK_APM_DURATION_MAX,
            cls.BK_APM_DURATION_MIN,
            cls.BK_APM_DURATION_SUM,
            cls.BK_APM_DURATION_DELTA,
            cls.BK_APM_DURATION_BUCKET,
        ]


class OtlpProtocol:
    GRPC: str = "grpc"
    HTTP_JSON: str = "http/json"

    @classmethod
    def choices(cls):
        return [
            (cls.GRPC, _("gRPC 上报")),
            (cls.HTTP_JSON, _("HTTP/Protobuf 上报")),
        ]


class TelemetryDataType(Enum):
    METRIC = "metric"
    LOG = "log"
    TRACE = "trace"
    PROFILING = "profiling"

    @classmethod
    def choices(cls):
        return [
            (cls.METRIC.value, _("指标")),
            (cls.LOG.value, _("日志")),
            (cls.TRACE.value, _("调用链")),
            (cls.PROFILING.value, _("性能分析")),
        ]

    @property
    def alias(self):
        return {
            self.METRIC.value: _lazy("指标"),
            self.LOG.value: _lazy("日志"),
            self.TRACE.value: _lazy("调用链"),
            self.PROFILING.value: _lazy("性能分析"),
        }.get(self.value, self.value)

    @cached_property
    def datasource_type(self):
        return {
            self.METRIC.value: "metric",
            self.LOG.value: "log",
            self.TRACE.value: "trace",
            self.PROFILING.value: "profiling",
        }.get(self.value)

    @classmethod
    def values(cls):
        return [i.value for i in cls]

    @classmethod
    def get_filter_fields(cls):
        return [
            {"id": cls.METRIC.value, "name": _("指标")},
            {"id": cls.LOG.value, "name": _("日志")},
            {"id": cls.TRACE.value, "name": _("调用链")},
            {"id": cls.PROFILING.value, "name": _("性能分析")},
        ]

    @cached_property
    def no_data_strategy_enabled(self):
        return {
            self.PROFILING.value: False,
        }.get(self.value, True)


class FormatType:
    # 默认：补充协议 + url 路径
    DEFAULT = "default"
    # simple：仅返回域名
    SIMPLE = "simple"

    @classmethod
    def choices(cls):
        return [(cls.DEFAULT, cls.DEFAULT), (cls.SIMPLE, cls.SIMPLE)]


class MetricTemporality:
    # 累积（Cumulative）：指标为 Counter 类型，数值只增不减，计算固定间隔（比如 1 分钟内）的请求量，需要用 increase 函数
    CUMULATIVE: str = "cumulative"
    # 差值（Delta）：指标为 Gauge 类型，数值是上报间隔，计算固定间隔（比如 1 分钟内）的请求量，需要用 sum_over_time 函数
    DELTA: str = "delta"

    # 默认使用 `service_name` 标识一个服务，允许通过动态配置，支持 callee_server & caller_server 此类非标准的服务检索。
    DYNAMIC_SERVER_FIELD: str = "${server}"

    @classmethod
    def choices(cls):
        return [(cls.CUMULATIVE, _("累积")), (cls.DELTA, _("差值"))]

    @classmethod
    def get_metric_config(cls, temporality: str) -> dict[str, str]:
        return {
            "temporality": temporality,
            "server_filter_method": "eq",
            "server_field": TRPCMetricTag.SERVICE_NAME,
            "service_field": "${service_name}",
        }


class Vendor:
    G = "Z2FsaWxlbw=="

    @classmethod
    def equal(cls, e, v):
        return e == v or base64.b64encode(v.encode()).decode() == e

    @classmethod
    def has_sdk(cls, service_sdk, expect_sdk):
        """在服务的 sdk 字段中寻找是否有特定 SDK"""
        if not service_sdk:
            return False
        return any(cls.equal(expect_sdk, i.get("name")) for i in service_sdk)


class CachedEnum(Enum):
    @classmethod
    @cache
    def from_value(cls, value):
        try:
            return cls(value)
        except Exception:  # pylint: disable=broad-except
            return cls.get_default(value)  # 处理未找到的情况

    @classmethod
    def get_default(cls, value):
        class _DefaultEnum:
            def __init__(self):
                self._value = value

            @property
            def value(self):
                return self._value

            def __getattr__(self, item):
                return getattr(self, item, None)

            def __setattr__(self, item, default_value):
                object.__setattr__(self, item, default_value)

        return _DefaultEnum()


class SpanKindCachedEnum(CachedEnum):
    SPAN_KIND_UNSPECIFIED = 0
    SPAN_KIND_INTERNAL = 1
    SPAN_KIND_SERVER = 2
    SPAN_KIND_CLIENT = 3
    SPAN_KIND_PRODUCER = 4
    SPAN_KIND_CONSUMER = 5

    @cached_property
    def label(self):
        return str({label["value"]: label["text"] for label in self.list()}.get(self, self.value))

    @classmethod
    @lru_cache(maxsize=1)
    def list(cls):
        return [
            {"value": cls.SPAN_KIND_UNSPECIFIED.value, "text": _("未指定(unspecified)")},
            {"value": cls.SPAN_KIND_INTERNAL.value, "text": _("内部(internal)")},
            {"value": cls.SPAN_KIND_SERVER.value, "text": _("被调")},
            {"value": cls.SPAN_KIND_CLIENT.value, "text": _("主调")},
            {"value": cls.SPAN_KIND_PRODUCER.value, "text": _("异步主调")},
            {"value": cls.SPAN_KIND_CONSUMER.value, "text": _("异步被调")},
        ]

    @classmethod
    def called_kinds(cls):
        """被调类型"""
        return [cls.SPAN_KIND_SERVER.value, cls.SPAN_KIND_CONSUMER.value]

    @classmethod
    def calling_kinds(cls):
        """主调类型"""
        return [cls.SPAN_KIND_CLIENT.value, cls.SPAN_KIND_PRODUCER.value]

    @classmethod
    def async_kinds(cls):
        """异步类型"""
        return [cls.SPAN_KIND_CONSUMER.value, cls.SPAN_KIND_PRODUCER.value]

    @classmethod
    def get_default(cls, value):
        default = super().get_default(value)
        default.label = value
        return default


TRACE_RESULT_TABLE_OPTION = {
    "es_unique_field_list": ["trace_id", "span_id", "parent_span_id", "start_time", "end_time", "span_name"],
    # 以下为 UnifyQuery 查询所需的元数据：
    # 是否根据查询时间范围，指定具体日期的索引进行查询。
    "need_add_time": True,
    # 默认查询时间字段，页面查询时间范围过滤与此字段联动。
    "time_field": {"name": "end_time", "type": "long", "unit": "microsecond"},
}

PRECALCULATE_RESULT_TABLE_OPTION = {
    # 是否根据查询时间范围，指定具体日期的索引进行查询。
    "need_add_time": True,
    # 默认查询时间字段，页面查询时间范围过滤与此字段联动。
    "time_field": {"name": PreCalculateSpecificField.MIN_START_TIME.value, "type": "long", "unit": "microsecond"},
}


class PrecalculateStorageConfig:
    TABLE_SCHEMA = [
        {
            "field_name": PreCalculateSpecificField.BK_TENANT_ID.value,
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "keyword"},
            "is_config_by_user": True,
            "description": "Bk Tenant Id",
        },
        {
            "field_name": PreCalculateSpecificField.BIZ_ID.value,
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "keyword"},
            "is_config_by_user": True,
            "description": "Bk Biz Id",
        },
        {
            "field_name": PreCalculateSpecificField.BIZ_NAME.value,
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "keyword"},
            "is_config_by_user": True,
            "description": "Bk Biz Name",
        },
        {
            "field_name": PreCalculateSpecificField.APP_ID.value,
            "field_type": ResultTableField.FIELD_TYPE_INT,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "integer"},
            "is_config_by_user": True,
            "description": "App Id",
        },
        {
            "field_name": PreCalculateSpecificField.APP_NAME.value,
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "keyword"},
            "is_config_by_user": True,
            "description": "App Name",
        },
        {
            "field_name": PreCalculateSpecificField.TRACE_ID.value,
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "keyword"},
            "is_config_by_user": True,
            "description": "Trace ID",
        },
        {
            "field_name": PreCalculateSpecificField.HIERARCHY_COUNT.value,
            "field_type": ResultTableField.FIELD_TYPE_INT,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "integer"},
            "is_config_by_user": True,
            "description": "Hierarchy Count",
        },
        {
            "field_name": PreCalculateSpecificField.SERVICE_COUNT.value,
            "field_type": ResultTableField.FIELD_TYPE_INT,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "integer"},
            "is_config_by_user": True,
            "description": "Service Count",
        },
        {
            "field_name": PreCalculateSpecificField.SPAN_COUNT.value,
            "field_type": ResultTableField.FIELD_TYPE_INT,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "integer"},
            "is_config_by_user": True,
            "description": "Span Count",
        },
        {
            "field_name": PreCalculateSpecificField.MIN_START_TIME.value,
            "field_type": ResultTableField.FIELD_TYPE_LONG,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "long"},
            "is_config_by_user": True,
            "description": "Min Start Time",
        },
        {
            "field_name": PreCalculateSpecificField.MAX_END_TIME.value,
            "field_type": ResultTableField.FIELD_TYPE_LONG,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "long"},
            "is_config_by_user": True,
            "description": "Max End Time",
        },
        {
            "field_name": PreCalculateSpecificField.TRACE_DURATION.value,
            "field_type": ResultTableField.FIELD_TYPE_LONG,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "long"},
            "is_config_by_user": True,
            "description": "Trace Duration",
        },
        {
            "field_name": PreCalculateSpecificField.SPAN_MAX_DURATION.value,
            "field_type": ResultTableField.FIELD_TYPE_LONG,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "long"},
            "is_config_by_user": True,
            "description": "Span Max Duration",
        },
        {
            "field_name": PreCalculateSpecificField.SPAN_MIN_DURATION.value,
            "field_type": ResultTableField.FIELD_TYPE_LONG,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "long"},
            "is_config_by_user": True,
            "description": "Span Min Duration",
        },
        {
            "field_name": PreCalculateSpecificField.ROOT_SERVICE.value,
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "keyword"},
            "is_config_by_user": True,
            "description": "Entry Service",
        },
        {
            "field_name": PreCalculateSpecificField.ROOT_SERVICE_SPAN_ID.value,
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "keyword"},
            "is_config_by_user": True,
            "description": "Root Service Span Id",
        },
        {
            "field_name": PreCalculateSpecificField.ROOT_SERVICE_SPAN_NAME.value,
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "keyword"},
            "is_config_by_user": True,
            "description": "Root Service Span Name",
        },
        {
            "field_name": PreCalculateSpecificField.ROOT_SERVICE_STATUS_CODE.value,
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "keyword"},
            "is_config_by_user": True,
            "description": "Root Service Status Code",
        },
        {
            "field_name": PreCalculateSpecificField.ROOT_SERVICE_CATEGORY.value,
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "keyword"},
            "is_config_by_user": True,
            "description": "Root Service Category",
        },
        {
            "field_name": PreCalculateSpecificField.ROOT_SERVICE_KIND.value,
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "keyword"},
            "is_config_by_user": True,
            "description": "Root Service Kind",
        },
        {
            "field_name": PreCalculateSpecificField.ROOT_SPAN_ID.value,
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "keyword"},
            "is_config_by_user": True,
            "description": "Root Span Id",
        },
        {
            "field_name": PreCalculateSpecificField.ROOT_SPAN_NAME.value,
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "keyword"},
            "is_config_by_user": True,
            "description": "Root Span Name",
        },
        {
            "field_name": PreCalculateSpecificField.ROOT_SPAN_SERVICE.value,
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "keyword"},
            "is_config_by_user": True,
            "description": "Root Span Service",
        },
        {
            "field_name": PreCalculateSpecificField.ROOT_SPAN_KIND.value,
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "keyword"},
            "is_config_by_user": True,
            "description": "Root Span Kind",
        },
        {
            "field_name": PreCalculateSpecificField.ERROR.value,
            "field_type": ResultTableField.FIELD_TYPE_BOOLEAN,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "boolean"},
            "is_config_by_user": True,
            "description": "error",
        },
        {
            "field_name": PreCalculateSpecificField.ERROR_COUNT.value,
            "field_type": ResultTableField.FIELD_TYPE_INT,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "integer"},
            "is_config_by_user": True,
            "description": "Error Count",
        },
        {
            "field_name": PreCalculateSpecificField.CATEGORY_STATISTICS.value,
            "field_type": ResultTableField.FIELD_TYPE_OBJECT,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "object", "es_dynamic": True},
            "is_config_by_user": True,
            "description": "Span分类统计",
        },
        {
            "field_name": PreCalculateSpecificField.KIND_STATISTICS.value,
            "field_type": ResultTableField.FIELD_TYPE_OBJECT,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "object", "es_dynamic": True},
            "is_config_by_user": True,
            "description": "Span类型统计",
        },
        {
            "field_name": PreCalculateSpecificField.COLLECTIONS.value,
            "field_type": ResultTableField.FIELD_TYPE_OBJECT,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "object", "es_dynamic": True},
            "is_config_by_user": True,
            "description": "常见标准字段数据",
        },
    ]


class OperatorGroupRelation(str, Enum):
    """操作符组间关系"""

    AND = "AND"
    OR = "OR"

    @classmethod
    def choices(cls):
        return [(relation.name, relation.value) for relation in cls]


# APM 自定义指标过滤规则，排除 RPC 主被调、Span 聚合指标，避免因数据量过大导致查询超时。
CUSTOM_METRICS_PROMQL_FILTER = ",".join(
    [
        '__name__!~"^rpc_(client|server)_(handled|started)_total"',
        '__name__!~"^rpc_(client|server)_handled_seconds_(sum|min|max|count|bucket)"',
        '__name__!~"^(bk_apm_|apm_).*"',
    ]
)
