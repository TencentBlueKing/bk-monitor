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
# 并调用 client。业务命名 ↔ v4 方言的编解码全部由基类和 V4NameCodec 完成。
# ---------------------------------------------------------------------------

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from ..iam_engine.provider.base import PermissionProvider
from ..iam_engine.provider.codec import NameCodec
from ..iam_engine.core.types import Subject, to_action_id
from ..iam_engine.provider.dialect_types import (
    DialectApplyURLRequest,
    DialectAuthRequest,
    DialectBatchByActionRequest,
    DialectBatchByResourceRequest,
)
from .client import V4Client
from .codec import V4NameCodec
from .config import V4Options, V4SystemInfo

if TYPE_CHECKING:
    from ..iam_engine.schema.definitions import ActionDef
    from ..iam_engine.schema.diff import MigrationPlan, MigrationReport
    from ..iam_engine.schema.registry import SchemaRegistry


class V4PermissionProvider(PermissionProvider):
    """IAM v4 RBAC 权限 Provider。

    - 鉴权：is_allowed 直接调 direct_auth；batch_* 由基类自动分片 + 串/并行。
    - 编解码：所有业务 ↔ v4 方言的转换由 V4NameCodec + 基类模板方法完成，
      子类只处理"方言 ID → v4 payload"。
    - 配置：完全由 IAM_FRAMEWORK.PROVIDERS[*].options 传入，
      Provider 不读 Django settings；具体字段参见 V4Options。
    """

    name: ClassVar[str] = "v4"
    codec_class: ClassVar[type[NameCodec]] = V4NameCodec

    def __init__(self, schema: SchemaRegistry, **options: Any) -> None:
        super().__init__(schema, **options)
        # 强类型解析 + 启动期校验（缺字段/类型错直接抛 ValueError）
        self._cfg: V4Options = V4Options.from_dict(options)
        # 分片/并发参数（覆盖基类默认值）
        self.CHUNK_SIZE = self._cfg.chunk_size
        self.MAX_WORKERS = self._cfg.max_workers
        # Client 解耦：配置全部注入，不直接读 Django settings
        self._client = V4Client(
            base_url=self._cfg.base_url,
            system_id=self._cfg.system.id,
            app_code=self._cfg.credentials.app_code,
            app_secret=self._cfg.credentials.app_secret,
            timeout=self._cfg.timeout,
        )

    # ================================================================
    # 系统信息（供命令行工具使用）
    # ================================================================

    def get_system_info(self) -> V4SystemInfo:
        return self._cfg.system

    # ================================================================
    # 方言层：单次鉴权
    # ================================================================

    def _is_allowed_dialect(self, request: DialectAuthRequest) -> bool:
        v4_resource = self._to_v4_resource(request) if request.resource else None
        return self._client.direct_auth(
            subject_id=request.subject.id,
            action_id=request.action_id,
            resource=v4_resource,
        )

    # ================================================================
    # 方言层：同 action、多 resource 单页
    # ================================================================

    def _batch_by_resource_dialect_page(
        self,
        request: DialectBatchByResourceRequest,
    ) -> list[tuple[str, bool]]:
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
        permissions = []
        for aid in request.action_ids:
            resources = []
            for r in request.resources:
                ancestors = [{"id": a.id, "type": a.type} for a in r.ancestors]
                resources.append({"id": r.id, "type": r.type, "ancestors": ancestors})
            permissions.append({"action_id": aid, "resources": resources})
        return self._client.generate_perm_apply_url(permissions)

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
          * ``"*"``：该资源类型下的任意资源都有权限
          * 父资源 ID：该父资源下所有子资源都有权限
          * 子资源 ID：单个资源实例的权限

        Args:
            subject: 鉴权主体
            action_id: 业务规范化 action_id（或 ActionDef）

        Returns:
            [{"type": <业务 rt_id>, "ids": [<业务 rid> 或 "*"]}, ...]
            所有 type/ids 都已经过 codec 解码为业务命名。
        """
        action_id_biz = to_action_id(action_id)

        # v4 平台限制：该接口只支持"关联资源的 action"（resource-free action 会被
        # 平台 400 拒绝，报 "Only supports action related to resource."）。
        # 前置从 schema 判断，resource-free 直接返回空，避免透传底层错误。
        try:
            action_def = self.schema.get_action(action_id_biz)
            if not action_def.resource_type:
                return []
        except Exception:
            # schema 里查不到时（未注册的 action_id），交给平台去返回业务错误
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
    # 内部工具
    # ================================================================

    @staticmethod
    def _to_v4_resource(request: DialectAuthRequest) -> dict:
        """DialectAuthRequest 里的单个 resource → v4 平台 payload。

        v4 的鉴权 body 只需要 {"id": ...}；apply_url 才需要 type/ancestors。
        """
        return {"id": request.resource.id} if request.resource else {}

    # ================================================================
    # health_check
    # ================================================================

    def health_check(self) -> dict:
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

    def plan_migration(self, schema: SchemaRegistry) -> MigrationPlan:
        from .migrator import V4Migrator

        migrator = V4Migrator(self._client, schema, self._cfg.system, self.codec)
        return migrator.plan_migration()

    def apply_migration(
        self,
        plan: MigrationPlan,
        *,
        dry_run: bool = False,
        allow_destructive: bool = False,
    ) -> MigrationReport:
        from .migrator import V4Migrator

        migrator = V4Migrator(self._client, self.schema, self._cfg.system, self.codec)
        return migrator.apply_migration(
            plan,
            dry_run=dry_run,
            allow_destructive=allow_destructive,
        )
