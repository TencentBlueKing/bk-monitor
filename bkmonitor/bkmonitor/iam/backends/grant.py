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
from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from iam_engine.schema.definitions import ResourceTypeDef


logger = logging.getLogger("iam_engine.permission_writer")


@dataclass(frozen=True)
class PermissionWriteTargetResult:
    """一次权限写操作在单个 Provider 的执行结果。"""

    provider_name: str
    succeeded: bool
    error_type: str = ""
    error_message: str = ""
    retry_scheduled: bool = False

    def as_log_dict(self) -> dict[str, str | bool]:
        return {
            "provider": self.provider_name,
            "succeeded": self.succeeded,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "retry_scheduled": self.retry_scheduled,
        }


@dataclass(frozen=True)
class PermissionWriteResult:
    """一次权限写操作对全部写目标的结果快照。

    本实现不持久化补偿任务。V4 同步失败仅在提交后尽力投递，
    重试重放被冻结的主体、角色、资源和有效期，不重算 expired_at。
    """

    targets: tuple[PermissionWriteTargetResult, ...]

    @property
    def succeeded(self) -> tuple[PermissionWriteTargetResult, ...]:
        return tuple(target for target in self.targets if target.succeeded)

    @property
    def failed(self) -> tuple[PermissionWriteTargetResult, ...]:
        return tuple(target for target in self.targets if not target.succeeded)

    @property
    def is_success(self) -> bool:
        return not self.failed

    @property
    def is_partial_failure(self) -> bool:
        return bool(self.succeeded and self.failed)

    def as_log_dict(self) -> dict[str, list[dict[str, str | bool]]]:
        return {
            "succeeded": [target.as_log_dict() for target in self.succeeded],
            "failed": [target.as_log_dict() for target in self.failed],
        }


def grant_creator_actions(
    providers,
    resource_type: ResourceTypeDef | str,
    resource_id: str,
    creator: str,
    expired_at: int | None = None,
    tenant_id: str = "",
) -> PermissionWriteResult:
    """向全部写目标授予创建者权限并返回逐目标结果。"""
    from django.db import transaction

    from iam_engine.migration.dual_write import DualWriteGrantOrchestrator
    from bkmonitor.iam.adapters.authorization import MonitorAuthorizationWriter
    from bkmonitor.iam.adapters.grant_tasks import dispatch_v4_creator_grant
    from iam_engine.provider.requests import to_resource_type_id
    from django.conf import settings
    from iam_engine.error_summary import sanitize_error_summary

    results = {}
    writers = {
        p.name: MonitorAuthorizationWriter(
            p,
            tenant_id=tenant_id,
            operator=creator,
            expired_at=expired_at,
        )
        for p in providers
    }

    def observe(version, resource_type, outcome):
        if outcome == "succeeded":
            results[version] = PermissionWriteTargetResult(version, True)
        elif outcome in {"sync_failed", "fallback_dispatched"}:
            results[version] = PermissionWriteTargetResult(
                version,
                False,
                "RetryScheduled",
                "V4 synchronous grant failed; retry on commit",
                True,
            )
        elif outcome in {"failed", "prepare_failed", "dispatch_failed"}:
            error = writers[version].last_error
            results[version] = PermissionWriteTargetResult(
                version,
                False,
                type(error).__name__ if error else outcome,
                sanitize_error_summary(error) if error else outcome,
            )

    orchestrator = DualWriteGrantOrchestrator(
        writers=tuple(writers.items()),
        tenant_id=tenant_id,
        operator=creator,
        on_commit=transaction.on_commit,
        dispatch_retry_grant=dispatch_v4_creator_grant,
        grant_observer=observe,
    )
    orchestrator.grant_creator_action(
        {
            "type": to_resource_type_id(resource_type),
            "id": str(resource_id),
            "creator": creator,
            "system": getattr(settings, "BK_IAM_SYSTEM_ID", "bk_monitorv3"),
        }
    )
    return PermissionWriteResult(tuple(results[p.name] for p in providers))
