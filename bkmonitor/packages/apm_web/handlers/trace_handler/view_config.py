# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - Resource SDK (BlueKing - Resource SDK) available.
Copyright (C) 2022 THL A29 Limited,
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
from apm.core.discover.precalculation.storage import PrecalculateStorage
from apm_web.constants import OPERATORS, TRACE_FIELD_ALIAS, CategoryEnum, QueryMode
from apm_web.handlers.es_handler import ESMappingHandler
from bkmonitor.utils.request import get_request_username
from constants.apm import PreCalculateSpecificField, SpanStandardField
from core.drf_resource import api


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
        for field_info in PrecalculateStorage.TABLE_SCHEMA:
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
                standard_fields_info[field_name] = self.es_mapping_fields_info[field_name]
        return standard_fields_info

    def get_fields_info_by_mode(self, mode: QueryMode) -> dict[str, dict]:
        """根据不同的模式返回不同的字段信息"""

        fields_info = {}
        if mode == QueryMode.TRACE:
            fields_info.update(copy.deepcopy(self.trace_collections_fields_info))
            fields_info.update(copy.deepcopy(self.pre_calculate_fields_info))
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

    def is_searched(self, mode: QueryMode, field_name: str, field_type: str) -> bool:
        """判断字段是否可以被查询"""

        is_searched = False
        if mode == QueryMode.TRACE:
            is_searched = field_name in self.trace_fields_info
        elif mode == QueryMode.SPAN:
            is_searched = field_name in self.span_fields_info
        return is_searched and field_type not in {"object"}

    def is_option_enabled(self, is_searched: bool, field_type: str) -> bool:
        """判断字段是否可以用于筛选

        候选项的值不依赖于 is_searched，但是选择候选项后要考虑是否能触发搜索
        """

        return is_searched and field_type not in {"object", "date"}

    def is_dimensions(self, is_searched: bool, field_name: str) -> bool:
        """判断字段是否可以用于聚合

        因为聚合也需要获取搜索的过滤条件，所以也依赖于 is_searched
        """

        return is_searched

    def can_displayed(self, mode: QueryMode, field_name: str, field_type: str) -> bool:
        """判断字段是否可以显示"""

        if field_type in {"object"}:
            return False

        can_display = False
        if mode == QueryMode.TRACE:
            can_display = field_name in self.trace_fields_info
        elif mode == QueryMode.SPAN:
            can_display = field_name in self.span_fields_info
        return can_display

    def get_supported_operations(self, field_type: str) -> list[str]:
        """获取字段支持的运算符"""

        return OPERATORS.get(field_type, [])

    def get_field_alias(self, field_name: str) -> str:
        """获取字段别名"""

        return TRACE_FIELD_ALIAS.get(field_name, field_name)

    def get_field_type(self, mode: QueryMode, field_name: str) -> str:
        """获取字段类型"""
        if mode == QueryMode.TRACE:
            fields_info = self.trace_fields_info
        else:
            fields_info = self.span_fields_info

        return fields_info.get(field_name, {}).get("type", "")

    def get_fields_info(self, mode: QueryMode, field_names: list[str]) -> list[dict]:
        fields = []
        for field_name in field_names:
            field_type = self.get_field_type(mode, field_name)
            is_searched = self.is_searched(mode, field_name, field_type)
            is_option_enabled = self.is_option_enabled(is_searched, field_type)
            is_dimensions = self.is_dimensions(is_searched, field_name)
            can_displayed = self.can_displayed(mode, field_name, field_type)
            fields.append(
                dict(
                    name=field_name,
                    alias=self.get_field_alias(field_name),
                    type=field_type,
                    is_searched=is_searched,
                    is_option_enabled=is_option_enabled,
                    is_dimensions=is_dimensions,
                    can_displayed=can_displayed,
                    supported_operations=self.get_supported_operations(field_type),
                )
            )
        return fields

    def get_all_fields_names_by_mode(self, mode: QueryMode) -> list[str]:
        """获取 trace / span 视角下可用的所有字段名称"""

        if mode == QueryMode.TRACE:
            return list(self.trace_fields_info)
        elif mode == QueryMode.SPAN:
            return list(self.span_fields_info)
        return []

    def get_fields_by_mode(self, mode: QueryMode) -> list[dict]:
        """获取 trace / span 视角下可用的字段信息"""

        all_fields_names = self.get_all_fields_names_by_mode(mode)
        fields = self.get_fields_info(mode, all_fields_names)
        # 顶层字段排前面，二级排序按字母排序
        fields.sort(key=lambda field: ("." in field["name"], field["name"]))
        return fields
