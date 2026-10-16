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
# Permission — IAM 鉴权适配层（Facade）
#
# 改造说明:
#   鉴权核心已委托给 公共 ModeRouter（is_allowed / batch_is_allowed / get_apply_url /
#   filter_space_list_by_action）。
#   Permission 保留：Django 身份解析、token 分享检查、skip_check 绕过、
#   SaaS 空间全家桶。
#
#   仍保留的旧依赖：
#     - get_iam_client → V3 平台 SDK 客户端，仅供 v3 平台集成点使用
#                        （反向回调 dispatcher + V1 遗留迁移工具），
#                        非 provider 中立鉴权入口，禁止新增调用方
#     - make_resource / batch_make_resource → monitor_web/iam/ 回调使用，
#                        已是纯 FwResource 构造
# ---------------------------------------------------------------------------

from __future__ import annotations

import logging
from collections import defaultdict

from django.conf import settings
from django.utils.functional import cached_property

from bkm_space.api import SpaceApi
from bkm_space.utils import bk_biz_id_to_space_uid, is_bk_saas_space
from bkmonitor.iam import ResourceEnum
from bkmonitor.iam.action import MINI_ACTION_IDS, ActionEnum, ActionMeta, canonicalize_action_id, get_action_by_id
from bkmonitor.iam.backends.v3.codec import MonitorV3Codec
from iam_engine.exceptions import CreatorGrantFailed, PermissionDenied, ProviderError
from bkmonitor.iam.handlers.grants import PermissionWriteResult, PermissionWriteTargetResult
from bkmonitor.iam.resource import to_resource_instance
from bkmonitor.iam.backends.v3.client import V3Client
from iam_engine.provider.requests import (
    ApplyURLRequest,
    BatchByResourceRequest,
    BatchAuthResult,
    ResourceAuthResult,
    VisibleResult,
    ResourceInstance as FwResource,
    Subject as FwSubject,
    SubjectType,
    to_action_id,
)
from bkmonitor.iam.backends.config import build_provider
from bkmonitor.iam import definitions
from bkmonitor.iam.concurrency import run_pair_concurrently
from iam_engine.migration.policy import MigrationPolicy
from iam_engine.core.config import AuthMode, DEFAULT_DUAL_STACK
from iam_engine.core.exceptions import InvalidAuthModeError
from iam_engine.core.requests import AuthRequest as SharedRequest, BatchAuthRequest
from iam_engine.core.types import AuthResult, AuthorizedResourceScope
from iam_engine.provider.bundle import LazyProviderBundles, ProviderBundle
from iam_engine.provider.router import ModeRouter
from iam_engine.provider.composition.union import UnionDecisionPolicy, UnionScopePolicy
from bkmonitor.iam.mode import get_mode_provider
from bkmonitor.models import ApiAuthToken
from bkmonitor.utils.request import get_request
from constants.common import DEFAULT_TENANT_ID
from core.errors.iam import ActionNotExistError, PermissionDeniedError
from core.errors.share import TokenValidatedError

logger = logging.getLogger(__name__)

# ActionIdMap 保留旧 Token 类型到动作的映射，值使用 ActionEnum 以兼容既有配置。
# 调用方可以传入 ActionEnum、ActionDef 或 action ID 字符串，因此匹配时统一按 action ID 比较。
ActionIdMap = {
    # 场景视图
    "host": [ActionEnum.VIEW_HOST],
    "collect": [ActionEnum.VIEW_COLLECTION],
    "uptime_check": [ActionEnum.VIEW_SYNTHETIC],
    "custom_metric": [ActionEnum.VIEW_CUSTOM_METRIC],
    "custom_event": [ActionEnum.VIEW_CUSTOM_EVENT],
    "kubernetes": [ActionEnum.VIEW_BUSINESS],
    # 自定义场景
    "scene_collect": [ActionEnum.VIEW_COLLECTION],
    "scene_custom_metric": [ActionEnum.VIEW_CUSTOM_METRIC],
    "scene_custom_event": [ActionEnum.VIEW_CUSTOM_EVENT],
    # 事件中心
    "event": [ActionEnum.VIEW_EVENT],
    # 仪表盘
    "dashboard": [ActionEnum.VIEW_SINGLE_DASHBOARD],
    # APM
    "apm": [ActionEnum.VIEW_APM_APPLICATION],
    # 故障根因定位
    "incident": [ActionEnum.VIEW_INCIDENT],
    # RUM
    "rum": [ActionEnum.VIEW_RUM_APPLICATION],
}

api_paths = ["/time_series/unify_query/", "log/query/", "time_series/unify_trace_query/"]


def _to_business_action_id(action_ref) -> str:
    """将 Action 引用统一为框架业务 ID，并兼容已登记的历史平台 ID。"""
    return canonicalize_action_id(to_action_id(action_ref))


def _skip_check_enabled(request) -> bool:
    """skip_check 解析：request 级覆盖 settings 级（与 Permission.__init__ 的合并逻辑一致）。"""
    if request is not None and hasattr(request, "skip_check"):
        return bool(request.skip_check)
    return bool(getattr(settings, "SKIP_IAM_PERMISSION_CHECK", False))


def check_iam_preflight(request, action_ref, skip_check=None) -> bool:
    """Permission 调用方（DRF 权限类等）使用的前置豁免判定。

    复刻旧版 Permission.is_allowed 的豁免顺序，命中任一即放行（返回 True），
    否则返回 False 进入真实鉴权：
      1. token 临时分享豁免（ApiAuthToken + ActionIdMap + api_paths）；
         仅命中当前 V3 基线明确的豁免条件时放行
      2. skip_check 豁免（request 级覆盖 settings 级）

    Args:
        request: Django request；None 表示后台/无请求上下文（只认 settings 级）
        action_ref: ActionDef、ActionEnum 成员或 action_id 字符串
        skip_check: 调用方已解析好的 skip 值（如 Permission 实例的 self.skip_check）；
                    为 None 时按 request 级覆盖 settings 级自动解析。
    """
    # token 临时分享权限豁免
    #
    # 沿用当前 V3 基线：view_business / ActionIdMap 场景 / api_paths 命中才放行。
    # 未登记的 token 类型按空动作列表处理。
    if request is not None and getattr(request, "token", None):
        try:
            record = ApiAuthToken.objects.get(token=request.token, bk_tenant_id=request.user.tenant_id)
        except ApiAuthToken.DoesNotExist:
            record = None

        action_id = _to_business_action_id(action_ref)
        if (
            action_id == _to_business_action_id(ActionEnum.VIEW_BUSINESS)
            or (record and any(action_id == _to_business_action_id(a) for a in ActionIdMap.get(record.type, [])))
            or any(path in request.path for path in api_paths)
        ):
            return True

    if skip_check is not None:
        return bool(skip_check)
    return _skip_check_enabled(request)


def check_iam_batch_preflight(request, actions) -> dict | None:
    """Permission 批量调用方（insert_permission_field / filter_data_by_permission）使用的前置豁免。

    复刻旧版 Permission.batch_is_allowed 的豁免语义：
      * request 带 token 且 ApiAuthToken 记录不存在 → 抛 TokenValidatedError（与旧版一致）；
      * token 存在时对每条 action 独立判定（view_business 恒等 / ActionIdMap 命中）；
      * skip_check（request 级覆盖 settings 级）→ 全部 True。

    Returns:
        None: 无需豁免，进入真实批量鉴权；
        {action_id: bool}: 豁免结果（对整批资源一致）。
    """
    if request is not None and getattr(request, "token", None):
        try:
            record = ApiAuthToken.objects.get(token=request.token, bk_tenant_id=request.user.tenant_id)
        except ApiAuthToken.DoesNotExist:
            raise TokenValidatedError

        result = {}
        allowed_action_ids = {_to_business_action_id(action) for action in ActionIdMap.get(record.type, [])}
        for action in actions:
            action_id = _to_business_action_id(action)
            result[action_id] = action_id == "view_business" or (record and action_id in allowed_action_ids)
        return result

    if _skip_check_enabled(request):
        return {_to_business_action_id(action): True for action in actions}

    return None


class Permission:
    """
    权限中心鉴权封装 — 公共 ModeRouter 适配层。
    """

    def __init__(self, username: str = "", bk_tenant_id: str = "", request=None):
        if username and bk_tenant_id:
            # 显式指定用户
            self.username = username
            self.bk_tenant_id = bk_tenant_id
        else:
            request = request or get_request(peaceful=True)
            if request:
                # web 请求：从 request.user 取
                self.username = request.user.username
                self.bk_tenant_id = request.user.tenant_id
            else:
                # 后台设置：本地 username + 默认租户
                logger.warning("IAM Permission init with local username, use default bk_tenant_id")
                from bkmonitor.utils.user import get_local_username

                self.username = get_local_username()
                if self.username is None:
                    raise ValueError("must provide `username` or `request` param to init")
                self.bk_tenant_id = DEFAULT_TENANT_ID

        self.request = request

        self._providers = None
        self._mode_router = None
        self._provider_bundles = None
        self.mode_provider = get_mode_provider()

        self.skip_check = getattr(settings, "SKIP_IAM_PERMISSION_CHECK", False)
        if request and hasattr(request, "skip_check"):
            logger.info(f"Permission: request.skip_check: {request.skip_check}")
            self.skip_check = request.skip_check

    @cached_property
    def iam_client(self):
        """Keep the SDK-shaped query/application boundary, backed by the shared router.

        Explicit V3 callbacks/model tools continue to use get_iam_client().
        Business consumers must not instantiate version-specific clients.
        """
        from bkmonitor.iam.handlers.mcp import MonitorMCPClient

        return MonitorMCPClient(self, self.bk_tenant_id)

    def make_request(self, action, resources=None):
        """Preserve the product request envelope; only IAM interprets action versions."""
        from iam import Action, Request, Subject

        action = get_action_by_id(_to_business_action_id(action))
        codec = MonitorV3Codec()
        resources = [
            codec.encode_resource(resource, self.get_iam_client(self.bk_tenant_id))
            if isinstance(resource, FwResource)
            else resource
            for resource in (resources or [])
        ]
        return Request(
            settings.BK_IAM_SYSTEM_ID,
            Subject("user", self.username),
            Action(codec.encode_action(action.id)),
            resources,
            None,
        )

    @property
    def schema(self):
        return getattr(self, "_schema", None) or definitions

    @property
    def providers(self):
        mode = self.mode_provider.get_mode()
        return {target.value: self.get_provider(target.value) for target in DEFAULT_DUAL_STACK.modes_for(mode)}

    def get_provider(self, name):
        if self._providers is None:
            self._providers = {}
        if name not in self._providers:
            self._providers[name] = build_provider(name, self.bk_tenant_id, username=self.username)
        return self._providers[name]

    @property
    def provider_bundles(self):
        from bkmonitor.iam.backends.v3.writer import V3AuthorizationWriter
        from bkmonitor.iam.backends.v4.writer import V4AuthorizationWriter

        if self._provider_bundles is not None:
            return self._provider_bundles

        def bundle(name):
            provider = self.get_provider(name)
            return ProviderBundle(
                auth=provider,
                application=provider,
                scope=provider,
                writer=(V3AuthorizationWriter if name == "v3" else V4AuthorizationWriter)(
                    provider, tenant_id=self.bk_tenant_id, operator=self.username
                ),
            )

        self._provider_bundles = LazyProviderBundles(
            {
                target: lambda target=target: bundle(target.value)
                for target in DEFAULT_DUAL_STACK.modes_for(AuthMode.UNION)
            }
        )
        return self._provider_bundles

    @property
    def mode_router(self):
        if self._mode_router is None:
            self._mode_router = ModeRouter(
                self.mode_provider, self.provider_bundles, pair_executor=run_pair_concurrently
            )
        return self._mode_router

    def _selected(self, resources=()):
        mode = self.mode_provider.get_mode(resources)
        modes = DEFAULT_DUAL_STACK.modes_for(mode)
        return [self.get_provider(item.value) for item in modes]

    def _is_allowed_request(self, request, *, mode=None):
        from iam_engine.exceptions import ProviderUnavailable

        decision = self._decide_request(request, mode=mode)
        if decision.degraded and not decision.allowed:
            raise ProviderUnavailable("IAM did not return an explicit authorization decision")
        return decision.allowed

    def _decide_request(self, request, *, mode=None):
        if self.skip_check:
            return UnionDecisionPolicy.decide((AuthResult.allow("bypass"),))
        router = self.mode_router if mode is None else self.mode_router.with_mode(mode)
        if isinstance(request, SharedRequest):
            return router.is_allowed(request)
        return router.is_allowed(
            SharedRequest(
                subject=request.subject,
                action_id=request.action_id,
                resources=(request.resource,) if request.resource is not None else (),
                environment=request.environment,
            )
        )

    def _batch_by_resource(self, request, *, mode=None):
        if not request.resources:
            return BatchAuthResult()
        router = self.mode_router if mode is None else self.mode_router.with_mode(mode)
        result = router.batch_is_allowed(
            BatchAuthRequest(
                subject=request.subject,
                action_ids=(request.action_id,),
                resource_groups=tuple((resource,) for resource in request.resources),
                environment=request.environment,
            )
        )
        resource_types = {str(r.id): r.type for r in request.resources}
        return BatchAuthResult(
            tuple(
                ResourceAuthResult(
                    item.action_id,
                    resource_types[item.resource_id],
                    item.resource_id,
                    item.decision.allowed,
                )
                for item in result.items
            )
        )

    def _batch_by_action(self, request):
        # Resource-free actions cannot be represented by BatchAuthRequest's nonempty groups.
        # Snapshot the mode once, including invalid-mode rejection, for the entire batch.
        try:
            mode = self.mode_provider.get_mode((request.resource,) if request.resource else ())
        except InvalidAuthModeError:
            return BatchAuthResult(
                tuple(
                    ResourceAuthResult(
                        to_action_id(a),
                        request.resource.type if request.resource else "",
                        str(request.resource.id) if request.resource else "",
                        False,
                    )
                    for a in request.action_ids
                )
            )

        router = self.mode_router.with_mode(mode)
        return BatchAuthResult(
            tuple(
                ResourceAuthResult(
                    to_action_id(action),
                    request.resource.type if request.resource else "",
                    str(request.resource.id) if request.resource else "",
                    router.is_allowed(
                        SharedRequest(
                            subject=request.subject,
                            action_id=action,
                            resources=(request.resource,) if request.resource else (),
                            environment=request.environment,
                        )
                    ).allowed,
                )
                for action in request.action_ids
            )
        )

    def _application_data(self, action_ids, resources, *, mode=None):
        try:
            if isinstance(mode, InvalidAuthModeError):
                raise mode
            mode = mode or self.mode_provider.get_mode(tuple(resources))
            application = MigrationPolicy.resolve_application(mode, self.provider_bundles)
        except Exception as error:
            logger.warning("IAM application provider unavailable: %s", error)
            return {}, ""
        try:
            data, url = application.provider.get_apply_data(action_ids, list(resources))
            if application.source_mode is DEFAULT_DUAL_STACK.current:
                return (data, url.strip()) if isinstance(url, str) and url.strip() else ({}, "")
            return data, url
        except Exception as error:
            if mode is AuthMode.V3:
                raise
            logger.warning("IAM application generation failed: %s", error)
        return {}, ""

    def _apply_url_request(self, request):
        return self._application_data(list(request.action_ids), request.resources)[1]

    def _apply_data_request(self, action_ids, resources, subject):
        return self._application_data(action_ids, resources)[0]

    def has_any_permission(self, subject, action_id):
        try:
            providers = self._selected()
        except InvalidAuthModeError:
            return False
        results = []
        for provider in providers:
            try:
                allowed = provider.has_any_permission(subject, action_id)
                results.append(AuthResult.allow(provider.name) if allowed is True else AuthResult.deny(provider.name))
            except Exception as error:
                results.append(AuthResult.error(provider.name, str(error), type(error).__name__))
        return UnionDecisionPolicy.decide(results).allowed

    def has_any_resource_permission(self, action):
        """产品权限入口：身份与引擎协议转换只发生在 IAM 适配边界。"""
        subject = FwSubject(id=self.username, type=SubjectType.USER, tenant_id=self.bk_tenant_id)
        return self.has_any_permission(subject, action)

    def filter_visible_resource_ids(self, action, resource_type, resource_ids, *, bk_biz_id):
        """产品资源范围入口；业务调用方只传本地 ID 和归属业务。"""
        subject = FwSubject(id=self.username, type=SubjectType.USER, tenant_id=self.bk_tenant_id)
        space = FwResource(type="space", id=str(bk_biz_id))
        candidates = tuple(FwResource(type=resource_type, id=str(rid), ancestor_chain=(space,)) for rid in resource_ids)
        return self.filter_visible_resources(subject, action, candidates)

    def filter_visible_resources(self, subject, action_id, candidates):
        from iam_engine.exceptions import ProviderUnavailable

        if not candidates:
            return VisibleResult()
        if candidates[0].type == "space":
            try:
                mode = self.mode_provider.get_mode(candidates)
                scope = self.mode_router.list_authorized_scope(
                    mode,
                    action_id=to_action_id(action_id),
                    resource_type="space",
                    subject={"type": subject.type, "id": subject.id},
                    candidate_ids=frozenset(str(r.id) for r in candidates),
                ).scope
            except InvalidAuthModeError as error:
                raise ProviderUnavailable(str(error)) from error
            if not scope.ok:
                raise ProviderUnavailable(scope.reason)
            return VisibleResult(scope.is_wildcard, tuple(str(r.id) for r in candidates if str(r.id) in scope.ids))
        try:
            providers = self._selected(candidates)
        except InvalidAuthModeError as error:
            raise ProviderUnavailable(str(error)) from error
        if not providers:
            raise ProviderUnavailable("no permission provider configured for selected mode")
        scopes = []
        resource_type = candidates[0].type
        for provider in providers:
            try:
                result = provider.filter_visible_resources(subject, action_id, candidates)
                scopes.append(
                    AuthorizedResourceScope.wildcard(resource_type, provider_name=provider.name)
                    if result.all_granted
                    else AuthorizedResourceScope.concrete(
                        resource_type, set(result.visible_ids), provider_name=provider.name
                    )
                )
            except Exception as error:
                scopes.append(
                    AuthorizedResourceScope.error(
                        resource_type,
                        provider_name=provider.name,
                        reason=str(error) or type(error).__name__,
                        error_type=type(error).__name__,
                    )
                )
        scope = UnionScopePolicy.merge(tuple(scopes))
        if not scope.ok:
            # 查询失败不能伪装成成功的空权限，尤其不能被 ACL 同步解释为撤权。
            raise ProviderUnavailable(scope.reason)
        if resource_type == "grafana_dashboard":
            # V3 的仪表盘实例范围来自策略，不能再次与本地候选求交而丢掉
            # bare UID、文件夹或尚未进入本地缓存的已授权实例；V4 已在批量查询中限定候选。
            return VisibleResult(scope.is_wildcard, tuple(sorted(scope.ids)))
        return VisibleResult(scope.is_wildcard, tuple(str(r.id) for r in candidates if str(r.id) in scope.ids))

    def query_policies(self, subject, action_id):
        return self._query("query_policy", subject, action_id)

    def _query(self, method, subject, action_id):
        results, errors = [], []
        for provider in self._selected():
            try:
                value = getattr(provider, method)(subject, action_id)
                if value is not None:
                    results.append(value)
            except Exception as error:
                errors.append(error)
        if errors and not results:
            raise errors[0]
        return results

    def query_policies_by_actions(self, subject, action_ids):
        results = {to_action_id(action): [] for action in action_ids}
        errors, succeeded = [], False
        for provider in self._selected():
            try:
                values = provider.query_policy_by_actions(subject, action_ids)
                succeeded = True
                for action_id, expression in values.items():
                    if expression is not None and action_id in results:
                        results[action_id].append(expression)
            except Exception as error:
                errors.append(error)
        if errors and not succeeded:
            raise errors[0]
        return results

    # ================================================================
    # V3 平台 SDK 客户端（仅 v3 平台集成点使用，非 provider 中立鉴权入口）
    # ================================================================

    @classmethod
    def get_iam_client(cls, bk_tenant_id: str):
        """获取 V3 平台 SDK 客户端。

        仅限 v3 平台集成点使用：
          * IAM v3 平台反向回调端点（ResourceApiDispatcher，平台调我们）

        非 provider 中立鉴权入口——业务鉴权一律走框架（is_allowed /
        filter_visible_resources 等），禁止新增调用方。
        """
        from django.utils.functional import SimpleLazyObject

        from config.tools.iam_credentials import get_saas_setting
        from bkmonitor.iam.backends.v3.compat import is_v1_compat_enabled

        # V3 资源 dispatcher 在 URLConf 导入时创建；推迟到首次调用，避免 migrate
        # 的 URL 检查阶段读取尚未准备好的 GlobalConfig。
        return SimpleLazyObject(
            lambda: V3Client(
                get_saas_setting("SAAS_APP_CODE"),
                get_saas_setting("SAAS_SECRET_KEY"),
                settings.BK_IAM_APIGATEWAY_URL,
                system_id=settings.BK_IAM_SYSTEM_ID,
                codec=MonitorV3Codec(),
                bk_tenant_id=bk_tenant_id,
                enable_v1_compat=is_v1_compat_enabled,
            )
        )

    # ================================================================
    # 鉴权 — 框架委托
    # ================================================================

    def is_allowed(self, action, resources: list = None, raise_exception: bool = False):
        """
        校验用户是否有动作的权限（委托 公共 ModeRouter）。

        V3 保留完整关联资源请求，由原 SDK 判断；V4/Union 的多资源列表
        按现有批量接口逐项判断，全部允许才返回 True。
        """
        # token 临时分享 / skip_check 前置豁免（与旧版逻辑一致；skip_check 传实例值，
        # 兼容调用方构造后修改 permission.skip_check 的既有用法）
        if check_iam_preflight(self.request, action, skip_check=self.skip_check):
            return True

        # 与 V3 一致：未知动作是输入错误，不进入 Provider 的故障降级或申请流程。
        get_action_by_id(action if isinstance(action, ActionMeta) else _to_business_action_id(action))

        resources = resources or []

        fw_resources = tuple(to_resource_instance(r) for r in resources)
        try:
            mode = self.mode_provider.get_mode(fw_resources)
        except InvalidAuthModeError as error:
            # 交给 Router 生成拒绝结果，不把非法配置回退为 V3。
            return self._is_allowed_resources(action, fw_resources, raise_exception, mode=error)
        if len(resources) <= 1 or mode is AuthMode.V3:
            return self._is_allowed_resources(action, fw_resources, raise_exception, mode=mode)

        # 多资源同类型 → batch_by_resource
        resource_types = {r.type for r in resources}
        if len(resource_types) > 1:
            raise ValueError(
                f"Permission.is_allowed 不支持混合资源类型（收到 {sorted(resource_types)}）；"
                "请按类型拆分调用，或直接使用 公共 ModeRouter 批量接口显式表达意图。"
            )

        return self._is_allowed_batch(action, resources, raise_exception, mode=mode)

    def _is_allowed_batch(self, action, resources: list, raise_exception: bool, *, mode=None):
        """内部：同类型多资源批量鉴权，所有资源都允许才返回 True。"""
        action_id_biz = _to_business_action_id(action)
        fw_resources = tuple(to_resource_instance(r) for r in resources)

        try:
            batch_result = self._batch_by_resource(
                BatchByResourceRequest(
                    subject=FwSubject(id=self.username, type=SubjectType.USER, tenant_id=self.bk_tenant_id),
                    action_id=action_id_biz,
                    resources=fw_resources,
                ),
                mode=mode,
            )
        except PermissionDenied as e:
            if raise_exception:
                raise self._build_permission_denied(action_id_biz, fw_resources[0], mode=mode) from e
            return False
        except ProviderError as e:
            logger.exception("[Permission.is_allowed batch] ProviderError: %s", e)
            if raise_exception:
                raise self._build_permission_denied(action_id_biz, fw_resources[0], mode=mode) from e
            return False

        # items 与请求资源顺序一致；按 resource_id 汇总允许集
        allowed_ids = {item.resource_id for item in batch_result.items if item.allowed}
        denied_resource: FwResource | None = None
        for r in fw_resources:
            if r.id not in allowed_ids:
                denied_resource = r
                break

        if denied_resource is None:
            return True

        if raise_exception:
            raise self._build_permission_denied(action_id_biz, denied_resource, mode=mode)
        return False

    def _is_allowed_resources(self, action, fw_resources: tuple[FwResource, ...], raise_exception: bool, *, mode=None):
        """保留 SDK 关联资源请求，不将默认 V3 请求拆成逐项批量鉴权。"""
        action_id_biz = _to_business_action_id(action)

        try:
            result = self._is_allowed_request(
                SharedRequest(
                    subject=FwSubject(id=self.username, type=SubjectType.USER, tenant_id=self.bk_tenant_id),
                    action_id=action_id_biz,
                    resources=fw_resources,
                ),
                mode=mode,
            )
        except PermissionDenied as e:
            if raise_exception:
                raise self._build_permission_denied(action_id_biz, fw_resources, mode=mode) from e
            return False
        except ProviderError as e:
            # Provider 层错误（含 ProviderUnavailable：平台不可达 / URL 缺失 / 超时）
            # 语义与 _is_allowed_batch 对齐：不冒泡到视图层（避免 500），
            # raise_exception=True 时降级为 PermissionDenied（用户看到"暂时无法验证
            # 权限"），False 时 log.exception + 返回 False。
            logger.exception("[Permission.is_allowed] ProviderError: %s", e)
            if raise_exception:
                raise self._build_permission_denied(action_id_biz, fw_resources, mode=mode) from e
            return False

        if not result and raise_exception:
            raise self._build_permission_denied(action_id_biz, fw_resources, mode=mode)

        return result

    def _build_permission_denied(self, action_id_biz: str, fw_resource, *, mode=None):
        """构建 PermissionDeniedError（含 SaaS 全家桶 + apply 数据）。"""
        resources = list(fw_resource) if isinstance(fw_resource, tuple) else ([fw_resource] if fw_resource else [])
        actions, detail_resources = self.prepare_apply_for_saas(resources)
        if not actions:
            detail_resources = resources
            try:
                actions = [get_action_by_id(action_id_biz)]
            except ActionNotExistError:
                actions = []
        apply_data, apply_url = self.get_apply_data(
            [a.id for a in actions] if actions else [action_id_biz],
            detail_resources,
            mode=mode,
        )
        try:
            action_name = get_action_by_id(action_id_biz).name
        except ActionNotExistError:
            action_name = action_id_biz
        return PermissionDeniedError(
            context={"action_name": action_name},
            data={"apply_url": apply_url},
            extra={"permission": apply_data},
        )

    def is_allowed_by_biz(self, bk_biz_id: int, action, raise_exception: bool = False):
        """
        判断用户对当前动作在该业务下是否有权限（委托 公共 ModeRouter）。
        """
        return self.is_allowed(
            action, [ResourceEnum.BUSINESS.create_simple_instance(bk_biz_id)], raise_exception=raise_exception
        )

    def batch_is_allowed(self, actions: list, resources: list[list]):
        """
        查询某批资源某批操作是否有权限（委托 公共 ModeRouter）。
        """
        result = defaultdict(dict)
        # token 临时分享权限豁免
        if self.request and getattr(self.request, "token", None):
            try:
                record = ApiAuthToken.objects.get(token=self.request.token, bk_tenant_id=self.request.user.tenant_id)
            except ApiAuthToken.DoesNotExist:
                raise TokenValidatedError
            allowed_action_ids = {_to_business_action_id(a) for a in ActionIdMap.get(record.type, [])}
            for action in actions:
                for resource in resources:
                    resource_id = resource[0].id
                    action_id = _to_business_action_id(action)
                    product_id = MonitorV3Codec().encode_action(action_id)
                    if action_id == "view_business" or (record and action_id in allowed_action_ids):
                        result[resource_id][product_id] = True
                    else:
                        result[resource_id][product_id] = False
            return result

        if self.skip_check:
            for action in actions:
                for resource in resources:
                    resource_id = resource[0].id
                    action_id = MonitorV3Codec().encode_action(_to_business_action_id(action))
                    result[resource_id][action_id] = True
            return result

        action_ids_biz = [_to_business_action_id(action) for action in actions]

        subject = FwSubject(id=self.username, type=SubjectType.USER, tenant_id=self.bk_tenant_id)
        groups = tuple(tuple(to_resource_instance(r) for r in group) for group in resources)
        request = BatchAuthRequest(subject, tuple(action_ids_biz), groups)
        try:
            mode = self.mode_provider.get_mode(tuple(r for group in groups for r in group))
        except InvalidAuthModeError as error:
            mode = error
        if mode is AuthMode.V3:
            return self.get_provider("v3").batch_product_is_allowed(request)
        decision = self.mode_router.with_mode(mode).batch_is_allowed(request)
        if any(item.decision.degraded and not item.decision.allowed for item in decision.items):
            logger.warning("IAM batch authorization degraded; no explicit grant")
        codec = MonitorV3Codec()
        for item in decision.items:
            result[item.resource_id][codec.encode_action(item.action_id)] = item.decision.allowed
        return result

    # ================================================================
    # 申请 URL / 申请数据 — 框架委托
    # ================================================================

    def get_apply_url(self, action_ids: list[str], resources: list = None, system_id: str = settings.BK_IAM_SYSTEM_ID):
        for action in action_ids:
            get_action_by_id(_to_business_action_id(action))
        action_ids_biz = [_to_business_action_id(action_id) for action_id in action_ids]
        fw_resources = tuple(to_resource_instance(r) for r in (resources or []))
        try:
            return self._apply_url_request(
                ApplyURLRequest(
                    subject=FwSubject(id=self.username, type=SubjectType.USER, tenant_id=self.bk_tenant_id),
                    action_ids=tuple(action_ids_biz),
                    resources=fw_resources,
                )
            )
        except ProviderError as e:
            logger.exception("[Permission.get_apply_url] ProviderError: %s", e)
            return ""

    def get_apply_data(self, actions, resources: list = None, *, mode=None):
        resources = resources or []

        for action in actions:
            get_action_by_id(action if isinstance(action, ActionMeta) else _to_business_action_id(action))
        action_ids_biz = [_to_business_action_id(action) for action in actions]
        fw_resources = [to_resource_instance(r) for r in resources]

        return self._application_data(action_ids_biz, fw_resources, mode=mode)

    # ================================================================
    # 创建者授权 — 框架委托
    # ================================================================

    def _grant_creator_actions(self, resource, creator, *, mode=None):
        from iam_engine.migration.dual_write import DualWriteGrantOrchestrator
        from iam_engine.error_summary import sanitize_error_summary

        mode = self.mode_provider.get_mode() if mode is None else mode
        writers = dict(MigrationPolicy.resolve_authorization_writers(mode, self.provider_bundles))
        results = {}

        def observe(version, resource_type, outcome):
            if outcome == "succeeded":
                results[version] = PermissionWriteTargetResult(version, True)
            elif outcome == "failed":
                error = writers[version].last_error
                results[version] = PermissionWriteTargetResult(
                    version,
                    False,
                    type(error).__name__ if error else outcome,
                    sanitize_error_summary(error) if error else outcome,
                )

        orchestrator = DualWriteGrantOrchestrator(
            writers=tuple(writers.items()),
            tenant_id=self.bk_tenant_id,
            grant_observer=observe,
        )
        orchestrator.grant_creator_action(
            {
                "system": settings.BK_IAM_SYSTEM_ID,
                "type": resource.type,
                "id": str(resource.id),
                "creator": creator,
                "name": getattr(resource, "name", "")
                or (getattr(resource, "attribute", None) or {}).get("name", str(resource.id)),
            }
        )
        return PermissionWriteResult(tuple(results[name] for name in writers))

    def grant_creator_action(
        self, resource, creator: str = None, raise_exception: bool = False
    ) -> PermissionWriteResult | None:
        """
        新建实例关联权限授权（委托公共双写编排），返回逐写后端结果。

        所选目标各同步尝试一次，不投递异步补偿。默认记录逐侧失败并继续其他目标；
        仅显式 raise_exception=True 时抛 CreatorGrantFailed，所有进程角色行为一致。
        """
        try:
            mode = self.mode_provider.get_mode()
            grant_result = self._grant_creator_actions(resource, creator or self.username, mode=mode)
        except Exception as e:  # pylint: disable=broad-except
            logger.exception(f"[grant_creator_action] Failed! resource: {resource}, result: {e}")
            if raise_exception:
                raise CreatorGrantFailed(
                    f"creator grant crashed: resource_type={resource.type}, resource_id={resource.id}"
                ) from e
            return None

        if grant_result.is_success:
            logger.info(
                "[grant_creator_action] Success! resource: %s, result: %s",
                resource,
                grant_result.as_log_dict(),
            )
            return grant_result

        logger.warning(
            "[grant_creator_action] Incomplete! resource: %s, result: %s",
            resource,
            grant_result.as_log_dict(),
        )
        if raise_exception:
            raise CreatorGrantFailed(
                f"creator grant incomplete: resource_type={resource.type}, "
                f"resource_id={resource.id}, result={grant_result.as_log_dict()}"
            )

        return grant_result

    # ================================================================
    # SaaS 空间全家桶 — V3 业务逻辑，框架无关
    # ================================================================

    def prepare_apply_for_saas(self, resources):
        if not resources or resources[0].type != ResourceEnum.BUSINESS.id:
            return [], []
        bk_biz_id = resources[0].id
        space_uid = bk_biz_id_to_space_uid(bk_biz_id)
        if not is_bk_saas_space(space_uid):
            return [], []
        actions = [get_action_by_id(a_id) for a_id in MINI_ACTION_IDS]
        return actions, [ResourceEnum.BUSINESS.create_instance(bk_biz_id)]

    # ================================================================
    # 空间列表过滤 — 走框架 filter_visible_resources（provider 中立）
    # ================================================================

    def filter_space_list_by_action(self, action: ActionMeta | str, using_cache=True) -> list[dict]:
        """
        获取有对应action权限的空间列表
        """
        space_list, _ = self.filter_space_list_by_action_with_scope(action, using_cache)
        return space_list

    def filter_space_list_by_action_with_scope(self, action, using_cache=True) -> tuple[list[dict], bool]:
        """获取有对应 action 权限的空间列表，并标识是否拥有全量空间权限。"""
        space_list = SpaceApi.list_spaces_dict(bk_tenant_id=self.bk_tenant_id, using_cache=using_cache)
        if self.skip_check:
            return space_list, True

        action_id_biz = _to_business_action_id(action)
        subject = FwSubject(id=self.username, type=SubjectType.USER, tenant_id=self.bk_tenant_id)
        candidates = tuple(FwResource(type="space", id=str(s["bk_biz_id"])) for s in space_list)

        try:
            result = self.filter_visible_resources(subject, action_id_biz, candidates)
        except ProviderError as e:
            logger.exception("[IAM Policy Query Error]: %s", e)
            return [], False

        if result.all_granted:
            return space_list, True

        visible_ids = set(result.visible_ids)
        return [s for s in space_list if str(s["bk_biz_id"]) in visible_ids], False

    # ================================================================
    # Resource 构造 — 保留（monitor_web/iam/ 回调使用）
    # ================================================================

    @classmethod
    def make_resource(cls, resource_type: str, instance_id: str):
        return FwResource(type=resource_type, id=str(instance_id))

    @classmethod
    def batch_make_resource(cls, resources: list[dict]):
        """
        批量构造resource对象
        """
        return [cls.make_resource(r["type"], r["id"]) for r in resources]

    # ================================================================
    # list_actions — 保持产品前端使用的 V3 元数据契约
    # ================================================================
    def list_actions(self):
        """返回平台注册的动作列表，字段兼容旧版 IAM V3 ``model.actions`` 返回结构。

        V3 模式仍查询 V3 平台并原样返回 model.actions；V4/Union 模式从本地
        Schema 投影相同的前端字段及历史 Action ID，不额外依赖 V3 平台可用性。
        """
        if self.mode_provider.get_mode() is AuthMode.V3:
            # 默认 V3 保留远端 model.actions 的完整协议与查询失败行为。
            from core.errors.api import BKAPIError

            provider = self.get_provider("v3")
            ok, message, data = provider.client._client.query(provider.system_id)
            if not ok:
                raise BKAPIError(
                    system_name=settings.BK_IAM_APP_CODE,
                    url=f"/api/v1/model/systems/{provider.system_id}/query",
                    result={"message": message},
                )
            return data["actions"]

        schema = self.schema
        codec = MonitorV3Codec()
        actions_data: list[dict] = []
        for action_def in schema.actions.values():
            v3_ext = (action_def.extensions or {}).get("v3", {}) or {}

            # related_resource_types：查 schema 获取资源类型名称，缺失时以 id 兜底
            related_resource_types: list[dict] = []
            rt_id = action_def.resource_type
            if rt_id:
                try:
                    rt_def = schema.resource_types[rt_id]
                    rt_name_en = (rt_def.extensions or {}).get("v3", {}).get("name_en", "") if rt_def else ""
                except Exception:  # noqa: BLE001  schema 未注册该资源类型时兜底
                    rt_def = None
                    rt_name_en = ""
                rt_v3 = rt_def.extensions.get("v3", {}) if rt_def else {}
                related_resource_types.append(
                    {
                        "system_id": settings.BK_IAM_SYSTEM_ID,
                        "id": rt_id,
                        "name": rt_def.name if rt_def else rt_id,
                        "name_en": rt_name_en,
                        "selection_mode": rt_v3.get("selection_mode", "instance"),
                        "related_instance_selections": rt_v3.get("related_instance_selections", []),
                    }
                )

            actions_data.append(
                {
                    "id": codec.encode_action(action_def.id),
                    "name": action_def.name,
                    "name_en": v3_ext.get("name_en", action_def.id),
                    "type": v3_ext.get("type", ""),
                    "version": v3_ext.get("version", 1),
                    "related_resource_types": related_resource_types,
                    "related_actions": list(v3_ext.get("related_actions", []) or []),
                    "description": action_def.description or "",
                }
            )
        return actions_data
