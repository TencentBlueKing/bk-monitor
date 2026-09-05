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
# System migration logging —— 基于 reconcile 后 MigrationReport 的通用日志摘要
# ---------------------------------------------------------------------------

from __future__ import annotations

import re
from dataclasses import dataclass

from ..schema.diff import Change, EntityKind, MigrationPlan, MigrationReport

_SECRET_VALUE_RE = re.compile(r"(?i)\b(app_secret|secret|token|password|api[_-]?key)\b\s*([=:])\s*[^,;\s]+")
_AUTHORIZATION_RE = re.compile(r"(?i)\bauthorization\b\s*[:=]\s*[^,;]+")


@dataclass(frozen=True)
class SystemMigrationLog:
    """供 CLI 与 Django 日志复用的系统迁移文本摘要。"""

    outcome: str
    summary: str
    details: tuple[str, ...] = ()

    @property
    def is_error(self) -> bool:
        return self.outcome == "failed"


def summarize_system_migration(
    plan: MigrationPlan,
    report: MigrationReport,
    *,
    dry_run: bool,
) -> SystemMigrationLog:
    """将某 Provider 已 reconcile 的系统迁移结果转成安全、稳定的日志摘要。

    ``plan`` 只用于在 NOOP 时提供 system ID；实际 CREATE / UPDATE / FAILED
    明细始终以 ``report`` 为准，避免记录 reconcile 前的本地假设。
    """
    provider_name = report.provider_name or plan.provider_name
    planned = _system_changes(plan.changes)
    actionable = _system_changes(report.would_apply if dry_run else report.applied)
    failed = [(change, error) for change, error in report.failed if change.kind == EntityKind.SYSTEM]
    skipped = [(change, reason) for change, reason in report.skipped if change.kind == EntityKind.SYSTEM]
    system_id = _system_id(actionable, [change for change, _error in failed], planned)
    prefix = f"[{provider_name}] system"

    if report.skipped_reason:
        return SystemMigrationLog(
            outcome="skipped",
            summary=f"{prefix}: skipped ({_safe_text(report.skipped_reason)}).",
        )

    if failed:
        applied_count = len(_system_changes(report.applied))
        applied_text = f", applied {applied_count}" if applied_count else ""
        return SystemMigrationLog(
            outcome="failed",
            summary=f"{prefix}: failed {len(failed)} change(s){applied_text}.",
            details=tuple(_format_failed_change(change, error) for change, error in failed),
        )

    if actionable:
        action_text = "would apply" if dry_run else "applied"
        return SystemMigrationLog(
            outcome="would_apply" if dry_run else "applied",
            summary=f"{prefix}: {action_text} {len(actionable)} change(s).",
            details=tuple(_format_change(change) for change in actionable),
        )

    if skipped:
        return SystemMigrationLog(
            outcome="skipped",
            summary=f"{prefix}: skipped {len(skipped)} change(s).",
            details=tuple(f"{_format_change(change)}; skip_reason={_safe_text(reason)}" for change, reason in skipped),
        )

    if system_id:
        return SystemMigrationLog(
            outcome="noop",
            summary=f"{prefix}: no changes (id={system_id}, reconciled=noop).",
        )
    return SystemMigrationLog(outcome="noop", summary=f"{prefix}: no system changes planned.")


def _system_changes(changes: list[Change]) -> list[Change]:
    return [change for change in changes if change.kind == EntityKind.SYSTEM]


def _system_id(*change_groups: list[Change]) -> str:
    for changes in change_groups:
        if changes:
            return changes[0].entity_id
    return ""


def _format_change(change: Change) -> str:
    details: list[str] = []
    if change.change_type.value == "create":
        details.extend(_create_metadata(change.after or {}))
    elif change.change_type.value == "update":
        fields = _changed_fields(change.before or {}, change.after or {})
        if fields:
            details.append(f"changed_fields={','.join(fields)}")
    if change.destructive:
        details.append("destructive=true")
    if change.reason:
        details.append(f"reason={_safe_text(change.reason)}")

    message = f"  - {change.change_type.value.upper()} {change.entity_id}"
    return f"{message} ({'; '.join(details)})" if details else message


def _format_failed_change(change: Change, error: str) -> str:
    return f"{_format_change(change)}; error={_safe_text(error, limit=300)}"


def _create_metadata(data: dict) -> list[str]:
    metadata: list[str] = []
    if "name" in data:
        metadata.append(f"name={_safe_text(data['name'])}")
    for key in ("description", "name_en", "description_en"):
        if key in data:
            metadata.append(f"{key}={'configured' if data[key] else 'empty'}")
    if "callback_url" in data:
        metadata.append(f"callback_url={'configured' if data['callback_url'] else 'empty'}")
    for key in ("managers", "clients"):
        if key in data:
            metadata.append(f"{key}={_collection_size(data[key])}")
    return metadata


def _changed_fields(before: dict, after: dict) -> list[str]:
    return sorted(key for key, value in after.items() if key != "id" and before.get(key) != value)


def _collection_size(value) -> int:
    if value is None:
        return 0
    if isinstance(value, str | bytes):
        return int(bool(value))
    try:
        return len(value)
    except TypeError:
        return 1


def _safe_text(value, *, limit: int = 120) -> str:
    text = " ".join(str(value).split())
    text = _SECRET_VALUE_RE.sub(r"\1\2***", text)
    text = _AUTHORIZATION_RE.sub("authorization=***", text)
    return text[:limit]
