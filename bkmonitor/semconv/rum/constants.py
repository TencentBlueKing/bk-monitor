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

SPAN_TYPE_COMMON_DISPLAY_FIELDS = [
    "span_name",
    "attributes.span_type",
    "end_time",
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
            self.VIEW: [
                *SPAN_TYPE_COMMON_DISPLAY_FIELDS,
                "elapsed_time",  # 耗时
                "attributes.outcome.type",  # 结果
                "attributes.view.name",  # 所在视图
                "resource.user_agent.name",  # 浏览器
                "attributes.user.id",  # 用户
            ],
            self.RESOURCE: [
                *SPAN_TYPE_COMMON_DISPLAY_FIELDS,
                "elapsed_time",
                "attributes.outcome.type",
                "attributes.http.request.method",  # Method
                "attributes.http.response.status_code",  # 状态码
                "attributes.view.name",
                "resource.user_agent.name",
                "attributes.user.id",
            ],
            self.ERROR: [
                *SPAN_TYPE_COMMON_DISPLAY_FIELDS,
                "attributes.outcome.type",
                "events.attributes.exception.type",
                "resource.user_agent.name",
                "attributes.user.id",
            ],
            self.VITAL: [
                *SPAN_TYPE_COMMON_DISPLAY_FIELDS,
                "attributes.outcome.type",
                "attributes.view.name",
                "resource.user_agent.name",
                "attributes.user.id",
            ],
            self.LONG_TASK: [
                *SPAN_TYPE_COMMON_DISPLAY_FIELDS,
                "attributes.long_task.blocking_duration",  # 阻塞时长
                "attributes.outcome.type",
                "attributes.view.name",
                "resource.user_agent.name",
                "attributes.user.id",
            ],
            self.ACTION: [
                *SPAN_TYPE_COMMON_DISPLAY_FIELDS,
                "elapsed_time",
                "attributes.outcome.type",
                "attributes.action.frustration.type",  # 挫败感
                "attributes.view.name",
                "resource.user_agent.name",
                "attributes.user.id",
            ],
            self.WEBSOCKET: [
                *SPAN_TYPE_COMMON_DISPLAY_FIELDS,
                "attributes.outcome.type",
                "attributes.view.name",
                "resource.user_agent.name",
                "attributes.user.id",
            ],
            self.CUSTOM: [
                *SPAN_TYPE_COMMON_DISPLAY_FIELDS,
                "elapsed_time",
                "attributes.outcome.type",
                "resource.user_agent.name",
                "attributes.user.id",
            ],
        }.get(self, SPAN_TYPE_COMMON_DISPLAY_FIELDS)


class ViewLoadingTimeSource(CachedEnum):
    """视图加载耗时来源"""

    AUTO = "auto"
    MANUAL = "manual"

    @cached_property
    def label(self) -> str:
        return {
            self.AUTO: _("自动"),
            self.MANUAL: _("手动"),
        }.get(self, self.value)

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]


class ViewLoadingType(CachedEnum):
    """视图加载类型"""

    INITIAL_LOAD = "initial_load"
    ROUTE_CHANGE = "route_change"
    SESSION_RENEWAL = "session_renewal"
    BF_CACHE = "bf_cache"

    @cached_property
    def label(self) -> str:
        return {
            self.INITIAL_LOAD: _("首次页面加载"),
            self.ROUTE_CHANGE: _("SPA 路由切换"),
            self.SESSION_RENEWAL: _("会话续期后重建"),
            self.BF_CACHE: _("从浏览器 BFCache 恢复"),
        }.get(self, self.value)

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]


class ViewPhase(CachedEnum):
    """视图生命周期阶段"""

    START = "start"
    UPDATE = "update"
    END = "end"

    @cached_property
    def label(self) -> str:
        return {
            self.START: _("开始"),
            self.UPDATE: _("更新"),
            self.END: _("结束"),
        }.get(self, self.value)

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]


class VitalInpInteractionType(CachedEnum):
    """INP 交互类型"""

    KEYUP = "keyup"
    KEYDOWN = "keydown"
    POINTERDOWN = "pointerdown"
    POINTERUP = "pointerup"

    @cached_property
    def label(self) -> str:
        return {
            self.KEYUP: _("松开按键"),
            self.KEYDOWN: _("按下按键"),
            self.POINTERDOWN: _("点击"),
            self.POINTERUP: _("松开"),
        }.get(self, self.value)

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]


class BlankScreenReason(CachedEnum):
    """白屏原因"""

    EMPTY_VIEWPORT = "empty_viewport"
    MISSING_ROOT = "missing_root"

    @cached_property
    def label(self) -> str:
        return {
            self.EMPTY_VIEWPORT: _("空白视口"),
            self.MISSING_ROOT: _("根元素缺失"),
        }.get(self, self.value)

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]


class LongTaskEntryType(CachedEnum):
    """长任务采集类型"""

    LONG_ANIMATION_FRAME = "long-animation-frame"
    LONG_TASK = "long-task"

    @cached_property
    def label(self) -> str:
        return {
            self.LONG_ANIMATION_FRAME: _("长动画帧"),
            self.LONG_TASK: _("长任务"),
        }.get(self, self.value)

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]


class ErrorSource(CachedEnum):
    """错误来源"""

    WINDOW_ERROR = "window.error"
    RESOURCE = "resource"
    UNHANDLED_REJECTION = "unhandledrejection"

    @cached_property
    def label(self) -> str:
        return {
            self.WINDOW_ERROR: _("窗口错误"),
            self.RESOURCE: _("资源加载错误"),
            self.UNHANDLED_REJECTION: _("未处理的 Promise 拒绝"),
        }.get(self, self.value)

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]


class DeviceType(CachedEnum):
    """设备类型"""

    DESKTOP = "desktop"
    MOBILE = "mobile"
    TABLET = "tablet"
    OTHER = "other"

    @cached_property
    def label(self) -> str:
        return {
            self.DESKTOP: _("桌面端"),
            self.MOBILE: _("移动端"),
            self.TABLET: _("平板端"),
            self.OTHER: _("其他"),
        }.get(self, self.value)

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]


class NetworkStatus(CachedEnum):
    """网络连接状态"""

    CONNECTED = "connected"
    NOT_CONNECTED = "not_connected"

    @cached_property
    def label(self) -> str:
        return {
            self.CONNECTED: _("已连接"),
            self.NOT_CONNECTED: _("未连接"),
        }.get(self, self.value)

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]


class NetworkEffectiveType(CachedEnum):
    """网络有效类型，对应浏览器 navigator.connection.effective_type 的原始值"""

    SLOW_2G = "slow-2g"
    G2 = "2g"
    G3 = "3g"
    G4 = "4g"

    @cached_property
    def label(self) -> str:
        return {
            self.SLOW_2G: _("极慢网络"),
            self.G2: _("较慢网络"),
            self.G3: _("中等网络"),
            self.G4: _("较快网络"),
        }.get(self, self.value)

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]


class NetworkConnectionType(CachedEnum):
    """网络连接类型，对应浏览器 navigator.connection.type 的原始值"""

    BLUETOOTH = "bluetooth"
    CELLULAR = "cellular"
    ETHERNET = "ethernet"
    MIXED = "mixed"
    NONE = "none"
    OTHER = "other"
    UNKNOWN = "unknown"
    WIFI = "wifi"
    WIMAX = "wimax"

    @cached_property
    def label(self) -> str:
        return {
            self.BLUETOOTH: _("蓝牙"),
            self.CELLULAR: _("蜂窝网络"),
            self.ETHERNET: _("以太网"),
            self.MIXED: _("混合连接"),
            self.NONE: _("无连接"),
            self.OTHER: _("其他"),
            self.UNKNOWN: _("未知"),
            self.WIFI: _("Wi-Fi"),
            self.WIMAX: _("WiMAX"),
        }.get(self, self.value)

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]


class NetworkProtocolName(CachedEnum):
    """应用层网络协议"""

    WEBSOCKET = "websocket"

    @cached_property
    def label(self) -> str:
        return {
            self.WEBSOCKET: _("WebSocket"),
        }.get(self, self.value)

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]


class SessionType(CachedEnum):
    """会话类型"""

    USER = "user"

    @cached_property
    def label(self) -> str:
        return {
            self.USER: _("用户"),
        }.get(self, self.value)

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]


class SessionPhase(CachedEnum):
    """会话生命周期阶段"""

    START = "start"
    ROTATE = "rotate"
    END = "end"

    @cached_property
    def label(self) -> str:
        return {
            self.START: _("创建"),
            self.ROTATE: _("轮换"),
            self.END: _("结束"),
        }.get(self, self.value)

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]


class SdkLanguage(CachedEnum):
    """SDK 语言"""

    WEBJS = "webjs"

    @cached_property
    def label(self) -> str:
        return {
            self.WEBJS: _("Web JS"),
        }.get(self, self.value)

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]


class VitalMetric(CachedEnum):
    """核心 Web 指标名"""

    CLS = "cls"
    INP = "inp"
    LCP = "lcp"
    FCP = "fcp"
    TTFB = "ttfb"

    @cached_property
    def label(self) -> str:
        return {
            self.CLS: _("CLS"),
            self.INP: _("INP"),
            self.LCP: _("LCP"),
            self.FCP: _("FCP"),
            self.TTFB: _("TTFB"),
        }.get(self, self.value)

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]


class OutcomeType(CachedEnum):
    """执行结果"""

    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    TIMEOUT = "timeout"
    ABORT = "abort"

    @cached_property
    def label(self) -> str:
        return {
            self.SUCCESS: _("成功"),
            self.WARNING: _("异常"),
            self.ERROR: _("失败"),
            self.TIMEOUT: _("超时"),
            self.ABORT: _("中止"),
        }.get(self, self.value)

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]


class ResourceType(CachedEnum):
    """资源类型"""

    FETCH = "fetch"
    XHR = "xhr"
    SCRIPT = "script"
    LINK = "link"
    IMG = "img"
    IMAGE = "image"
    CSS = "css"
    IFRAME = "iframe"
    FRAME = "frame"
    OTHER = "other"

    @cached_property
    def label(self) -> str:
        return {
            self.FETCH: _("Fetch API 请求"),
            self.XHR: _("XMLHttpRequest 请求"),
            self.SCRIPT: _("脚本资源"),
            self.LINK: _("链接加载的资源"),
            self.IMG: _("图片资源"),
            self.IMAGE: _("图片资源"),
            self.CSS: _("CSS 规则加载的资源"),
            self.IFRAME: _("内嵌文档资源"),
            self.FRAME: _("内嵌文档资源"),
            self.OTHER: _("其他类型"),
        }.get(self, self.value)

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]


class ResourceRenderBlockingStatus(CachedEnum):
    """资源渲染阻塞状态"""

    BLOCKING = "blocking"
    NON_BLOCKING = "non-blocking"

    @cached_property
    def label(self) -> str:
        return {
            self.BLOCKING: _("可能阻塞页面渲染"),
            self.NON_BLOCKING: _("不会阻塞页面渲染"),
        }.get(self, self.value)

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]


class FrustrationType(CachedEnum):
    """用户挫败类型"""

    RAGE_CLICK = "rage_click"
    ERROR_CLICK = "error_click"
    DEAD_CLICK = "dead_click"

    @cached_property
    def label(self) -> str:
        return {
            self.RAGE_CLICK: _("狂暴点击"),
            self.ERROR_CLICK: _("错误点击"),
            self.DEAD_CLICK: _("无效点击"),
        }.get(self, self.value)

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]
