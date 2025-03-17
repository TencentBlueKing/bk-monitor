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
import abc
from typing import Optional

from apm_web.constants import TRACE_DEFAULT_CONFIG_CONTENT, TRACE_DEFAULT_CONFIG_NAME
from apm_web.models.trace import (
    TraceDefaultConfigTemplate,
    TraceUserAppCustomConfig,
    TraceUserAppDefaultConfig,
)
from bkmonitor.utils.request import get_request_username


class TraceUserCustomConfigHandler:
    """负责处理 Tracing 检索页面用户自定义的配置信息"""

    def __init__(self, bk_biz_id: int, app_name: str, username: str = ""):
        self.bk_biz_id = bk_biz_id
        self.app_name = app_name
        self.username = username or get_request_username()

    def get_user_custom_config_obj(self) -> TraceUserAppCustomConfig:
        """获取用户自定义的配置信息"""

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

    def get_default_config_template_obj(self) -> TraceDefaultConfigTemplate:
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


class TraceViewConfigManager:
    """Tracing 检索页面的视图配置信息，包含 trace 视角和 span 视角的配置信息

    例如表头显示字段，设置筛选字段等
    """

    def __init__(self, bk_biz_id: int, app_name: str, username: str = ""):
        self.user_config = TraceUserCustomConfigHandler(bk_biz_id, app_name, username)
        self.default_config = TraceDefaultConfigHandler(bk_biz_id, app_name, username)

    def get_config(self) -> dict:
        """将用户自定义配置和默认配置进行合并

        优先用户自定义配置
        """
        # 获取默认配置
        template_obj = self.default_config.get_default_config_template_obj()
        trace_default_config: dict = template_obj.trace_config
        span_default_config: dict = template_obj.span_config

        # 获取用户自定义配置
        user_custom_config_obj = self.user_config.get_user_custom_config_obj()
        trace_custom_config: dict = user_custom_config_obj.trace_config
        span_custom_config: dict = user_custom_config_obj.span_config

        # 覆盖默认配置字典的顶层配置
        trace_default_config.update(trace_custom_config)
        span_default_config.update(span_custom_config)
        return {
            "trace_config": trace_default_config,
            "span_config": span_default_config,
        }
