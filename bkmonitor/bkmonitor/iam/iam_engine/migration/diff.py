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
# Schema 快照 diff —— 用于 makemigrations 自动生成迁移文件
# ---------------------------------------------------------------------------

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..schema.diff import Change


def diff_snapshots(current: dict, previous: dict) -> list[Change]:
    """对比两个 schema 快照，生成操作列表（业务命名，不含 codec 编码）。

    快照格式：to_snapshot() / from_snapshot() 的输入输出。
    extensions 变更视为 UPDATE，由各 Provider 自行读取关心的 key。

    Args:
        current: 当前 definitions 的 schema 快照。
        previous: 上次迁移文件的 target_snapshot（首次迁移时传空 dict）。

    Returns:
        list[Change]: 业务命名的变更操作列表，按拓扑顺序排列。
    """
    from ..schema.diff import Change, ChangeType, EntityKind

    changes: list[Change] = []
    prev_actions = previous.get("actions", {})
    prev_rts = previous.get("resource_types", {})
    prev_roles = previous.get("roles", {})

    cur_actions = current.get("actions", {})
    cur_rts = current.get("resource_types", {})
    cur_roles = current.get("roles", {})

    # --- ResourceTypes ---
    for rt_id, rt_data in cur_rts.items():
        after = _rt_after(rt_id, rt_data)
        if rt_id not in prev_rts:
            changes.append(
                Change(
                    kind=EntityKind.RESOURCE_TYPE,
                    change_type=ChangeType.CREATE,
                    entity_id=rt_id,
                    after=after,
                    reason="New resource type",
                )
            )
        elif rt_data != prev_rts[rt_id]:
            changes.append(
                Change(
                    kind=EntityKind.RESOURCE_TYPE,
                    change_type=ChangeType.UPDATE,
                    entity_id=rt_id,
                    before=_rt_after(rt_id, prev_rts[rt_id]),
                    after=after,
                    reason=_change_reason(prev_rts[rt_id], rt_data),
                )
            )
    for rt_id in set(prev_rts) - set(cur_rts):
        changes.append(
            Change(
                kind=EntityKind.RESOURCE_TYPE,
                change_type=ChangeType.DELETE,
                entity_id=rt_id,
                before=_rt_after(rt_id, prev_rts[rt_id]),
                reason="Resource type removed from schema",
                destructive=True,
            )
        )

    # --- Actions ---
    for a_id, a_data in cur_actions.items():
        after = _action_after(a_id, a_data)
        if a_id not in prev_actions:
            changes.append(
                Change(
                    kind=EntityKind.ACTION,
                    change_type=ChangeType.CREATE,
                    entity_id=a_id,
                    after=after,
                    reason="New action",
                )
            )
        else:
            prev_a = prev_actions[a_id]
            rt_changed = prev_a.get("resource_type", "") != a_data.get("resource_type", "")
            if rt_changed:
                changes.append(
                    Change(
                        kind=EntityKind.ACTION,
                        change_type=ChangeType.DELETE,
                        entity_id=a_id,
                        before=_action_after(a_id, prev_a),
                        reason="Action resource_type changed (recreate required)",
                        destructive=True,
                    )
                )
                changes.append(
                    Change(
                        kind=EntityKind.ACTION,
                        change_type=ChangeType.CREATE,
                        entity_id=a_id,
                        after=after,
                        reason="Action resource_type changed (recreate required)",
                    )
                )
            elif prev_a != a_data:
                changes.append(
                    Change(
                        kind=EntityKind.ACTION,
                        change_type=ChangeType.UPDATE,
                        entity_id=a_id,
                        before=_action_after(a_id, prev_a),
                        after=after,
                        reason=_change_reason(prev_a, a_data),
                    )
                )
    for a_id in set(prev_actions) - set(cur_actions):
        changes.append(
            Change(
                kind=EntityKind.ACTION,
                change_type=ChangeType.DELETE,
                entity_id=a_id,
                before=_action_after(a_id, prev_actions[a_id]),
                reason="Action removed from schema",
                destructive=True,
            )
        )

    # --- Roles ---
    for r_id, r_data in cur_roles.items():
        after = _role_after(r_id, r_data)
        if r_id not in prev_roles:
            changes.append(
                Change(
                    kind=EntityKind.ROLE, change_type=ChangeType.CREATE, entity_id=r_id, after=after, reason="New role"
                )
            )
        else:
            prev_r = prev_roles[r_id]
            if prev_r != r_data:
                before = _role_after(r_id, prev_r)
                changes.append(
                    Change(
                        kind=EntityKind.ROLE,
                        change_type=ChangeType.UPDATE,
                        entity_id=r_id,
                        before=before,
                        after=after,
                        reason=_change_reason(prev_r, r_data),
                    )
                )
    for r_id in set(prev_roles) - set(cur_roles):
        prev_r = prev_roles[r_id]
        changes.append(
            Change(
                kind=EntityKind.ROLE,
                change_type=ChangeType.DELETE,
                entity_id=r_id,
                before=_role_after(r_id, prev_r),
                reason="Role removed from schema",
                destructive=True,
            )
        )

    return changes


def _entity_after(entity_id: str, data: dict, extra: dict | None = None) -> dict:
    """构造实体快照的 after/before：完整搬运快照字段（含 extensions，不解释其内部）。

    迁移文件据此自包含（provider 可读取自己关心的方言字段，如 extensions["v3"]["action_id"]），
    diff 层保持中立——只搬运不解释。
    """
    after = {
        "id": entity_id,
        "name": data["name"],
        "description": data.get("description", ""),
        "extensions": dict(data.get("extensions", {})),
    }
    if extra:
        after.update(extra)
    return after


def _action_after(a_id: str, data: dict) -> dict:
    return _entity_after(a_id, data, {"resource_type_id": data.get("resource_type", "")})


def _rt_after(rt_id: str, data: dict) -> dict:
    return _entity_after(rt_id, data, {"ancestors": [data.get("ancestor", "")] if data.get("ancestor") else []})


def _role_after(r_id: str, data: dict) -> dict:
    return _entity_after(r_id, data, {"actions": data.get("actions", [])})


def _field_diff(prev: dict, cur: dict) -> list[str]:
    """返回哪些顶层字段发生了变更。"""
    keys = set(prev) | set(cur)
    return sorted(k for k in keys if prev.get(k) != cur.get(k))


def _change_reason(prev: dict, cur: dict) -> str:
    changed = _field_diff(prev, cur)
    return f"fields changed: {', '.join(changed)}" if changed else "Changed"
