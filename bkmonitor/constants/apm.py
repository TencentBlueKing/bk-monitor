from dataclasses import dataclass

from django.db.models import TextChoices
from django.utils.translation import ugettext_lazy as _
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
class StandardFieldCategory:
    BASE = "base"
    HTTP = "http"
    RPC = "rpc"
    DB = "db"
    MESSAGING = "messaging"
    ASYNC_BACKEND = "async_backend"

    @classmethod
    def get_label_by_key(cls, key: str):
        return {
            cls.BASE: _("基础信息"),
            cls.HTTP: _("网页"),
            cls.RPC: _("远程调用"),
            cls.DB: _("数据库"),
            cls.MESSAGING: _("消息队列"),
            cls.ASYNC_BACKEND: _("后台任务"),
        }.get(key, key)


@dataclass
class StandardField:
    source: str
    key: str
    value: str
    display_level: str
    category: str


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
            SpanAttributes.HTTP_SCHEME,
            _("HTTP协议"),
            StandardFieldDisplayLevel.ADVANCES,
            StandardFieldCategory.HTTP,
        ),
        StandardField(
            OtlpKey.ATTRIBUTES,
            SpanAttributes.HTTP_FLAVOR,
            _("HTTP服务名称"),
            StandardFieldDisplayLevel.ADVANCES,
            StandardFieldCategory.HTTP,
        ),
        StandardField(
            OtlpKey.ATTRIBUTES,
            SpanAttributes.HTTP_METHOD,
            _("HTTP方法"),
            StandardFieldDisplayLevel.ADVANCES,
            StandardFieldCategory.HTTP,
        ),
        StandardField(
            OtlpKey.ATTRIBUTES,
            SpanAttributes.HTTP_STATUS_CODE,
            _("HTTP状态码"),
            StandardFieldDisplayLevel.ADVANCES,
            StandardFieldCategory.HTTP,
        ),
        StandardField(
            OtlpKey.ATTRIBUTES,
            SpanAttributes.RPC_METHOD,
            _("RPC方法"),
            StandardFieldDisplayLevel.ADVANCES,
            StandardFieldCategory.RPC,
        ),
        StandardField(
            OtlpKey.ATTRIBUTES,
            SpanAttributes.RPC_SERVICE,
            _("RPC服务"),
            StandardFieldDisplayLevel.ADVANCES,
            StandardFieldCategory.RPC,
        ),
        StandardField(
            OtlpKey.ATTRIBUTES,
            SpanAttributes.RPC_SYSTEM,
            _("RPC系统名"),
            StandardFieldDisplayLevel.ADVANCES,
            StandardFieldCategory.RPC,
        ),
        StandardField(
            OtlpKey.ATTRIBUTES,
            SpanAttributes.RPC_GRPC_STATUS_CODE,
            _("gRPC状态码"),
            StandardFieldDisplayLevel.ADVANCES,
            StandardFieldCategory.RPC,
        ),
        StandardField(
            OtlpKey.ATTRIBUTES,
            SpanAttributes.DB_NAME,
            _("数据库名称"),
            StandardFieldDisplayLevel.ADVANCES,
            StandardFieldCategory.DB,
        ),
        StandardField(
            OtlpKey.ATTRIBUTES,
            SpanAttributes.DB_OPERATION,
            _("数据库操作"),
            StandardFieldDisplayLevel.ADVANCES,
            StandardFieldCategory.DB,
        ),
        StandardField(
            OtlpKey.ATTRIBUTES,
            SpanAttributes.DB_SYSTEM,
            _("数据库类型"),
            StandardFieldDisplayLevel.ADVANCES,
            StandardFieldCategory.DB,
        ),
        StandardField(
            OtlpKey.ATTRIBUTES,
            SpanAttributes.MESSAGING_SYSTEM,
            _("消息系统"),
            StandardFieldDisplayLevel.ADVANCES,
            StandardFieldCategory.MESSAGING,
        ),
        StandardField(
            OtlpKey.ATTRIBUTES,
            SpanAttributes.MESSAGING_DESTINATION,
            _("消息目的地"),
            StandardFieldDisplayLevel.ADVANCES,
            StandardFieldCategory.MESSAGING,
        ),
        StandardField(
            OtlpKey.ATTRIBUTES,
            SpanAttributes.MESSAGING_DESTINATION_KIND,
            _("消息目的地类型"),
            StandardFieldDisplayLevel.ADVANCES,
            StandardFieldCategory.MESSAGING,
        ),
        StandardField(
            OtlpKey.ATTRIBUTES,
            "celery.action",
            _("Celery操作名称"),
            StandardFieldDisplayLevel.ADVANCES,
            StandardFieldCategory.MESSAGING,
        ),
        StandardField(
            OtlpKey.ATTRIBUTES,
            "celery.task_name",
            _("Celery任务名称"),
            StandardFieldDisplayLevel.ADVANCES,
            StandardFieldCategory.MESSAGING,
        ),
        StandardField(
            OtlpKey.ATTRIBUTES,
            SpanAttributes.NET_PEER_NAME,
            _("远程服务器名称"),
            StandardFieldDisplayLevel.ADVANCES,
            StandardFieldCategory.HTTP,
        ),
        StandardField(
            OtlpKey.ATTRIBUTES,
            SpanAttributes.PEER_SERVICE,
            _("远程服务名"),
            StandardFieldDisplayLevel.ADVANCES,
            StandardFieldCategory.HTTP,
        ),
        StandardField(
            OtlpKey.RESOURCE,
            ResourceAttributes.SERVICE_NAME,
            _("服务名"),
            StandardFieldDisplayLevel.BASE,
            StandardFieldCategory.BASE,
        ),
        StandardField(
            OtlpKey.RESOURCE,
            ResourceAttributes.SERVICE_VERSION,
            _("服务版本"),
            StandardFieldDisplayLevel.BASE,
            StandardFieldCategory.BASE,
        ),
        StandardField(
            OtlpKey.RESOURCE,
            ResourceAttributes.TELEMETRY_SDK_LANGUAGE,
            _("SDK语言"),
            StandardFieldDisplayLevel.BASE,
            StandardFieldCategory.BASE,
        ),
        StandardField(
            OtlpKey.RESOURCE,
            ResourceAttributes.TELEMETRY_SDK_NAME,
            _("SDK名称"),
            StandardFieldDisplayLevel.BASE,
            StandardFieldCategory.BASE,
        ),
        StandardField(
            OtlpKey.RESOURCE,
            ResourceAttributes.TELEMETRY_SDK_VERSION,
            _("SDK版本"),
            StandardFieldDisplayLevel.BASE,
            StandardFieldCategory.BASE,
        ),
        StandardField(
            OtlpKey.RESOURCE,
            ResourceAttributes.SERVICE_NAMESPACE,
            _("服务命名空间"),
            StandardFieldDisplayLevel.BASE,
            StandardFieldCategory.BASE,
        ),
        StandardField(
            OtlpKey.RESOURCE,
            ResourceAttributes.SERVICE_INSTANCE_ID,
            _("服务实例ID"),
            StandardFieldDisplayLevel.BASE,
            StandardFieldCategory.BASE,
        ),
        StandardField(
            OtlpKey.RESOURCE, "net.host.ip", _("主机IP"), StandardFieldDisplayLevel.BASE, StandardFieldCategory.BASE
        ),
        StandardField(
            OtlpKey.RESOURCE, "net.host.port", _("主机端口"), StandardFieldDisplayLevel.BASE, StandardFieldCategory.BASE
        ),
        StandardField(
            OtlpKey.RESOURCE, "net.host.name", _("主机名称"), StandardFieldDisplayLevel.BASE, StandardFieldCategory.BASE
        ),
        StandardField(
            OtlpKey.RESOURCE, "bk.instance.id", _("实例"), StandardFieldDisplayLevel.BASE, StandardFieldCategory.BASE
        ),
        StandardField(OtlpKey.KIND, OtlpKey.KIND, _("类型"), StandardFieldDisplayLevel.BASE, StandardFieldCategory.BASE),
        StandardField(
            OtlpKey.SPAN_NAME,
            OtlpKey.SPAN_NAME,
            _("接口名称"),
            StandardFieldDisplayLevel.BASE,
            StandardFieldCategory.BASE,
        ),
    ]

    @classmethod
    def standard_fields(cls):
        """获取标准字段"""
        res = []
        for i in cls.COMMON_STANDARD_FIELDS:
            if i.source == i.key:
                res.append(i.source)
            else:
                res.append(f"{i.source}.{i.key}")
        return res

    @classmethod
    def list_standard_fields(cls):
        """按照层级获取标准字段"""
        base_fields = []
        advances_fields = []

        for i in cls.COMMON_STANDARD_FIELDS:
            if i.source == i.key:
                if i.display_level == StandardFieldDisplayLevel.BASE:
                    base_fields.append({"name": i.value, "id": i.source})
                else:
                    advances_fields.append({"name": i.value, "id": i.source, "category": i.category})
            else:
                if i.display_level == StandardFieldDisplayLevel.BASE:
                    base_fields.append({"name": i.value, "id": f"{i.source}.{i.key}"})
                else:
                    advances_fields.append({"name": i.value, "id": f"{i.source}.{i.key}", "category": i.category})

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
        base_fields = [i for i in cls.COMMON_STANDARD_FIELDS if i.display_level == StandardFieldDisplayLevel.BASE]
        ad_fields = [i for i in cls.COMMON_STANDARD_FIELDS if i.display_level == StandardFieldDisplayLevel.ADVANCES]

        for item in base_fields + ad_fields:
            k = f"{item.source}.{item.key}" if item.source != item.key else item.key
            res.append(
                {
                    "name": f"{item.value}({k})",
                    "key": k,
                    "type": "string",
                }
            )

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

    TRPC_NAMESPACE = "trpc.namespace"
    TRPC_CALLER_SERVICE = "trpc.caller_service"
    TRPC_CALLEE_SERVICE = "trpc.callee_service"
    TRPC_CALLER_METHOD = "trpc.caller_method"
    TRPC_CALLEE_METHOD = "trpc.callee_method"
    TRPC_STATUS_TYPE = "trpc.status_type"
    TRPC_STATUS_CODE = "trpc.status_code"


class IndexSetSource(TextChoices):
    """日志索引集来源类型"""

    HOST_COLLECT = "host_collect", _("主机采集项")
    SERVICE_RELATED = "service_related", _("服务关联")


class FlowType(TextChoices):
    """Flow类型"""

    TAIL_SAMPLING = "tail_sampling", _("尾部采样Flow")


class TailSamplingSupportMethod(TextChoices):
    """计算平台-尾部采样中采样规则支持配置的操作符"""

    GT = "gt", _("gt")
    GTE = "gte", _("gte")
    LT = "lt", _("lt")
    LTE = "lte", _("lte")
    EQ = (
        "eq",
        _("eq"),
    )
    NEQ = "neq", _("neq")
    REG = "reg", _("reg")
    NREG = "nreg", _("nreg")


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
