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
# 只实现"方言层"接口：接收编码后的 Dialect* 结构，通过 V3Client SDK
# 调用 V3 IAM 平台 API。业务命名 ↔ V3 方言的编解码全部由基类和注入的 codec 完成。
#
# codec 类通过 IAM_FRAMEWORK.PROVIDER_CATALOG["v3"].options.codec_class 配置。
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
from .policy_converter import iam_dict_to_expression
from ..iam_engine.core.exceptions import ProviderError
from ..iam_engine.core.types import (
    ResourceInstance as CoreResourceInstance,
    Subject as CoreSubject,
    VisibleResult,
    to_action_id,
    to_resource_type_id,
)
from ..iam_engine.policy.evaluator import DictEvaluator
from ..iam_engine.policy.expression import Op, PolicyExpression
from ..iam_engine.provider.base import PermissionProvider
from ..iam_engine.provider.dialect_types import (
    DialectApplyURLRequest,
    DialectAuthRequest,
    DialectBatchByActionRequest,
    DialectBatchByResourceRequest,
    DialectResource,
)
from . import PROVIDER_NAME
from .config import V3Options, V3SystemInfo
from ..iam_engine.schema.definitions import ResourceTypeDef

if TYPE_CHECKING:
    from ..iam_engine.schema.diff import MigrationPlan, MigrationReport
    from ..iam_engine.schema.registry import SchemaRegistry

logger = logging.getLogger(__name__)


def _build_eval_obj(resource: CoreResourceInstance, with_id: bool = True) -> dict:
    """把 ResourceInstance 转成 DictEvaluator 的求值对象。

    key 为 IAM 表达式 field 全名（"{rt}.id" / "{rt}._bk_iam_path_"）。
    with_id=False 时 id 置空串，用于"空 id 求值"的全量授权判定。
    """
    rt_biz = to_resource_type_id(resource.type)
    path = "".join(f"/{to_resource_type_id(a.type)},{a.id}/" for a in resource.ancestor_chain)
    return {
        f"{rt_biz}.id": resource.id if with_id else "",
        f"{rt_biz}._bk_iam_path_": path,
    }


class V3PermissionProvider(PermissionProvider):
    """IAM v3 ABAC 权限 Provider。

    鉴权：
        is_allowed 调 V3Client SDK；读操作走缓存、写操作不走。

    编解码：
        codec 类通过 options.codec_class 配置（dotted path），
        由基类 __init__ 实例化。子类只处理"方言 ID → V3 SDK payload"。

    配置：
        完全由 IAM_FRAMEWORK.PROVIDER_CATALOG["v3"].options 传入，
        Provider 不读 Django settings；具体字段参见 V3Options。
    """

    #: Provider 标识，用于日志/监控/命令行 --provider 参数。
    name: str = PROVIDER_NAME

    def __init__(self, schema: SchemaRegistry, **options: Any) -> None:
        """初始化 V3 Provider。

        从 options 解析 V3Options、实例化 V3Client。
        codec 由基类 PermissionProvider.__init__ 根据 options.codec_class 创建。

        Args:
            schema: 框架统一构建的冻结 SchemaRegistry。
            **options: IAM_FRAMEWORK.PROVIDER_CATALOG["v3"].options 原样透传的字典，
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

        iam_generate_config 会通过基类的 serialize_system_info 导出完整字段。

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
        """同 action、多 resource 批量鉴权（方言层单页，≤ CHUNK_SIZE）。

        SDK 批量鉴权在本地做策略求值，依赖 resource.attribute 的 _bk_iam_path_
        （由 ancestors 构造），因此必须携带祖先链；优先使用基类下发的完整
        resources（含方言祖先链），兼容只有 resource_ids 的旧构造。
        """
        client = self._get_client(request.subject.tenant_id)
        resources = request.resources or tuple(
            DialectResource(type=request.resource_type, id=rid) for rid in request.resource_ids
        )
        sdk_resources_list = []
        for r in resources:
            # SDK 本地求值对 _bk_iam_path_ 做直接索引（iam/eval/object.py），
            # 无祖先链时给空串占位，避免 KeyError，并按"无路径不命中"求值
            attribute = None if r.ancestors else {"_bk_iam_path_": ""}
            sdk_resources_list.append([client.make_resource(r.type, r.id, ancestors=r.ancestors, attribute=attribute)])

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
            # SDK 批量鉴权本地求值依赖 _bk_iam_path_，必须携带祖先链；
            # 无祖先链时给空串占位，避免 iam/eval/object.py 直接索引 KeyError
            attribute = None if request.resource.ancestors else {"_bk_iam_path_": ""}
            sdk_resources_list.append(
                [
                    client.make_resource(
                        request.resource.type,
                        request.resource.id,
                        ancestors=request.resource.ancestors,
                        attribute=attribute,
                    )
                ]
            )
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
            # 平台生成失败：优先走 fallback_apply_url（业务侧显式配置的兜底跳转地址），
            # 未配置则维持"返回空串"的既有降级契约，由上层 Permission 层决定如何呈现。
            return self._cfg.fallback_apply_url
        return url or self._cfg.fallback_apply_url

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
        # 补全资源实例
        resolved_resources = [self._resolve(r) for r in resources]
        # 编码 action_ids → V3 方言
        dialect_action_ids = [self.codec.encode_action(a) for a in action_ids]

        action_to_resources_list: list[dict] = []
        for dialect_aid in dialect_action_ids:
            action_id_biz = self.codec.decode_action(dialect_aid)

            # 编码 resource 为 SDK Resource 格式
            sdk_resources: list = []
            if self._action_has_resource(action_id_biz) and resolved_resources:
                for r in resolved_resources:
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
    # 策略表达式查询（低层能力）
    # ================================================================

    def query_policy(
        self,
        subject: CoreSubject,
        action_id: str,
    ) -> PolicyExpression | None:
        """查询单个 action 的策略 AST。

        语义约定：
          * 查询成功、用户无权限（IAM 返回空策略）→ PolicyExpression.none()
          * 查询失败 → 抛框架统一异常 ProviderError，由调用方（framework/permission 层）降级处理
        """
        action_id_biz = to_action_id(action_id)
        try:
            _ = self.schema.get_action(action_id_biz)
        except Exception:
            logger.warning("[iam_v3:query_policy] unknown action_id=%s", action_id_biz)
            return None

        v3_action_id = self.codec.encode_action(action_id_biz)

        client = self._get_client(subject.tenant_id)
        sdk_request = client.make_request(subject.id, v3_action_id)

        # SDK 异常在 provider 公开边界转换为框架统一异常（上层不感知 v3/v4 差异）
        try:
            dict_ast = client._do_policy_query(sdk_request, with_resources=False)
        except AuthAPIError as e:
            raise ProviderError(
                f"[iam_v3:query_policy] policy query failed, action={action_id_biz}, user={subject.id}"
            ) from e
        expr = iam_dict_to_expression(dict_ast)
        return expr if expr is not None else PolicyExpression.none()

    def query_policy_by_actions(
        self,
        subject: CoreSubject,
        action_ids: list[str],
    ) -> dict[str, PolicyExpression | None]:
        """批量查询多个 action 的策略 AST。

        语义约定：
          * 批量成功、未返回/空 condition 的 action（用户无权限）→ PolicyExpression.none()
          * 批量失败 → 抛框架统一异常 ProviderError，由调用方（framework/permission 层）降级为逐个查询
        """
        action_ids_biz = [to_action_id(a) for a in action_ids]
        valid_aids = []
        for aid in action_ids_biz:
            try:
                self.schema.get_action(aid)
                valid_aids.append(aid)
            except Exception:
                logger.warning("[iam_v3:query_policy_by_actions] unknown action_id=%s", aid)

        if not valid_aids:
            return {aid: PolicyExpression.none() for aid in action_ids_biz}

        v3_action_ids = [self.codec.encode_action(aid) for aid in valid_aids]

        client = self._get_client(subject.tenant_id)
        sdk_request = client.make_multi_action_request(subject.id, v3_action_ids)

        # SDK 异常在 provider 公开边界转换为框架统一异常（上层不感知 v3/v4 差异）
        try:
            raw_list = client._do_policy_query_by_actions(sdk_request, with_resources=False)
        except AuthAPIError as e:
            raise ProviderError(
                f"[iam_v3:query_policy_by_actions] batch policy query failed, actions={valid_aids}, user={subject.id}"
            ) from e

        # raw_list: [{"action": {"id": "v3_id"}, "condition": {...}}, ...]
        # 先构建有效结果，再补齐未返回的 action
        result: dict[str, PolicyExpression | None] = {}
        for item in raw_list or []:
            v3_aid = item.get("action", {}).get("id", "")
            if not v3_aid:
                continue
            biz_aid = self.codec.decode_action(v3_aid)
            if biz_aid:
                expr = iam_dict_to_expression(item.get("condition"))
                # 空 condition = 用户无权限 → none()，与"查询失败"区分
                result[biz_aid] = expr if expr is not None else PolicyExpression.none()

        # 未返回的 action：批量查询成功但没有该 action 的策略 → 无权限
        for aid in action_ids_biz:
            if aid not in result:
                result[aid] = PolicyExpression.none()

        return result

    # ================================================================
    # 可见性能力（低层能力）
    # ================================================================

    def has_any_permission(
        self,
        subject: CoreSubject,
        action_id: str,
    ) -> bool:
        """v3：query_policy 返回非空表达式即视为有实例级权限（近似判定）。

        跨 org 场景可能"有权限但不在当前 org"——由资源层精确过滤兜底，
        与旧 Grafana 行为一致（表达式全局解析后按 org 匹配）。
        AuthAPIError 向上抛，由调用方决定降级。
        """
        expr = self.query_policy(subject, action_id)
        return expr is not None and expr.op != Op.NONE

    def filter_visible_resources(
        self,
        subject: CoreSubject,
        action_id: str,
        candidates: tuple[CoreResourceInstance, ...],
    ) -> VisibleResult:
        """v3：query_policy 表达式 + DictEvaluator 本地求值（1 次 API）。

        性能约定：顶层资源候选可达数十万（如 space 列表过滤），
        对 "{rt}.id" 上的 IN/EQ 叶子走集合快速路径，避免逐候选求值。
        """
        expr = self.query_policy(subject, action_id)
        if expr is None or expr.op == Op.NONE:
            return VisibleResult()
        if expr.op == Op.ANY:
            return VisibleResult(all_granted=True, visible_ids=tuple(c.id for c in candidates))
        if not candidates:
            return VisibleResult()

        # 快速路径："{rt}.id" 的 IN/EQ → 集合过滤（O(N) set 查找，与旧 filter_space_list 的 IN 分支对齐）
        rt_biz = to_resource_type_id(candidates[0].type)
        id_field = f"{rt_biz}.id"
        if expr.op == Op.IN and expr.field == id_field:
            allowed = {str(v) for v in (expr.value or ())}
            return VisibleResult(visible_ids=tuple(c.id for c in candidates if c.id in allowed))
        if expr.op == Op.EQ and expr.field == id_field:
            allowed = str(expr.value)
            return VisibleResult(visible_ids=tuple(c.id for c in candidates if c.id == allowed))

        evaluator = DictEvaluator()

        # 全量判定：空 id + 首个候选的父链（约定同批候选共享父链，如 Grafana 单 org 一批）
        all_granted = False
        if evaluator.evaluate(expr, _build_eval_obj(candidates[0], with_id=False)):
            all_granted = True

        visible: list[str] = []
        for c in candidates:
            if evaluator.evaluate(expr, _build_eval_obj(c)):
                visible.append(c.id)

        return VisibleResult(all_granted=all_granted, visible_ids=tuple(visible))

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
        from .migrator import V3Migrator

        migrator = V3Migrator(self._iam_client, schema, self._cfg, self.codec, self.name)
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
        from .migrator import V3Migrator

        migrator = V3Migrator(self._iam_client, self.schema, self._cfg, self.codec, self.name)
        return migrator.apply_migration(
            plan,
            dry_run=dry_run,
            allow_destructive=allow_destructive,
        )
