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
# V3Migrator — IAM v3 模型迁移（plan_migration / apply_migration）
#
# 与 v4 的 V4Migrator 对齐：迁移逻辑独立于鉴权 Provider，
# V3PermissionProvider 的 plan_migration / apply_migration 委托本类执行。
# ---------------------------------------------------------------------------

from __future__ import annotations

from typing import TYPE_CHECKING
from collections.abc import Callable

from iam.contrib.iam_migration.utils.do_migrate import Client as IamMigrateClient

from ..iam_engine.core.exceptions import DestructiveMigrationBlocked, MigrationFailed
from ..iam_engine.provider.codec import IdentityCodec
from ..iam_engine.schema.diff import Change, ChangeType, EntityKind, MigrationPlan, MigrationReport
from ..iam_engine.schema.definitions import ActionDef, ResourceTypeDef
from ..iam_engine.schema.visibility import is_change_visible_to, is_visible_to
from .client import V3Client
from .config import V3Options

if TYPE_CHECKING:
    from ..iam_engine.schema.registry import SchemaRegistry


class V3Migrator:
    """IAM v3 模型迁移器。

    plan_migration(scope) —— 从本地 schema + 系统配置生成迁移计划（不查远端）。
        scope="system" 只生成系统注册 Change；
        scope="full" 生成系统 + 资源类型 + 操作的全量 Change。

    apply_migration(plan) —— 查远端 + reconcile + 执行。
        根据 plan 中的 Change 类型决定查询范围，将每个 Change 与远端实际状态
        做 reconcile（CREATE+已有→跳过, UPDATE+没有→降级CREATE, DELETE+没有→跳过），
        并按"两阶段排序"执行（DELETE 前置：平台约束同 system 内 action name 唯一，
        id 变更必须"先删旧、再建新"）。

    异常：执行失败抛 MigrationFailed；破坏性变更未显式允许抛
        DestructiveMigrationBlocked（方言 id 变更拦截等）。
    """

    _KIND_ORDER: dict[EntityKind, int] = {
        EntityKind.SYSTEM: 0,
        EntityKind.RESOURCE_TYPE: 1,
        EntityKind.ACTION: 2,
        EntityKind.ROLE: 3,
    }

    def __init__(
        self,
        iam_client: V3Client,
        schema: SchemaRegistry,
        cfg: V3Options,
        codec: IdentityCodec,
        provider_name: str = "v3",
    ) -> None:
        """初始化 V3 迁移器。

        Args:
            iam_client: V3Client，用于查询远端系统/实体状态（query_system）。
            schema: 冻结的 SchemaRegistry（本地 definitions 与方言字段兜底来源）。
            cfg: V3Options（system 配置 / credentials / base_url / provider_config_path 等）。
            codec: action_id 等方言编解码器（与 Provider 同一实例）。
            provider_name: Provider 标识（迁移报告与 recorder 记录使用）。
        """
        self._iam_client: V3Client = iam_client
        self.schema: SchemaRegistry = schema
        self._cfg: V3Options = cfg
        self.codec: IdentityCodec = codec
        self.provider_name: str = provider_name

    # ================================================================
    # plan_migration —— 本地生成迁移计划（不查远端）
    # ================================================================

    def plan_migration(self, *, scope: str = "full") -> MigrationPlan:
        """从本地 definitions + V3Options 生成迁移计划（不查远端）。

        Args:
            scope: "system" 只生成系统注册 Change；
                   "full" 生成系统+资源类型+操作的全量 Change。

        Returns:
            MigrationPlan: 包含 provider_name 和 changes 列表的变更计划。
        """
        changes: list[Change] = []

        # ---- System ----
        # 只含"已配置"字段：name_en/description_en 为空串表示未配置（不管理，
        # 远端保留既有值）；实际注册以 _reconcile_system_changes 为准。
        system_info: dict = {
            "id": self._cfg.system.id,
            "name": self._cfg.system.name,
            "description": self._cfg.system.description,
            "clients": list(self._cfg.system.clients),
        }
        if self._cfg.system.name_en:
            system_info["name_en"] = self._cfg.system.name_en
        if self._cfg.system.description_en:
            system_info["description_en"] = self._cfg.system.description_en
        changes.append(
            Change(
                kind=EntityKind.SYSTEM,
                change_type=ChangeType.CREATE,
                entity_id=self._cfg.system.id,
                after=system_info,
                reason="System registration (local plan)",
            )
        )

        if scope == "system":
            return MigrationPlan(provider_name=self.provider_name, changes=changes)

        # ---- Resource Types ----
        for rt in self.schema.all_resource_types():
            if not is_visible_to(rt, self.provider_name):
                continue
            v3_ext = dict(rt.extensions.get("v3", {}))
            if not v3_ext:
                continue
            changes.append(
                Change(
                    kind=EntityKind.RESOURCE_TYPE,
                    change_type=ChangeType.CREATE,
                    entity_id=rt.id,
                    after={
                        "id": rt.id,
                        "name": rt.name,
                        "name_en": v3_ext.get("name_en") or rt.id,
                        "system_id": v3_ext.get("system_id", self._cfg.system.id),
                        "selection_mode": v3_ext.get("selection_mode", "instance"),
                        "related_instance_selections": v3_ext.get("related_instance_selections", []),
                        # v3 平台必填：资源实例回调 API 路径（老版本在迁移 json 配置，现从 options 读）
                        "provider_config": {"path": self._cfg.provider_config_path},
                    },
                    reason="New resource type",
                )
            )

        # ---- Actions ----
        for action in self.schema.all_actions():
            if not is_visible_to(action, self.provider_name):
                continue
            v3_ext = dict(action.extensions.get("v3", {}))
            if not v3_ext:
                continue
            dialect_id = self.codec.encode_action(action.id)
            changes.append(
                Change(
                    kind=EntityKind.ACTION,
                    change_type=ChangeType.CREATE,
                    entity_id=action.id,
                    after={
                        "id": dialect_id,
                        "name": action.name,
                        "name_en": v3_ext.get("name_en") or action.id,
                        "type": v3_ext.get("type", ""),
                        "version": v3_ext.get("version", 1),
                        "related_actions": v3_ext.get("related_actions", []),
                        "related_resource_types": self._build_related_resource_types(action),
                    },
                    reason="New action",
                )
            )

        return MigrationPlan(provider_name=self.provider_name, changes=changes)

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
        """应用变更计划（查远端 + reconcile + 执行）。

        根据 plan 中的 Change 类型决定查询范围：
          - 只有 SYSTEM → 只查远端系统信息
          - 包含 ACTION/RT → 查远端全量

        Args:
            plan: plan_migration 或迁移文件产出的 Change 列表。
            dry_run: 只演练，不真正提交。
            allow_destructive: 是否允许破坏性变更。
        """
        report = MigrationReport(provider_name=self.provider_name)

        if plan.has_destructive() and not allow_destructive:
            report.skipped_reason = "Destructive changes blocked; set allow_destructive=True"
            return report

        # ---- 可见性过滤：SYSTEM 无 extensions 概念放行；其余按 payload.extensions 判定 ----
        # 迁移文件生成阶段是 provider 中立的（diff 层只搬运不解释 extensions），
        # 因此把 only_providers / exclude_providers 的过滤下沉到 apply 阶段。
        # 目前主要治愈潜在场景（如 only_providers=("v4",)、exclude_providers=("v3",)），
        # 与 v4 apply 入口过滤保持对称，避免未来增加 v3 排除项时重复踩坑。
        visible_changes: list[Change] = []
        for c in plan.changes:
            if c.kind == EntityKind.SYSTEM or is_change_visible_to(c, self.provider_name):
                visible_changes.append(c)
            else:
                report.skipped.append((c, "not_visible_to_provider"))
        plan = MigrationPlan(provider_name=self.provider_name, changes=visible_changes)

        # ---- SYSTEM reconcile：查远端系统，决定实际操作 ----
        system_changes = [c for c in plan.changes if c.kind == EntityKind.SYSTEM and c.change_type != ChangeType.NOOP]
        has_system = bool(system_changes)
        if has_system:
            ok, _msg, data = self._iam_client.query_system()
            remote_system = data.get("base_info") if ok else None
            reconciled_system = self._reconcile_system_changes(system_changes, remote_system)
            other_changes = [c for c in plan.changes if c.kind != EntityKind.SYSTEM]
            plan = MigrationPlan(provider_name=self.provider_name, changes=reconciled_system + other_changes)

        # ---- ACTION / RT reconcile：查远端全量 ----
        has_entities = any(c.kind in (EntityKind.ACTION, EntityKind.RESOURCE_TYPE) for c in plan.changes)
        remote_actions: set[str] = set()
        remote_rts: set[str] = set()
        if has_entities:
            ok, _msg, data = self._iam_client.query_system()
            if ok:
                remote_actions = {a["id"] for a in (data.get("actions") or [])}
                remote_rts = {r["id"] for r in (data.get("resource_types") or [])}

        # 迁移执行 client（SDK 返回码风格，非异常风格）
        client = IamMigrateClient(
            self._cfg.credentials.app_code,
            self._cfg.credentials.app_secret,
            self._cfg.base_url,
            bk_tenant_id=self._cfg.bk_tenant_id,
        )

        # ---- 执行前两阶段排序：DELETE 前置（引用者先删），CREATE/UPDATE 后置（被引用者先建）----
        # 平台约束：同 system 内 action name 唯一（含不同 id），"先建后删"的同名重建会被拒绝；
        # 因此 id 变更（rename）必须"先删旧、再建新"。同阶段内保持 diff 相对顺序，
        # 不破坏依赖：CREATE/UPDATE 阶段 RT 先于 ACTION；DELETE 阶段 ACTION 先于 RT。

        def _exec_sort_key(c: Change) -> tuple:
            kind = self._KIND_ORDER.get(c.kind, 99)
            if c.change_type == ChangeType.DELETE:
                return (0, -kind, c.entity_id)
            return (1, kind, c.entity_id)

        plan = MigrationPlan(
            provider_name=self.provider_name,
            changes=sorted(plan.changes, key=_exec_sort_key),
        )

        for change in plan.changes:
            if change.change_type == ChangeType.NOOP:
                continue

            # ROLE：v3 平台无角色实体概念，静默跳过（不产生平台调用、不计入 applied）
            if change.kind == EntityKind.ROLE:
                report.skipped.append((change, "no_platform_concept"))
                continue

            # SYSTEM 已在主循环前通过 _reconcile_system_changes 单独 reconcile，
            # 这里直接执行，不再经过 _reconcile_change（后者对 SYSTEM 返回 None）
            actual = (
                change
                if change.kind == EntityKind.SYSTEM
                else self._reconcile_change(change, remote_actions, remote_rts)
            )
            if actual is None:
                # reconcile 判定无需执行（如平台已存在）→ 跳过并记录原因
                report.skipped.append((change, "remote_exists"))
                continue

            if dry_run:
                report.would_apply.append(actual)
                continue

            try:
                self._execute_change(client, actual, allow_destructive=allow_destructive)
                report.applied.append(actual)
            except Exception as e:
                report.failed.append((actual, f"{type(e).__name__}: {e}"[:500]))

        return report

    # ================================================================
    # 内部：reconcile
    # ================================================================

    def _reconcile_system_changes(self, system_changes: list, remote_system: dict | None) -> list:
        """用远端系统信息 reconcile 本地的 SYSTEM Change。

        remote_system=None → 系统未注册 → 保留 CREATE。
        remote_system 已存在且匹配 → 替换为 NOOP。
        remote_system 已存在但不同 → 替换为 UPDATE。

        全部由 default 配置驱动（配置即权威，不做本地∪平台合并）：
          * id/name/description/name_en/description_en/clients 均为配置字段；
          * clients 以配置为准整体比较与同步（默认值即老版本 json 的
            "bk_monitorv3,bkci,bk_paas3,paasv3cli"），部署方通过环境变量
            BK_IAM_V3_SYSTEM_CLIENTS 控制白名单；
          * name_en/description_en 默认取老版本 json 既有值（非空），
            显式配空串 = 不管理该字段；
          * 平台 system 模型无 managers 字段，配置契约中已移除。
        """

        def _to_csv(items) -> str:
            return ",".join(x for x in items if x)

        def _csv_set(raw) -> set:
            return {x for x in (raw or "").split(",") if x}

        # 只含已配置字段：name_en/description_en 空串时不加入（不管理）
        local: dict = {
            "id": self._cfg.system.id,
            "name": self._cfg.system.name,
            "description": self._cfg.system.description,
            "clients": _to_csv(self._cfg.system.clients),
        }
        if self._cfg.system.name_en:
            local["name_en"] = self._cfg.system.name_en
        if self._cfg.system.description_en:
            local["description_en"] = self._cfg.system.description_en
        if remote_system is None:
            return system_changes  # 系统未注册，保留原样（CREATE）

        # 已配置字段（clients 按集合比较，顺序无关）与远端一致 → NOOP
        meta_ok = self._system_dicts_equal(local, remote_system, set(local) - {"clients"})
        clients_ok = _csv_set(local["clients"]) == _csv_set(remote_system.get("clients"))
        if meta_ok and clients_ok:
            return [Change(kind=EntityKind.SYSTEM, change_type=ChangeType.NOOP, entity_id=self._cfg.system.id)]

        # UPDATE：以本地配置为准整体同步（clients 不做合并，按配置覆盖）
        return [
            Change(
                kind=EntityKind.SYSTEM,
                change_type=ChangeType.UPDATE,
                entity_id=self._cfg.system.id,
                before=remote_system,
                after=local,
                reason="System config differs",
            )
        ]

    @staticmethod
    def _system_dicts_equal(local: dict, remote: dict, keys: set) -> bool:
        for k in keys:
            lv = local.get(k)
            rv = remote.get(k)
            if isinstance(lv, list) and isinstance(rv, list):
                if sorted(lv) != sorted(rv):
                    return False
            elif lv != rv:
                return False
        return True

    def _reconcile_change(self, change: Change, remote_actions: set[str], remote_rts: set[str]) -> Change | None:
        """将单个 Change 与远端实际状态做 reconcile。

        存在性判定使用【方言 id】而非框架 id：ACTION 优先取 extensions["v3"]["action_id"]
        （与 _execute_change 的 enrich 同一来源），缺失时回退 codec 编码。
        避免"框架 id ≠ 方言 id"的 action（如 view_rum_application → view_rum_application_v2）
        被误判为平台缺失，从而对已存在实体重复 CREATE（add_action 失败）。

        判定 id 按 change_type 取实体"在平台上的形态"：
          * CREATE → after（新实体的方言 id）
          * UPDATE / DELETE → before（实体当前在平台的方言 id）
        否则"方言 id 变更"的 UPDATE（after 方言 id 是新的、平台只有旧形态）会被
        误判为缺失而转成 CREATE，绕过 UPDATE 分支的方言变更检测
        （_action_dialect_id_changed → 拦截/重建逻辑失效）。

        Returns:
            应执行的 Change；None 表示无需操作（跳过）。
        """
        kind = change.kind
        if kind == EntityKind.SYSTEM:
            return None  # SYSTEM 已在 apply_migration 主循环前单独 reconcile，这里不应再出现

        # UPDATE / DELETE 以 before（当前在平台的形态）判定；CREATE 用 after
        probe = change.after if change.change_type == ChangeType.CREATE else change.before
        probe = probe or {}
        dialect_id = probe.get("id", change.entity_id) if probe else change.entity_id

        if kind == EntityKind.ACTION:
            v3_ext = probe.get("extensions") or {}
            v3_ext = v3_ext.get("v3") or {}
            ext_action_id = v3_ext.get("action_id")
            if ext_action_id:
                dialect_id = ext_action_id
            elif change.entity_id:
                dialect_id = self.codec.encode_action(change.entity_id)
            exists = dialect_id in remote_actions
        elif kind == EntityKind.RESOURCE_TYPE:
            exists = dialect_id in remote_rts
        else:
            return change

        if change.change_type == ChangeType.CREATE and exists:
            return None  # 远端已有，跳过
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
    # 内部：执行
    # ================================================================

    def _execute_change(self, client, change: Change, *, allow_destructive: bool = False) -> None:
        """按 Change 类型调用 V3 SDK Client 执行（CREATE/UPDATE 前统一方言补全）。

        职责分层：
          * _enrich_action_payload / _enrich_resource_type_payload：方言字段补全
            （优先 after.extensions——迁移文件自包含；缺失回查 schema——兼容旧文件）
          * _apply_*_change：按类型执行；ACTION UPDATE 时检测方言 id 变更，
            不允许破坏性变更则明确报错，允许则按"先删后建"重建
        """
        if change.kind == EntityKind.SYSTEM:
            self._apply_system_change(client, change)
            return
        if change.kind == EntityKind.ACTION:
            data = self._enrich_action_payload(change, dict(change.after or {}))
            self._apply_action_change(client, change, data, allow_destructive)
            return
        if change.kind == EntityKind.RESOURCE_TYPE:
            data = self._enrich_resource_type_payload(change, dict(change.after or {}))
            self._apply_resource_type_change(client, change, data)
            return
        # ROLE：防御分支（正常路径已在 apply 循环前置进 skipped，见 apply_migration）

    def _v3_ext_of(self, data: dict, lookup: Callable[[], ActionDef | ResourceTypeDef]) -> tuple:
        """取 v3 方言字段与实体定义。

        - v3_ext：优先 after.extensions（迁移文件自包含，不解释其内部）；
          缺失时回查 schema（兼容 plan_migration 扁平 after 与旧迁移文件）。
        - entity_def：总是尝试从 schema 获取（related_resource_types / parents 等
          平台结构需要从定义重建），获取失败时为 None。

        Returns:
            (v3_ext, entity_def)：entity_def 为 ActionDef/ResourceTypeDef 或 None
        """
        v3_ext = dict((data.get("extensions") or {}).get("v3", {}))
        entity = None
        try:
            entity = lookup()
            if not v3_ext:
                v3_ext = dict(entity.extensions.get("v3", {}))
        except Exception:
            entity = None
        return v3_ext, entity

    def _action_v3_ext(self, change: Change, data: dict) -> tuple:
        return self._v3_ext_of(data, lambda: self.schema.get_action(change.entity_id))

    def _resource_type_v3_ext(self, change: Change, data: dict) -> tuple:
        return self._v3_ext_of(data, lambda: self.schema.get_resource_type(change.entity_id))

    def _enrich_action_payload(self, change: Change, data: dict) -> dict:
        """ACTION 方言补全：id 编码 + name_en/type/version/related_actions/related_resource_types。"""
        v3_ext, action_def = self._action_v3_ext(change, data)
        # id：diff/迁移文件链路的 after 为业务 id，必须编码为 v3 平台方言 id（encode 幂等）
        data["id"] = self.codec.encode_action(change.entity_id)
        if change.change_type not in (ChangeType.CREATE, ChangeType.UPDATE):
            return data
        data.setdefault("name_en", v3_ext.get("name_en") or change.entity_id)
        if action_def is not None:
            data.setdefault("related_resource_types", self._build_related_resource_types(action_def))
            data.setdefault("type", v3_ext.get("type", ""))
            data.setdefault("version", v3_ext.get("version", 1))
            data.setdefault("related_actions", v3_ext.get("related_actions", []))
        # resource_type_id 是框架概念字段，v3 平台不识别，剔除
        data.pop("resource_type_id", None)
        return data

    def _enrich_resource_type_payload(self, change: Change, data: dict) -> dict:
        """RT 方言补全：id 编码 + name_en/provider_config/system_id/selection_mode/parents。"""
        v3_ext, rt_def = self._resource_type_v3_ext(change, data)
        data["id"] = self.codec.encode_resource_type(change.entity_id)
        if change.change_type not in (ChangeType.CREATE, ChangeType.UPDATE):
            return data
        data.setdefault("name_en", v3_ext.get("name_en") or change.entity_id)
        data.setdefault("provider_config", {"path": self._cfg.provider_config_path})
        if rt_def is not None:
            data.setdefault("system_id", v3_ext.get("system_id", self._cfg.system.id))
            data.setdefault("selection_mode", v3_ext.get("selection_mode", "instance"))
            data.setdefault("related_instance_selections", v3_ext.get("related_instance_selections", []))
        self._apply_parents(change, data, rt_def)
        return data

    def _apply_parents(self, change: Change, data: dict, rt_def: ResourceTypeDef | None) -> None:
        """框架 ancestors -> v3 parents；ancestor 缺失时从 schema 的 rt_def.ancestor 补。"""
        if data.get("parents"):
            return
        ancestor_ids = [a if isinstance(a, str) else a.get("id", "") for a in (data.pop("ancestors", None) or [])]
        if not ancestor_ids and rt_def is not None and rt_def.ancestor:
            ancestor_ids = [rt_def.ancestor]
        ancestor_ids = [a for a in ancestor_ids if a]
        if ancestor_ids:
            data["parents"] = [{"id": a, "system_id": data.get("system_id", self._cfg.system.id)} for a in ancestor_ids]

    def _apply_system_change(self, client, change: Change) -> None:
        system_id = self._cfg.system.id
        data = change.after or {}
        if change.change_type == ChangeType.CREATE:
            ok, _msg = client.add_system(system_id, data)
        elif change.change_type == ChangeType.UPDATE:
            ok, _msg = client.update_system(system_id, data)
        else:
            return
        if not ok:
            raise MigrationFailed(f"System {change.change_type.value} failed: {_msg}")

    def _apply_action_change(self, client, change: Change, data: dict, allow_destructive: bool) -> None:
        """ACTION 执行；UPDATE 时检测方言 id 变更（重建或报错，见 _action_dialect_id_changed）。"""
        system_id = self._cfg.system.id
        if change.change_type == ChangeType.CREATE:
            ok, _msg = client.add_action(system_id, data)
        elif change.change_type == ChangeType.UPDATE:
            old_dialect_id = self._action_dialect_id_changed(change, data)
            if old_dialect_id:
                if not allow_destructive:
                    raise DestructiveMigrationBlocked(
                        "action 方言 id 变更（{} -> {}）需要重建，"
                        "请允许破坏性变更后执行（migrate 命令加 --allow-destructive），"
                        "或先清理旧 action 的关联策略".format(old_dialect_id, data.get("id"))
                    )
                self._rebuild_action(client, system_id, old_dialect_id, data)
                return
            ok, _msg = client.update_action(system_id, data)
        elif change.change_type == ChangeType.DELETE:
            ok, _msg = client.delete_action(system_id, data)
        else:
            return
        if not ok:
            raise MigrationFailed("Action {} {} failed: {}".format(change.change_type.value, data.get("id"), _msg))

    def _action_dialect_id_changed(self, change: Change, data: dict) -> str | None:
        """方言 id 变更检测：before/after 的 extensions["v3"]["action_id"] 不同则返回旧方言 id。

        依赖新 diff 产物（before/after 含 extensions）；旧迁移文件无 extensions 时无法检测（返回 None）。
        """
        before = change.before or {}
        old = (before.get("extensions") or {}).get("v3", {}).get("action_id", "")
        new = (data.get("extensions") or {}).get("v3", {}).get("action_id", "") or data.get("id", "")
        if old and new and old != new:
            return old
        return None

    def _rebuild_action(self, client, system_id: str, old_dialect_id: str, data: dict) -> None:
        """方言 id 变更重建（先删后建）。

        与 apply_migration 的两阶段排序（DELETE 前置）保持一致：平台约束
        同 system 内 action name 唯一（含不同 id），同名"先建后删"会被拒绝，
        因此必须"先删旧、再建新"。

        幂等兜底：delete_action 对不存在的 id 报 conflict（非幂等）；重跑场景
        旧方言 id 可能已被上次删除 → 删除失败时查 query_system 确认旧 id 已
        不存在，已不存在则视为删除成功继续建新。真正删除失败（如策略关联）
        时明确报错，提示先撤销关联策略。
        """
        ok, _msg = client.delete_action(system_id, {"id": old_dialect_id})
        if not ok:
            # 确认是否已不存在（幂等重跑场景：旧 id 已被上次删除）
            _ok2, _m2, remote = self._iam_client.query_system()
            remote_ids = {a["id"] for a in (remote or {}).get("actions") or []} if _ok2 else set()
            if old_dialect_id in remote_ids:
                raise MigrationFailed(
                    f"重建失败：旧 action {old_dialect_id} 删除失败（{_msg}）；请先撤销其关联策略后重试"
                )
            # 旧 id 已不存在 → 视为删除成功，继续建新
        ok, _msg = client.add_action(system_id, data)
        if not ok:
            raise MigrationFailed(
                "重建失败：新 action {} 创建失败（{}）；旧 action {} 已删除，重跑 migrate 可重试".format(
                    data.get("id"), _msg, old_dialect_id
                )
            )

    def _apply_resource_type_change(self, client, change: Change, data: dict) -> None:
        system_id = self._cfg.system.id
        if change.change_type == ChangeType.CREATE:
            ok, _msg = client.add_resource_type(system_id, data)
        elif change.change_type == ChangeType.UPDATE:
            ok, _msg = client.update_resource_type(system_id, data)
        elif change.change_type == ChangeType.DELETE:
            ok, _msg = client.delete_resource_type(system_id, data)
        else:
            return
        if not ok:
            raise MigrationFailed(
                "ResourceType {} {} failed: {}".format(change.change_type.value, data.get("id"), _msg)
            )

    # ================================================================
    # 内部：从 schema 拼 V3 的 related_resource_types
    # ================================================================

    def _build_related_resource_types(self, action_def: ActionDef) -> list[dict]:
        """从 ActionDef.resource_type + ResourceTypeDef.extensions["v3"] 拼出 V3 格式。"""
        rt_id = action_def.resource_type
        if not rt_id:
            return []
        try:
            rt_def = self.schema.get_resource_type(rt_id)
            v3_ext = dict(rt_def.extensions.get("v3", {}))
        except Exception:
            v3_ext = {}
        return [
            {
                "system_id": v3_ext.get("system_id", self._cfg.system.id),
                "id": rt_id,
                "selection_mode": v3_ext.get("selection_mode", "instance"),
                "related_instance_selections": v3_ext.get("related_instance_selections", []),
            }
        ]
