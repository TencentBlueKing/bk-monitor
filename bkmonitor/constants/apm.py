import base64
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from typing import Any, Dict, List

from django.db.models import TextChoices
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.utils.translation import gettext_lazy as _lazy
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.semconv.trace import SpanAttributes


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
            ValueSource.METRIC,
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
    def standard_fields(cls) -> List[str]:
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

    BIZ_ID = "biz_id"
    BIZ_NAME = "biz_name"
    APP_ID = "app_id"
    APP_NAME = "app_name"
    TRACE_ID = "trace_id"
    HIERARCHY_COUNT = "hierarchy_count"
    SERVICE_COUNT = "service_count"
    SPAN_COUNT = "span_count"
    MIN_START_TIME = "min_start_time"
    MAX_END_TIME = "max_end_time"
    TRACE_DURATION = "trace_duration"
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
    ERROR = "error"
    ERROR_COUNT = "error_count"
    TIME = "time"
    CATEGORY_STATISTICS = "category_statistics"
    KIND_STATISTICS = "kind_statistics"
    COLLECTIONS = "collections"

    @classmethod
    def search_fields(cls):
        """获取可供搜索的字段"""
        return list(set(list(cls.values)) - set(cls.hidden_fields()))

    @classmethod
    def hidden_fields(cls):
        """获取隐藏字段"""
        return [cls.BIZ_ID, cls.BIZ_NAME, cls.APP_ID, cls.APP_NAME, cls.TIME, cls.COLLECTIONS]


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
    def tags(cls) -> List[Dict[str, str]]:
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
    def callee_tags(cls) -> List[Dict[str, str]]:
        # 被调已经固定「被调服务」，不需要展示
        return [tag for tag in cls.tags() if tag["value"] != cls.CALLEE_SERVER]

    @classmethod
    def caller_tags(cls) -> List[Dict[str, str]]:
        # 主调已经固定「主调服务」，不需要展示
        return [tag for tag in cls.tags() if tag["value"] != cls.CALLER_SERVER]

    @classmethod
    def tag_trace_mapping(cls) -> Dict[str, Dict[str, Any]]:
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
    def caller_tag_trace_mapping(cls) -> Dict[str, Dict[str, Any]]:
        return {tag: trace_tag_info for tag, trace_tag_info in cls.tag_trace_mapping().items() if tag not in ["callee"]}

    @classmethod
    def callee_tag_trace_mapping(cls) -> Dict[str, Dict[str, Any]]:
        return {tag: trace_tag_info for tag, trace_tag_info in cls.tag_trace_mapping().items() if tag not in ["caller"]}


class TrpcTagDrillOperation:
    CALLER = "caller"
    CALLEE = "callee"
    TRACE = "trace"
    TOPO = "topo"
    SERVICE = "service"

    @classmethod
    def caller_support_operations(cls) -> List[Dict[str, Any]]:
        tag_trace_mapping: Dict[str, Dict[str, Any]] = TRPCMetricTag.caller_tag_trace_mapping()
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
    def callee_support_operations(cls) -> List[Dict[str, Any]]:
        tag_trace_mapping: Dict[str, Dict[str, Any]] = TRPCMetricTag.callee_tag_trace_mapping()
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


class BkCollectorComp:
    """一些 bk-collector 的固定值"""

    NAMESPACE = "bkmonitor-operator"

    DEPLOYMENT_NAME = "bkm-collector"

    # ConfigMap 模版
    # ConfigMap: 平台配置名称
    CONFIG_MAP_PLATFORM_TPL_NAME = "bk-collector-platform.conf.tpl"
    # ConfigMap: 应用配置名称
    CONFIG_MAP_APPLICATION_TPL_NAME = "bk-collector-application.conf.tpl"

    # Secrets 配置
    SECRET_PLATFORM_NAME = "bk-collector-platform"
    SECRET_SUBCONFIG_APM_NAME = "bk-collector-subconfig-apm-{}-{}"  # 这里的名字不能随意变，逻辑上依赖
    SECRET_PLATFORM_CONFIG_FILENAME_NAME = "platform.conf"
    SECRET_APPLICATION_CONFIG_FILENAME_NAME = "application-{}.conf"  # 这里的名字不能随意变，逻辑上依赖
    SECRET_APPLICATION_CONFIG_MAX_COUNT = 20  # 每个 Secret 存放 20 个 APM 应用配置

    # Labels 过滤条件
    LABEL_COMPONENT_VALUE = "bk-collector"
    LABEL_TYPE_SUB_CONFIG = "subconfig"
    LABEL_TYPE_PLATFORM_CONFIG = "platform"
    LABEL_SOURCE_APPLICATION_CONFIG = "apm"

    # 缓存 KEY: 安装了 bk-collector 的集群 id 列表
    CACHE_KEY_CLUSTER_IDS = "bk-collector:clusters"


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
    def get_metric_config(cls, temporality: str) -> Dict[str, str]:
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
    @lru_cache(maxsize=None)
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
