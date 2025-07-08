"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
import os
import typing

from jinja2 import FileSystemLoader, Template

from jinja2.sandbox import SandboxedEnvironment as Environment

from .context_manager.base import FieldManager, ScopeType
from .plugin import LanguageEnum


class Help:
    help_md_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "help_md_new")

    def __init__(self, context: dict[str, typing.Any]):
        self.env: Environment = Environment(loader=FileSystemLoader(searchpath=self.help_md_path))
        self.context: dict[str, str] = context
        self.context.update(FieldManager.get_context(ScopeType.OPEN.value))

    def get_help_md(self, plugin_id: str, language: str, deployment_id: str) -> str:
        context: dict[str, typing.Any] = copy.deepcopy(self.context)
        if language == LanguageEnum.GOLANG.id:
            # Go OTLP SDK 不能传 schema，OT SDK 设计如此，所以引导也不加
            context["access_config"]["otlp"]["endpoint"] = context["access_config"]["otlp"]["endpoint"].replace(
                "http://", ""
            )
            context["access_config"]["otlp"]["http_endpoint"] = context["access_config"]["otlp"][
                "http_endpoint"
            ].replace("http://", "")

        rendered_context: dict[str, str] = {}
        for field, val in context.items():
            if isinstance(val, str):
                # 对 string 字段先渲染一遍
                val = Environment().from_string(val).render(context)
            rendered_context[field] = val

        filename: str = f"{plugin_id}.{language}.{deployment_id}.md"
        template: Template = self.env.get_template(filename)
        return template.render(rendered_context)
