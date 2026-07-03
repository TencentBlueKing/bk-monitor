"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import argparse
from dataclasses import dataclass
from typing import Any, ClassVar

from django.core.management import BaseCommand, CommandError

from apm.core.handlers.application_hepler import ApplicationHelper
from apm.models import ApmApplication, TraceDataSource
from apm.resources import ApplyDatasourceResource
from constants.apm import TelemetryDataType

TARGET_SHARED: str = "shared"
TARGET_EXCLUSIVE: str = "exclusive"
TARGET_CHOICES: tuple[str, str] = (TARGET_SHARED, TARGET_EXCLUSIVE)


@dataclass(frozen=True)
class TraceDataSourceMigrationContext:
    bk_biz_id: int
    app_name: str
    application: ApmApplication
    trace_datasource: TraceDataSource | None

    @property
    def current_mode(self) -> str:
        if not self.trace_datasource:
            return "not_created"
        if self.trace_datasource.is_shared:
            return TARGET_SHARED
        return TARGET_EXCLUSIVE

    @property
    def result_table_id(self) -> str:
        if not self.trace_datasource:
            return ""
        return self.trace_datasource.result_table_id

    @property
    def has_backup(self) -> bool:
        return bool(self.trace_datasource and self.trace_datasource.backup_link_info)

    @property
    def needs_index_set_repair(self) -> bool:
        return bool(
            self.trace_datasource
            and not self.trace_datasource.is_shared
            and self.trace_datasource.result_table_id
            and not self.trace_datasource.index_set_id
        )


class Command(BaseCommand):
    help = "APM Trace 数据源迁入共享或迁出独占"

    TARGET_SHARED: ClassVar[str] = TARGET_SHARED
    TARGET_EXCLUSIVE: ClassVar[str] = TARGET_EXCLUSIVE
    TARGET_CHOICES: ClassVar[tuple[str, str]] = TARGET_CHOICES

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--target",
            choices=self.TARGET_CHOICES,
            required=True,
            help="目标模式：shared 表示迁入共享，exclusive 表示迁出独占",
        )
        parser.add_argument(
            "--apps",
            nargs="+",
            required=True,
            help="应用列表，格式为 <bk_biz_id>:<app_name>，例如 2:app_a 2:app_b",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="输出当前状态、目标状态、是否有备份和预计动作等信息，不执行迁移",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        target: str = options["target"]
        dry_run: bool = options["dry_run"]
        apps: list[tuple[int, str]] = self.parse_apps(options["apps"])
        contexts: list[TraceDataSourceMigrationContext] = [
            self.get_migration_context(bk_biz_id, app_name) for bk_biz_id, app_name in apps
        ]

        if dry_run:
            for index, context in enumerate(contexts):
                if index > 0:
                    self.stdout.write("")
                self.write_dry_run_status(context, target)
            return

        for context in contexts:
            self.migrate_app(context, target)

    @staticmethod
    def parse_apps(app_values: list[str]) -> list[tuple[int, str]]:
        """解析命令行应用参数，并按首次出现顺序去重。"""
        apps: list[tuple[int, str]] = []
        seen: set[tuple[int, str]] = set()
        for app_value in app_values:
            if ":" not in app_value:
                raise CommandError(f"--apps 参数格式错误：{app_value}，期望格式为 <bk_biz_id>:<app_name>")

            bk_biz_id_text, app_name = app_value.split(":", 1)
            try:
                bk_biz_id = int(bk_biz_id_text)
            except ValueError as exc:
                raise CommandError(f"--apps 参数业务 ID 非整数：{app_value}") from exc

            if not app_name:
                raise CommandError(f"--apps 参数应用名为空：{app_value}")

            app_key = (bk_biz_id, app_name)
            if app_key in seen:
                continue
            apps.append(app_key)
            seen.add(app_key)
        return apps

    def write_dry_run_status(self, context: TraceDataSourceMigrationContext, target: str) -> None:
        """输出单个应用的 dry-run 状态。"""
        result_table_id: str = context.result_table_id
        action: str
        if not context.trace_datasource:
            action = f"create {target} datasource"
        elif context.current_mode == target and not context.needs_index_set_repair:
            action = "keep the current mode unchanged"
        elif context.current_mode == target:
            action = "repair current exclusive datasource"
        elif target == self.TARGET_SHARED:
            action = "backup exclusive link info and migrate to shared"
        elif context.has_backup:
            action = "release shared pool usage and recover exclusive link info"
        else:
            action = "release shared pool usage and create exclusive datasource"

        self.stdout.write(
            "\n".join(
                [
                    "[dry-run]",
                    f"application_id：{context.application.id}",
                    f"bk_biz_id：{context.bk_biz_id}",
                    f"app_name：{context.app_name}",
                    f"current_mode：{context.current_mode}",
                    f"target_mode：{target}",
                    f"result_table_id：{result_table_id or '-'}",
                    f"has_backup：{context.has_backup}",
                    f"action：{action}",
                ]
            )
        )

    def migrate_app(self, context: TraceDataSourceMigrationContext, target: str) -> None:
        """迁移单个应用 Trace 数据源。"""
        if context.current_mode == target and not context.needs_index_set_repair:
            self.stdout.write(
                self.style.SUCCESS(
                    f"已跳过 Trace 数据源迁移：bk_biz_id={context.bk_biz_id}, "
                    f"app_name={context.app_name}, mode={target}"
                )
            )
            return

        trace_datasource_option: dict[str, Any] = ApplicationHelper.get_default_storage_config(
            context.bk_biz_id, context.app_name
        )
        if not trace_datasource_option.get("es_storage_cluster"):
            raise CommandError(
                f"无法获取默认 Trace 存储配置：bk_biz_id={context.bk_biz_id}, app_name={context.app_name}"
            )

        shared_datasource_types: list[str] = [TelemetryDataType.TRACE.value] if target == self.TARGET_SHARED else []
        ApplyDatasourceResource().request(
            {
                "application_id": context.application.id,
                "trace_datasource_option": trace_datasource_option,
                "shared_datasource_types": shared_datasource_types,
            }
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"已完成 Trace 数据源迁移：bk_biz_id={context.bk_biz_id}, app_name={context.app_name}, mode={target}"
            )
        )

    @staticmethod
    def get_migration_context(bk_biz_id: int, app_name: str) -> TraceDataSourceMigrationContext:
        application: ApmApplication | None = ApmApplication.objects.filter(
            bk_biz_id=bk_biz_id, app_name=app_name
        ).first()
        if not application:
            raise CommandError(f"业务下应用不存在：bk_biz_id={bk_biz_id}, app_name={app_name}")

        trace_datasource: TraceDataSource | None = TraceDataSource.objects.filter(
            bk_biz_id=bk_biz_id, app_name=app_name
        ).first()
        return TraceDataSourceMigrationContext(
            bk_biz_id=bk_biz_id,
            app_name=app_name,
            application=application,
            trace_datasource=trace_datasource,
        )
