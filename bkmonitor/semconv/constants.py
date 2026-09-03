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


class FieldDisplayType(CachedEnum):
    """字段展示类型，用于告知前端如何渲染字段值"""

    DATETIME = "datetime"
    DURATION = "duration"

    @cached_property
    def label(self) -> str:
        return {
            self.DATETIME: _("日期"),
            self.DURATION: _("持续时长"),
        }.get(self, self.value)

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]


class FieldUnit(CachedEnum):
    US = "us"
    MS = "ms"
    BYTES = "bytes"

    @cached_property
    def label(self) -> str:
        return {
            self.US: _("微秒"),
            self.MS: _("毫秒"),
            self.BYTES: _("字节"),
        }.get(self, self.value)

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]


class SpanKind(CachedEnum):
    """Span 类型"""

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
    def choices(cls) -> list[tuple[int, str]]:
        return [(member.value, member.label) for member in cls]


class SpanStatusCode(CachedEnum):
    """Span 状态码"""

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
    def choices(cls) -> list[tuple[int, str]]:
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
            self.WARNING: _("警告"),
            self.ERROR: _("错误"),
            self.TIMEOUT: _("超时"),
            self.ABORT: _("中止"),
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


class NetworkConnectionType(CachedEnum):
    """网络连接类型，对应浏览器 navigator.connection.type 的原始值"""

    NONE = "none"
    CELLULAR = "cellular"
    WIFI = "wifi"
    BLUETOOTH = "bluetooth"
    ETHERNET = "ethernet"
    WIMAX = "wimax"
    OTHER = "other"
    UNKNOWN = "unknown"

    @cached_property
    def label(self) -> str:
        return {
            self.NONE: _("无连接"),
            self.CELLULAR: _("蜂窝网络"),
            self.WIFI: _("Wi-Fi"),
            self.BLUETOOTH: _("蓝牙"),
            self.ETHERNET: _("以太网"),
            self.WIMAX: _("WiMAX"),
            self.OTHER: _("其他"),
            self.UNKNOWN: _("未知"),
        }.get(self, self.value)

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]
