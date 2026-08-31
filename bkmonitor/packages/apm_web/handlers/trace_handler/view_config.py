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

import copy
from functools import cached_property
from typing import Any

from apm.constants import KindCategory
from apm_web.constants import CategoryEnum, QueryMode, SPAN_SORTED_FIELD
from apm_web.handlers.query import get_query
from apm_web.handlers.query.span import SpanQuery
from apm_web.handlers.trace_handler.query import TraceQueryTransformer
from apm_web.models import Application
from constants.apm import PreCalculateSpecificField, SpanStandardField, PrecalculateStorageConfig, OtlpKey
from constants.otel_query import FIELD_OPERATIONS, EnabledStatisticsDimension

NON_SEARCHABLE_FIELD_TYPES = {"object", "nested"}
DIMENSION_FIELD_TYPES = {dimension.value for dimension in EnabledStatisticsDimension}
TRACE_NON_DIMENSION_FIELDS = {
    PreCalculateSpecificField.MIN_START_TIME.value,
    PreCalculateSpecificField.MAX_END_TIME.value,
    PreCalculateSpecificField.ROOT_SPAN_ID.value,
    PreCalculateSpecificField.TRACE_ID.value,
}
SPAN_NON_DIMENSION_FIELDS = {
    PreCalculateSpecificField.TIME.value,
    OtlpKey.START_TIME,
    OtlpKey.END_TIME,
    OtlpKey.SPAN_ID,
    OtlpKey.TRACE_ID,
}
SPAN_SORTED_FIELD_INDEX_MAP = {field_name: index for index, field_name in enumerate(SPAN_SORTED_FIELD)}


class TraceFieldsInfoHandler:
    """trace 检索页面不同视角下的所有字段信息"""

    # 预计算对象字段扩展信息
    TRACE_PRE_OBJECTS_FIELDS_EXTEND = {
        PreCalculateSpecificField.KIND_STATISTICS.value: {
            KindCategory.ASYNC: {"field_type": "integer"},
            KindCategory.SYNC: {"field_type": "integer"},
            KindCategory.INTERNAL: {"field_type": "integer"},
            KindCategory.UNSPECIFIED: {"field_type": "integer"},
        },
        PreCalculateSpecificField.CATEGORY_STATISTICS.value: {
            CategoryEnum.DB: {"field_type": "integer"},
            CategoryEnum.RPC: {"field_type": "integer"},
            CategoryEnum.HTTP: {"field_type": "integer"},
            CategoryEnum.OTHER: {"field_type": "integer"},
            CategoryEnum.MESSAGING: {"field_type": "integer"},
            CategoryEnum.ASYNC_BACKEND: {"field_type": "integer"},
        },
    }

    def __init__(self, bk_biz_id: int, app_name: str):
        self.bk_biz_id = bk_biz_id
        self.app_name = app_name

    @cached_property
    def application(self) -> Application:
        return Application.objects.get(bk_biz_id=self.bk_biz_id, app_name=self.app_name)

    @cached_property
    def span_fields_info(self) -> dict[str, dict[str, Any]]:
        """通过 unify-query 获取 Span 原始表的字段信息。"""

        return get_query(self.application.build_data_sources()).query_fields(None, None)

    @staticmethod
    def _build_static_field_info(field_type: str) -> dict[str, Any]:
        """为非 UQ 来源的 Trace 预计算字段补齐展示元数据。"""

        is_searchable = field_type not in NON_SEARCHABLE_FIELD_TYPES
        return {
            "field_type": field_type,
            "is_searchable": is_searchable,
            "is_list": is_searchable,
            "supported_operations": FIELD_OPERATIONS.get(field_type, []),
        }

    @cached_property
    def pre_calculate_fields_info(self) -> dict[str, dict[str, Any]]:
        """获取预计算字段信息

        补齐 view_config 所需的字段元数据。
        """

        # 预计算的所有字段信息
        pre_storage_field_types: dict[str, str] = {}
        for field_info in PrecalculateStorageConfig.TABLE_SCHEMA:
            pre_storage_field_types[field_info["field_name"]] = field_info.get("option", {}).get("es_type", "")

        # 返回 search_fields 中的字段信息
        pre_calculate_fields_info: dict[str, dict[str, Any]] = {}
        for field_name in PreCalculateSpecificField.search_fields():
            if field_name is None:
                continue
            if field_name in self.TRACE_PRE_OBJECTS_FIELDS_EXTEND:
                for child_field, child_field_info in self.TRACE_PRE_OBJECTS_FIELDS_EXTEND[field_name].items():
                    child_field_name = f"{field_name}.{child_field}"
                    pre_calculate_fields_info[child_field_name] = self._build_static_field_info(
                        child_field_info["field_type"]
                    )
            else:
                pre_calculate_fields_info[field_name] = self._build_static_field_info(
                    pre_storage_field_types.get(field_name, "")
                )
        return pre_calculate_fields_info

    @property
    def trace_collections_fields_info(self) -> dict[str, dict[str, Any]]:
        """获取 trace collections 中可能存在的字段

        从 span_fields_info 提取 view_config 所需的字段元数据。
        """

        # 获取所有的标准字段名
        field_names = [standard_field.field for standard_field in SpanStandardField.COMMON_STANDARD_FIELDS]
        span_fields_info = self.span_fields_info
        standard_fields_info: dict[str, dict[str, Any]] = {}
        for field_name in field_names:
            if field_name in span_fields_info:
                trace_field_name = TraceQueryTransformer.to_pre_cal_field(field_name)
                if trace_field_name == "collections.kind":
                    standard_fields_info[trace_field_name] = self._build_static_field_info(
                        EnabledStatisticsDimension.KEYWORD.value
                    )
                    continue

                span_field_info = span_fields_info[field_name]
                standard_fields_info[trace_field_name] = {
                    key: span_field_info[key]
                    for key in ("field_type", "is_searchable", "is_list", "supported_operations")
                }
        return standard_fields_info

    def get_fields_info_by_mode(self, mode: str) -> dict[str, dict[str, Any]]:
        """根据不同的模式返回不同的字段信息"""

        fields_info: dict[str, dict[str, Any]] = {}
        if mode == QueryMode.TRACE:
            fields_info.update(copy.deepcopy(self.pre_calculate_fields_info))
            fields_info.update(copy.deepcopy(self.trace_collections_fields_info))
        elif mode == QueryMode.SPAN:
            fields_info.update(copy.deepcopy(self.span_fields_info))
        return fields_info


class TraceFieldsHandler:
    """Trace 检索页面字段相关处理"""

    FIELD_ALIAS_MAP_LIST: list[dict[str, Any]] = SpanQuery.FIELD_ALIAS_MAP_LIST

    def __init__(self, bk_biz_id: int, app_name: str):
        self.bk_biz_id = bk_biz_id
        self.app_name = app_name
        self.fields_info_handler = TraceFieldsInfoHandler(self.bk_biz_id, self.app_name)

    @cached_property
    def trace_fields_info(self) -> dict[str, dict[str, Any]]:
        """获取 trace 视角下可用的字段信息"""

        return self.fields_info_handler.get_fields_info_by_mode(QueryMode.TRACE)

    @cached_property
    def span_fields_info(self) -> dict[str, dict[str, Any]]:
        """获取 span 视角下可用的字段信息"""

        return self.fields_info_handler.get_fields_info_by_mode(QueryMode.SPAN)

    def get_field_alias(self, field_name: str) -> str:
        """获取字段别名"""
        field_name = TraceQueryTransformer.to_common_field(field_name)
        for mapping in reversed(self.FIELD_ALIAS_MAP_LIST):
            if field_name in mapping:
                return mapping[field_name] or field_name
        return field_name

    @staticmethod
    def is_dimensions(mode: str, field_name: str, field_type: str) -> bool:
        """判断字段是否支持当前查询视角的统计分析。"""

        if field_type not in DIMENSION_FIELD_TYPES:
            return False
        if mode == QueryMode.TRACE:
            return field_name not in TRACE_NON_DIMENSION_FIELDS
        if mode == QueryMode.SPAN:
            return field_name not in SPAN_NON_DIMENSION_FIELDS
        return True

    def get_fields_info(self, mode: str, field_names: list[str]) -> list[dict[str, Any]]:
        """获取字段信息"""

        fields_info = self.trace_fields_info if mode == QueryMode.TRACE else self.span_fields_info
        fields: list[dict[str, Any]] = []
        for field_name in field_names:
            field_info = fields_info[field_name]
            fields.append(
                dict(
                    name=field_name,
                    alias=self.get_field_alias(field_name),
                    type=field_info["field_type"],
                    is_searched=field_info["is_searchable"],
                    is_dimensions=self.is_dimensions(mode, field_name, field_info["field_type"]),
                    can_displayed=field_info["is_list"],
                    supported_operations=field_info["supported_operations"],
                )
            )
        return fields

    def get_all_fields_names_by_mode(self, mode: str) -> list[str]:
        """获取 trace / span 视角下可用的所有字段名称"""

        field_names = []
        if mode == QueryMode.TRACE:
            field_names = list(self.trace_fields_info)
            # 尽可能顶层字段排前面，同层级按原有定义顺序不变
            field_names.sort(key=lambda field_name: "." in field_name)
        elif mode == QueryMode.SPAN:
            # 去除 Span 协议外的字段，以及旧 ES mapping 展开逻辑不会返回的 object / nested 字段。
            span_fields_info = self.span_fields_info
            field_names = [
                field_name
                for field_name, field_info in span_fields_info.items()
                if field_name.split(".")[0] in SPAN_SORTED_FIELD and field_info["is_searchable"]
            ]
            field_names.sort(
                key=lambda field_name: (
                    # 顶层字段优先
                    "." in field_name,
                    # 顶层字段按给定的顺序排序
                    SPAN_SORTED_FIELD_INDEX_MAP.get(field_name, 0),
                    # 非顶层字段按字母排序
                    field_name,
                )
            )
        return field_names

    def get_fields_by_mode(self, mode: str) -> list[dict[str, Any]]:
        """获取 trace / span 视角下可用的字段信息"""

        all_fields_names = self.get_all_fields_names_by_mode(mode)
        fields = self.get_fields_info(mode, all_fields_names)
        return fields
