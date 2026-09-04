"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from semconv.rum.attributes import span_attributes
from semconv.rum.field import FieldSpec
from semconv.rum.metric import web_vitals
from semconv.rum.registry import FieldRegistry
from semconv.rum.trace.attributes import Attributes
from semconv.rum.trace.events import Events
from semconv.rum.trace.links import Links
from semconv.rum.trace.resource import Resource
from semconv.rum.trace.status import Status


class SpanSpec(FieldSpec):
    """RUM Span 字段树根节点。

    组织整棵字段树，并通过 ``from_field()`` 支持按完整路径查找字段描述符。

    用法::

        spec = SpanSpec.from_field("attributes.span_type")
        spec = SpanSpec.from_field("status.code")
        spec = SpanSpec.from_field("resource.user_agent.name")

    Web Vitals 虚拟字段（CLS / INP / LCP / FCP / TTFB）也注册在根级，
    可直接通过字段名查找::

        spec = SpanSpec.from_field("LCP")
    """

    # ── Span 根级字段 ──────────────────────────────────────────────────────────
    # 后端补充字段
    TIME = span_attributes.TIME
    BK_BIZ_ID = span_attributes.BK_BIZ_ID
    APP_NAME = span_attributes.APP_NAME

    TRACE_ID = span_attributes.TRACE_ID
    TRACE_STATE = span_attributes.TRACE_STATE
    SPAN_NAME = span_attributes.SPAN_NAME
    SPAN_ID = span_attributes.SPAN_ID
    PARENT_SPAN_ID = span_attributes.PARENT_SPAN_ID
    KIND = span_attributes.KIND
    # 时间字段
    START_TIME = span_attributes.START_TIME
    END_TIME = span_attributes.END_TIME
    ELAPSED_TIME = span_attributes.ELAPSED_TIME

    # ── Web Vitals 虚拟字段（根级，非嵌套）────────────────────────────────────
    CLS = web_vitals.CLS
    INP = web_vitals.INP
    LCP = web_vitals.LCP
    FCP = web_vitals.FCP
    TTFB = web_vitals.TTFB

    # ── 复合字段 ───────────────────────────────────────────────────────────────
    STATUS = Status(field_name="status")
    RESOURCE = Resource(field_name="resource")
    EVENTS = Events(field_name="events")
    LINKS = Links(field_name="links")
    ATTRIBUTES = Attributes(field_name="attributes")

    @classmethod
    def from_field(cls, field_name: str) -> FieldSpec:
        """按完整路径查找字段描述符。

        :param field_name: 字段完整路径，如 ``"attributes.span_type"``、``"status.code"``。
        :return: 已注册的共享 ``FieldSpec`` 对象；未注册时返回仅含原始字段名的新 ``FieldSpec``。
        """
        return _SPAN_FIELDS.from_field(field_name)


# 模块级单例，延迟初始化避免循环导入
_SPAN_FIELDS = FieldRegistry(SpanSpec(field_name=""))
