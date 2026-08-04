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
# ---------------------------------------------------------------------------

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from ..iam_engine.provider.base import PermissionProvider
from ..iam_engine.provider.mixins import BatchMixin
from ..iam_engine.core.types import (
    ApplyURLRequest,
    AuthRequest,
    ResourceAuthResult,
    to_action_id,
    to_resource_type_id,
)
from .client import V4Client
from .config import V4Options, V4SystemInfo

if TYPE_CHECKING:
    from ..iam_engine.schema.diff import MigrationPlan, MigrationReport
    from ..iam_engine.schema.registry import SchemaRegistry


class V4PermissionProvider(BatchMixin, PermissionProvider):
    """IAM v4 RBAC 权限 Provider。

    鉴权：is_allowed 对单资源直接调 direct_auth（避免不必要的批量开销）；
    batch_by_resource / batch_by_action 由 BatchMixin 提供分片 + 串/并行。

    配置：完全由 IAM_FRAMEWORK.PROVIDERS[*].options 传入，
    Provider 不读 Django settings；具体字段参见 V4Options。
    """

    name: ClassVar[str] = "v4"

    def __init__(self, schema: SchemaRegistry, **options: Any) -> None:
        super().__init__(schema, **options)
        # 强类型解析 + 启动期校验（缺字段/类型错直接抛 ValueError）
        self._cfg: V4Options = V4Options.from_dict(options)
        # BatchMixin 依赖的分片/并发参数
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
    # is_allowed — 单资源走 direct_auth
    # ================================================================

    def is_allowed(self, request: AuthRequest) -> bool:
        action_id = to_action_id(request.action_id)
        resource = {"id": request.resource.id} if request.resource else None
        return self._client.direct_auth(
            subject_id=request.subject.id,
            action_id=action_id,
            resource=resource,
        )

    # ================================================================
    # batch_by_resource  (BatchMixin 提供分片 + 串/并行)
    # ================================================================

    def _batch_by_resource_page(self, subject, action_id, batch):
        action_id_str = to_action_id(action_id)
        v4_resources = [{"id": r.id} for r in batch]
        resp = self._client.direct_auth_by_resources(
            subject_id=subject.id,
            action_id=action_id_str,
            resources=v4_resources,
        )
        rt_id = to_resource_type_id(batch[0].type) if batch and batch[0].type else ""
        return [
            ResourceAuthResult(
                action_id=action_id_str,
                resource_type=rt_id,
                resource_id=rid,
                allowed=allowed,
            )
            for rid, allowed in resp.items()
        ]

    # ================================================================
    # batch_by_action  (BatchMixin 提供分片 + 串/并行)
    # ================================================================

    def _batch_by_action_page(self, subject, action_ids, resource):
        v4_resource = {"id": resource.id} if resource else None
        resp = self._client.direct_auth_by_actions(
            subject_id=subject.id,
            action_ids=list(action_ids),
            resource=v4_resource,
        )
        rt_id = to_resource_type_id(resource.type) if resource else ""
        rid = resource.id if resource else ""
        return [
            ResourceAuthResult(
                action_id=aid,
                resource_type=rt_id,
                resource_id=rid,
                allowed=allowed,
            )
            for aid, allowed in resp.items()
        ]

    # ================================================================
    # get_apply_url
    # ================================================================

    def get_apply_url(self, request: ApplyURLRequest) -> str:
        permissions = []
        for action_id in request.action_ids:
            aid = to_action_id(action_id)
            try:
                action_def = self.schema.get_action(aid)
            except Exception:
                action_def = None
            resources = []
            for r in request.resources:
                ancestors = [{"id": a.id, "type": to_resource_type_id(a.type)} for a in r.ancestor_chain]
                resources.append(
                    {
                        "id": r.id,
                        "type": action_def.resource_type if action_def else to_resource_type_id(r.type or ""),
                        "ancestors": ancestors,
                    }
                )
            permissions.append({"action_id": aid, "resources": resources})
        return self._client.generate_perm_apply_url(permissions)

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

        migrator = V4Migrator(self._client, schema, self._cfg.system)
        return migrator.plan_migration()

    def apply_migration(
        self,
        plan: MigrationPlan,
        *,
        dry_run: bool = False,
        allow_destructive: bool = False,
    ) -> MigrationReport:
        from .migrator import V4Migrator

        migrator = V4Migrator(self._client, self.schema, self._cfg.system)
        return migrator.apply_migration(
            plan,
            dry_run=dry_run,
            allow_destructive=allow_destructive,
        )
