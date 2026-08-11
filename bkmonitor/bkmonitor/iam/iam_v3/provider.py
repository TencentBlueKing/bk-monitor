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
# 调用 V3 IAM 平台 API。业务命名 ↔ V3 方言的编解码全部由基类和 MonitorV3Codec 完成。
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

from iam import MultiActionRequest, Request, Resource, Subject
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
from ..definitions.codec_v3 import MonitorV3Codec
from .config import V3Options, V3SystemInfo

if TYPE_CHECKING:
    from ..iam_engine.schema.diff import MigrationPlan, MigrationReport
    from ..iam_engine.schema.registry import SchemaRegistry

logger = logging.getLogger(__name__)


class V3PermissionProvider(PermissionProvider):
    """IAM v3 ABAC 权限 Provider。

    鉴权：
        is_allowed 调 CompatibleIAM SDK；读操作走缓存、写操作不走。

    编解码：
        codec 为 MonitorV3Codec，在构造时从 schema extensions["v3"] 构建映射表。
        子类只处理"方言 ID → V3 SDK payload"。

    配置：
        完全由 IAM_FRAMEWORK.PROVIDERS[*].options 传入，
        Provider 不读 Django settings；具体字段参见 V3Options。
    """

    #: Provider 标识，用于日志/监控/命令行 --provider 参数。
    name: str = PROVIDER_NAME

    def __init__(self, schema: SchemaRegistry, **options: Any) -> None:
        """初始化 V3 Provider。

        从 options 解析 V3Options、替换 codec、实例化 CompatibleIAM。

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
        # 替换 codec：V3 需要 action_id 映射能力
        self.codec = MonitorV3Codec(schema)
        # CompatibleIAM SDK 客户端：配置全部注入，不读 Django settings
        from bkmonitor.iam.compatible import CompatibleIAM

        self._iam_client = CompatibleIAM(
            self._cfg.credentials.app_code,
            self._cfg.credentials.app_secret,
            self._cfg.base_url,
            bk_tenant_id=self._cfg.bk_tenant_id,
        )

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

        Args:
            request: 已编码为 V3 方言的鉴权请求。

        Returns:
            True 表示允许；False 为拒绝或异常。
        """
        # lazy import：action.py 模块级别会访问 Django settings
        from bkmonitor.iam.action import get_action_by_id

        # 解码回业务 action_id，用于判断读写策略
        action_id_biz = self.codec.decode_action(request.action_id)

        # 从 action.py 获取 SDK ActionMeta 对象（含 related_resource_types 等元数据）
        v3_action = get_action_by_id(request.action_id)

        # 构建 SDK Request
        sdk_resources: list[Resource] = []
        if request.resource:
            # 无关联资源的 action 清空 resources（与现有 Permission.is_allowed 一致）
            if not v3_action.related_resource_types:
                sdk_resources = []
            else:
                attr: dict[str, Any] = {}
                # 构建 _bk_iam_path_（V3 父子资源链）
                if request.resource.ancestors:
                    path_parts = [f"/{a.type},{a.id}/" for a in request.resource.ancestors]
                    attr["_bk_iam_path_"] = "".join(path_parts)
                sdk_resources = [
                    Resource(
                        system=self._cfg.system.id,
                        type=request.resource.type,
                        id=request.resource.id,
                        attribute=attr,
                    )
                ]

        sdk_request = Request(
            system=self._cfg.system.id,
            subject=Subject("user", request.subject.id),
            action=v3_action,
            resources=sdk_resources,
            environment=None,
        )

        try:
            if self.codec.is_read_action(action_id_biz):
                return self._iam_client.is_allowed_with_cache(sdk_request)
            return self._iam_client.is_allowed(sdk_request)
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
        """同 action、多 resource 批量鉴权（方言层单页，≤ CHUNK_SIZE）。

        Args:
            request: 已编码为 V3 方言的批量鉴权请求。

        Returns:
            list[(dialect_resource_id, allowed)]: 每个资源的鉴权结果。
        """
        from bkmonitor.iam.action import get_action_by_id

        v3_action = get_action_by_id(request.action_id)

        # 构建资源列表：每组资源一个 [Resource] 列表
        sdk_resources_list: list[list[Resource]] = []
        for rid in request.resource_ids:
            sdk_resources_list.append(
                [Resource(system=self._cfg.system.id, type=request.resource_type, id=rid, attribute={})]
            )

        sdk_request = MultiActionRequest(
            system=self._cfg.system.id,
            subject=Subject("user", request.subject.id),
            actions=[v3_action],
            resources=[],
            environment=None,
        )
        try:
            result = self._iam_client.batch_resource_multi_actions_allowed(sdk_request, sdk_resources_list)
        except AuthAPIError:
            logger.exception("[iam_v3:batch_by_resource] AuthAPIError for action=%s", request.action_id)
            return [(rid, False) for rid in request.resource_ids]

        # result 格式: {resource_id: {action_id: bool}}
        return [(rid, result.get(rid, {}).get(request.action_id, False)) for rid in request.resource_ids]

    # ================================================================
    # 方言层：多 action、同 resource 单页
    # ================================================================

    def _batch_by_action_dialect_page(
        self,
        request: DialectBatchByActionRequest,
    ) -> list[tuple[str, bool]]:
        """多 action、同一 resource（或无 resource）批量鉴权（方言层单页）。

        Args:
            request: 已编码为 V3 方言的批量鉴权请求。

        Returns:
            list[(dialect_action_id, allowed)]: 每个 action 的鉴权结果。
        """
        from bkmonitor.iam.action import get_action_by_id

        v3_actions = [get_action_by_id(aid) for aid in request.action_ids]

        # 构建资源列表
        sdk_resources_list: list[list[Resource]] = []
        if request.resource:
            sdk_resources_list.append(
                [
                    Resource(
                        system=self._cfg.system.id,
                        type=request.resource.type,
                        id=request.resource.id,
                        attribute={},
                    )
                ]
            )
        else:
            # 无资源场景：传一个空列表
            sdk_resources_list.append([])

        sdk_request = MultiActionRequest(
            system=self._cfg.system.id,
            subject=Subject("user", request.subject.id),
            actions=v3_actions,
            resources=[],
            environment=None,
        )
        try:
            result = self._iam_client.batch_resource_multi_actions_allowed(sdk_request, sdk_resources_list)
        except AuthAPIError:
            logger.exception("[iam_v3:batch_by_action] AuthAPIError")
            return [(aid, False) for aid in request.action_ids]

        # 有 resource 时 key 是 resource.id，无 resource 时 key 是 ""
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
        from bkmonitor.iam.action import get_action_by_id

        actions: list[ActionWithResources | ActionWithoutResources] = []

        for dialect_aid in request.action_ids:
            try:
                v3_action = get_action_by_id(dialect_aid)
            except Exception:
                # 找不到 action 定义时退化为无资源 action
                actions.append(ActionWithoutResources(dialect_aid))
                continue

            if not v3_action.related_resource_types:
                # 无关联资源的 action
                actions.append(ActionWithoutResources(dialect_aid))
            else:
                related_types: list[RelatedResourceType] = []
                for rrt_dict in v3_action.related_resource_types:
                    instances: list[ResourceInstance] = []
                    for r in request.resources:
                        if r.type == rrt_dict["id"]:
                            instances.append(ResourceInstance([ResourceNode(type=r.type, id=r.id, name=r.id)]))
                    selection_mode = rrt_dict.get("selection_mode", "instance")
                    related_instance_selections = rrt_dict.get("related_instance_selections", [])
                    related_types.append(
                        RelatedResourceType(
                            system_id=rrt_dict["system_id"],
                            id=rrt_dict["id"],
                            instances=instances,
                            selection_mode=selection_mode if isinstance(selection_mode, str) else "",
                            related_instance_selections=list(related_instance_selections),
                        )
                    )
                actions.append(ActionWithResources(dialect_aid, related_types))

        application = Application(self._cfg.system.id, actions=actions)
        ok, message, url = self._iam_client.get_apply_url(application)
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
        from bkmonitor.iam.action import get_action_by_id

        # 编码 action_ids → V3 方言
        dialect_action_ids = [self.codec.encode_action(a) for a in action_ids]

        action_to_resources_list: list[dict] = []
        for dialect_aid in dialect_action_ids:
            try:
                v3_action = get_action_by_id(dialect_aid)
            except Exception:
                continue

            # 编码 resource 为 SDK Resource 格式
            sdk_resources: list[Resource] = []
            if v3_action.related_resource_types and resources:
                for r in resources:
                    rt_biz = to_resource_type_id(r.type)
                    dialect_rt = self.codec.encode_resource_type(rt_biz)
                    dialect_rid = self.codec.encode_resource_id(rt_biz, r.id)
                    sdk_resources.append(
                        Resource(
                            system=self._cfg.system.id,
                            type=dialect_rt,
                            id=dialect_rid,
                            attribute={"name": r.name or r.id},
                        )
                    )
            else:
                sdk_resources = []

            action_to_resources_list.append(
                {"action": v3_action, "resources_list": [sdk_resources] if sdk_resources else [[]]}
            )

        return gen_perms_apply_data(
            system=self._cfg.system.id,
            subject=Subject("user", subject.id),
            action_to_resources_list=action_to_resources_list,
        )

    # ================================================================
    # health_check
    # ================================================================

    def health_check(self) -> dict:
        """探活检查。

        调用 V3 IAM 平台 query 接口验证连通性。

        Returns:
            dict: {"status": "ok"|"error", "provider": "v3", ...}
        """
        try:
            ok, message, data = self._iam_client._client.query(self._cfg.system.id)
            return {
                "status": "ok" if ok else "error",
                "provider": self.name,
                "remote_id": self._cfg.system.id,
                "message": message,
            }
        except Exception as e:
            return {"status": "error", "provider": self.name, "error": str(e)[:200]}

    # ================================================================
    # plan_migration / apply_migration（Phase 1：空实现）
    # ================================================================

    def plan_migration(self, schema: SchemaRegistry) -> MigrationPlan:
        """Phase 1：返回空变更计划。V3 迁移走原有 JSON migration 方式。"""
        from ..iam_engine.schema.diff import MigrationPlan

        return MigrationPlan(provider_name=self.name, changes=[])

    def apply_migration(
        self,
        plan: MigrationPlan,
        *,
        dry_run: bool = False,
        allow_destructive: bool = False,
    ) -> MigrationReport:
        """Phase 1：空操作。V3 迁移走原有 JSON migration 方式。"""
        from ..iam_engine.schema.diff import MigrationReport

        return MigrationReport(provider_name=self.name)
