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
from typing import Optional

from django.utils.functional import cached_property

from apm.core.discover.precalculation.storage import PrecalculateStorage
from apm_web.constants import (
    OPERATORS,
    TRACE_DEFAULT_CONFIG_CONTENT,
    TRACE_DEFAULT_CONFIG_NAME,
    TRACE_FIELD_ALIAS,
    QueryMode,
)
from apm_web.handlers.es_handler import ESMappingHandler
from apm_web.models.trace import (
    TraceDefaultConfigTemplate,
    TraceUserAppCustomConfig,
    TraceUserAppDefaultConfig,
)
from bkmonitor.utils.request import get_request_username
from constants.apm import PreCalculateSpecificField, SpanStandardField
from core.drf_resource import api


class TraceUserCustomConfigHandler:
    """负责处理 Tracing 检索页面用户自定义的配置信息"""

    def __init__(self, bk_biz_id: int, app_name: str, username: str = ""):
        self.bk_biz_id = bk_biz_id
        self.app_name = app_name
        self.username = username or get_request_username()

    @cached_property
    def user_custom_config_obj(self) -> TraceUserAppCustomConfig:
        """获取用户自定义的配置对象"""

        config_obj, created = TraceUserAppCustomConfig.objects.get_or_create(
            bk_biz_id=self.bk_biz_id, app_name=self.app_name, username=self.username
        )
        return config_obj

    def update_user_custom_config_obj(
        self, trace_config: Optional[dict] = None, span_config: Optional[dict] = None
    ) -> TraceUserAppCustomConfig:
        """更新或自动创建用户自定义的配置信息"""

        config_obj = self.get_user_custom_config_obj()

        # 如果都为 None，则不更新
        if trace_config is None and span_config is None:
            return config_obj

        config_obj.trace_config = config_obj.trace_config if trace_config is None else trace_config
        config_obj.span_config = config_obj.span_config if span_config is None else span_config
        config_obj.save()
        return config_obj


class TraceDefaultConfigHandler:
    """负责处理 Tracing 检索页面用户默认的配置信息"""

    def __init__(self, bk_biz_id: int, app_name: str, username: str = ""):
        self.bk_biz_id = bk_biz_id
        self.app_name = app_name
        self.username = username or get_request_username()

    def _get_global_config_template_obj(self) -> TraceDefaultConfigTemplate:
        """获取或创建默认的配置模板对象"""

        template_obj, created = TraceDefaultConfigTemplate.objects.get_or_create(
            name=TRACE_DEFAULT_CONFIG_NAME,
            defaults={
                "trace_config": TRACE_DEFAULT_CONFIG_CONTENT["trace_config"],
                "span_config": TRACE_DEFAULT_CONFIG_CONTENT["span_config"],
            },
        )
        return template_obj

    def _get_config_template_obj(self, config_id: int) -> TraceDefaultConfigTemplate:
        """获取配置的模板对象"""

        if config_id <= 0:
            return self._get_global_config_template_obj()

        template_obj = TraceDefaultConfigTemplate.objects.filter(id=config_id).first()
        template_obj = template_obj or self._get_global_config_template_obj()
        return template_obj

    @cached_property
    def default_config_template_obj(self) -> TraceDefaultConfigTemplate:
        """获取默认的配置信息"""

        default_config_obj, created = TraceUserAppDefaultConfig.objects.get_or_create(
            bk_biz_id=self.bk_biz_id,
            app_name=self.app_name,
            username=self.username,
        )
        template_obj = self._get_config_template_obj(default_config_obj.config_template_id)
        # 如果模板 id 和查询到的不一致，就重新赋值保存
        if default_config_obj.config_template_id != template_obj.id:
            default_config_obj.config_template_id = template_obj.id
            default_config_obj.save()
        return template_obj


class TraceFieldsHandler:
    ES_MAPPING_API = api.apm_api.query_es_mapping

    def __init__(self, bk_biz_id: int, app_name: str):
        self.bk_biz_id = bk_biz_id
        self.app_name = app_name

    @cached_property
    def es_mapping(self) -> dict:
        """获取 es_mapping"""

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
            pre_calculate_fields_info[field_name] = pre_storage_dict.get(field_name, {})
        return pre_calculate_fields_info

    @cached_property
    def es_mapping_standard_fields_info(self) -> dict[str, dict]:
        """获取 es_mapping 中的标准字段信息

        保持和 es_mapping_fields_info 一样的结构{field_name: {"type": ""}}
        """

        field_names = [standard_field.field for standard_field in SpanStandardField.COMMON_STANDARD_FIELDS]
        es_mapping_fields_info = self.es_mapping_fields_info
        standard_fields_info = {}
        for field_name in field_names:
            if field_name in es_mapping_fields_info:
                standard_fields_info[field_name] = es_mapping_fields_info[field_name]
        return standard_fields_info

    def is_searched(self, mode: QueryMode, field_name: str, field_type: str) -> bool:
        """判断字段是否可以被查询"""

        is_searched = False
        if mode == QueryMode.TRACE:
            is_searched = (
                field_name in self.pre_calculate_fields_info or field_name in self.es_mapping_standard_fields_info
            )
        elif mode == QueryMode.SPAN:
            is_searched = field_name in self.es_mapping_fields_info
        return is_searched and field_type not in {"object"}

    def is_option_enabled(self, is_searched: bool, field_type: str) -> bool:
        """判断字段是否可以用于筛选

        候选项的值不依赖于 is_searched，但是选择候选项后要考虑是否能触发搜索
        """

        return is_searched and field_type not in {"text", "object"}

    def is_dimensions(self, is_searched: bool, field_name: str) -> bool:
        """判断字段是否可以用于聚合

        因为聚合也需要获取搜索的过滤条件，所以也依赖于 is_searched
        """

        return is_searched

    def get_supported_operations(self, field_type: str) -> list[str]:
        """获取字段支持的运算符"""

        return OPERATORS.get(field_type, [])

    def get_field_alias(self, field_name: str) -> str:
        """获取字段别名"""

        return TRACE_FIELD_ALIAS.get(field_name, field_name)

    def get_field_type(self, field_name: str) -> str:
        """获取字段类型"""

        field_type = ""
        if field_name in self.es_mapping_fields_info:
            field_type = self.es_mapping_standard_fields_info.get(field_name, {}).get("type", "")
        elif field_name in self.pre_calculate_fields_info:
            field_type = self.pre_calculate_fields_info.get(field_name, {}).get("type", "")

        return field_type

    def get_fields_info(self, mode: QueryMode, field_names: list[str]) -> list[dict]:
        fields = []
        for field_name in field_names:
            field_type = self.get_field_type(field_name)
            is_searched = self.is_searched(mode, field_name, field_type)
            is_option_enabled = self.is_option_enabled(is_searched, field_type)
            is_dimensions = self.is_dimensions(is_searched, field_name)
            fields.append(
                dict(
                    name=field_name,
                    alias=self.get_field_alias(field_name),
                    type=field_type,
                    is_searched=is_searched,
                    is_option_enabled=is_option_enabled,
                    is_dimensions=is_dimensions,
                    supported_operations=self.get_supported_operations(field_name),
                )
            )
        return fields

    def get_all_field_names_by_mode(self, mode: QueryMode) -> list[str]:
        """获取 trace / span 视角下可用的所有字段名称"""

        all_field_names = []
        if mode == QueryMode.TRACE:
            # 预计算表可搜索的字段和存在于 es_mapping 中的标准字段取一个并集
            all_field_names.extend(list(self.pre_calculate_fields_info))
            all_field_names.extend(list(self.es_mapping_standard_fields_info))
        elif mode == QueryMode.SPAN:
            all_field_names = list(self.es_mapping_fields_info)
        return list(set(all_field_names))

    def get_fields_by_mode(self, mode: QueryMode) -> list[dict]:
        """获取 trace / span 视角下可用的字段信息"""

        all_field_names = self.get_all_field_names_by_mode(mode)
        fields = self.get_fields_info(mode, all_field_names)
        # 顶层字段排前面，二级排序按字母排序
        fields.sort(key=lambda field: ("." in field["name"], field["name"]))
        return fields


class TraceViewConfigManager:
    """Tracing 检索页面的视图配置信息，包含 trace 视角和 span 视角的配置信息

    例如表头显示字段，设置筛选字段等
    """

    def __init__(self, bk_biz_id: int, app_name: str, username: str = ""):
        self.bk_biz_id = bk_biz_id
        self.app_name = app_name
        self.username = username or get_request_username()
        self.default_config = TraceDefaultConfigHandler(bk_biz_id, app_name, username)
        self.user_config = TraceUserCustomConfigHandler(bk_biz_id, app_name, username)
        self.fields_handler = TraceFieldsHandler(bk_biz_id, app_name)

    def get_config_by_mode(self, mode: QueryMode) -> dict:
        """根据不同的视角获取不同的配置信息"""

        template_obj = self.default_config.default_config_template_obj
        user_custom_config_obj = self.user_config.user_custom_config_obj

        if mode == QueryMode.TRACE:
            default_config: dict = template_obj.trace_config
            custom_config: dict = user_custom_config_obj.trace_config
        elif mode == QueryMode.SPAN:
            default_config: dict = template_obj.span_config
            custom_config: dict = user_custom_config_obj.span_config

        else:
            return {}

        default_config.update(custom_config)
        default_config.update(
            {
                "user_custom_config": custom_config,
            }
        )
        return default_config
