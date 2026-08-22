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
# MigrationPlanner — 依赖解析 + 拓扑排序，计算待应用迁移列表
# ---------------------------------------------------------------------------

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

from ..core.exceptions import MigrationPreCheckFailed

if TYPE_CHECKING:
    from .loader import Migration, MigrationLoader
    from .recorder import MigrationRecorder


class MigrationPlanner:
    """给定 loader + recorder + provider name，输出待应用的迁移列表（拓扑序）。

    校验：
      - 依赖图无环（DAG）
      - 所有依赖都在已发现的迁移文件中
      - 首个迁移依赖为空（入度为 0 的起点）
      - 已应用的迁移的依赖必须也已应用
    """

    def __init__(
        self,
        loader: MigrationLoader,
        recorder: MigrationRecorder,
        provider: str,
    ) -> None:
        """初始化规划器。

        Args:
            loader: 迁移文件加载器。
            recorder: 迁移状态记录器。
            provider: Provider 名（如 "v4"、"v3"）。
        """
        self._loader = loader
        self._recorder = recorder
        self._provider = provider

    def get_pending(self) -> list[Migration]:
        """计算待应用的迁移列表（拓扑序）。

        Returns:
            list[Migration]: 按依赖拓扑序排列的待应用迁移。

        Raises:
            MigrationPreCheckFailed: 依赖图有环、缺失依赖、已应用迁移的依赖未应用等。
        """
        all_migrations = self._loader.load_all()
        if not all_migrations:
            return []

        applied = set(self._recorder.get_applied(self._provider))

        # 校验已应用迁移的依赖也已应用
        for name in applied:
            m = all_migrations.get(name)
            if m is None:
                continue
            for dep in m.dependencies:
                if dep not in applied:
                    raise MigrationPreCheckFailed(
                        f"Provider {self._provider!r}: applied migration {name!r} "
                        f"depends on {dep!r} which has not been applied"
                    )

        # 只考虑未应用的迁移
        pending_migrations = [m for name, m in all_migrations.items() if name not in applied]

        if not pending_migrations:
            return []

        # 构建依赖图，只考虑未应用的迁移节点
        pending_names = {m.name for m in pending_migrations}
        in_degree: dict[str, int] = {}
        children: dict[str, list[str]] = {}

        for m in pending_migrations:
            in_degree.setdefault(m.name, 0)
            children.setdefault(m.name, [])

        for m in pending_migrations:
            for dep in m.dependencies:
                if dep in pending_names:
                    # 未应用迁移之间的依赖边
                    children[dep].append(m.name)
                    in_degree[m.name] = in_degree.get(m.name, 0) + 1
                elif dep in applied:
                    # 依赖已应用的迁移，不算入度
                    pass
                else:
                    raise MigrationPreCheckFailed(f"Migration {m.name!r} depends on {dep!r} which is not found")

        # Kahn 拓扑排序
        queue: deque[str] = deque(name for name, deg in in_degree.items() if deg == 0)
        if not queue:
            raise MigrationPreCheckFailed(
                "Migration dependency graph has no entry point (all nodes have in-degree > 0)"
            )

        sorted_names: list[str] = []
        while queue:
            name = queue.popleft()
            sorted_names.append(name)
            for child in children.get(name, []):
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        if len(sorted_names) != len(pending_migrations):
            raise MigrationPreCheckFailed(
                "Migration dependency graph contains a cycle among: "
                + ", ".join(n for n, d in in_degree.items() if d > 0)
            )

        # 按拓扑序返回
        name_to_migration = {m.name: m for m in pending_migrations}
        return [name_to_migration[name] for name in sorted_names]
