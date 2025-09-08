"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - Resource SDK (BlueKing - Resource SDK) available.
Copyright (C) 2017-2025 Tencent,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import html
import logging
import re
from dataclasses import dataclass
from typing import Any
from collections.abc import Callable

from django.utils.translation import gettext_lazy as _
from luqum.auto_head_tail import auto_head_tail
from luqum.elasticsearch import ElasticsearchQueryBuilder
from luqum.exceptions import ParseError
from luqum.parser import lexer, parser
from luqum.tree import SearchField, Word
from luqum.visitor import TreeTransformer
from opentelemetry.trace import StatusCode

from apm_web.constants import CategoryEnum, QueryMode
from apm_web.handlers.trace_handler.base import (
    SpanPredicate,
    StatusCodeAttributePredicate,
)
from bkmonitor.utils.elasticsearch.handler import BaseTreeTransformer
from constants.apm import (
    OtlpKey,
    PreCalculateSpecificField,
    SpanKind,
    SpanStandardField,
    StandardField,
    ValueSource,
)
from core.drf_resource import api
from core.errors.alert import QueryStringParseError

logger = logging.getLogger(__name__)


class QueryStringBuilder:
    WILDCARD_PATTERN: str = "*"

    # Refer: https://opentelemetry.io/docs/specs/otel/trace/api/#retrieving-the-traceid-and-spanid
    # TraceId must be a 32-hex-character lowercase string
    # Add possible spaces and quotes.
    # Add possible field prefixes like `trace_id: xxx`.
    TRACE_ID_PATTERN = re.compile(r"^\s*[\"']?(?:trace_id\s*:\s*)?\s*[\"']?\s*([0-9a-f]{32})\s*[\"']?\s*[\"']?$")

    # SpanId must be a 16-hex-character lowercase string
    SPAN_ID_PATTERN = re.compile(r"^\s*[\"']?(?:span_id\s*:\s*)?\s*[\"']?\s*([0-9a-f]{16})\s*[\"']?\s*[\"']?$")

    NO_KEYWORD_QUERY_PATTERN = re.compile(r"[+\-=&|><!(){}\[\]^\"~*?:/]|AND|OR|TO|NOT|^\d+$")

    def __init__(self, query_string: str):
        self._query_string: str = query_string.strip()
        # 预测字段，用于增强检索。
        self._predicted_field: str = ""

    @property
    def query_string(self):
        return self.special_check(self.html_unescape(self._query_string))

    @property
    def predicted_query_string(self):
        query_string: str = self.query_string
        if not self._predicted_field:
            return query_string
        return f"{self._predicted_field}: {query_string}"

    def html_unescape(self, query_string: str) -> str:
        """html 转码"""
        if query_string:
            return html.unescape(query_string)
        return ""

    @classmethod
    def _is_trace_id(cls, query_string: str) -> bool:
        return cls.TRACE_ID_PATTERN.search(query_string) is not None

    @classmethod
    def extract_keyword(cls, pattern: re.Pattern, query_string: str) -> str:
        """提取关键字"""
        match: re.Match = pattern.search(query_string)
        if match:
            return match.group(1)
        return ""

    @classmethod
    def _is_span_id(cls, query_string: str):
        return cls.SPAN_ID_PATTERN.search(query_string) is not None

    @classmethod
    def extract_span_id(cls, query_string: str) -> str:
        return cls.extract_keyword(cls.SPAN_ID_PATTERN, query_string)

    @classmethod
    def extract_trace_id(cls, query_string: str) -> str:
        return cls.extract_keyword(cls.TRACE_ID_PATTERN, query_string)

    @classmethod
    def extract(cls, extract_funcs: dict[str, Callable[[str], str]], query_string: str) -> tuple[str, str]:
        """提取查询语句中的关键字和预测字段"""
        for predicted_field, extract_func in extract_funcs.items():
            keyword: str = extract_func(query_string)
            if keyword:
                return predicted_field, keyword
        return "", query_string

    def special_check(self, query_string: str) -> str:
        """特殊字符检查"""
        if query_string.strip() == "":
            return self.WILDCARD_PATTERN

        # TraceID & SpanID 直接走精确查询
        extract_funcs: dict[str, Callable[[str], str]] = {
            OtlpKey.SPAN_ID: self.extract_span_id,
            OtlpKey.TRACE_ID: self.extract_trace_id,
        }
        predicted_field, keyword = self.extract(extract_funcs, query_string)
        if predicted_field:
            self._predicted_field = predicted_field
            return f'"{keyword}"'

        if self.NO_KEYWORD_QUERY_PATTERN.search(query_string):
            return query_string

        # 关键字匹配加上通配符，解决页面检索 ${keyword} 被加上双引号当成精确查询的问题
        return f"{self.WILDCARD_PATTERN}{query_string}{self.WILDCARD_PATTERN}"


class QueryBuilder(ElasticsearchQueryBuilder):
    """
    Elasticsearch query_string 到 DSL 转换器
    """

    def _yield_nested_children(self, parent, children):
        yield from children


class QueryTreeTransformer(BaseTreeTransformer):
    # 需要进行值转换的字段
    VALUE_TRANSLATE_FIELDS = {}

    DOC_SCHEMA = {}

    def __init__(self, bk_biz_id, app_name):
        self.bk_biz_id = bk_biz_id
        self.app_name = app_name
        super().__init__()

    @classmethod
    def get_doc_schema(cls):
        return

    @classmethod
    def transform_field_to_es_field(cls, field: str, for_agg=False):
        return field

    @classmethod
    def transform_value_with_search_field(cls, value: str) -> str:
        return QueryStringBuilder(value).query_string

    @classmethod
    def transform_value_without_search_field(cls, value: str) -> str:
        # 语法子树为未指定 Field 的模糊检索，增加预测的 Field，提高查询效率。
        return QueryStringBuilder(value).predicted_query_string

    def visit_search_field(self, node, context):
        if context.get("ignore_search_field"):
            yield from self.generic_visit(node, context)
        else:
            origin_node_name = node.name
            node = SearchField(self.transform_field_to_es_field(node.name), node.expr)
            yield from self.generic_visit(
                node, {"search_field_name": node.name, "search_field_origin_name": origin_node_name}
            )

    def generate_query(self, query_string: str) -> str:
        if not query_string:
            return ""

        # 如果直接命中 TraceID / SpanID 检索，无需解析语法树，避免 "trace_id: "xx"" 语法树误识别为多层的问题。
        extract_funcs: dict[str, Callable[[str], str]] = {
            OtlpKey.SPAN_ID: QueryStringBuilder.extract_span_id,
            OtlpKey.TRACE_ID: QueryStringBuilder.extract_trace_id,
        }
        predicted_field, keyword = QueryStringBuilder.extract(extract_funcs, query_string)
        if predicted_field:
            return f'{predicted_field}: "{keyword}"'

        try:
            query_tree = parser.parse(query_string, lexer=lexer)
        except ParseError as e:
            raise QueryStringParseError({"msg": e})

        if str(query_tree) == "*":
            # 如果只有一个* es特殊符号不需要作为字符串处理
            return "*"

        transformer = self.__class__(self.bk_biz_id, self.app_name)
        query_tree = transformer.visit(query_tree)

        # 手动修改后的语法数可能会有一些空格丢失的问题，因此需要对树的头尾进行重整
        query_tree = auto_head_tail(query_tree)

        return QueryStringBuilder(str(query_tree)).predicted_query_string


class SpanQueryTransformer(QueryTreeTransformer):
    pass


class TraceQueryTransformer(QueryTreeTransformer):
    PRE_CALC_STANDARD_FIELD_PREFIX = "collections"

    DIRECT_FIELD_NAME_MAPPING = {
        "span_name": f"{PRE_CALC_STANDARD_FIELD_PREFIX}.span_name",
        "kind": f"{PRE_CALC_STANDARD_FIELD_PREFIX}.kind",
    }

    @classmethod
    def to_common_field(cls, field: str) -> str:
        """去掉前缀，转为标准字段"""
        if field.startswith(f"{cls.PRE_CALC_STANDARD_FIELD_PREFIX}."):
            return field[len(cls.PRE_CALC_STANDARD_FIELD_PREFIX) + 1 :]
        return field

    @classmethod
    def to_pre_cal_field(cls, field: str) -> str:
        """转换为预字段的字段"""
        if field in cls.DIRECT_FIELD_NAME_MAPPING:
            return cls.DIRECT_FIELD_NAME_MAPPING[field]

        # attribute, resource 也需要转换
        if field.startswith(OtlpKey.ATTRIBUTES) or field.startswith(OtlpKey.RESOURCE):
            return f"{cls.PRE_CALC_STANDARD_FIELD_PREFIX}.{field}"

        return field

    @classmethod
    def transform_field_to_es_field(cls, field: str, for_agg=False):
        return cls.to_pre_cal_field(field)


class FieldTransformer(TreeTransformer):
    # 如果filters包含这个字段 需要忽略 因为duration字段在TRACE/span检索中有特殊处理
    FILTERS_IGNORE_FIELDS = ["duration"]

    def __init__(self, fields, opposite=False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_has_field_not_in_fields = False
        self.fields = fields
        self.opposite = opposite

    def visit_search_field(self, node, _):
        name = TraceQueryTransformer.to_common_field(node.name)
        if not self.opposite:
            if name not in self.fields:
                self.is_has_field_not_in_fields = True
        else:
            if name in self.fields:
                self.is_has_field_not_in_fields = True

        yield node

    def has_file_not_in_filters(self, filters):
        all_fields = self.FILTERS_IGNORE_FIELDS + self.fields

        for i in filters:
            key: str = TraceQueryTransformer.to_common_field(i["key"])
            if not self.opposite:
                if key not in all_fields:
                    return True
            else:
                if key in all_fields:
                    return True
        return False


class OptionValues:
    FIELDS: list["Field"] = []
    API = None
    STANDARD_FIELD_MAPPING: dict[str, StandardField] = {
        field_info.field: field_info for field_info in SpanStandardField.COMMON_STANDARD_FIELDS
    }

    @dataclass
    class Field:
        # 需要获取候选值的字段
        id: str
        value_source: str
        label: str

    def __init__(self, bk_biz_id, app_name):
        self.bk_biz_id = bk_biz_id
        self.app_name = app_name

    def _get_option_values_from_method(self, fields: list[str]) -> dict[str, list[dict[str, Any]]]:
        option_values: dict[str, list[dict[str, Any]]] = {}
        for field in fields:
            option_values[field] = getattr(self, f"get_{field.replace('.', '_')}")()
        return option_values

    def _get_option_values_from_api(
        self,
        value_source: str,
        fields: list[str],
        start_time: int,
        end_time: int,
        filters: list,
        query_string: str,
        limit: int,
    ) -> dict[str, list[dict[str, Any]]]:
        field_transformer: Callable[[str], str] = {
            ValueSource.TRACE: self._transform_field_to_log_field,
            ValueSource.METRIC: self._transform_field_to_metric_field,
        }[value_source]

        field_mapping: dict[str, str] = {}
        query_api_fields: list[str, str] = []
        for field in fields:
            api_field: str = field_transformer(field)
            field_mapping[api_field] = field
            query_api_fields.append(api_field)

        params = {
            "bk_biz_id": self.bk_biz_id,
            "app_name": self.app_name,
            "start_time": start_time,
            "end_time": end_time,
            "fields": query_api_fields,
            "datasource_type": value_source,
            "filters": filters,
            "query_string": query_string,
            "limit": limit,
        }
        field_values_mapping: dict[str, list[Any]] = self.API(params)

        option_values: dict[str, list[dict[str, Any]]] = {}
        for api_field, field in field_mapping.items():
            option_values[field] = [{"value": val, "text": val} for val in field_values_mapping.get(api_field) or []]

        return option_values

    @classmethod
    def _transform_field_to_log_field(cls, field: str) -> str:
        return field

    @classmethod
    def _transform_field_to_metric_field(cls, field: str) -> str:
        field_info: StandardField | None = cls.STANDARD_FIELD_MAPPING.get(field)
        if field_info is not None and field_info.value_source == ValueSource.METRIC:
            return field_info.metric_dimension
        return field

    @classmethod
    def _get_value_source_fields(
        cls, fields: list[str], filters: list[dict[str, str]] | None = None, query_string: str = ""
    ) -> dict[str, list[str]]:
        source_fields: dict[str, list[str]] = {}
        field_mapping: dict[str, OptionValues.Field] = cls._get_field_mapping()
        for field in fields:
            if field in field_mapping:
                value_source: str = field_mapping[field].value_source
            else:
                # 默认通过 Trace 数据获取
                value_source: str = ValueSource.TRACE
            source_fields.setdefault(value_source, []).append(field)

        # 如果有过滤条件，value_source 统一都走trace，因为目前指标数据源不支持模糊检索
        if filters or (query_string not in ["", "*"]):
            source_fields.setdefault(ValueSource.TRACE, []).extend(source_fields.pop(ValueSource.METRIC, []))
        return source_fields

    @classmethod
    def _get_field_mapping(cls) -> dict[str, Field]:
        return {field_info.id: field_info for field_info in cls.FIELDS}

    def get_fields_option_values(
        self,
        fields: list[str],
        start_time: int,
        end_time: int,
        filters: list[dict[str, str]],
        query_string: str,
        limit: int,
    ) -> dict[str, list[dict[str, Any]]]:
        option_values: dict[str, list[dict[str, Any]]] = {}
        value_source_fields: dict[str, list[str]] = self._get_value_source_fields(
            fields, filters=filters, query_string=query_string
        )
        for value_source, fields in value_source_fields.items():
            if value_source == ValueSource.METHOD:
                option_values.update(self._get_option_values_from_method(fields))
            else:
                option_values.update(
                    self._get_option_values_from_api(
                        value_source, fields, start_time, end_time, filters, query_string, limit
                    )
                )
        return option_values

    def get_kind(self):
        return SpanKind.list()

    def get_status_code(self):
        return [
            {"value": StatusCode.UNSET.value, "text": _("未设置")},
            {"value": StatusCode.OK.value, "text": _("正常")},
            {"value": StatusCode.ERROR.value, "text": _("异常")},
        ]


class TraceOptionValues(OptionValues):
    API = api.apm_api.query_trace_option_values

    FIELDS = [
        OptionValues.Field(id="root_service_category", value_source=ValueSource.METHOD, label=_("入口类型")),
        OptionValues.Field(id="root_service_kind", value_source=ValueSource.METHOD, label=_("入口服务类型")),
        OptionValues.Field(id="root_span_kind", value_source=ValueSource.METHOD, label=_("根 Span 类型")),
    ] + [
        OptionValues.Field(id=field_info.field, value_source=field_info.value_source, label=field_info.value)
        for field_info in SpanStandardField.COMMON_STANDARD_FIELDS
    ]

    @classmethod
    def _transform_field_to_log_field(cls, field: str) -> str:
        if field in PreCalculateSpecificField.search_fields():
            return field
        if field.startswith(TraceQueryTransformer.PRE_CALC_STANDARD_FIELD_PREFIX):
            return field
        return f"{TraceQueryTransformer.PRE_CALC_STANDARD_FIELD_PREFIX}.{field}"

    def get_root_service_category(self):
        res = []
        for i in CategoryEnum.get_filter_fields():
            if i["id"] == CategoryEnum.ALL:
                continue
            res.append({"value": i["id"], "text": i["name"]})

        return res

    def get_root_service_kind(self):
        return SpanKind.list()

    def get_root_span_kind(self):
        return SpanKind.list()


class SpanOptionValues(OptionValues):
    API = api.apm_api.query_span_option_values

    FIELDS = [
        OptionValues.Field(id=field_info.field, value_source=field_info.value_source, label=field_info.value)
        for field_info in SpanStandardField.COMMON_STANDARD_FIELDS
    ]


class QueryHandler:
    """查询语句处理"""

    @classmethod
    def process_query_string(cls, transformer: QueryTreeTransformer, query_string: str | None) -> str | None:
        if not query_string:
            return ""
        return transformer.generate_query(query_string)

    @classmethod
    def has_field_not_in_fields_in_query(cls, query, fields, opposite):
        """判断查询语句中是否包含非标准字段"""

        tree = parser.parse(query, lexer=lexer)
        if isinstance(tree, Word):
            return False

        transformer = FieldTransformer(fields, opposite)
        transformer.visit(tree)
        return transformer.is_has_field_not_in_fields

    @classmethod
    def has_field_not_in_fields(cls, query, filters, fields, opposite=False):
        """判断query和filters中是否有key在fields里面"""
        if query:
            is_query_contain = cls.has_field_not_in_fields_in_query(query, fields, opposite)
            if is_query_contain:
                return is_query_contain

        return FieldTransformer(fields, opposite).has_file_not_in_filters(filters)

    @classmethod
    def query_option_values(cls, mode, bk_biz_id, app_name, start_time, end_time):
        if mode == QueryMode.TRACE:
            option = TraceOptionValues(bk_biz_id, app_name)
        else:
            option = SpanOptionValues(bk_biz_id, app_name)

        return option.get_option_values(start_time, end_time)

    @classmethod
    def get_file_option_values(cls, bk_biz_id, app_name, fields, start_time, end_time, mode):
        if mode == "pre_calculate":
            # 使用预计算表查询 -> 补充前缀collections
            option = TraceOptionValues(bk_biz_id, app_name)
        else:
            option = SpanOptionValues(bk_biz_id, app_name)

        return option.get_fields_option_values(fields, start_time, end_time, filters=[], query_string="", limit=500)

    @classmethod
    def get_fields_option_values(
        cls, bk_biz_id, app_name, fields, start_time, end_time, limit, filters, query_string, mode
    ):
        if mode == QueryMode.TRACE:
            option = TraceOptionValues(bk_biz_id, app_name)
        else:
            option = SpanOptionValues(bk_biz_id, app_name)

        return option.get_fields_option_values(fields, start_time, end_time, filters, query_string, limit)

    @classmethod
    def handle_trace_list(cls, trace_list):
        """对API返回的Trace列表进行额外处理"""
        for i in trace_list:
            i["root_service_status_code"] = StatusCodeAttributePredicate.predicate_error(
                i["root_service_category"], i.get("root_service_status_code")
            )
            i["root_service_category"] = {
                "text": CategoryEnum.get_label_by_key(i["root_service_category"]),
                "value": i["root_service_category"],
            }

    @classmethod
    def handle_span_list(cls, span_list):
        """对API返回的Span列表进行额外处理"""
        for i in span_list:
            i["status_code"] = SpanPredicate.predicate_status_code(i)
