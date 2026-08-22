"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

# ---------------------------------------------------------------------------
# MigrationLoader — 从指定目录发现、加载、校验迁移文件
#
# 迁移文件命名规范：NNNN_description.py（NNNN 为 4 位递增编号）。
# 每个文件必须导出：
#     dependencies: list[str]        — 依赖的迁移文件名列表
#     operations: list[Change]       — 该迁移包含的变更操作
#     target_snapshot: dict          — 迁移执行后的完整 schema 快照
# ---------------------------------------------------------------------------

from __future__ import annotations

import importlib
import os
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..core.exceptions import MigrationPreCheckFailed

if TYPE_CHECKING:
    from ..schema.diff import Change

_MIGRATION_FILE_RE = re.compile(r"^(\d{4})_(\w+)\.py$")


@dataclass
class Migration:
    """加载完成的单个迁移文件表示。"""

    name: str
    """迁移名（如 "0001_initial"）。"""
    dependencies: list[str]
    """依赖的迁移名列表。"""
    operations: list[Change]
    """该迁移包含的变更操作（业务命名）。"""
    target_snapshot: dict
    """迁移执行后的完整 schema 快照（供 makemigrations 对比用）。"""


class MigrationLoader:
    """基础迁移加载器——从文件系统目录发现和加载迁移文件。

    约定：
      - 迁移文件名匹配 ``NNNN_description.py``（NNNN 为 4 位数字）
      - 每个文件模块层面导出 ``dependencies``、``operations``、``target_snapshot``
      - 框架不做 DB 操作，由调用方通过 recorder 追踪状态
    """

    def __init__(self, directory: str):
        """初始化加载器。

        Args:
            directory: 迁移文件所在目录的绝对路径。
        """
        self._directory = directory

    def load_all(self) -> dict[str, Migration]:
        """扫描目录，加载所有迁移文件，返回 {name: Migration} 字典。

        校验：
          - 文件名符合 NNNN_description.py
          - 文件可 import
          - 导出 dependencies（list[str]）、operations（list[Change]）、target_snapshot（dict）

        Returns:
            dict: 以迁移名为 key 的 Migration 对象字典。

        Raises:
            MigrationPreCheckFailed: 校验失败（缺失字段、类型错误等）。
        """
        if not os.path.isdir(self._directory):
            return {}

        migrations: dict[str, Migration] = {}

        for fname in sorted(os.listdir(self._directory)):
            m = _MIGRATION_FILE_RE.match(fname)
            if not m:
                continue
            name = f"{m.group(1)}_{m.group(2)}"
            module_path = os.path.join(self._directory, fname)

            try:
                spec = importlib.util.spec_from_file_location(f"iam_migration_{name}", module_path)
                if spec is None or spec.loader is None:
                    raise MigrationPreCheckFailed(f"Cannot load migration {name}: invalid spec")
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            except Exception as e:
                raise MigrationPreCheckFailed(f"Cannot load migration {name}: {e}") from e

            migrations[name] = Migration(
                name=name,
                dependencies=self._get_attr(module, "dependencies", name, default=[]),
                operations=self._get_attr(module, "operations", name, default=[]),
                target_snapshot=self._get_attr(module, "target_snapshot", name, default={}),
            )

        return migrations

    @staticmethod
    def _get_attr(module, attr: str, name: str, default=None):
        val = getattr(module, attr, None)
        if val is None and default is None:
            raise MigrationPreCheckFailed(f"Migration {name} missing required attribute {attr!r}")
        return val if val is not None else default
