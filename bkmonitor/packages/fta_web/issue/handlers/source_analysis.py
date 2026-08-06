"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from core.drf_resource import api


class SourceAnalysisOptionsHandler:
    """封装源码分析配置页所需的蓝盾选项，并屏蔽上游字段差异。"""

    GIT_REPOSITORY_TYPES = frozenset({"CODE_GIT", "CODE_GITLAB", "CODE_TGIT", "GITHUB"})

    @staticmethod
    def _validate_list(data, resource_name: str) -> list[dict]:
        if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
            raise ValueError(f"invalid {resource_name} response")
        return data

    @classmethod
    def list_bkci_projects(cls) -> list[dict]:
        projects = cls._validate_list(api.devops.list_user_project(), "project")
        options = []
        for project in projects:
            project_id = project.get("project_code")
            project_name = project.get("project_name")
            if not project_id or not project_name:
                raise ValueError("project response misses project_code or project_name")
            options.append({"id": project_id, "name": project_name})
        return options

    @classmethod
    def list_bkci_repositories(cls, project_id: str) -> list[dict]:
        repository_page = api.devops.list_user_repository(project_id=project_id)
        if not isinstance(repository_page, dict):
            raise ValueError("invalid repository response")
        repositories = cls._validate_list(repository_page.get("records"), "repository")
        options = []
        for repository in repositories:
            repository_type = str(repository.get("type") or "").upper()
            if repository_type not in cls.GIT_REPOSITORY_TYPES:
                continue

            alias = repository.get("aliasName")
            if not alias:
                raise ValueError("repository response misses aliasName")

            # repositoryHashId 仅用于蓝盾内部接口联查；配置和前端选项均以不可变的代码库别名为准。
            options.append({"id": alias, "name": alias, "scm_type": "GIT"})
        return options
