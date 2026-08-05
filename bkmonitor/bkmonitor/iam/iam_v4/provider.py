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
