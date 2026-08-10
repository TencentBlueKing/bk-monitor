"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.utils.translation import gettext_lazy as _
from django.utils.functional import cached_property

from constants.elasticsearch import QueryStringOperators
from constants.apm import CachedEnum


OTEL_SPAN_COMMON_FIELD_ALIAS = {
    "elapsed_time": _("耗时"),
    "end_time": _("结束时间"),
    "kind": _("类型"),
    "links": _("关联信息"),
    "parent_span_id": _("父 Span ID"),
    "span_id": _("Span ID"),
    "span_name": _("接口名称"),
    "start_time": _("开始时间"),
    "time": _("时间"),
    "trace_id": _("Trace ID"),
    "trace_state": _("Trace 状态"),
}


class OperatorEnum:
    """操作符枚举"""

    class OperatorOptions:
        """操作符选项"""

        IS_WILDCARD = {"label": _("使用通配符"), "name": "is_wildcard", "default": False}
        GROUP_RELATION = {
            "label": _("组间关系"),
            "name": "group_relation",
            "default": "OR",
            "children": [
                {"label": "AND", "value": "AND"},
                {"label": "OR", "value": "OR"},
            ],
        }

    EXISTS = {"operator": "exists", "label": _("存在"), "placeholder": _("确认字段已存在")}
    NOT_EXISTS = {"operator": "not exists", "label": _("不存在"), "placeholder": _("确认字段不存在")}
    EQUAL = {"operator": "equal", "label": "=", "placeholder": _("请选择或直接输入，Enter分隔")}
    NOT_EQUAL = {"operator": "not_equal", "label": "!=", "placeholder": _("请选择或直接输入，Enter分隔")}
    LIKE = {"operator": "like", "label": _("包含"), "placeholder": _("请选择或直接输入，Enter分隔")}
    NOT_LIKE = {"operator": "not_like", "label": _("不包含"), "placeholder": _("请选择或直接输入，Enter分隔")}
    GT = {"operator": "gt", "label": ">", "placeholder": _("请选择或直接输入")}
    LT = {"operator": "lt", "label": "<", "placeholder": _("请选择或直接输入")}
    GTE = {"operator": "gte", "label": ">=", "placeholder": _("请选择或直接输入")}
    LTE = {"operator": "lte", "label": "<=", "placeholder": _("请选择或直接输入")}

    LIKE_WILDCARD = {
        "operator": "like",
        "label": _("包含"),
        "placeholder": _("请选择或直接输入，Enter分隔"),
        "options": [OperatorOptions.IS_WILDCARD, OperatorOptions.GROUP_RELATION],
    }
    NOT_LIKE_WOLDCARD = {
        "operator": "not_like",
        "label": _("不包含"),
        "placeholder": _("请选择或直接输入，Enter分隔"),
        "options": [OperatorOptions.IS_WILDCARD, OperatorOptions.GROUP_RELATION],
    }

    QueryStringOperatorMapping = {
        EXISTS["operator"]: QueryStringOperators.EXISTS,
        NOT_EXISTS["operator"]: QueryStringOperators.NOT_EXISTS,
        EQUAL["operator"]: QueryStringOperators.EQUAL,
        NOT_EQUAL["operator"]: QueryStringOperators.NOT_EQUAL,
        LIKE["operator"]: QueryStringOperators.INCLUDE,
        NOT_LIKE["operator"]: QueryStringOperators.NOT_INCLUDE,
        GT["operator"]: QueryStringOperators.GT,
        LT["operator"]: QueryStringOperators.LT,
        GTE["operator"]: QueryStringOperators.GTE,
        LTE["operator"]: QueryStringOperators.LTE,
        "between": QueryStringOperators.BETWEEN,
    }


class FieldTypeEnum(CachedEnum):
    """字段类型枚举"""

    KEYWORD = "keyword"
    TEXT = "text"
    INTEGER = "integer"
    LONG = "long"
    DOUBLE = "double"
    DATE = "date"
    BOOLEAN = "boolean"
    CONFLICT = "conflict"

    @cached_property
    def label(self) -> str:
        return str(
            {
                self.KEYWORD: _("keyword"),
                self.TEXT: _("text"),
                self.INTEGER: _("integer"),
                self.LONG: _("long"),
                self.DOUBLE: _("double"),
                self.DATE: _("date"),
                self.BOOLEAN: _("boolean"),
                self.CONFLICT: _("conflict"),
            }.get(self, self.value)
        )

    @classmethod
    def get_default(cls, value):
        default = super().get_default(value)
        default.label = value
        return default

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [
            (cls.KEYWORD.value, cls.KEYWORD.label),
            (cls.TEXT.value, cls.TEXT.label),
            (cls.INTEGER.value, cls.INTEGER.label),
            (cls.LONG.value, cls.LONG.label),
            (cls.DOUBLE.value, cls.DOUBLE.label),
            (cls.DATE.value, cls.DATE.label),
            (cls.BOOLEAN.value, cls.BOOLEAN.label),
            (cls.CONFLICT.value, cls.CONFLICT.label),
        ]


OTEL_FIELD_OPERATIONS = {
    FieldTypeEnum.KEYWORD.value: [
        OperatorEnum.EQUAL,
        OperatorEnum.NOT_EQUAL,
        OperatorEnum.EXISTS,
        OperatorEnum.NOT_EXISTS,
        OperatorEnum.LIKE,
        OperatorEnum.NOT_LIKE,
    ],
    FieldTypeEnum.TEXT.value: [
        OperatorEnum.EQUAL,
        OperatorEnum.NOT_EQUAL,
        OperatorEnum.LIKE_WILDCARD,
        OperatorEnum.NOT_LIKE_WOLDCARD,
        OperatorEnum.EXISTS,
        OperatorEnum.NOT_EXISTS,
    ],
    FieldTypeEnum.INTEGER.value: [
        OperatorEnum.EQUAL,
        OperatorEnum.NOT_EQUAL,
        OperatorEnum.GT,
        OperatorEnum.GTE,
        OperatorEnum.LT,
        OperatorEnum.LTE,
        OperatorEnum.EXISTS,
        OperatorEnum.NOT_EXISTS,
    ],
    FieldTypeEnum.LONG.value: [
        OperatorEnum.EQUAL,
        OperatorEnum.NOT_EQUAL,
        OperatorEnum.GT,
        OperatorEnum.GTE,
        OperatorEnum.LT,
        OperatorEnum.LTE,
        OperatorEnum.EXISTS,
        OperatorEnum.NOT_EXISTS,
    ],
    FieldTypeEnum.DOUBLE.value: [
        OperatorEnum.EQUAL,
        OperatorEnum.NOT_EQUAL,
        OperatorEnum.GT,
        OperatorEnum.GTE,
        OperatorEnum.LT,
        OperatorEnum.LTE,
        OperatorEnum.EXISTS,
        OperatorEnum.NOT_EXISTS,
    ],
    FieldTypeEnum.DATE.value: [
        OperatorEnum.EQUAL,
        OperatorEnum.NOT_EQUAL,
        OperatorEnum.GT,
        OperatorEnum.GTE,
        OperatorEnum.LT,
        OperatorEnum.LTE,
        OperatorEnum.EXISTS,
        OperatorEnum.NOT_EXISTS,
    ],
    FieldTypeEnum.BOOLEAN.value: [
        OperatorEnum.EQUAL,
        OperatorEnum.NOT_EQUAL,
        OperatorEnum.EXISTS,
        OperatorEnum.NOT_EXISTS,
    ],
    FieldTypeEnum.CONFLICT.value: [
        OperatorEnum.EQUAL,
        OperatorEnum.NOT_EQUAL,
        OperatorEnum.GT,
        OperatorEnum.GTE,
        OperatorEnum.LT,
        OperatorEnum.LTE,
        OperatorEnum.EXISTS,
        OperatorEnum.NOT_EXISTS,
    ],
}
