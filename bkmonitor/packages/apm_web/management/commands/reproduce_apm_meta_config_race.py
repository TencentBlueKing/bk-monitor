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

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from threading import Barrier, Lock, local as thread_local
from typing import Any
from unittest import mock

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import close_old_connections

from apm_web.constants import DEFAULT_APM_APP_EVENT_CONFIG
from apm_web.models import ApmMetaConfig, Application


@dataclass(frozen=True)
class RaceResult:
    worker_index: int
    invoke_status: str


class ForcedMissingQuerySet:
    """Force the old exists-then-create path to cross the race window together."""

    def __init__(self, barrier: Barrier) -> None:
        self._barrier = barrier

    def exists(self) -> bool:
        self._barrier.wait(timeout=10)
        return False

    def update(self, **kwargs: Any) -> int:
        return 0


class Command(BaseCommand):
    help = "复现 / 验证 APM 应用维度配置创建竞态冲突"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("-b", "--bk_biz_id", type=int, required=True, help="测试应用所属业务 ID")
        parser.add_argument("-a", "--app_name", type=str, required=True, help="测试应用名称")
        parser.add_argument(
            "--workers",
            type=int,
            default=2,
            help="并发 worker 数量，默认 2。修复前建议保持 2，便于稳定得到 1 成功 1 失败。",
        )
        parser.add_argument(
            "--reset-config",
            action="store_true",
            help="执行前删除目标 application_event_config。仅对指定测试应用生效。",
        )
        parser.add_argument(
            "--expect-race",
            action="store_true",
            help="期望修复前竞态复现：至少一个 worker 返回 IntegrityError。",
        )
        parser.add_argument(
            "--expect-fixed",
            action="store_true",
            help="期望修复后竞态消失：所有 worker 均成功，且最终只有一条配置。",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if options["expect_race"] and options["expect_fixed"]:
            raise CommandError("--expect-race 和 --expect-fixed 只能选择一个")
        if options["workers"] < 2:
            raise CommandError("--workers 必须大于等于 2")

        app: Application = Application.objects.get(bk_biz_id=options["bk_biz_id"], app_name=options["app_name"])
        target_filter: dict[str, Any] = {
            "config_level": ApmMetaConfig.APPLICATION_LEVEL,
            "level_key": app.application_id,
            "config_key": Application.EVENT_CONFIG_KEY,
        }

        existing_count: int = ApmMetaConfig.objects.filter(**target_filter).count()
        if existing_count and not options["reset_config"]:
            raise CommandError(
                "目标配置已存在。若确认这是预发布测试应用，请加 --reset-config 后重试；"
                "否则先换一个不会影响真实用户的测试应用。"
            )
        if options["reset_config"]:
            deleted_count, _ = ApmMetaConfig.objects.filter(**target_filter).delete()
            self.stdout.write(f"reset target config, deleted_count={deleted_count}")

        results: list[RaceResult] = self._run_race(options["workers"], target_filter, app.application_id)
        final_rows: dict[str, Any] = (
            ApmMetaConfig.objects.filter(**target_filter)
            .order_by("-id")
            .values(
                "id",
                "config_level",
                "level_key",
                "config_key",
                "config_value",
            )
            .first()
            or {}
        )

        for result in sorted(results, key=lambda item: item.worker_index):
            self.stdout.write(f"worker: {result.worker_index}；invoke_status: {result.invoke_status}")
        self.stdout.write(f"final_rows= {final_rows}")

        integrity_error_count: int = sum(1 for result in results if "IntegrityError" in result.invoke_status)
        success_count: int = sum(1 for result in results if result.invoke_status.startswith("success"))

        if options["expect_race"]:
            if integrity_error_count < 1:
                raise CommandError("未复现 IntegrityError，不符合 --expect-race 预期")
            self.stdout.write(self.style.SUCCESS("race reproduced: event config creation conflict is triggered."))
            return

        if options["expect_fixed"]:
            if success_count != options["workers"] or integrity_error_count or not final_rows:
                raise CommandError("竞态仍未被消除，不符合 --expect-fixed 预期")
            self.stdout.write(self.style.SUCCESS("race fixed: all workers succeeded and one event config row remains."))
            return

        if integrity_error_count:
            self.stdout.write(self.style.WARNING("race reproduced: event config creation conflict is triggered."))
        else:
            self.stdout.write(self.style.SUCCESS("race not triggered: all workers completed successfully."))

    def _run_race(self, workers: int, target_filter: dict[str, Any], application_id: int) -> list[RaceResult]:
        barrier = Barrier(workers)
        original_filter = ApmMetaConfig.objects.filter
        original_update_or_create = ApmMetaConfig.objects.update_or_create
        worker_context = thread_local()
        operation_lock = Lock()
        operation_by_worker: dict[int, str] = {}

        def fake_filter(*args: Any, **kwargs: Any) -> Any:
            if not args and kwargs == target_filter:
                return ForcedMissingQuerySet(barrier)
            return original_filter(*args, **kwargs)

        def traced_update_or_create(*args: Any, **kwargs: Any) -> Any:
            obj, created = original_update_or_create(*args, **kwargs)
            worker_index = getattr(worker_context, "worker_index", None)
            if worker_index is not None:
                with operation_lock:
                    operation_by_worker[worker_index] = "create" if created else "update"
            return obj, created

        with (
            mock.patch.object(ApmMetaConfig.objects, "filter", side_effect=fake_filter),
            mock.patch.object(ApmMetaConfig.objects, "update_or_create", side_effect=traced_update_or_create),
        ):
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = [
                    executor.submit(
                        self._setup_config,
                        index,
                        application_id,
                        worker_context,
                        operation_by_worker,
                    )
                    for index in range(workers)
                ]
                return [future.result() for future in as_completed(futures)]

    @staticmethod
    def _setup_config(
        worker_index: int,
        application_id: int,
        worker_context: Any,
        operation_by_worker: dict[int, str],
    ) -> RaceResult:
        close_old_connections()
        worker_context.worker_index = worker_index
        try:
            result = ApmMetaConfig.application_config_setup(
                application_id,
                Application.EVENT_CONFIG_KEY,
                DEFAULT_APM_APP_EVENT_CONFIG,
            )
            operation = Command._get_success_operation(worker_index, result, operation_by_worker)
            return RaceResult(
                worker_index=worker_index,
                invoke_status=f"success，{operation} event config successfully",
            )
        except Exception as exc:  # pylint: disable=broad-except
            return RaceResult(worker_index=worker_index, invoke_status=f"failure，{type(exc).__name__}: {exc}")
        finally:
            if hasattr(worker_context, "worker_index"):
                del worker_context.worker_index
            close_old_connections()

    @staticmethod
    def _get_success_operation(worker_index: int, result: Any, operation_by_worker: dict[int, str]) -> str:
        if worker_index in operation_by_worker:
            return operation_by_worker[worker_index]
        if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], bool):
            return "create" if result[1] else "update"
        return "create"
