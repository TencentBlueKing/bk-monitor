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

from dataclasses import dataclass


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

    所选目标各同步写入一次，不进行异步补偿。
    retry_scheduled 仅保留结果字段兼容性，始终为 False。
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
