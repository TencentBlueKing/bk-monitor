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

from django.utils.functional import cached_property

from apm.constants import KindCategory
from apm_web.constants import CategoryEnum, QueryMode, SPAN_SORTED_FIELD
from apm_web.handlers.es_handler import ESMappingHandler
from apm_web.handlers.trace_handler.query import TraceQueryTransformer
from apm_web.trace.constants import OPERATORS, TRACE_FIELD_ALIAS
from bkmonitor.utils.request import get_request_username
from constants.apm import PreCalculateSpecificField, SpanStandardField, PrecalculateStorageConfig
from core.drf_resource import api
from packages.apm_web.trace.constants import EnabledStatisticsDimension


class TraceFieldsInfoHandler:
    """trace 检索页面不同视角下的所有字段信息"""

    ES_MAPPING_API = api.apm_api.query_es_mapping

    # 预计算对象字段扩展信息
    TRACE_PRE_OBJECTS_FIELDS_EXTEND = {
        PreCalculateSpecificField.KIND_STATISTICS.value: {
            KindCategory.ASYNC: {"type": "integer"},
            KindCategory.SYNC: {"type": "integer"},
            KindCategory.INTERNAL: {"type": "integer"},
            KindCategory.UNSPECIFIED: {"type": "integer"},
        },
        PreCalculateSpecificField.CATEGORY_STATISTICS.value: {
            CategoryEnum.DB: {"type": "integer"},
            CategoryEnum.RPC: {"type": "integer"},
            CategoryEnum.HTTP: {"type": "integer"},
            CategoryEnum.OTHER: {"type": "integer"},
            CategoryEnum.MESSAGING: {"type": "integer"},
            CategoryEnum.ASYNC_BACKEND: {"type": "integer"},
        },
    }

    def __init__(self, bk_biz_id: int, app_name: str, username: str = ""):
        self.bk_biz_id = bk_biz_id
        self.app_name = app_name
        self.username = username or get_request_username()

    @property
    def es_mapping(self) -> dict:
        """获取 span 原始表的 es_mapping 的原始数据"""

        return self.ES_MAPPING_API(bk_biz_id=self.bk_biz_id, app_name=self.app_name)

    @cached_property
    def es_mapping_fields_info(self) -> dict[str, dict]:
        """获取 es_mapping 展开后的字典信息"""

        es_mapping_handler = ESMappingHandler(self.es_mapping)
        return es_mapping_handler.flatten_all_index_mapping_properties()

    @cached_property
    def pre_calculate_fields_info(self) -> dict[str, dict]:
        """获取预计算字段信息

        保持和 es_mapping_fields_info 一样的结构{field_name: {"type": ""}}
        """

        # 预计算的所有字段信息
        pre_storage_dict = {}
        for field_info in PrecalculateStorageConfig.TABLE_SCHEMA:
            pre_storage_dict[field_info["field_name"]] = dict(type=field_info.get("option", {}).get("es_type", ""))

        # 返回 search_fields 中的字段信息
        pre_calculate_fields_info = {}
        for field_name in PreCalculateSpecificField.search_fields():
            if field_name in self.TRACE_PRE_OBJECTS_FIELDS_EXTEND:
                for child_field, child_field_info in self.TRACE_PRE_OBJECTS_FIELDS_EXTEND[field_name].items():
                    pre_calculate_fields_info[f"{field_name}.{child_field}"] = copy.deepcopy(child_field_info)
            else:
                pre_calculate_fields_info[field_name] = pre_storage_dict.get(field_name, {})
        return pre_calculate_fields_info

    @property
    def trace_collections_fields_info(self) -> dict[str, dict]:
        """获取 trace collections 中可能存在的字段

        保持和 es_mapping_fields_info 一样的结构{field_name: {"type": ""}}
        """

        # 获取所有的标准字段名
        field_names = [standard_field.field for standard_field in SpanStandardField.COMMON_STANDARD_FIELDS]
        standard_fields_info = {}
        for field_name in field_names:
            if field_name in self.es_mapping_fields_info:
                standard_fields_info.setdefault(TraceQueryTransformer.to_pre_cal_field(field_name), {}).update(
                    self.es_mapping_fields_info[field_name]
                )
        return standard_fields_info

    def get_fields_info_by_mode(self, mode: QueryMode) -> dict[str, dict]:
        """根据不同的模式返回不同的字段信息"""

        fields_info = {}
        if mode == QueryMode.TRACE:
            fields_info.update(copy.deepcopy(self.pre_calculate_fields_info))
            fields_info.update(copy.deepcopy(self.trace_collections_fields_info))
        elif mode == QueryMode.SPAN:
            fields_info.update(copy.deepcopy(self.es_mapping_fields_info))
        return fields_info


class TraceFieldsHandler:
    """Trace 检索页面字段相关处理"""

    def __init__(self, bk_biz_id: int, app_name: str, username: str = ""):
        self.bk_biz_id = bk_biz_id
        self.app_name = app_name
        self.username = username or get_request_username()
        self.fields_info_handler = TraceFieldsInfoHandler(self.bk_biz_id, self.app_name)

    @cached_property
    def trace_fields_info(self) -> dict[str, dict]:
        """获取 trace 视角下可用的字段信息"""

        return self.fields_info_handler.get_fields_info_by_mode(QueryMode.TRACE)

    @cached_property
    def span_fields_info(self) -> dict[str, dict]:
        """获取 span 视角下可用的字段信息"""

        return self.fields_info_handler.get_fields_info_by_mode(QueryMode.SPAN)

    def is_searched(self, field_type: str) -> bool:
        """判断字段是否可以被查询"""

        return field_type not in {"object", "nested"}

    def is_dimensions(self, mode: QueryMode, field_name: str, field_type: str) -> bool:
        """判断字段是否可以用于聚合和获取枚举值"""

        if field_type in [dimension_type.value for dimension_type in EnabledStatisticsDimension]:
            if mode == QueryMode.TRACE:
                return field_name not in ["min_start_time", "max_end_time", "root_span_id", "trace_id"]
            elif mode == QueryMode.SPAN:
                return field_name not in ["time", "start_time", "end_time", "span_id", "trace_id"]
            else:
                return True
        return False

    def can_displayed(self, field_type: str) -> bool:
        """判断字段是否可以显示"""

        return field_type not in {"object", "nested"}

    def get_supported_operations(self, field_type: str) -> list[str]:
        """获取字段支持的运算符"""

        return OPERATORS.get(field_type, [])

    def get_field_alias(self, field_name: str) -> str:
        """获取字段别名"""
        field_name: str = TraceQueryTransformer.to_common_field(field_name)
        return TRACE_FIELD_ALIAS.get(field_name) or field_name

    def get_field_type(self, mode: QueryMode, field_name: str) -> str:
        """获取字段类型"""
        convert_keyword_fields = ["collections.kind"]
        if mode == QueryMode.TRACE and field_name in convert_keyword_fields:
            return EnabledStatisticsDimension.KEYWORD.value

        if mode == QueryMode.TRACE:
            fields_info = self.trace_fields_info
        else:
            fields_info = self.span_fields_info

        return fields_info.get(field_name, {}).get("type", "")

    def get_fields_info(self, mode: QueryMode, field_names: list[str]) -> list[dict]:
        """获取字段信息"""

        fields = []
        for field_name in field_names:
            field_type = self.get_field_type(mode, field_name)
            fields.append(
                dict(
                    name=field_name,
                    alias=self.get_field_alias(field_name),
                    type=field_type,
                    is_searched=self.is_searched(field_type),
                    is_dimensions=self.is_dimensions(mode, field_name, field_type),
                    can_displayed=self.can_displayed(field_type),
                    supported_operations=self.get_supported_operations(field_type),
                )
            )
        return fields

    def get_all_fields_names_by_mode(self, mode: QueryMode) -> list[str]:
        """获取 trace / span 视角下可用的所有字段名称"""

        field_names = []
        if mode == QueryMode.TRACE:
            field_names = list(self.trace_fields_info)
            # 尽可能顶层字段排前面，同层级按原有定义顺序不变
            field_names.sort(key=lambda field_name: "." in field_name)
        elif mode == QueryMode.SPAN:
            field_names = list(self.span_fields_info)
            # 去除 Span 协议中没有的字段（比如：监控内置字段、bkbase 内置字段等）
            field_names = [f for f in field_names if f.split(".")[0] in SPAN_SORTED_FIELD]
            field_names.sort(
                key=lambda field_name: (
                    # 顶层字段优先
                    "." in field_name,
                    # 顶层字段按给定的顺序排序
                    SPAN_SORTED_FIELD.index(field_name) if field_name in SPAN_SORTED_FIELD else 0,
                    # 非顶层字段按字母排序
                    field_name,
                )
            )
        return field_names

    def get_fields_by_mode(self, mode: QueryMode) -> list[dict]:
        """获取 trace / span 视角下可用的字段信息"""

        all_fields_names = self.get_all_fields_names_by_mode(mode)
        fields = self.get_fields_info(mode, all_fields_names)
        return fields
