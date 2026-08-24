"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from functools import cached_property

from django.utils.translation import gettext_lazy as _

from constants.apm import CachedEnum


# 告警级别常量
class AlertLevel:
    ERROR = 1
    WARN = 2
    INFO = 3


# 告警状态常量
class AlertStatus:
    ABNORMAL = "ABNORMAL"
    RECOVERED = "RECOVERED"


# 数据状态常量
class DataStatus:
    NORMAL = "normal"
    NO_DATA = "no_data"
    DISABLED = "disabled"


# 无数据告警策略配置 key
NODATA_ERROR_STRATEGY_CONFIG_KEY = "nodata_error_strategy_id"

# 无数据告警检测周期（分钟）
DEFAULT_NO_DATA_PERIOD = 10

# 默认 QPS 限制
DEFAULT_RUM_APP_QPS = 500

# 默认 Apdex 配置（单位 ms）
DEFAULT_RUM_APDEX_CONFIG = {
    "apdex_api_request": 500,
    "apdex_view_load": 500,
}

# 应用列表异步指标列名
ASYNC_COLUMN_LCP_P75 = "lcp_p75"
ASYNC_COLUMN_JS_ERROR_RATE = "js_error_rate"
ASYNC_COLUMN_API_FAIL_RATE = "api_fail_rate"

# 首页应用列表异步指标列名选择
ASYNC_COLUMN_CHOICES = [ASYNC_COLUMN_LCP_P75, ASYNC_COLUMN_JS_ERROR_RATE, ASYNC_COLUMN_API_FAIL_RATE]


class DefaultSetupConfig:
    """RUM 创建应用默认配置"""

    DEFAULT_ES_RETENTION_DAYS = 7
    DEFAULT_ES_NUMBER_OF_REPLICAS = 1
    DEFAULT_ES_RETENTION_DAYS_MAX = 7
    DEFAULT_ES_NUMBER_OF_REPLICAS_MAX = 3
    PRIVATE_ES_RETENTION_DAYS_MAX = 30
    PRIVATE_ES_NUMBER_OF_REPLICAS_MAX = 10


class BizConfigKey:
    """业务级配置键名"""

    DEFAULT_ES_RETENTION_DAYS_MAX = "default_es_retention_days_max"
    PRIVATE_ES_RETENTION_DAYS_MAX = "private_es_retention_days_max"
    DEFAULT_ES_NUMBER_OF_REPLICAS_MAX = "default_es_number_of_replicas_max"
    PRIVATE_ES_NUMBER_OF_REPLICAS_MAX = "private_es_number_of_replicas_max"


RUM_WEB_CLIENT_CHOICES = [
    "web",
]


class CalculationMethod:
    # 健康度
    APDEX = "apdex"


class Apdex:
    DIMENSION_KEY = "apdex_type"
    SATISFIED = "satisfied"
    TOLERATING = "tolerating"
    FRUSTRATED = "frustrated"
    ERROR = "error"

    @classmethod
    def get_label_by_key(cls, key: str):
        return {cls.SATISFIED: _("满意"), cls.TOLERATING: _("可容忍"), cls.FRUSTRATED: _("烦躁期")}.get(key, key)

    @classmethod
    def get_status_by_key(cls, key: str):
        return {
            cls.SATISFIED: {"type": Status.SUCCESS, "text": cls.get_label_by_key(key)},
            cls.TOLERATING: {"type": Status.WAITING, "text": cls.get_label_by_key(key)},
            cls.FRUSTRATED: {"type": Status.FAILED, "text": cls.get_label_by_key(key)},
        }.get(key, {"type": None, "text": "--"})


class Status:
    """状态"""

    NORMAL = "normal"
    WARNING = "warning"
    FAILED = "failed"
    SUCCESS = "success"
    DISABLED = "disabled"
    WAITING = "waiting"

    @classmethod
    def get_label_by_key(cls, key: str):
        return {
            cls.NORMAL: _("正常"),
            cls.WARNING: _("预警"),
            cls.FAILED: _("异常"),
            cls.SUCCESS: _("成功"),
            cls.DISABLED: _("禁用"),
            cls.WAITING: _("等待"),
        }.get(key, key)


RUM_APPLICATION_DEFAULT_METRIC = {
    "lcp_p75": 0.0,
    "js_error_rate": 0.0,
    "api_fail_rate": 0.0,
}

# RUM 应用列表页, 应用相关指标 key -> BKMONITOR_{PLATFORM}_{ENVIRONMENT}_RUM_APPLICATION_METRIC_{bk_biz_id}_{application_id}
RUM_APPLICATION_METRIC = "BKMONITOR_{}_{}_RUM_APPLICATION_METRIC_{}_{}"


class RumQueryMode(CachedEnum):
    """RUM 查询层级模式"""

    SPAN = "span"
    VIEW = "view"
    SESSION = "session"

    @cached_property
    def label(self) -> str:
        return self.value

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]


SPAN_TYPE_COMMON_DISPLAY_FIELDS = [
    "span_name",
    "attributes.span_type",
    "end_time",
    "elapsed_time",
    "status.code",
    "attributes.view.url_template",
    "attributes.user.id",
]


class RumSpanType(CachedEnum):
    """RUM Span 数据类型"""

    VIEW = "view"
    RESOURCE = "resource"
    ERROR = "error"
    VITAL = "vital"
    LONG_TASK = "long_task"
    ACTION = "action"
    WEBSOCKET = "websocket"
    CUSTOM = "custom"

    @cached_property
    def label(self) -> str:
        return str(
            {
                self.VIEW: _("视图"),
                self.RESOURCE: _("资源"),
                self.ERROR: _("错误"),
                self.VITAL: _("网页指标"),
                self.LONG_TASK: _("长任务"),
                self.ACTION: _("用户交互"),
                self.WEBSOCKET: "WebSocket",
                self.CUSTOM: _("自定义事件"),
            }.get(self, str(self.value))
        )

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]

    @classmethod
    def values(cls) -> list[str]:
        return [member.value for member in cls]

    @cached_property
    def display_fields(self) -> list[str]:
        return {
            self.VIEW: [*SPAN_TYPE_COMMON_DISPLAY_FIELDS],
            self.RESOURCE: [
                *SPAN_TYPE_COMMON_DISPLAY_FIELDS,
                "attributes.resource.type",
                "attributes.http.request.method",
            ],
            self.ERROR: [*SPAN_TYPE_COMMON_DISPLAY_FIELDS, "attributes.error.source"],
            self.VITAL: [*SPAN_TYPE_COMMON_DISPLAY_FIELDS, "attributes.vital.metric", "attributes.vital.value"],
            self.LONG_TASK: [
                *SPAN_TYPE_COMMON_DISPLAY_FIELDS,
                "attributes.long_task.name",
                "attributes.long_task.entry_type",
            ],
            self.ACTION: [*SPAN_TYPE_COMMON_DISPLAY_FIELDS, "attributes.action.id", "attributes.action.type"],
            self.WEBSOCKET: [*SPAN_TYPE_COMMON_DISPLAY_FIELDS],
            self.CUSTOM: [*SPAN_TYPE_COMMON_DISPLAY_FIELDS],
        }.get(self, SPAN_TYPE_COMMON_DISPLAY_FIELDS)


class RumSpanKind(CachedEnum):
    """RUM Span 类型"""

    UNSPECIFIED = 0
    INTERNAL = 1
    SERVER = 2
    CLIENT = 3
    PRODUCER = 4
    CONSUMER = 5

    @cached_property
    def label(self) -> str:
        return str(
            {
                self.UNSPECIFIED: _("未定义"),
                self.INTERNAL: _("内部调用"),
                self.SERVER: _("同步被调"),
                self.CLIENT: _("同步主调"),
                self.PRODUCER: _("异步主调"),
                self.CONSUMER: _("异步被调"),
            }.get(self, str(self.value))
        )

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]


class RumSpanStatusCode(CachedEnum):
    """RUM Span 状态码"""

    UNSET = 0
    OK = 1
    ERROR = 2

    @cached_property
    def label(self) -> str:
        return str(
            {
                self.UNSET: _("未设置"),
                self.OK: _("正常"),
                self.ERROR: _("异常"),
            }.get(self, str(self.value))
        )

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]


class RumDeviceType(CachedEnum):
    """RUM 设备类型"""

    DESKTOP = "desktop"
    MOBILE = "mobile"
    TABLET = "tablet"
    OTHER = "other"

    @cached_property
    def label(self) -> str:
        return str(
            {
                self.DESKTOP: _("桌面设备"),
                self.MOBILE: _("移动设备"),
                self.TABLET: _("平板设备"),
                self.OTHER: _("其他设备"),
            }.get(self, str(self.value))
        )

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]


# RUM 检索页分组配置（新协议：每个分组含 name、alias、fields 列表）
# fields 列表中每项为字段名，view_config 构建时会从 query_fields 结果中填充完整字段信息
# supported_span_types：该分组适用的 Span 类型列表，前端据此在切换类型时折叠不相关分组
RUM_SEARCH_PAGE_GROUPS: dict[str, list[dict]] = {
    "span": [
        {
            "name": "COMMON",
            "alias": _("公共字段"),
            "supported_span_types": RumSpanType.values(),
            "field_names": [
                "kind",
                "span_name",
                "attributes.span_type",
                "elapsed_time",
                "status.code",
                "status.message",
            ],
        },
        {
            "name": "APP_VERSION",
            "alias": _("应用 & 版本"),
            "supported_span_types": RumSpanType.values(),
            "field_names": [
                "resource.service.name",
                "resource.service.version",
                "resource.deployment.environment.name",
                "resource.telemetry.sdk.version",
                "resource.telemetry.sdk.language",
                "resource.telemetry.sdk.name",
            ],
        },
        {
            "name": "DEVICE_BROWSER",
            "alias": _("终端 & 浏览器"),
            "supported_span_types": RumSpanType.values(),
            "field_names": [
                "resource.device.type",
                "resource.user_agent.name",
                "resource.user_agent.version",
                "resource.user_agent.os.name",
            ],
        },
        {
            "name": "NETWORK_GEO",
            "alias": _("网络 & 地域"),
            "supported_span_types": RumSpanType.values(),
            "field_names": [
                "attributes.network.connection.type",
                "attributes.network.effective_type",
            ],
        },
        {
            "name": "USER",
            "alias": _("用户"),
            "supported_span_types": RumSpanType.values(),
            "field_names": [
                "attributes.user.id",
            ],
        },
        {
            "name": "RESOURCE",
            "alias": _("资源加载"),
            "supported_span_types": [RumSpanType.RESOURCE.value],
            "field_names": [
                "attributes.resource.type",
                "attributes.url.template",
                "attributes.http.request.method",
                "attributes.http.response.status_code",
                "attributes.resource.size",
                "attributes.resource.protocol",
            ],
        },
        {
            "name": "VIEW",
            "alias": _("视图"),
            "supported_span_types": [RumSpanType.VIEW.value],
            "field_names": [
                "attributes.view.referrer",
                "attributes.view.url_template",
            ],
        },
        {
            "name": "ACTION",
            "alias": _("用户交互"),
            "supported_span_types": [RumSpanType.ACTION.value],
            "field_names": [
                "attributes.action.type",
                "attributes.action.target.name",
            ],
        },
        {
            "name": "WEB_VITALS",
            "alias": _("网页指标（Web Vitals）"),
            "supported_span_types": [RumSpanType.VITAL.value],
            "field_names": [
                "CLS",
                "INP",
                "LCP",
                "FCP",
                "TTFB",
            ],
        },
    ],
    "view": [],
    "session": [],
}

# RUM 字段别名
RUM_FIELD_ALIAS = {}
