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
# V3PermissionProvider — IAM v3 (ABAC) 鉴权 Provider
#
# 只实现"方言层"接口：接收编码后的 Dialect* 结构，通过 CompatibleIAM SDK
# 调用 V3 IAM 平台 API。业务命名 ↔ V3 方言的编解码全部由基类和注入的 codec 完成。
#
# codec 类通过 IAM_FRAMEWORK.PROVIDERS[*].options.codec_class 配置。
#
# 与 V4 Provider 的关键差异：
#   1. 使用 CompatibleIAM SDK（而非 V4 HTTP client）
#   2. 读操作走 is_allowed_with_cache（SDK 缓存），写操作走 is_allowed
#   3. 批量鉴权走 batch_resource_multi_actions_allowed
#   4. apply_url 走 SDK 的 Application + get_apply_url
#   5. Phase 1：plan_migration / apply_migration 返回空（V3 迁移走原有 JSON 方式）
# ---------------------------------------------------------------------------

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from iam.apply.models import (
    ActionWithoutResources,
    ActionWithResources,
    Application,
    RelatedResourceType,
    ResourceInstance,
    ResourceNode,
)
from iam.exceptions import AuthAPIError
from iam.utils import gen_perms_apply_data

from .client import V3Client
from ..iam_engine.core.types import (
    ResourceInstance as CoreResourceInstance,
    Subject as CoreSubject,
    to_resource_type_id,
)
from ..iam_engine.provider.base import PermissionProvider
from ..iam_engine.provider.dialect_types import (
    DialectApplyURLRequest,
    DialectAuthRequest,
    DialectBatchByActionRequest,
    DialectBatchByResourceRequest,
)
from . import PROVIDER_NAME
from .config import V3Options, V3SystemInfo
from ..iam_engine.schema.definitions import ResourceTypeDef

if TYPE_CHECKING:
    from ..iam_engine.schema.diff import MigrationPlan, MigrationReport
    from ..iam_engine.schema.registry import SchemaRegistry

logger = logging.getLogger(__name__)


class V3PermissionProvider(PermissionProvider):
    """IAM v3 ABAC 权限 Provider。

    鉴权：
        is_allowed 调 CompatibleIAM SDK；读操作走缓存、写操作不走。

    编解码：
        codec 类通过 options.codec_class 配置（dotted path），
        由基类 __init__ 实例化。子类只处理"方言 ID → V3 SDK payload"。

    配置：
        完全由 IAM_FRAMEWORK.PROVIDERS[*].options 传入，
        Provider 不读 Django settings；具体字段参见 V3Options。
    """

    #: Provider 标识，用于日志/监控/命令行 --provider 参数。
    name: str = PROVIDER_NAME

    def __init__(self, schema: SchemaRegistry, **options: Any) -> None:
        """初始化 V3 Provider。

        从 options 解析 V3Options、实例化 CompatibleIAM。
        codec 由基类 PermissionProvider.__init__ 根据 options.codec_class 创建。

        Args:
            schema: 框架统一构建的冻结 SchemaRegistry。
            **options: IAM_FRAMEWORK.PROVIDERS[*].options 原样透传的字典，
                必须包含 V3Options 所需的所有字段。

        Raises:
            ValueError: options 字段缺失或类型不匹配。
        """
        super().__init__(schema, **options)
        # 强类型解析 + 启动期校验
        self._cfg: V3Options = V3Options.from_dict(options)
        # 分片/并发参数（覆盖基类默认值）
        self.CHUNK_SIZE = self._cfg.chunk_size
        self.MAX_WORKERS = self._cfg.max_workers

        self._default_tenant_id = self._cfg.bk_tenant_id
        self._clients: dict[str, V3Client] = {}
        # 默认 client（系统级操作：health_check / migration / make_* 工厂方法）
        self._iam_client = self._get_client("")

    def _get_client(self, tenant_id: str = ""):
        """按租户 ID 获取或创建 V3Client。"""
        tid = tenant_id or self._default_tenant_id
        if tid not in self._clients:
            self._clients[tid] = V3Client(
                self._cfg.credentials.app_code,
                self._cfg.credentials.app_secret,
                self._cfg.base_url,
                system_id=self._cfg.system.id,
                codec=self.codec,
                bk_tenant_id=tid,
            )
        return self._clients[tid]

    # ================================================================
    # 系统信息（供命令行/诊断使用）
    # ================================================================

    def get_system_info(self) -> V3SystemInfo:
        """返回 Provider 的系统信息对象。

        命令行工具（如 iam_generate_config）以 duck typing 消费
        .id / .name / .description / .managers / .clients 等字段。

        Returns:
            V3SystemInfo: V3 平台的系统注册信息。
        """
        return self._cfg.system

    # ================================================================
    # 方言层：单次鉴权
    # ================================================================

    def _is_allowed_dialect(self, request: DialectAuthRequest) -> bool:
        """单次鉴权（方言层）。

        读操作使用 is_allowed_with_cache（SDK 缓存），写操作直接 is_allowed。
        """
        client = self._get_client(request.subject.tenant_id)
        action_id_biz = self.codec.decode_action(request.action_id)

        # 构建 SDK resources
        sdk_resources: list = []
        if request.resource and self._action_has_resource(action_id_biz):
            sdk_resources = [
                client.make_resource(
                    request.resource.type,
                    request.resource.id,
                    ancestors=request.resource.ancestors,
                )
            ]

        sdk_request = client.make_request(
            request.subject.id,
            request.action_id,
            sdk_resources,
        )

        try:
            if self.codec.is_read_action(action_id_biz):
                return client.is_allowed_with_cache(sdk_request)
            return client.is_allowed(sdk_request)
        except AuthAPIError:
            logger.exception("[iam_v3:is_allowed] AuthAPIError for action=%s", request.action_id)
            return False

    # ================================================================
    # 方言层：同 action、多 resource 单页
    # ================================================================

    def _batch_by_resource_dialect_page(
        self,
        request: DialectBatchByResourceRequest,
    ) -> list[tuple[str, bool]]:
        """同 action、多 resource 批量鉴权（方言层单页，≤ CHUNK_SIZE）。"""
        client = self._get_client(request.subject.tenant_id)
        sdk_resources_list = [[client.make_resource(request.resource_type, rid)] for rid in request.resource_ids]

        sdk_request = client.make_multi_action_request(
            request.subject.id,
            [request.action_id],
        )
        try:
            result = client.batch_resource_multi_actions_allowed(sdk_request, sdk_resources_list)
        except AuthAPIError:
            logger.exception("[iam_v3:batch_by_resource] AuthAPIError for action=%s", request.action_id)
            return [(rid, False) for rid in request.resource_ids]

        return [(rid, result.get(rid, {}).get(request.action_id, False)) for rid in request.resource_ids]

    # ================================================================
    # 方言层：多 action、同 resource 单页
    # ================================================================

    def _batch_by_action_dialect_page(
        self,
        request: DialectBatchByActionRequest,
    ) -> list[tuple[str, bool]]:
        """多 action、同一 resource（或无 resource）批量鉴权（方言层单页）。"""
        client = self._get_client(request.subject.tenant_id)
        sdk_resources_list: list[list] = []
        if request.resource:
            sdk_resources_list.append([client.make_resource(request.resource.type, request.resource.id)])
        else:
            sdk_resources_list.append([])

        sdk_request = client.make_multi_action_request(
            request.subject.id,
            list(request.action_ids),
        )
        try:
            result = client.batch_resource_multi_actions_allowed(sdk_request, sdk_resources_list)
        except AuthAPIError:
            logger.exception("[iam_v3:batch_by_action] AuthAPIError")
            return [(aid, False) for aid in request.action_ids]

        rid_key = request.resource.id if request.resource else ""
        action_results = result.get(rid_key, {})
        return [(aid, action_results.get(aid, False)) for aid in request.action_ids]

    # ================================================================
    # 方言层：apply_url
    # ================================================================

    def _get_apply_url_dialect(self, request: DialectApplyURLRequest) -> str:
        """生成权限申请 URL（方言层）。

        使用 SDK 的 Application 模型 + get_apply_url，
        与现有 Permission._make_application 逻辑保持一致。

        Args:
            request: 已编码为 V3 方言的申请 URL 请求。

        Returns:
            str: IAM 平台的权限申请页面 URL。
        """
        client = self._get_client(request.subject.tenant_id)
        actions: list[ActionWithResources | ActionWithoutResources] = []

        for dialect_aid in request.action_ids:
            action_id_biz = self.codec.decode_action(dialect_aid)

            if not self._action_has_resource(action_id_biz):
                # 无关联资源的 action
                actions.append(ActionWithoutResources(dialect_aid))
            else:
                # 从 schema 构建 related_resource_types
                try:
                    action_def = self.schema.get_action(action_id_biz)
                    rrt_list = self._build_related_resource_types(action_def)
                except Exception:
                    actions.append(ActionWithoutResources(dialect_aid))
                    continue

                related_types: list[RelatedResourceType] = []
                for rrt_dict in rrt_list:
                    instances: list[ResourceInstance] = []
                    for r in request.resources:
                        if r.type == rrt_dict["id"]:
                            instances.append(ResourceInstance([ResourceNode(type=r.type, id=r.id, name=r.id)]))
                    related_types.append(
                        RelatedResourceType(
                            system_id=rrt_dict["system_id"],
                            type=rrt_dict["id"],
                            instances=instances,
                        )
                    )
                actions.append(ActionWithResources(dialect_aid, related_types))

        application = Application(self._cfg.system.id, actions=actions)
        ok, message, url = client.get_apply_url(application)
        if not ok:
            logger.error("[iam_v3:get_apply_url] generate apply url fail: %s", message)
            # 返回空字符串，上层可兜底处理
            return ""
        return url

    # ================================================================
    # 权限申请数据 —— 委托 SDK gen_perms_apply_data
    # ================================================================

    def get_apply_data(
        self,
        action_ids: list[str],
        resources: list[CoreResourceInstance],
        subject: CoreSubject,
    ) -> dict | None:
        """生成 IAM Application 格式的权限申请数据。

        使用 SDK 的 gen_perms_apply_data，与现有 Permission.get_apply_data 一致。

        Args:
            action_ids: 业务 action_id 列表
            resources: 被拒的资源实例列表
            subject: 鉴权主体（保留签名一致性）

        Returns:
            IAM Application 格式 dict。
        """
        client = self._get_client(subject.tenant_id)
        # 编码 action_ids → V3 方言
        dialect_action_ids = [self.codec.encode_action(a) for a in action_ids]

        action_to_resources_list: list[dict] = []
        for dialect_aid in dialect_action_ids:
            action_id_biz = self.codec.decode_action(dialect_aid)

            # 编码 resource 为 SDK Resource 格式
            sdk_resources: list = []
            if self._action_has_resource(action_id_biz) and resources:
                for r in resources:
                    rt_biz = to_resource_type_id(r.type)
                    dialect_rt = self.codec.encode_resource_type(rt_biz)
                    dialect_rid = self.codec.encode_resource_id(rt_biz, r.id)
                    sdk_resources.append(
                        client.make_resource(
                            dialect_rt,
                            dialect_rid,
                            attribute={"name": r.name or r.id},
                        )
                    )
            else:
                sdk_resources = []

            action_to_resources_list.append(
                {
                    "action": client.make_action(dialect_aid),
                    "resources_list": [sdk_resources] if sdk_resources else [[]],
                }
            )

        return gen_perms_apply_data(
            system=self._cfg.system.id,
            subject=client.make_subject(subject.id),
            action_to_resources_list=action_to_resources_list,
        )

    # ================================================================
    # grant_creator_action — 创建者授权
    # ================================================================

    def grant_creator_action(
        self,
        resource_type: ResourceTypeDef | str,
        resource_id: str,
        creator: str,
        expired_at: int | None = None,
        tenant_id: str = "",
    ) -> None:
        """V3: 调 grant_resource_creator_actions API，无需角色/过期时间。"""
        from ..iam_engine.core.types import to_resource_type_id

        client = self._get_client(tenant_id)
        rt_id = to_resource_type_id(resource_type)
        dialect_rt = self.codec.encode_resource_type(rt_id)
        dialect_rid = self.codec.encode_resource_id(rt_id, resource_id)

        application = {
            "system": self._cfg.system.id,
            "type": dialect_rt,
            "id": dialect_rid,
            "name": resource_id,
            "creator": creator,
        }
        client.grant_resource_creator_actions(application)

    # ================================================================
    # 内部：action 元数据辅助方法
    # ================================================================

    def _action_has_resource(self, action_id_biz: str) -> bool:
        """从 schema 判断 action 是否关联资源类型（替代旧 related_resource_types 判断）。"""
        try:
            action_def = self.schema.get_action(action_id_biz)
            return bool(action_def.resource_type)
        except Exception:
            return False

    # ================================================================
    # health_check
    # ================================================================

    def health_check(self) -> dict:
        """探活检查，委托给 V3Client。"""
        result = self._iam_client.health_check()
        result["provider"] = self.name
        result["remote_id"] = self._cfg.system.id
        return result

    # ================================================================
    # plan_migration / apply_migration
    # ================================================================

    def plan_migration(self, schema: SchemaRegistry, *, scope: str = "full") -> MigrationPlan:
        """从本地 definitions + V3Options 生成迁移计划（不查远端）。

        Args:
            schema: 冻结的 SchemaRegistry。
            scope: "system" 只生成系统注册 Change；
                   "full" 生成系统+资源类型+操作的全量 Change。

        Returns:
            MigrationPlan: 包含 provider_name 和 changes 列表的变更计划。
        """
        from ..iam_engine.schema.diff import Change, ChangeType, EntityKind, MigrationPlan

        changes: list[Change] = []

        # ---- System ----
        system_info = {
            "id": self._cfg.system.id,
            "name": self._cfg.system.name,
            "description": self._cfg.system.description,
            "managers": list(self._cfg.system.managers),
            "clients": list(self._cfg.system.clients),
        }
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
            return MigrationPlan(provider_name=self.name, changes=changes)

        # ---- Resource Types ----
        for rt in schema.all_resource_types():
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
                        "system_id": v3_ext.get("system_id", "bk_monitorv3"),
                        "selection_mode": v3_ext.get("selection_mode", "instance"),
                        "related_instance_selections": v3_ext.get("related_instance_selections", []),
                    },
                    reason="New resource type",
                )
            )

        # ---- Actions ----
        for action in schema.all_actions():
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
                        "type": v3_ext.get("type", ""),
                        "version": v3_ext.get("version", 1),
                        "related_resource_types": self._build_related_resource_types(action),
                    },
                    reason="New action",
                )
            )

        return MigrationPlan(provider_name=self.name, changes=changes)

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
        from ..iam_engine.schema.diff import ChangeType, EntityKind, MigrationPlan, MigrationReport

        report = MigrationReport(provider_name=self.name)

        if plan.has_destructive() and not allow_destructive:
            report.skipped_reason = "Destructive changes blocked; set allow_destructive=True"
            return report

        # ---- SYSTEM reconcile：查远端系统，决定实际操作 ----
        system_changes = [c for c in plan.changes if c.kind == EntityKind.SYSTEM and c.change_type != ChangeType.NOOP]
        has_system = bool(system_changes)
        if has_system:
            ok, _msg, data = self._iam_client.query_system()
            remote_system = data.get("base_info") if ok else None
            reconciled_system = self._reconcile_system_changes(system_changes, remote_system)
            other_changes = [c for c in plan.changes if c.kind != EntityKind.SYSTEM]
            plan = MigrationPlan(provider_name=self.name, changes=reconciled_system + other_changes)

        # ---- ACTION / RT reconcile：查远端全量 ----
        has_entities = any(c.kind in (EntityKind.ACTION, EntityKind.RESOURCE_TYPE) for c in plan.changes)
        remote_actions: set[str] = set()
        remote_rts: set[str] = set()
        if has_entities:
            ok, _msg, data = self._iam_client.query_system()
            if ok:
                remote_actions = {a["id"] for a in (data.get("actions") or [])}
                remote_rts = {r["id"] for r in (data.get("resource_types") or [])}

        # SDK Client
        from iam.contrib.iam_migration.utils.do_migrate import Client

        client = Client(
            self._cfg.credentials.app_code,
            self._cfg.credentials.app_secret,
            self._cfg.base_url,
            bk_tenant_id=self._cfg.bk_tenant_id,
        )

        for change in plan.changes:
            if change.change_type == ChangeType.NOOP:
                continue

            actual = self._reconcile_change(change, remote_actions, remote_rts)
            if actual is None:
                continue

            if dry_run:
                report.would_apply.append(actual)
                continue

            try:
                self._execute_change(client, actual)
                report.applied.append(actual)
            except Exception as e:
                report.failed.append((actual, str(e)[:500]))

        return report

    # ================================================================
    # 内部：reconcile
    # ================================================================

    def _reconcile_system_changes(self, system_changes: list, remote_system: dict | None) -> list:
        """用远端系统信息 reconcile 本地的 SYSTEM Change。

        remote_system=None → 系统未注册 → 保留 CREATE。
        remote_system 已存在且匹配 → 替换为 NOOP。
        remote_system 已存在但不同 → 替换为 UPDATE。
        """
        from ..iam_engine.schema.diff import Change, ChangeType, EntityKind

        local = {
            "id": self._cfg.system.id,
            "name": self._cfg.system.name,
            "description": self._cfg.system.description,
            "managers": list(self._cfg.system.managers),
            "clients": list(self._cfg.system.clients),
        }
        if remote_system is None:
            return system_changes  # 系统未注册，保留原样（CREATE）

        keys = {"id", "name", "description", "managers", "clients"}
        if self._system_dicts_equal(local, remote_system, keys):
            # 远端一致 → NOOP
            return [Change(kind=EntityKind.SYSTEM, change_type=ChangeType.NOOP, entity_id=self._cfg.system.id)]
        # 远端不同 → UPDATE
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

    @staticmethod
    def _reconcile_change(change, remote_actions: set[str], remote_rts: set[str]):
        """将单个 Change 与远端实际状态做 reconcile。"""
        from ..iam_engine.schema.diff import Change, ChangeType, EntityKind

        kind = change.kind
        if kind == EntityKind.SYSTEM:
            return None  # SYSTEM 已在 apply_migration 主循环前单独 reconcile，这里不应再出现

        dialect_id = change.after.get("id", change.entity_id) if change.after else change.entity_id

        if kind == EntityKind.ACTION:
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

    def _execute_change(self, client, change) -> None:
        """按 Change 类型调用 V3 SDK Client 执行。"""
        from ..iam_engine.schema.diff import ChangeType, EntityKind

        system_id = self._cfg.system.id

        if change.kind == EntityKind.SYSTEM:
            if change.change_type == ChangeType.CREATE:
                ok, _msg = client.add_system(system_id, change.after)
            elif change.change_type == ChangeType.UPDATE:
                ok, _msg = client.update_system(system_id, change.after)
            else:
                return
            if not ok:
                raise RuntimeError(f"System {change.change_type.value} failed: {_msg}")

        elif change.kind == EntityKind.ACTION:
            data = change.after
            if change.change_type == ChangeType.CREATE:
                ok, _msg = client.add_action(system_id, data)
            elif change.change_type == ChangeType.UPDATE:
                ok, _msg = client.update_action(system_id, data)
            elif change.change_type == ChangeType.DELETE:
                ok, _msg = client.delete_action(system_id, data)
            else:
                return
            if not ok:
                raise RuntimeError(f"Action {change.change_type.value} {data.get('id')} failed: {_msg}")

        elif change.kind == EntityKind.RESOURCE_TYPE:
            data = change.after
            if change.change_type == ChangeType.CREATE:
                ok, _msg = client.add_resource_type(system_id, data)
            elif change.change_type == ChangeType.UPDATE:
                ok, _msg = client.update_resource_type(system_id, data)
            elif change.change_type == ChangeType.DELETE:
                ok, _msg = client.delete_resource_type(system_id, data)
            else:
                return
            if not ok:
                raise RuntimeError(f"ResourceType {change.change_type.value} {data.get('id')} failed: {_msg}")

    # ================================================================
    # 内部：从 schema 拼 V3 的 related_resource_types
    # ================================================================

    def _build_related_resource_types(self, action_def) -> list[dict]:
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
                "system_id": v3_ext.get("system_id", "bk_monitorv3"),
                "id": rt_id,
                "selection_mode": v3_ext.get("selection_mode", "instance"),
                "related_instance_selections": v3_ext.get("related_instance_selections", []),
            }
        ]
