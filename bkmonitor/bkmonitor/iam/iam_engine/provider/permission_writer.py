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

from .base import PermissionProvider

if TYPE_CHECKING:
    from ..schema.definitions import ResourceTypeDef


logger = logging.getLogger("iam_engine.permission_writer")


@dataclass(frozen=True)
class PermissionWriteTargetResult:
    """一次权限写操作在单个 Provider 的执行结果。"""

    provider_name: str
    succeeded: bool
    error_type: str = ""
    error_message: str = ""

    def as_log_dict(self) -> dict[str, str | bool]:
        return {
            "provider": self.provider_name,
            "succeeded": self.succeeded,
            "error_type": self.error_type,
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class PermissionWriteResult:
    """一次权限写操作对全部写目标的结果快照。

    当前 ``on_failure=log`` 不持久化补偿任务。重试会把相同 desired state 重放到
    每个写目标，因此各 Provider 的授权写接口必须幂等。
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


class PermissionWriter:
    """独立于读鉴权策略的权限写入器。

    ``providers`` 来自统一的 ``WRITE.PROVIDERS`` 配置。创建者授权是第一个
    消费该目标集合的写操作；后续授权、撤销等写接口继续复用本对象，而不是各自
    引入新的 Provider 环境变量。
    """

    def __init__(self, providers: list[PermissionProvider], on_failure: str = "log") -> None:
        if not providers:
            raise ValueError("PermissionWriter requires at least one provider")
        if on_failure != "log":
            raise ValueError("PermissionWriter currently supports only on_failure='log'")
        if len({provider.name for provider in providers}) != len(providers):
            raise ValueError(f"PermissionWriter provider names must be unique, got {[p.name for p in providers]}")

        self.providers = list(providers)
        self.on_failure = on_failure

    def grant_creator_action(
        self,
        resource_type: ResourceTypeDef | str,
        resource_id: str,
        creator: str,
        expired_at: int | None = None,
        tenant_id: str = "",
    ) -> PermissionWriteResult:
        """向全部写目标授予创建者权限并返回逐目标结果。"""
        targets: list[PermissionWriteTargetResult] = []
        for provider in self.providers:
            try:
                provider.grant_creator_action(resource_type, resource_id, creator, expired_at, tenant_id)
            except Exception as exc:  # noqa: BLE001
                result = PermissionWriteTargetResult(
                    provider_name=provider.name,
                    succeeded=False,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
                targets.append(result)
                logger.exception(
                    "permission write failed: operation=grant_creator_action provider=%s resource=%s/%s "
                    "creator=%s tenant_id=%s result=%s",
                    provider.name,
                    resource_type,
                    resource_id,
                    creator,
                    tenant_id,
                    result.as_log_dict(),
                )
            else:
                targets.append(PermissionWriteTargetResult(provider_name=provider.name, succeeded=True))
        return PermissionWriteResult(targets=tuple(targets))
