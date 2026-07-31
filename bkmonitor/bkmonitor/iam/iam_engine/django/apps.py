"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from __future__ import annotations

import logging

from django.apps import AppConfig

from bkmonitor.iam.iam_engine.django.conf import load_framework

logger = logging.getLogger("iam_engine.django")


class IamEngineConfig(AppConfig):
    """iam_engine Django 集成入口。

    注册到 INSTALLED_APPS：
        INSTALLED_APPS = [
            ...
            "bkmonitor.iam.iam_engine.django",
        ]

    启动流程：
        1. AppConfig.ready() 触发 load_framework()
        2. load_framework() 读 settings.IAM_FRAMEWORK → 构建 IAMFramework
        3. 根据 MIGRATION.MODE 决定是否自动执行 schema 迁移
    """

    name = "bkmonitor.iam.iam_engine.django"
    label = "iam_engine"
    verbose_name = "IAM Engine"

    _framework_loaded = False
    _migration_done = False

    def ready(self) -> None:
        if self._framework_loaded:
            return
        self._framework_loaded = True

        fw = load_framework()
        logger.info("iam_engine framework loaded: %d provider(s)", len(fw.providers))

        self._maybe_auto_migrate(fw)

    def _maybe_auto_migrate(self, fw) -> None:
        """根据 MIGRATION.MODE 决定自动迁移行为。"""
        from django.conf import settings

        raw = getattr(settings, "IAM_FRAMEWORK", {})
        migration_cfg = raw.get("MIGRATION", {})
        mode = migration_cfg.get("MODE", "manual")

        if mode == "manual":
            return

        if mode in ("auto", "auto_full"):
            self._run_auto_migration(fw, migration_cfg)
        elif mode == "semi_auto":
            from django.db.models.signals import post_migrate

            post_migrate.connect(
                lambda **kw: self._run_auto_migration(fw, migration_cfg),
                sender=self,
            )

    def _run_auto_migration(self, fw, migration_cfg: dict) -> None:
        # 进程内幂等：同一进程只跑一次自动迁移（防 runserver autoreload / 测试重复触发）
        if self._migration_done:
            return
        self._migration_done = True

        allow_destructive = migration_cfg.get("ALLOW_DESTRUCTIVE", False) or migration_cfg.get("MODE") == "auto_full"

        # 注意：多副本部署的分布式互斥由各 Provider 的 apply_migration 实现自行
        # 负责（例如 builtin/v4/migrator.py 内部用 RedisLock 包裹）。
        # 框架层不引入锁依赖——不同 Provider 的锁后端需求不同（Redis / DB / 文件锁）。

        for provider in fw.providers.values():
            try:
                plan = provider.plan_migration(fw.schema)
                if not plan.changes:
                    logger.info("iam_engine migration: %s — no changes", provider.name)
                    continue
                logger.info("iam_engine migration: %s — %s", provider.name, plan.summary())
                provider.apply_migration(
                    plan,
                    dry_run=False,
                    allow_destructive=allow_destructive,
                )
            except Exception:
                logger.exception(
                    "iam_engine auto migration failed for provider=%s",
                    provider.name,
                )
