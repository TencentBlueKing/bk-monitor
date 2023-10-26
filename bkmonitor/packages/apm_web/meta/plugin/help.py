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
from collections import defaultdict

from apm_web.meta.plugin.plugin import DeploymentEnum, LanguageEnum


class Help:
    help_md_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "help_md")

    def __init__(self, plugin_id):
        self._plugin_id = plugin_id

    def get_help_md(self):
        help_md_map = {}
        for file, content in self.scan_help_md():
            help_md_map[file] = content

        result = defaultdict(dict)
        for language in LanguageEnum.get_values():
            for deployment in DeploymentEnum.get_values():
                result[language.id][deployment.id] = help_md_map.get(
                    f"{self._plugin_id}.{language.id}.{deployment.id}",
                    help_md_map.get(f"{self._plugin_id}.{language.id}.{deployment.category.id}", ""),
                )
        return result

    def scan_help_md(self):
        for file in os.listdir(self.help_md_path):
            if file.startswith(self._plugin_id):
                yield file.replace(".md", ""), self.load_md_file(file.replace(".md", ""))

    @classmethod
    def load_md_file(cls, filename):
        file_path = os.path.join(cls.help_md_path, f"{filename}.md")
        with open(file_path, "r", encoding="utf8") as f:
            return f.read()
