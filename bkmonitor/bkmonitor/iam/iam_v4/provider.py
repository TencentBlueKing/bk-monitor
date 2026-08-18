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
# V4PermissionProvider — IAM v4 (RBAC) 鉴权 Provider
#
# 只实现"方言层"接口：接收编码后的 Dialect* 结构，直接组装 v4 平台 payload
# 并调用 client。业务命名 ↔ v4 方言的编解码全部由基类和注入的 codec 完成。
# codec 类通过 IAM_FRAMEWORK.PROVIDERS[*].options.codec_class 配置。
# ---------------------------------------------------------------------------

from __future__ import annotations

import importlib
import logging
from typing import TYPE_CHECKING, Any

from ..iam_engine.callback.service import CallbackService
from ..iam_engine.core.types import (
    BatchByResourceRequest,
    ResourceInstance,
    Subject,
    VisibleResult,
    to_action_id,
    to_resource_type_id,
)
from ..iam_engine.core.utils import chunked
from ..iam_engine.provider.base import PermissionProvider
from ..iam_engine.provider.dialect_types import (
    DialectApplyURLRequest,
    DialectAuthRequest,
    DialectBatchByActionRequest,
    DialectBatchByResourceRequest,
)
from . import PROVIDER_NAME
from .client import V4Client
from .config import V4Options, V4SystemInfo

if TYPE_CHECKING:
    from ..iam_engine.schema.definitions import ActionDef, ResourceTypeDef, RoleDef
    from ..iam_engine.schema.diff import MigrationPlan, MigrationReport
    from ..iam_engine.schema.registry import SchemaRegistry

logger = logging.getLogger(__name__)


class V4PermissionProvider(PermissionProvider):
    """IAM v4 RBAC 权限 Provider。

    鉴权：
        is_allowed 直接调 direct_auth；batch_* 由基类自动分片 + 串/并行。

    编解码：
        codec 类通过 options.codec_class 配置（dotted path），
        由基类 __init__ 实例化。子类只处理"方言 ID → v4 payload"。

    配置：
        完全由 IAM_FRAMEWORK.PROVIDERS[*].options 传入，
        Provider 不读 Django settings；具体字段参见 V4Options。

    回调：
        每个 Provider 实例持有自己的 CallbackService，codec 由本 Provider 注入。
    """

    #: Provider 标识，用于日志/监控/命令行 --provider 参数。
    name: str = PROVIDER_NAME

    def __init__(self, schema: SchemaRegistry, **options: Any) -> None:
        """初始化 v4 Provider。

        从 options 中解析 V4Options、实例化 V4Client 和 CallbackService。
        codec 由基类 PermissionProvider.__init__ 根据 options.codec_class 创建。

        Args:
            schema: 框架统一构建的冻结 SchemaRegistry。
            **options: IAM_FRAMEWORK.PROVIDERS[*].options 原样透传的字典，
                必须包含 V4Options 所需的所有字段。

        Raises:
            ValueError: options 字段缺失或类型不匹配。
        """
        super().__init__(schema, **options)
        # 强类型解析 + 启动期校验（缺字段/类型错直接抛 ValueError）
        self._cfg: V4Options = V4Options.from_dict(options)
        # 分片/并发参数（覆盖基类默认值）
        self.CHUNK_SIZE = self._cfg.chunk_size
        self.MAX_WORKERS = self._cfg.max_workers
        # Client：配置全部注入，不直接读 Django settings
        self._client = V4Client(
            base_url=self._cfg.base_url,
            system_id=self._cfg.system.id,
            app_code=self._cfg.credentials.app_code,
            app_secret=self._cfg.credentials.app_secret,
            timeout=self._cfg.timeout,
        )
        # 导入 callback handler 模块，触发 @register_xxx 装饰器注册
        callback_module: str = options.get("callback_module", "")
        if callback_module:
            importlib.import_module(callback_module)
        # 回调服务：持有本 Provider 的 codec
        self.callback_service = CallbackService(self.codec)

    # ================================================================
    # 系统信息（供命令行/诊断使用）
    # ================================================================

    def get_system_info(self) -> V4SystemInfo:
        """返回 Provider 的系统信息对象。

        命令行工具（如 iam_generate_config）以 duck typing 消费
        .id / .name / .description / .managers / .clients / .callback_url。

        Returns:
            V4SystemInfo: v4 平台的系统注册信息。
        """
        return self._cfg.system

    # ================================================================
    # 方言层：单次鉴权
    # ================================================================

    def _is_allowed_dialect(self, request: DialectAuthRequest) -> bool:
        """单次鉴权（方言层）。

        Args:
            request: 已编码为 v4 方言的鉴权请求。

        Returns:
            True 表示允许；False 表示业务语义拒绝，非系统错误。

        容错：平台对不存在的实体（如 action 已删除）的鉴权查询返回 400
        "action not found" 等错误 → 视为拒绝（与 v3 的 AuthAPIError 兜底语义对齐），
        避免实体删除/未同步期间鉴权抛异常。
        """
        v4_resource = self._to_v4_resource(request) if request.resource else None
        try:
            return self._client.direct_auth(
                subject_id=request.subject.id,
                action_id=request.action_id,
                resource=v4_resource,
            )
        except Exception:
            logger.exception("[iam_v4:is_allowed] error for action=%s", request.action_id)
            return False

    # ================================================================
    # 方言层：同 action、多 resource 单页
    # ================================================================

    def _batch_by_resource_dialect_page(
        self,
        request: DialectBatchByResourceRequest,
    ) -> list[tuple[str, bool]]:
        """同 action、多 resource 批量鉴权（方言层单页，≤ CHUNK_SIZE）。

        Args:
            request: 已编码为 v4 方言的批量鉴权请求。

        Returns:
            list[(dialect_resource_id, allowed)]: 每个资源的鉴权结果，
            resource_id 为 v4 方言格式。
        """
        v4_resources = [{"id": rid} for rid in request.resource_ids]
        resp = self._client.direct_auth_by_resources(
            subject_id=request.subject.id,
            action_id=request.action_id,
            resources=v4_resources,
        )
        return [(rid, allowed) for rid, allowed in resp.items()]

    # ================================================================
    # 方言层：多 action、同 resource 单页
    # ================================================================

    def _batch_by_action_dialect_page(
        self,
        request: DialectBatchByActionRequest,
    ) -> list[tuple[str, bool]]:
        """多 action、同一 resource 批量鉴权（方言层单页）。

        Args:
            request: 已编码为 v4 方言的批量鉴权请求。

        Returns:
            list[(dialect_action_id, allowed)]: 每个 action 的鉴权结果，
            action_id 为 v4 方言格式。
        """
        v4_resource = None
        if request.resource:
            v4_resource = {"id": request.resource.id}
        resp = self._client.direct_auth_by_actions(
            subject_id=request.subject.id,
            action_ids=list(request.action_ids),
            resource=v4_resource,
        )
        return [(aid, allowed) for aid, allowed in resp.items()]

    # ================================================================
    # 方言层：apply_url
    # ================================================================

    def _get_apply_url_dialect(self, request: DialectApplyURLRequest) -> str:
        """生成权限申请 URL（方言层）。

        Args:
            request: 已编码为 v4 方言的申请 URL 请求。

        Returns:
            str: IAM 平台的权限申请页面 URL。
        """
        permissions = []
        for aid in request.action_ids:
            resources = []
            for r in request.resources:
                ancestors = [{"id": a.id, "type": a.type} for a in r.ancestors]
                resources.append({"id": r.id, "type": r.type, "ancestors": ancestors})
            permissions.append({"action_id": aid, "resources": resources})
        return self._client.generate_perm_apply_url(permissions)

    # ================================================================
    # 权限申请数据 —— 与 V3 gen_perms_apply_data 兼容
    # ================================================================

    def get_apply_data(
        self,
        action_ids: list[str],
        resources: list[ResourceInstance],
        subject: Subject,  # noqa: ARG002 保留签名一致性
    ) -> dict | None:
        """生成 IAM Application 格式的权限申请数据。

        纯本地拼接，不调 V4 IAM 平台 API。资源展示名称通过 callback_service
        分发到对应 handler 查询（数据库 / 缓存）。

        Args:
            action_ids: 业务 action_id 列表
            resources: 被拒的资源实例列表
            subject: 鉴权主体（未用，保留签名）

        Returns:
            IAM Application 格式 dict，字段与 V3 gen_perms_apply_data 兼容。
        """
        system_id = self._cfg.system.id
        resolved_resources = [self._resolve(r) for r in resources]
        actions_data: list[dict] = []

        for action_id_biz in action_ids:
            try:
                action_def = self.schema.get_action(action_id_biz)
            except Exception:
                action_def = None

            action_name = action_def.name if action_def else action_id_biz
            dialect_action_id = self.codec.encode_action(action_id_biz)

            related_resource_types: list[dict] = []
            rt_id: str = action_def.resource_type if action_def else ""

            if rt_id and resolved_resources:
                instance_ids = [r.id for r in resolved_resources]
                # 通过回调服务补全展示名称
                display_map: dict[str, str] = {}
                if hasattr(self, "callback_service"):
                    try:
                        info = self.callback_service.dispatch_fetch_instance_info(rt_id, instance_ids, ["display_name"])
                        display_map = {
                            self.codec.decode_resource_id(rt_id, item["id"]): item.get("display_name", item["id"])
                            for item in info
                        }
                    except Exception:
                        display_map = {}
                # 未命中回调服务时回退到 resource.id
                instances: list[list[dict]] = [
                    [
                        {
                            "type": rt_id,
                            "id": self.codec.encode_resource_id(rt_id, r.id),
                            "name": display_map.get(r.id, r.id),
                        }
                    ]
                    for r in resolved_resources
                ]
                related_resource_types.append(
                    {
                        "system_id": system_id,
                        "id": rt_id,
                        "instances": instances,
                    }
                )

            actions_data.append(
                {
                    "id": dialect_action_id,
                    "name": action_name,
                    "related_resource_types": related_resource_types,
                }
            )

        return {"system": system_id, "actions": actions_data}

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
        """V4: 调 add_authorization API，默认角色 space_operator，默认 30 天过期。
        tenant_id 当前忽略，待 V4 支持多租户后使用。"""
        import time

        from ..iam_engine.core.types import to_resource_type_id

        rt_id = to_resource_type_id(resource_type)
        dialect_rt = self.codec.encode_resource_type(rt_id)
        dialect_rid = self.codec.encode_resource_id(rt_id, resource_id)

        if expired_at is None:
            expired_at = int(time.time()) + 30 * 24 * 3600  # 默认 30 天

        authorization = {
            "subject": {"type": "user", "id": creator},
            "role_id": "space_operator",
            "related_resource_type_id": dialect_rt,
            "resources": [{"type": dialect_rt, "id": dialect_rid}],
            "expired_at": expired_at,
        }
        self._client.add_authorization([authorization], operator=creator)

    # ================================================================
    # 有权限的资源列表 —— IAM v4 独有能力
    # ================================================================

    def get_authorized_resources(
        self,
        subject: Subject,
        action_id: ActionDef | str,
    ) -> list[dict]:
        """查询用户对某个 action 有权限的资源列表（业务命名）。

        平台仅支持顶层资源类型查询（第一层）。返回结果可能包含：
          - ``"*"``：该资源类型下的任意资源都有权限
          - 父资源 ID：该父资源下所有子资源都有权限
          - 子资源 ID：单个资源实例的权限

        Args:
            subject: 鉴权主体。
            action_id: 业务规范化 action_id（或 ActionDef）。

        Returns:
            list[dict]: 如 ``[{"type": "space", "ids": ["3", "*"]}, ...]``，
            所有 type/ids 都已经过 codec 解码为业务命名。
            resource-free action（action 不关联资源类型）直接返回空列表。
        """
        action_id_biz = to_action_id(action_id)

        # v4 平台限制：该接口只支持"关联资源的 action"。
        # resource-free action 从 schema 判断，直接返回空。
        try:
            action_def = self.schema.get_action(action_id_biz)
            if not action_def.resource_type:
                return []
        except Exception:
            # schema 里查不到时，交给平台去返回业务错误
            pass

        dialect_action = self.codec.encode_action(action_id_biz)

        raw = self._client.get_authorized_resources(
            subject_id=subject.id,
            action_id=dialect_action,
        )

        # 方言 → 业务命名回解
        results: list[dict] = []
        for item in raw:
            d_type = item.get("type", "")
            d_ids = item.get("ids") or []
            rt_biz = self.codec.decode_resource_type(d_type) if d_type else ""
            biz_ids: list[str] = []
            for d_id in d_ids:
                if d_id == "*":
                    biz_ids.append("*")
                else:
                    biz_ids.append(self.codec.decode_resource_id(rt_biz, d_id))
            results.append({"type": rt_biz, "ids": biz_ids})
        return results

    # ================================================================
    # 可见性能力（框架统一抽象）
    # ================================================================

    def has_any_permission(
        self,
        subject: Subject,
        action_id: str,
    ) -> bool:
        """v4 平台无子资源反向查询 API → 保守放行 True，由资源层精确过滤兜底。"""
        return True

    def filter_visible_resources(
        self,
        subject: Subject,
        action_id: str,
        candidates: tuple[ResourceInstance, ...],
    ) -> VisibleResult:
        """v4：按候选资源层级分派。

        * 顶层资源（如 space，数量可达数十万）：走平台原生反向列举
          get_authorized_resources（1 次 API），与候选求交 —— 禁止批量鉴权。
        * 子资源（如 grafana_dashboard，单批候选可控）：正向批量鉴权。
        """
        if not candidates:
            return VisibleResult()

        rt_biz = to_resource_type_id(candidates[0].type)
        if self._is_top_level_resource(rt_biz):
            return self._filter_visible_top_level(subject, action_id, rt_biz, candidates)

        result = self.batch_by_resource(
            BatchByResourceRequest(subject=subject, action_id=action_id, resources=candidates)
        )
        return VisibleResult(
            all_granted=False,
            visible_ids=tuple(item.resource_id for item in result.items if item.allowed),
        )

    def _is_top_level_resource(self, rt_biz: str) -> bool:
        """schema 中无 ancestor 的资源类型为顶层资源。未知类型保守视为非顶层（走批量）。"""
        if not rt_biz:
            return False
        try:
            return not self.schema.get_resource_type(rt_biz).ancestor
        except Exception:
            return False

    def _filter_visible_top_level(
        self,
        subject: Subject,
        action_id: str,
        rt_biz: str,
        candidates: tuple[ResourceInstance, ...],
    ) -> VisibleResult:
        """顶层资源反向列举：get_authorized_resources 与候选求交。"""
        authorized = self.get_authorized_resources(subject, action_id)

        all_granted = False
        authorized_ids: set[str] = set()
        for item in authorized:
            if item.get("type") != rt_biz:
                continue
            item_ids = item.get("ids") or []
            if "*" in item_ids:
                all_granted = True
            authorized_ids.update(str(i) for i in item_ids if i != "*")

        visible_ids = tuple(c.id for c in candidates if c.id in authorized_ids)
        return VisibleResult(all_granted=all_granted, visible_ids=visible_ids)

    # ================================================================
    # 角色授权 —— IAM v4 独有能力
    # ================================================================

    def add_authorization(
        self,
        *,
        subject: Subject,
        role: RoleDef | str,
        resource_type: ResourceTypeDef | str | None,
        resource_ids: list[str],
        expired_at: int,
        operator: str,
    ) -> None:
        """给用户授予某个角色的权限（业务命名）。

        典型场景：用户创建资源后自动授予该资源相关的角色权限。

        Args:
            subject: 授权对象。
            role: 角色（RoleDef 或业务 role_id）。
            resource_type: 授权维度（ResourceTypeDef / 业务 rt_id / None）；
                None 表示无关资源类型的授权（此时 resource_ids 必须为空）。
            resource_ids: 授权的资源实例业务 ID 列表；
                - 单个业务 ID：``["2", "3"]``
                - ``["*"]``：该资源类型下的无限制授权
                - ``[]``：仅在 resource_type=None 时合法（无关资源类型授权）。
            expired_at: Unix 时间戳；最大 365 天后（平台限制）。
            operator: 操作人用户名（写入 X-Bkiam-Operator 请求头）。

        Raises:
            ValueError: 参数不合法（resource_type 与 resource_ids 组合不匹配）。
            ProviderUnavailable: HTTP 层异常。
            ProviderError: IAM 业务错误。
        """
        # 业务命名归一化
        role_id_biz = role.id if hasattr(role, "id") else str(role)
        if resource_type is None:
            rt_id_biz = ""
        elif hasattr(resource_type, "id"):
            rt_id_biz = resource_type.id
        else:
            rt_id_biz = str(resource_type)

        # 校验入参组合
        if not rt_id_biz and resource_ids:
            raise ValueError("resource_type=None 时 resource_ids 必须为空（无关资源类型授权）")
        if rt_id_biz and not resource_ids:
            raise ValueError(f"resource_type={rt_id_biz!r} 时必须提供至少一个 resource_id")

        # 业务命名 → v4 方言编码
        dialect_role = self.codec.encode_role(role_id_biz)
        dialect_rt = self.codec.encode_resource_type(rt_id_biz) if rt_id_biz else ""

        # 分片：resource_ids 按 CHUNK_SIZE 切片，每批独立调用平台 API
        for rid_chunk in chunked(tuple(resource_ids), self.CHUNK_SIZE):
            resources: list[dict] = []
            for rid in rid_chunk:
                if rid == "*":
                    resources.append({"type": dialect_rt, "id": "*"})
                else:
                    resources.append(
                        {
                            "type": dialect_rt,
                            "id": self.codec.encode_resource_id(rt_id_biz, rid),
                        }
                    )
            payload = [
                {
                    "subject": {"type": subject.type.value, "id": subject.id},
                    "role_id": dialect_role,
                    "related_resource_type_id": dialect_rt,
                    "resources": resources,
                    "expired_at": expired_at,
                }
            ]
            self._client.add_authorization(payload, operator=operator)

    # ================================================================
    # 内部工具
    # ================================================================

    @staticmethod
    def _to_v4_resource(request: DialectAuthRequest) -> dict:
        """DialectAuthRequest 里的单个 resource → v4 平台鉴权 payload。

        v4 的鉴权 body 只需要 {"id": ...}；apply_url 才需要 type/ancestors。

        Args:
            request: 已编码的方言鉴权请求。

        Returns:
            dict: v4 平台鉴权 API 的 resource 字段。
        """
        return {"id": request.resource.id} if request.resource else {}

    # ================================================================
    # health_check
    # ================================================================

    def health_check(self) -> dict:
        """探活检查。

        调用 v4 平台 retrieve_system 验证连通性和系统注册状态。

        Returns:
            dict: ``{"status": "ok"|"error", "provider": "v4", ...}``
        """
        try:
            system = self._client.retrieve_system()
            return {
                "status": "ok",
                "provider": self.name,
                "remote_id": system.get("data", {}).get("id", ""),
            }
        except Exception as e:
            return {"status": "error", "provider": self.name, "error": str(e)[:200]}

    # ================================================================
    # plan_migration / apply_migration
    # ================================================================

    def plan_migration(self, schema: SchemaRegistry, *, scope: str = "full") -> MigrationPlan:
        """从本地 definitions + V4Options 生成迁移计划（不查远端）。

        Args:
            schema: 冻结的 SchemaRegistry。
            scope: "system" / "full"。
        """
        from .migrator import V4Migrator

        migrator = V4Migrator(self._client, schema, self._cfg.system, self.codec)
        return migrator.plan_migration(scope=scope)

    def apply_migration(
        self,
        plan: MigrationPlan,
        *,
        dry_run: bool = False,
        allow_destructive: bool = False,
    ) -> MigrationReport:
        """应用变更计划（查远端 + reconcile + 执行）。

        Args:
            plan: plan_migration 或迁移文件产出的 Change 列表。
            dry_run: 只演练，不真正提交。
            allow_destructive: 是否允许破坏性变更。
        """
        from .migrator import V4Migrator

        migrator = V4Migrator(self._client, self.schema, self._cfg.system, self.codec)
        return migrator.apply_migration(
            plan,
            dry_run=dry_run,
            allow_destructive=allow_destructive,
        )
