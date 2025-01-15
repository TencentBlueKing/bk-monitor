# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import importlib
import os
import re
from collections import defaultdict
from typing import Callable, Dict, List, Type


class BaseMigration:
    dependencies: List[str] = []
    operations: List[Callable] = []


class Migrator:
    re_name = re.compile(r"^\d{4}_\w+\.py$")

    def __init__(self, app: str, path: str):
        """
        :param path: 迁移文件夹路径
        """
        self.app: str = app
        self.path: str = path
        self.migrations: Dict[str, Type[BaseMigration]] = {}
        self.migrations_children: Dict[str, List[str]] = defaultdict(list)
        # 用于检查是否有环，key为迁移文件名，value为[入度, 出度]
        self.degrees: Dict[str, List[int, int]] = defaultdict(lambda: [0, 0])

    def load_migration(self):
        """
        加载path下的迁移文件
        """
        dirname = os.path.dirname(importlib.import_module("{}".format(self.path)).__file__)

        # 加载所有迁移文件
        for file in os.listdir(dirname):
            if not self.re_name.match(file):
                continue

            name = file[:-3]
            m = importlib.import_module("{}.{}".format(self.path, name))
            migration = getattr(m, "Migration", None)
            if not migration:
                continue

            self.migrations[name] = migration
            for dependency in migration.dependencies:
                # 更新依赖关系
                self.migrations_children[dependency].append(name)

                # 更新入度和出度
                self.degrees[name][0] += 1
                self.degrees[dependency][1] += 1

        # 检查是否有迁移文件
        if not self.migrations:
            return

        # 检查迁移文件依赖图
        self.check_migration_graph()

    def check_migration_graph(self):
        """
        检查迁移图
        1. 0001_initial必须存在且作为开始节点
        2. 依赖图必须包含所有的迁移文件
        3. 检查是否是有向无环图
        4. 只能有一个结束节点
        """

        # 检查0001_initial是否存在
        if "0001_initial" not in self.migrations:
            raise Exception("migration 0001_initial not found")

        # 只有0001_initial的入度允许为0，其他迁移文件的入度必须大于0
        # 只允许存在一个出度为0的节点，即结束节点
        end_count = 0
        for name, degree in self.degrees.items():
            # 检查0001_initial的入度是否为0
            if name == "0001_initial":
                if degree[0] != 0:
                    raise Exception("migration 0001_initial should be root of dependency graph")
                else:
                    continue

            # 检查是否有除0001_initial外的迁移文件没有入度
            if degree[0] == 0:
                raise Exception("migration {} should not be root of dependency graph".format(name))

            # 检查是否存在多个结束节点
            if degree[1] == 0:
                end_count += 1
                if end_count > 1:
                    raise Exception("only one migration should be end of dependency graph")

        # 检查是否有环
        queue = ["0001_initial"]
        visited = set()
        while queue:
            name = queue.pop(0)
            # 将相邻节点的入度减1
            for child in self.migrations_children[name]:
                self.degrees[child][0] -= 1
                # 如果入度为0，则加入队列
                if self.degrees[child][0] == 0:
                    queue.append(child)

            # 将当前节点标记为已访问
            visited.add(name)

        # 如果有节点没有被访问，则说明有环
        if len(visited) != len(self.migrations):
            raise Exception("migration graph has circle")

    def migrate(self, *args, **kwargs):
        """
        执行迁移
        """
        print("start migrate {}...".format(self.app))
        from bkmonitor.models.config import MonitorMigration

        self.load_migration()

        # 没有迁移文件，直接返回
        if not self.migrations:
            return

        # 检查是否已经迁移过
        try:
            migrated = set(MonitorMigration.objects.filter(app=self.app).values_list("name", flat=True))
        except Exception:
            # 无迁移记录表, 直接退出
            return

        # 从0001_initial开始迁移
        queue = ["0001_initial"]
        while queue:
            name = queue.pop(0)
            queue.extend(self.migrations_children[name])

            # 如果已经迁移过，则跳过
            if name in migrated:
                continue

            print("iam migrate: {}".format(name))

            # 执行迁移
            for operation in self.migrations[name].operations:
                operation()

            # 记录迁移记录
            MonitorMigration.objects.create(app=self.app, name=name)
            migrated.add(name)

        print("migrate {} success".format(self.app))
