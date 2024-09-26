# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import os
import typing

from jinja2 import Environment, FileSystemLoader, Template


class Help:
    help_md_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "help_md_new")

    def __init__(self, context: typing.Dict[str, str]):
        print(self.help_md_path)
        self.env: Environment = Environment(loader=FileSystemLoader(searchpath=self.help_md_path))
        self.context: typing.Dict[str, str] = context

    def get_help_md(self, plugin_id: str, language: str, deployment_id: str) -> str:
        filename: str = f"{plugin_id}.{language}.{deployment_id}.md"
        template: Template = self.env.get_template(filename)
        return template.render(self.context)
