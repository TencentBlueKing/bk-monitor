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
# V4Migrator — IAM v4 模型迁移（plan_migration / apply_migration）
# ---------------------------------------------------------------------------

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from ..iam_engine.core.exceptions import ProviderUnavailable
from ..iam_engine.provider.codec import IdentityCodec, NameCodec
from ..iam_engine.schema.diff import Change, ChangeType, EntityKind, MigrationPlan, MigrationReport
from ..iam_engine.schema.visibility import is_visible_to
from .client import V4Client

if TYPE_CHECKING:
    from ..iam_engine.schema.registry import SchemaRegistry
    from .config import V4SystemInfo

logger = logging.getLogger(__name__)


class V4Migrator:
    """IAM v4 模型迁移器。

    可见性过滤：
        本 Migrator 仅处理对 ``provider_name="v4"`` 可见的 schema 实体。
        在 schema 实体的 ``extensions`` 里用 ``only_providers`` /
        ``exclude_providers`` 声明归属或排除（见 ``schema.visibility``）。

        本地不可见的实体：不会参与 diff（既不会被 CREATE，也不会因为在本地
        缺失而把远端对应实体删除 — 因为本地 dialect_id 集合完全不包含它们，
        无法与远端同名实体形成同一可见性下的 orphan）。
    """

    # 拓扑顺序：创建时 System → ResourceType → Action → Role；删除时反向
    _KIND_ORDER: dict[EntityKind, int] = {
        EntityKind.SYSTEM: 0,
        EntityKind.RESOURCE_TYPE: 1,
        EntityKind.ACTION: 2,
        EntityKind.ROLE: 3,
    }

    def __init__(
        self,
        client: V4Client,
        schema: SchemaRegistry,
        system_def: V4SystemInfo,
        codec: NameCodec | None = None,
    ):
        self._client = client
        self._schema = schema
        self._system = system_def
        # 迁移器写往平台的字段（action_id / resource_type_id / resource ancestors 等）
        # 需要经过 codec 编码为方言；未注入时用恒等 codec 保持向后兼容。
        self._codec: NameCodec = codec or IdentityCodec()

    # ================================================================
    # plan_migration
    # ================================================================

    def plan_migration(self) -> MigrationPlan:
        """拉取远端状态，与本地 schema diff，生成 MigrationPlan。

        - 系统未注册（404）→ 全部本地实体标记 CREATE
        - IAM 平台故障（超时/500/403）→ ProviderUnavailable 直接抛出，调用方感知
        - 系统已注册 → 正常 diff
        """
        remote_system = self._fetch_remote_system()

        if remote_system is None:
            # 系统未注册，无需查远端 rt/action/role，全部 CREATE
            changes = self._plan_all_create()
        else:
            changes: list[Change] = []
            changes.extend(self._diff_system(remote_system))
            changes.extend(self._diff_resource_types(self._fetch_remote_resource_types()))
            changes.extend(self._diff_actions(self._fetch_remote_actions()))
            changes.extend(self._diff_roles(self._fetch_remote_roles()))

        plan = MigrationPlan(provider_name="v4", changes=self._topology_sort(changes))
        logger.info(
            "[iam_v4:migration:plan] summary=%s destructive=%s",
            plan.summary(),
            plan.has_destructive(),
        )
        return plan

    # ================================================================
    # apply_migration
    # ================================================================

    def apply_migration(
        self,
        plan: MigrationPlan,
        *,
        dry_run: bool = False,
        allow_destructive: bool = False,
    ) -> MigrationReport:
        """执行迁移计划。按拓扑顺序执行变更，确保创建和删除的依赖正确。"""
        report = MigrationReport(provider_name="v4", started_at=datetime.now(tz=timezone.utc))

        if plan.has_destructive() and not allow_destructive:
            report.skipped_reason = "Destructive changes blocked; set allow_destructive=True"
            report.finished_at = datetime.now(tz=timezone.utc)
            logger.warning("[iam_v4:migration:apply] %s", report.skipped_reason)
            return report

        sorted_changes = self._topology_sort(plan.changes)

        for change in sorted_changes:
            if change.change_type == ChangeType.NOOP:
                continue
            if dry_run:
                report.would_apply.append(change)
                continue
            try:
                self._apply_change(change)
                report.applied.append(change)
                logger.info("[iam_v4:migration:apply] %s %s", change.change_type.value, change.entity_id)
            except Exception as e:
                report.failed.append((change, str(e)[:500]))
                logger.error("[iam_v4:migration:fail] %s %s: %s", change.change_type.value, change.entity_id, e)

        report.finished_at = datetime.now(tz=timezone.utc)
        logger.info(
            "[iam_v4:migration:done] applied=%d would_apply=%d failed=%d elapsed=%.1fs",
            len(report.applied),
            len(report.would_apply),
            len(report.failed),
            report.elapsed_seconds,
        )
        return report

    # ================================================================
    # 远端数据拉取（404 与真错误区分对待）
    # ================================================================

    def _fetch_remote_system(self) -> dict | None:
        """拉取远端 system。404 → None（未注册），其他异常 → 向上抛。"""
        try:
            return self._client.retrieve_system()
        except ProviderUnavailable as e:
            if e.code == 404:
                return None
            raise

    def _fetch_remote_actions(self) -> dict[str, dict]:
        try:
            return self._paginate(self._client.list_actions, "actions")
        except ProviderUnavailable as e:
            if e.code == 404:
                return {}
            raise

    def _fetch_remote_resource_types(self) -> dict[str, dict]:
        try:
            return self._paginate(self._client.list_resource_types, "resource_types")
        except ProviderUnavailable as e:
            if e.code == 404:
                return {}
            raise

    def _fetch_remote_roles(self) -> dict[str, dict]:
        try:
            return self._paginate(self._client.list_roles, "roles")
        except ProviderUnavailable as e:
            if e.code == 404:
                return {}
            raise

    def _paginate(self, api_fn, key: str) -> dict[str, dict]:
        """翻页拉取全量列表，按 id 索引。"""
        items: dict[str, dict] = {}
        page = 1
        while True:
            resp = api_fn(page=page, page_size=100)
            data = resp.get("data", {})
            results = data.get("results") or []
            for item in results:
                items[item["id"]] = item
            pagination = data.get("pagination", {})
            if page >= pagination.get("total_pages", 1):
                break
            page += 1
        return items

    # ================================================================
    # 全量 CREATE（系统未注册时使用）
    # ================================================================

    def _plan_all_create(self) -> list[Change]:
        """系统不存在时，所有本地实体标记为 CREATE。"""
        changes: list[Change] = []

        # System
        changes.append(
            Change(
                kind=EntityKind.SYSTEM,
                change_type=ChangeType.CREATE,
                entity_id=self._system.id,
                after={
                    "id": self._system.id,
                    "name": self._system.name,
                    "description": self._system.description,
                    "managers": list(self._system.managers),
                    "clients": list(self._system.clients),
                    "callback_url": self._system.callback_url,
                },
                reason="System not registered in IAM v4",
            )
        )

        # ResourceTypes
        for rt in self._schema.all_resource_types():
            if not is_visible_to(rt, "v4"):
                continue
            d_rt_id = self._codec.encode_resource_type(rt.id)
            d_anc = self._codec.encode_resource_type(rt.ancestor) if rt.ancestor else ""
            changes.append(
                Change(
                    kind=EntityKind.RESOURCE_TYPE,
                    change_type=ChangeType.CREATE,
                    entity_id=rt.id,
                    after={"id": d_rt_id, "name": rt.name, "ancestors": [d_anc] if d_anc else []},
                    reason="New resource type",
                )
            )

        # Actions
        for a in self._schema.all_actions():
            if not is_visible_to(a, "v4"):
                continue
            changes.append(
                Change(
                    kind=EntityKind.ACTION,
                    change_type=ChangeType.CREATE,
                    entity_id=a.id,
                    after={
                        "id": self._codec.encode_action(a.id),
                        "name": a.name,
                        "resource_type_id": self._codec.encode_resource_type(a.resource_type)
                        if a.resource_type
                        else "",
                    },
                    reason="New action",
                )
            )

        # Roles
        for r in self._schema.all_roles():
            if not is_visible_to(r, "v4"):
                continue
            changes.append(
                Change(
                    kind=EntityKind.ROLE,
                    change_type=ChangeType.CREATE,
                    entity_id=r.id,
                    after={
                        "id": self._codec.encode_role(r.id),
                        "name": r.name,
                        "description": r.description,
                        "actions": [
                            {
                                "id": self._codec.encode_action(b.action_id),
                                "resource_type_id": self._codec.encode_resource_type(b.resource_type)
                                if b.resource_type
                                else "",
                            }
                            for b in r.actions
                        ],
                    },
                    reason="New role",
                )
            )

        return changes

    # ================================================================
    # Diff 逻辑（系统已注册时使用）
    # ================================================================

    def _diff_system(self, remote: dict | None) -> list[Change]:
        local = {
            "id": self._system.id,
            "name": self._system.name,
            "description": self._system.description,
            "managers": list(self._system.managers),
            "clients": list(self._system.clients),
            "callback_url": self._system.callback_url,
        }
        if remote is None:
            return [
                Change(
                    kind=EntityKind.SYSTEM,
                    change_type=ChangeType.CREATE,
                    entity_id=self._system.id,
                    after=local,
                    reason="System not registered in IAM v4",
                )
            ]
        remote_data = remote.get("data", remote)
        keys = {"id", "name", "description", "managers", "clients", "callback_url"}
        if self._dicts_equal(local, remote_data, keys):
            return [Change(kind=EntityKind.SYSTEM, change_type=ChangeType.NOOP, entity_id=self._system.id)]
        return [
            Change(
                kind=EntityKind.SYSTEM,
                change_type=ChangeType.UPDATE,
                entity_id=self._system.id,
                before=remote_data,
                after=local,
                reason="System config differs",
            )
        ]

    def _diff_resource_types(self, remote: dict[str, dict]) -> list[Change]:
        changes: list[Change] = []
        local_rts = {rt.id: rt for rt in self._schema.all_resource_types() if is_visible_to(rt, "v4")}
        for rt_id, rt in local_rts.items():
            d_rt_id = self._codec.encode_resource_type(rt.id)
            d_anc = self._codec.encode_resource_type(rt.ancestor) if rt.ancestor else ""
            local = {"id": d_rt_id, "name": rt.name, "ancestors": [d_anc] if d_anc else []}
            if d_rt_id not in remote:
                changes.append(
                    Change(
                        kind=EntityKind.RESOURCE_TYPE,
                        change_type=ChangeType.CREATE,
                        entity_id=rt_id,
                        after=local,
                        reason="New resource type",
                    )
                )
            else:
                rmt = remote[d_rt_id]
                rmt_anc = rmt.get("ancestors") or []
                if isinstance(rmt_anc, str):
                    rmt_anc = [rmt_anc]
                if rmt.get("name") != rt.name or rmt_anc != local["ancestors"]:
                    changes.append(
                        Change(
                            kind=EntityKind.RESOURCE_TYPE,
                            change_type=ChangeType.UPDATE,
                            entity_id=rt_id,
                            before=rmt,
                            after=local,
                            reason="Resource type differs",
                        )
                    )
                else:
                    changes.append(
                        Change(
                            kind=EntityKind.RESOURCE_TYPE,
                            change_type=ChangeType.NOOP,
                            entity_id=rt_id,
                        )
                    )
        local_dialect_ids = {self._codec.encode_resource_type(rt_id) for rt_id in local_rts}
        for d_rt_id in set(remote) - local_dialect_ids:
            changes.append(
                Change(
                    kind=EntityKind.RESOURCE_TYPE,
                    change_type=ChangeType.DELETE,
                    entity_id=self._codec.decode_resource_type(d_rt_id),
                    before=remote[d_rt_id],
                    reason="Not in local schema",
                    destructive=True,
                )
            )
        return changes

    def _diff_actions(self, remote: dict[str, dict]) -> list[Change]:
        changes: list[Change] = []
        local_actions = {a.id: a for a in self._schema.all_actions() if is_visible_to(a, "v4")}
        for aid, a in local_actions.items():
            d_aid = self._codec.encode_action(a.id)
            d_rt = self._codec.encode_resource_type(a.resource_type) if a.resource_type else ""
            local = {"id": d_aid, "name": a.name, "resource_type_id": d_rt}
            if d_aid not in remote:
                changes.append(
                    Change(
                        kind=EntityKind.ACTION,
                        change_type=ChangeType.CREATE,
                        entity_id=aid,
                        after=local,
                        reason="New action",
                    )
                )
            else:
                rmt = remote[d_aid]
                if rmt.get("name") != a.name or rmt.get("resource_type_id") != d_rt:
                    changes.append(
                        Change(
                            kind=EntityKind.ACTION,
                            change_type=ChangeType.UPDATE,
                            entity_id=aid,
                            before=rmt,
                            after=local,
                            reason="Action differs",
                        )
                    )
                else:
                    changes.append(Change(kind=EntityKind.ACTION, change_type=ChangeType.NOOP, entity_id=aid))
        local_dialect_ids = {self._codec.encode_action(aid) for aid in local_actions}
        for d_aid in set(remote) - local_dialect_ids:
            changes.append(
                Change(
                    kind=EntityKind.ACTION,
                    change_type=ChangeType.DELETE,
                    entity_id=self._codec.decode_action(d_aid),
                    before=remote[d_aid],
                    reason="Not in local schema",
                    destructive=True,
                )
            )
        return changes

    def _diff_roles(self, remote: dict[str, dict]) -> list[Change]:
        changes: list[Change] = []
        local_roles = {r.id: r for r in self._schema.all_roles() if is_visible_to(r, "v4")}
        for rid, r in local_roles.items():
            d_rid = self._codec.encode_role(r.id)
            local_actions = [
                {
                    "id": self._codec.encode_action(b.action_id),
                    "resource_type_id": self._codec.encode_resource_type(b.resource_type) if b.resource_type else "",
                }
                for b in r.actions
            ]
            local = {"id": d_rid, "name": r.name, "description": r.description, "actions": local_actions}
            if d_rid not in remote:
                changes.append(
                    Change(
                        kind=EntityKind.ROLE,
                        change_type=ChangeType.CREATE,
                        entity_id=rid,
                        after=local,
                        reason="New role",
                    )
                )
            else:
                rmt = remote[d_rid]
                rmt_actions = sorted(
                    [
                        {"id": a["id"], "resource_type_id": a.get("resource_type_id", "")}
                        for a in rmt.get("actions", [])
                    ],
                    key=lambda x: (x["id"], x["resource_type_id"]),
                )
                loc_actions = sorted(local_actions, key=lambda x: (x["id"], x["resource_type_id"]))
                if rmt.get("name") != r.name or rmt_actions != loc_actions:
                    changes.append(
                        Change(
                            kind=EntityKind.ROLE,
                            change_type=ChangeType.UPDATE,
                            entity_id=rid,
                            before=rmt,
                            after=local,
                            reason="Role differs",
                        )
                    )
                else:
                    changes.append(Change(kind=EntityKind.ROLE, change_type=ChangeType.NOOP, entity_id=rid))
        local_dialect_ids = {self._codec.encode_role(rid) for rid in local_roles}
        for d_rid in set(remote) - local_dialect_ids:
            changes.append(
                Change(
                    kind=EntityKind.ROLE,
                    change_type=ChangeType.DELETE,
                    entity_id=self._codec.decode_role(d_rid),
                    before=remote[d_rid],
                    reason="Not in local schema",
                    destructive=True,
                )
            )
        return changes

    # ================================================================
    # 执行变更
    # ================================================================

    def _apply_change(self, change: Change) -> None:
        if change.kind == EntityKind.SYSTEM:
            if change.change_type == ChangeType.CREATE:
                self._client.create_system(change.after or {})
            elif change.change_type == ChangeType.UPDATE:
                self._client.update_system(change.after or {})
        elif change.kind == EntityKind.RESOURCE_TYPE:
            d_entity_id = self._codec.encode_resource_type(change.entity_id)
            if change.change_type == ChangeType.CREATE:
                self._client.batch_create_resource_types([change.after])
            elif change.change_type == ChangeType.UPDATE:
                self._client.update_resource_type(d_entity_id, change.after or {})
            elif change.change_type == ChangeType.DELETE:
                self._client.delete_resource_type(d_entity_id)
        elif change.kind == EntityKind.ACTION:
            d_entity_id = self._codec.encode_action(change.entity_id)
            if change.change_type == ChangeType.CREATE:
                self._client.batch_create_actions([change.after])
            elif change.change_type == ChangeType.UPDATE:
                self._client.update_action(d_entity_id, change.after or {})
            elif change.change_type == ChangeType.DELETE:
                self._client.delete_action(d_entity_id)
        elif change.kind == EntityKind.ROLE:
            d_entity_id = self._codec.encode_role(change.entity_id)
            if change.change_type == ChangeType.CREATE:
                self._client.batch_create_roles([change.after])
            elif change.change_type == ChangeType.UPDATE:
                self._client.update_role(
                    d_entity_id,
                    {
                        "name": (change.after or {}).get("name", ""),
                        "description": (change.after or {}).get("description", ""),
                    },
                )
                # 计算 actions 增量差异（v4 平台 DELETE/POST 均要求非空数组）
                before_actions = (change.before or {}).get("actions", []) or []
                after_actions = (change.after or {}).get("actions", []) or []

                def _key(a: dict) -> tuple:
                    return (a.get("id", ""), a.get("resource_type_id", ""))

                before_map = {_key(a): a for a in before_actions}
                after_map = {_key(a): a for a in after_actions}
                to_remove = [before_map[k] for k in before_map.keys() - after_map.keys()]
                to_add = [after_map[k] for k in after_map.keys() - before_map.keys()]
                if to_remove:
                    self._client.batch_delete_role_actions(d_entity_id, to_remove)
                if to_add:
                    self._client.batch_create_role_actions(d_entity_id, to_add)
            elif change.change_type == ChangeType.DELETE:
                self._client.delete_role(d_entity_id)

    # ================================================================
    # helpers
    # ================================================================

    @staticmethod
    def _ancestor_depth(change: Change) -> int:
        """计算资源类型的祖先深度（用于拓扑排序）。顶级资源=0，子资源=祖先数。"""
        ancestors = (change.after or {}).get("ancestors", []) or (change.before or {}).get("ancestors", [])
        if isinstance(ancestors, str):
            ancestors = [ancestors]
        return len(ancestors)

    @classmethod
    def _topology_sort(cls, changes: list[Change]) -> list[Change]:
        """按拓扑顺序排序 changes。

        总体两阶段：CREATE/UPDATE 全部先执行 → DELETE 全部后执行。
        CREATE/UPDATE 阶段内：System → RT(父→子) → Action → Role
        DELETE 阶段内：Role → Action → RT(子→父) → System
        （避免出现 "action 还被 role 引用就先删 action" 的问题）
        """

        def key(c: Change) -> tuple:
            kind_order = cls._KIND_ORDER.get(c.kind, 99)
            depth = cls._ancestor_depth(c)
            # phase=0: CREATE/UPDATE/NOOP；phase=1: DELETE（整体后置）
            if c.change_type == ChangeType.DELETE:
                return (1, -kind_order, -depth, c.entity_id)
            return (0, kind_order, depth, c.entity_id)

        return sorted(changes, key=key)

    @staticmethod
    def _dicts_equal(local: dict, remote: dict, keys: set) -> bool:
        for k in keys:
            lv = local.get(k)
            rv = remote.get(k)
            if isinstance(lv, list) and isinstance(rv, list):
                if sorted(lv) != sorted(rv):
                    return False
            elif lv != rv:
                return False
        return True
