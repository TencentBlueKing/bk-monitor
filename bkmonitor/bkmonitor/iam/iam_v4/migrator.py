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

from ..iam_engine.core.exceptions import MigrationFailed, ProviderUnavailable
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

    plan_migration(scope) —— 从本地 schema + 系统配置生成迁移计划（不查远端）。
        scope="system" 只生成系统注册 Change；
        scope="full" 生成系统+资源类型+操作+角色的全量 Change。

    apply_migration(plan) —— 查远端 + reconcile + 执行。
        根据 plan 中的 Change 类型决定查询范围，将每个 Change 与远端实际状态
        做 reconcile（CREATE+已有→跳过, UPDATE+没有→降级CREATE, DELETE+没有→跳过）。

    可见性过滤：仅处理对 provider_name="v4" 可见的 schema 实体。
    """

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
        self._codec: NameCodec = codec or IdentityCodec()

    # ================================================================
    # plan_migration —— 纯本地生成（不查远端）
    # ================================================================

    def plan_migration(self, *, scope: str = "full") -> MigrationPlan:
        """从本地 definitions + 系统配置生成迁移计划。

        通过 _diff_system(None) / _diff_*(空 dict) 得到全量 CREATE Change。
        scope="system" 时只包含系统，其余 entity 不参与。

        Args:
            scope: "system" / "full"。
        """
        changes: list[Change] = []

        # System —— 通过 _diff_system(None) 得到 CREATE
        changes.extend(self._diff_system(None))

        if scope == "system":
            plan = MigrationPlan(provider_name="v4", changes=self._topology_sort(changes))
            logger.info("[iam_v4:migration:plan:system] %d change(s)", len(changes))
            return plan

        # ResourceTypes / Actions / Roles —— 通过 _diff_*(空 dict) 全部标记 CREATE
        changes.extend(self._diff_resource_types({}))
        changes.extend(self._diff_actions({}))
        changes.extend(self._diff_roles({}))

        plan = MigrationPlan(provider_name="v4", changes=self._topology_sort(changes))
        logger.info(
            "[iam_v4:migration:plan:full] summary=%s",
            plan.summary(),
        )
        return plan

    # ================================================================
    # apply_migration —— 查远端 + reconcile + 执行
    # ================================================================

    def apply_migration(
        self,
        plan: MigrationPlan,
        *,
        dry_run: bool = False,
        allow_destructive: bool = False,
    ) -> MigrationReport:
        """应用迁移计划（查远端 + reconcile + 执行）。

        入参 plan 可以来自 plan_migration 或迁移文件。
        """
        report = MigrationReport(provider_name="v4", started_at=datetime.now(tz=timezone.utc))

        if plan.has_destructive() and not allow_destructive:
            report.skipped_reason = "Destructive changes blocked; set allow_destructive=True"
            report.finished_at = datetime.now(tz=timezone.utc)
            logger.warning("[iam_v4:migration:apply] %s", report.skipped_reason)
            return report

        sorted_changes = self._topology_sort(plan.changes)

        # ---- SYSTEM reconcile：查远端系统，用 _diff_system 决定实际操作 ----
        has_system = self._has_entity_kinds(plan, {EntityKind.SYSTEM})
        if has_system:
            remote_system = self._fetch_remote_system()
            system_reconciled = self._diff_system(remote_system)
            # 用 reconcile 后的 system change 替换 plan 中原有的
            sorted_changes = system_reconciled + [c for c in sorted_changes if c.kind != EntityKind.SYSTEM]

        # ---- ACTION / RT / ROLE reconcile：查远端全量 ----
        has_entities = self._has_entity_kinds(plan, {EntityKind.ACTION, EntityKind.RESOURCE_TYPE, EntityKind.ROLE})
        remote_actions: dict[str, dict] = {}
        remote_rts: dict[str, dict] = {}
        remote_roles: dict[str, dict] = {}
        if has_entities:
            try:
                remote_actions = self._fetch_remote_actions()
            except Exception:
                pass
            try:
                remote_rts = self._fetch_remote_resource_types()
            except Exception:
                pass
            try:
                remote_roles = self._fetch_remote_roles()
            except Exception:
                pass

        for change in sorted_changes:
            if change.change_type == ChangeType.NOOP:
                continue

            # reconcile：将"本地期望"与"远端实际"对照，决定真实操作
            actual = self._reconcile_change(change, remote_actions, remote_rts, remote_roles)
            if actual is None:
                # reconcile 判定无需执行（如平台已存在）→ 跳过并记录原因
                report.skipped.append((change, "remote_exists"))
                continue

            if dry_run:
                report.would_apply.append(actual)
                continue

            try:
                self._apply_change(actual)
                report.applied.append(actual)
                logger.info("[iam_v4:migration:apply] %s %s", actual.change_type.value, actual.entity_id)
            except Exception as e:
                report.failed.append((actual, f"{type(e).__name__}: {e}"[:500]))
                logger.error("[iam_v4:migration:fail] %s %s: %s", actual.change_type.value, actual.entity_id, e)

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
    # reconcile
    # ================================================================

    @staticmethod
    def _has_entity_kinds(plan: MigrationPlan, kinds: set[EntityKind]) -> bool:
        return any(c.kind in kinds for c in plan.changes)

    @staticmethod
    def _reconcile_change(
        change: Change,
        remote_actions: dict[str, dict],
        remote_rts: dict[str, dict],
        remote_roles: dict[str, dict],
    ) -> Change | None:
        """将单个 Change 与远端实际状态做 reconcile。

        Returns:
            应执行的 Change；None 表示无需操作（跳过）。
        """
        kind = change.kind

        # SYSTEM 由调用方单独处理，这里原样返回
        if kind == EntityKind.SYSTEM:
            return change

        dialect_id = change.after.get("id", change.entity_id) if change.after else change.entity_id

        if kind == EntityKind.ACTION:
            exists = dialect_id in remote_actions
        elif kind == EntityKind.RESOURCE_TYPE:
            exists = dialect_id in remote_rts
        elif kind == EntityKind.ROLE:
            exists = dialect_id in remote_roles
        else:
            return change

        if change.change_type == ChangeType.CREATE and exists:
            return None
        if change.change_type == ChangeType.UPDATE and not exists:
            return Change(
                kind=kind,
                change_type=ChangeType.CREATE,
                entity_id=change.entity_id,
                after=change.after,
                reason=f"UPDATE→CREATE (not found remote): {change.reason}",
            )
        if change.change_type == ChangeType.DELETE and not exists:
            return None
        return change

    # ================================================================
    # 远端数据拉取（404 与真错误区分对待）
    # ================================================================

    def _fetch_remote_system(self) -> dict | None:
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
        items: dict[str, dict] = {}
        page = 1
        while page <= 100:
            resp = api_fn(page=page, page_size=100)
            data = resp.get("data", {})
            results = data.get("results") or []
            for item in results:
                items[item["id"]] = item
            pagination = data.get("pagination", {})
            total_pages = pagination.get("total_pages", 1)
            if page >= total_pages or not results:
                break
            page += 1
        return items

    # ================================================================
    # Diff 逻辑（_diff_system(None) → CREATE，_diff_*(空dict) → 全量 CREATE）
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
                    reason="System registration (local plan)",
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
                    changes.append(Change(kind=EntityKind.RESOURCE_TYPE, change_type=ChangeType.NOOP, entity_id=rt_id))
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
                rt_changed = rmt.get("resource_type_id", "") != d_rt
                name_changed = rmt.get("name") != a.name
                if rt_changed:
                    changes.append(
                        Change(
                            kind=EntityKind.ACTION,
                            change_type=ChangeType.DELETE,
                            entity_id=aid,
                            before=rmt,
                            reason="Action resource_type_id changed (recreate required)",
                            destructive=True,
                        )
                    )
                    changes.append(
                        Change(
                            kind=EntityKind.ACTION,
                            change_type=ChangeType.CREATE,
                            entity_id=aid,
                            after=local,
                            reason="Action resource_type_id changed (recreate required)",
                        )
                    )
                elif name_changed:
                    changes.append(
                        Change(
                            kind=EntityKind.ACTION,
                            change_type=ChangeType.UPDATE,
                            entity_id=aid,
                            before=rmt,
                            after=local,
                            reason="Action name differs",
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
        """执行单个 Change；失败统一包装为 MigrationFailed（与 v3 V3Migrator 对齐）。"""
        try:
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
                    self._client.update_action(d_entity_id, {"name": (change.after or {}).get("name", "")})
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
        except Exception as e:
            raise MigrationFailed(
                f"{change.kind.value} {change.change_type.value} {change.entity_id} failed: {e}"
            ) from e

    # ================================================================
    # helpers
    # ================================================================

    @staticmethod
    def _ancestor_depth(change: Change) -> int:
        ancestors = (change.after or {}).get("ancestors", []) or (change.before or {}).get("ancestors", [])
        if isinstance(ancestors, str):
            ancestors = [ancestors]
        return len(ancestors)

    @classmethod
    def _topology_sort(cls, changes: list[Change]) -> list[Change]:
        """按拓扑顺序排序 changes。

        总体两阶段：DELETE 全部先执行 → CREATE/UPDATE 后执行（先删后建）。
        与 v3 provider 执行策略一致：平台对同名实体重建（id 变更）有约束，
        必须先删旧再建新；同时保证依赖方向不被破坏——
        DELETE 阶段内：Role → Action → RT(子→父) → System（引用者先删）
        CREATE/UPDATE 阶段内：System → RT(父→子) → Action → Role（被引用者先建）
        """

        def key(c: Change) -> tuple:
            kind_order = cls._KIND_ORDER.get(c.kind, 99)
            depth = cls._ancestor_depth(c)
            if c.change_type == ChangeType.DELETE:
                return (0, -kind_order, -depth, c.entity_id)
            return (1, kind_order, depth, c.entity_id)

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
