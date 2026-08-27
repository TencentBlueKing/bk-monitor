"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

# ---------------------------------------------------------------------------
# Permission —— 业务侧 IAM 门面
#
# 鉴权 / 批量 / 申请 / 空间列表 / 创建者授权都从这里进出。业务模块不要直接
# 调 backends.v3|v4 或 ModeRouter。本类负责：
#   1. 解析 username / tenant
#   2. 按 DualStackSpec 装配 ProviderBundle
#   3. 把 iam.Resource 转成引擎 ResourceInstance
#   4. demo 业务豁免、指标、申请失败兜底
#
# 反向回调仍走 views/resources.py 与 views/resources_v4.py，不经过本门面。
# ---------------------------------------------------------------------------

import warnings

from django.conf import settings
from iam import Resource

from apps.iam import metrics
from apps.iam.backends.v3 import V3AuthorizationWriter, V3PermissionProvider
from apps.iam.backends.v3.client import build_v3_client
from apps.iam.backends.v3.meta import get_system_info as get_v3_system_info
from apps.iam.backends.v4 import V4AuthorizationWriter, V4PermissionProvider
from apps.iam.backends.v4.callback_client import V4CallbackIAM
from apps.iam.concurrency import run_pair_concurrently
from apps.iam.backends.v4.config import resolve_v4_gateway_url
from apps.iam.exceptions import IAMDependencyError, PermissionDeniedError
from apps.iam.handlers.actions import ActionMeta, get_action_by_id
from apps.iam.handlers.resources import Business as BusinessResource
from apps.iam.handlers.resources import ResourceEnum, get_resource_by_id
from apps.iam.iam_engine.core.config import AuthMode, DEFAULT_DUAL_STACK
from apps.iam.iam_engine.core.exceptions import InvalidAuthModeError
from apps.iam.iam_engine.core.requests import (
    AuthRequest as EngineAuthRequest,
    BatchAuthRequest as EngineBatchAuthRequest,
    ResourceInstance as EngineResourceInstance,
    Subject as EngineSubject,
    to_definition_id,
)
from apps.iam.iam_engine.core.types import AuthDecision, AuthStatus, AuthorizedResourceScope, BatchAuthDecision
from apps.iam.iam_engine.migration.policy import ApplicationResolution, MigrationPolicy
from apps.iam.iam_engine.migration.dual_write import DualWriteGrantOrchestrator
from apps.iam.iam_engine.provider.bundle import ProviderBundle
from apps.iam.iam_engine.provider.capabilities import (
    AuthorizationWriter,
    AuthorizedScopeProvider,
    PermissionApplicationProvider,
)
from apps.iam.iam_engine.provider.router import ModeRouter
from apps.iam.mode import get_mode_provider
from apps.utils.local import get_request, get_request_username, get_local_username, get_request_tenant_id
from apps.utils.log import logger


class Permission:
    """权限中心鉴权封装：对外保持 bool / (apply_data, apply_url)，对内走双栈编排。"""

    def __init__(self, username: str = "", bk_tenant_id: str = "", request=None):
        if username and bk_tenant_id:
            self.username = username
            self.bk_tenant_id = bk_tenant_id
        else:
            try:
                request = request or get_request(peaceful=True)
                # web请求
                if request:
                    self.username = request.user.username
                    self.bk_tenant_id = get_request_tenant_id()
                else:
                    self.bk_tenant_id = settings.BK_APP_TENANT_ID
                    logger.warning(
                        "IAM Permission init with local username, use default bk_tenant_id: %s", self.bk_tenant_id
                    )
                    # 后台设置
                    self.username = get_local_username()
                    if self.username is None:
                        raise ValueError("must provide `username` or `request` param to init")
            except Exception:  # pylint: disable=broad-except
                self.bk_tenant_id = settings.BK_APP_TENANT_ID
                self.username = get_request_username()

        self.iam_client = self.get_iam_client(self.bk_tenant_id)
        # 是否跳过权限中心校验
        # 如果request header 中携带token，通过获取token中的鉴权类型type匹配action
        self.skip_check = getattr(settings, "SKIP_IAM_PERMISSION_CHECK", False)
        if request and getattr(request, "skip_check", False):
            self.skip_check = True

        self._mode_router = None
        self._provider_bundles = None
        self._v3_provider = None
        self._v4_provider = None
        self._v4_authorization_writer = None

    # ================================================================
    # 平台客户端（仅回调 / V3 SDK 集成点，不是业务鉴权入口）
    # ================================================================

    @classmethod
    def get_iam_client(cls, bk_tenant_id: str):
        """V3 IAM SDK 客户端。业务鉴权请走 is_allowed，不要新增直接调用。"""

        return build_v3_client(bk_tenant_id)

    @classmethod
    def get_v4_callback_iam_client(cls, bk_tenant_id: str):
        """V4 反向回调验签客户端，只给 views/resources_v4.py 用。"""
        return V4CallbackIAM(
            settings.APP_CODE, settings.SECRET_KEY, settings.BK_IAM_APIGATEWAY_URL, bk_tenant_id=bk_tenant_id
        )

    # ================================================================
    # 双栈装配 —— Bundle + ModeRouter + DualStackSpec
    # ================================================================

    @property
    def provider_bundles(self) -> dict[AuthMode, ProviderBundle]:
        if self._provider_bundles is None:
            self._provider_bundles = self._build_provider_bundles()
        return self._provider_bundles

    @property
    def mode_router(self) -> ModeRouter:
        if self._mode_router is None:
            self._mode_router = ModeRouter(
                mode_provider=get_mode_provider(),
                bundles=self.provider_bundles,
                pair_executor=run_pair_concurrently,
                stack=DEFAULT_DUAL_STACK,
            )
        return self._mode_router

    def _build_provider_bundles(self) -> dict[AuthMode, ProviderBundle]:
        """按协议版本注入能力。换代时在这里加新 key，拓扑的 current 指向它即可。"""

        v3_provider = self.get_v3_provider()
        v4_provider = self.get_v4_provider()
        return {
            AuthMode.V3: ProviderBundle(
                auth=v3_provider,
                application=v3_provider,
                writer=V3AuthorizationWriter(self.iam_client),
                scope=v3_provider,
            ),
            AuthMode.V4: ProviderBundle(
                auth=v4_provider,
                application=self.get_v4_permission_application_provider(),
                writer=self.get_v4_authorization_writer(),
                scope=v4_provider,
            ),
        }

    def get_v3_provider(self) -> V3PermissionProvider:
        if self._v3_provider is None:
            self._v3_provider = V3PermissionProvider(
                self.iam_client,
                settings.BK_IAM_SYSTEM_ID,
                action_resolver=get_action_by_id,
            )
        return self._v3_provider

    def get_v4_provider(self):
        if self._v4_provider is None:
            self._v4_provider = V4PermissionProvider.from_settings(
                username=self.username,
                bk_tenant_id=self.bk_tenant_id,
                action_resolver=get_action_by_id,
            )
        return self._v4_provider

    def get_v4_permission_application_provider(self) -> PermissionApplicationProvider | None:
        return self.get_v4_provider()

    def get_v4_authorization_writer(self) -> AuthorizationWriter | None:
        if not resolve_v4_gateway_url():
            return None
        if self._v4_authorization_writer is None:
            self._v4_authorization_writer = V4AuthorizationWriter.from_settings(
                username=self.username,
                bk_tenant_id=self.bk_tenant_id,
            )
        return self._v4_authorization_writer

    # ================================================================
    # 请求转换 —— iam.Resource → 引擎 ResourceInstance
    # ================================================================

    def make_engine_request(self, action: ActionMeta | str, resources: list[Resource] = None) -> EngineAuthRequest:
        action = get_action_by_id(action)
        return EngineAuthRequest(
            subject=EngineSubject(id=self.username, tenant_id=self.bk_tenant_id),
            action_id=action,
            resources=tuple(self._to_engine_resource(resource) for resource in (resources or [])),
        )

    def make_engine_batch_request(
        self,
        actions: list[ActionMeta | str],
        resources: list[list[Resource]],
    ) -> EngineBatchAuthRequest:
        return EngineBatchAuthRequest(
            subject=EngineSubject(id=self.username, tenant_id=self.bk_tenant_id),
            action_ids=tuple(get_action_by_id(action) for action in actions),
            resource_groups=tuple(
                tuple(self._to_engine_resource(resource) for resource in resource_group) for resource_group in resources
            ),
        )

    @staticmethod
    def _to_engine_resource(resource: Resource) -> EngineResourceInstance:
        attributes = dict(resource.attribute or {})
        return EngineResourceInstance(
            system=resource.system,
            type=resource.type,
            id=str(resource.id),
            name=attributes.get("name", ""),
            attributes=attributes,
        )

    # ================================================================
    # 无权限申请 —— MigrationPolicy 选边，生产只走 get_apply_data
    # ================================================================

    def get_apply_url(
        self, action_ids: list[str], resources: list[Resource] = None, system_id: str = settings.BK_IAM_SYSTEM_ID
    ):
        """Deprecated: 仓库外脚本请改用 ``get_apply_data``，取返回值的第二个元素。

        本方法有意收缩：生产路径已经由 ``get_apply_data`` 带出 URL。
        仍保留转发，避免仓库外直接调用变成 AttributeError。
        ``system_id`` 不再透传；与 ``BK_IAM_SYSTEM_ID`` 不一致时打 warning。
        """

        message = (
            "Permission.get_apply_url is deprecated; use get_apply_data and take the URL from the second return value"
        )
        warnings.warn(message, DeprecationWarning, stacklevel=2)
        logger.warning(message)
        if system_id != settings.BK_IAM_SYSTEM_ID:
            logger.warning(
                "Permission.get_apply_url ignores system_id=%s; apply URL is generated for %s",
                system_id,
                settings.BK_IAM_SYSTEM_ID,
            )
        _data, url = self.get_apply_data(action_ids, resources)
        return url

    def get_apply_data(
        self,
        actions: list[ActionMeta | str],
        resources: list[Resource] = None,
        *,
        mode: AuthMode | str | None = None,
    ):
        """
        生成本系统无权限数据
        """
        resources = resources or []
        resolved_mode = self._resolve_safe_apply_mode(resources, mode)
        stack = self.mode_router.stack
        application = MigrationPolicy.resolve_application(resolved_mode, self.provider_bundles, stack=stack)
        try:
            return self._call_application_provider(application, actions, resources)
        except Exception as error:  # pylint: disable=broad-except
            if application.source_mode is not stack.current:
                raise

            if resolved_mode is AuthMode.UNION:
                logger.warning(
                    "[IAM Apply] mode=%s %s provider failed, fallback to %s: %s",
                    resolved_mode.value,
                    stack.current.value,
                    stack.legacy.value,
                    error,
                )
                legacy_application = MigrationPolicy.resolve_application(
                    stack.legacy, self.provider_bundles, stack=stack
                )
                return self._call_application_provider(legacy_application, actions, resources)

            # 纯 current 模式最终会不再保留 legacy，这里不做“回退旧栈”的迁移期兼容，
            # 只记录错误并返回退化的申请数据，保证鉴权拒绝流程不会因为申请数据生成失败而变成 500。
            logger.error(
                "[IAM Apply] mode=%s %s apply data generation failed: %s",
                resolved_mode.value,
                stack.current.value,
                error,
            )
            return {}, settings.BK_IAM_SAAS_HOST

    def _call_application_provider(
        self,
        application: ApplicationResolution,
        actions: list[ActionMeta | str],
        resources: list[Resource],
    ):
        return application.provider.get_apply_data(
            [get_action_by_id(action) for action in actions],
            [self._to_engine_resource(resource) for resource in resources],
        )

    def _resolve_safe_apply_mode(self, resources: list[Resource], mode: AuthMode | str | None) -> AuthMode:
        """统一"显式传入模式"与"自动读取模式"两条入口，任何非法值都安全回退 legacy。

        调用方既可能显式传入 mode（例如 is_allowed 把 decision.mode 原样传回，可能是非法字符串），
        也可能不传 mode 走 ModeProvider 自动解析（环境变量优先，否则 Feature Toggle；
        可能因配置非法抛出 InvalidAuthModeError）。
        这里统一兜底，避免任何一条路径把异常/非法值泄漏给直接调用 get_apply_data 的业务代码。
        """
        fallback_mode = self.mode_router.stack.legacy
        if mode is not None:
            resolved_mode = AuthMode.safe_coerce(mode, default=fallback_mode)
            if resolved_mode.value != mode:
                logger.warning(
                    "[IAM Apply] invalid auth mode=%r is not a valid AuthMode, falling back to %s apply",
                    mode,
                    resolved_mode.value,
                )
            return resolved_mode

        try:
            return self._resolve_auth_mode(resources)
        except InvalidAuthModeError as error:
            logger.warning(
                "[IAM Apply] failed to resolve auth mode (%s), falling back to %s apply",
                error.reason,
                fallback_mode.value,
            )
            return fallback_mode

    def _resolve_auth_mode(self, resources: list[Resource]) -> AuthMode:
        engine_resources = tuple(self._to_engine_resource(resource) for resource in resources)
        return self.mode_router.mode_provider.get_mode(engine_resources)

    @staticmethod
    def is_demo_biz_resource(resources: list[Resource] = None):
        """
        判断资源是否为demo业务的资源
        """
        if not settings.DEMO_BIZ_ID:
            return False
        if not resources:
            return False
        if not len(resources) == 1:
            return False
        if (resources[0].system, resources[0].type, str(resources[0].id)) == (
            BusinessResource.system_id,
            BusinessResource.id,
            str(settings.DEMO_BIZ_ID),
        ):
            # 业务类型资源判断资源ID
            return True
        if resources[0].attribute and resources[0].attribute.get("_bk_iam_path_", "").startswith(
            f"/biz,{settings.DEMO_BIZ_ID}/"
        ):
            # 其他类型资源，判断路径
            return True
        return False

    # ================================================================
    # 鉴权 —— ModeRouter；对外仍返回 bool
    # ================================================================

    def is_allowed(self, action: ActionMeta | str, resources: list[Resource] = None, raise_exception: bool = False):
        """
        校验用户是否有动作的权限
        :param action: 动作
        :param resources: 依赖的资源实例列表
        :param raise_exception: 鉴权失败时是否需要抛出异常
        """
        action = get_action_by_id(action)
        if not action.related_resource_types:
            resources = []

        # ===== 针对demo业务的权限豁免 开始 ===== #
        if self.is_demo_biz_resource(resources):
            # 如果是demo业务，则进行权限豁免，分为读写权限
            if settings.DEMO_BIZ_EDIT_ENABLED or action.is_read_action():
                return True
        # ===== 针对demo业务的权限豁免 结束 ===== #

        request = self.make_engine_request(action, resources)
        decision = self.mode_router.is_allowed(request)
        self._record_decision(action.id, decision, self._resource_type_label(request.resources))
        result = decision.allowed

        if not result and raise_exception:
            apply_data, apply_url = self.get_apply_data([action], resources, mode=decision.mode)
            raise PermissionDeniedError(
                action_name=action.name,
                apply_url=apply_url,
                permission=apply_data,
            )

        return result

    def is_allowed_by_biz(self, bk_biz_id: int, action: ActionMeta | str, raise_exception: bool = False):
        """
        判断用户对当前动作在该业务下是否有权限
        """
        if self.skip_check:
            return True

        resources = [ResourceEnum.BUSINESS.create_simple_instance(bk_biz_id)]
        return self.is_allowed(action, resources, raise_exception)

    def batch_is_allowed(self, actions: list[ActionMeta], resources: list[list[Resource]]):
        """
        查询某批资源某批操作是否有权限
        """
        actions = [get_action_by_id(action) for action in actions]
        request = self.make_engine_batch_request(actions, resources)
        decision = self.mode_router.batch_is_allowed(request)
        self._record_batch_decision(decision, request)
        result = decision.as_allowed_dict()

        # ===== 针对demo业务的权限豁免 开始 ===== #
        for action in actions:
            if not settings.DEMO_BIZ_EDIT_ENABLED and not action.is_read_action():
                continue
            for resource in resources:
                resource_id = resource[0].id
                action_id = action.id
                if self.is_demo_biz_resource(resource) and resource_id in result and action_id in result[resource_id]:
                    result[resource_id][action_id] = True
        # ===== 针对demo业务的权限豁免 结束 ===== #

        return result

    @staticmethod
    def _resource_type_label(resources: tuple[EngineResourceInstance, ...]) -> str:
        """无关联资源的 Action 用占位值，保证 label 取值集合固定。"""
        if not resources:
            return metrics.RESOURCE_TYPE_NONE
        return to_definition_id(resources[0].type)

    @staticmethod
    def _mode_label(mode: str) -> str:
        """把决策模式归一到闭合取值。

        非法模式配置会被 ModeRouter 原样写进 AuthDecision.mode，而它来自环境变量或 Feature Toggle，
        是运维可改写的配置，直接当 label 用就不再是有限枚举。这里不套 AuthMode.safe_coerce，因为它会把误配折叠成
        v3、反而掩盖配置错误；误配单独归到 invalid，仍可与 IAM_PROVIDER_RESULT_COUNT 里
        provider="mode"、error_type="InvalidPermissionMode" 的样本对上。
        """
        try:
            return AuthMode(mode).value
        except ValueError:
            return "invalid"

    @classmethod
    def _observe_decision(cls, decision: AuthDecision, *, action_id: str, resource_type: str, api: str) -> None:
        """把一次决策拆成决策级、Provider 级和 union 分歧三类指标。

        degraded 和 hit_provider_names 都由 ModeRouter 与 UnionDecisionPolicy 算定，这里只做 label 归一，
        不重新推导，避免观测口径与真实决策口径出现两套实现。

        统计的是 IAM 双栈决策本身，不含 demo 业务豁免：单点路径豁免命中时直接返回、根本没有决策可记，
        批量路径记的也是豁免改写前的 IAM 原始判定。
        """
        mode = cls._mode_label(decision.mode)
        metrics.IAM_AUTH_DECISION_COUNT.labels(
            mode=mode,
            action_id=action_id,
            resource_type=resource_type,
            api=api,
            allowed=str(decision.allowed).lower(),
            hit_provider="+".join(sorted(decision.hit_provider_names)) or "none",
            degraded=str(decision.degraded).lower(),
        ).inc()
        for result in decision.provider_results:
            metrics.IAM_PROVIDER_RESULT_COUNT.labels(
                mode=mode,
                provider=result.provider_name,
                action_id=action_id,
                api=api,
                status=result.status.value,
                error_type=result.error_type,
            ).inc()
        for pattern in cls._union_divergence_patterns(decision):
            metrics.IAM_UNION_DIVERGENCE_COUNT.labels(action_id=action_id, api=api, pattern=pattern).inc()

    @staticmethod
    def _union_divergence_patterns(decision: AuthDecision) -> tuple[str, ...]:
        """只统计双栈同时参与时的分歧，单栈模式没有可比对的另一侧。"""
        if decision.mode != AuthMode.UNION.value or len(decision.provider_results) < 2:
            return ()

        error_results = tuple(result for result in decision.provider_results if result.status is AuthStatus.ERROR)
        if len(error_results) == len(decision.provider_results):
            return ("both_error",)

        patterns = [f"{result.provider_name}_error" for result in error_results]
        # 只有一侧明确允许、另一侧明确拒绝才是策略层面的不一致；报错那一侧已由上面的 pattern 说明，
        # 再计一次 only_allow 会把依赖故障和策略差异混成同一个口径。
        allowed_results = tuple(result for result in decision.provider_results if result.status is AuthStatus.ALLOW)
        denied_results = tuple(result for result in decision.provider_results if result.status is AuthStatus.DENY)
        if len(allowed_results) == 1 and denied_results:
            patterns.append(f"{allowed_results[0].provider_name}_only_allow")
        return tuple(patterns)

    @classmethod
    def _record_decision(cls, action_id: str, decision: AuthDecision, resource_type: str) -> None:
        cls._observe_decision(
            decision,
            action_id=action_id,
            resource_type=resource_type,
            api=metrics.AUTH_API_IS_ALLOWED,
        )

        error_results = tuple(result for result in decision.provider_results if result.status is AuthStatus.ERROR)
        if not error_results:
            return
        logger.warning(
            "[IAM Decision] mode=%s action=%s allowed=%s degraded=%s hit=%s errors=%s",
            decision.mode,
            action_id,
            decision.allowed,
            decision.degraded,
            decision.hit_provider_names,
            tuple((result.provider_name, result.error_type, result.reason) for result in error_results),
        )

    @classmethod
    def _record_batch_decision(cls, decision: BatchAuthDecision, request: EngineBatchAuthRequest) -> None:
        # BatchAuthRequest 已保证每个 resource_group 非空，与单点路径共用同一套 label 归一。
        resource_types = {
            str(resource_group[0].id): cls._resource_type_label(resource_group)
            for resource_group in request.resource_groups
        }
        for item in decision.items:
            cls._observe_decision(
                item.decision,
                action_id=item.action_id,
                resource_type=resource_types.get(item.resource_id, metrics.RESOURCE_TYPE_NONE),
                api=metrics.AUTH_API_BATCH_IS_ALLOWED,
            )

        error_results = tuple(
            result
            for item in decision.items
            for result in item.decision.provider_results
            if result.status is AuthStatus.ERROR
        )
        if not error_results:
            return
        errors = tuple(
            dict.fromkeys((result.provider_name, result.error_type, result.reason) for result in error_results)
        )
        logger.warning(
            "[IAM Batch Decision] error_result_count=%s errors=%s",
            len(error_results),
            errors,
        )

    # ================================================================
    # Resource 构造 / V3 系统信息（回调与旧接口）
    # ================================================================

    @classmethod
    def make_resource(cls, resource_type: str, instance_id: str) -> Resource:
        """
        构造resource对象
        :param resource_type: 资源类型
        :param instance_id: 实例ID
        """
        resource_meta = get_resource_by_id(resource_type)
        return resource_meta.create_instance(instance_id)

    @classmethod
    def batch_make_resource(cls, resources: list[dict]):
        """
        批量构造resource对象
        """
        return [cls.make_resource(r["type"], r["id"]) for r in resources]

    def get_system_info(self):
        """
        获取权限中心注册的动作列表
        """
        return get_v3_system_info(self.iam_client, settings.BK_IAM_SYSTEM_ID)

    # ================================================================
    # 空间列表 —— GET /meta/spaces/mine/；union 并集，双侧失败才 fail-closed
    # ================================================================

    def filter_space_list_by_action(
        self, action: ActionMeta | str, bk_tenant_id: str = "", space_list: list = None
    ) -> list:
        """
        根据动作过滤用户有权限的业务列表。

        统一走 AuthorizedScopeProvider 契约：Provider 声明 requires_candidate_ids 时
        （V3 需要本地候选做表达式求值）先加载全量 Space，否则先查 IAM 再按 bk_biz_id 定向查库。
        UNION 模式下两侧并发查询后取并集；双侧都失败才 fail-closed。
        """
        try:
            return self._filter_space_list_by_action(action, bk_tenant_id, space_list)
        except IAMDependencyError as error:
            logger.error(
                "[IAM Decision] space scope failed: provider=%s reason=%s",
                error.provider or "unknown",
                error.reason,
            )
            raise

    def _filter_space_list_by_action(
        self, action: ActionMeta | str, bk_tenant_id: str = "", space_list: list = None
    ) -> list:
        from apps.log_search.models import Space

        if settings.IGNORE_IAM_PERMISSION:
            if space_list is not None:
                return space_list
            return Space.get_all_spaces(bk_tenant_id=bk_tenant_id)

        action = get_action_by_id(action)
        try:
            mode = self.mode_router.mode_provider.get_mode()
        except InvalidAuthModeError as error:
            raise IAMDependencyError(error.reason, provider="mode") from error

        scope_providers = self.mode_router.scope_providers_for(mode)

        # 所有 Provider 都能独立给出授权范围且调用方未预加载列表：
        # IAM 先查 → 定向查库，避免先扫全量 Space。
        if space_list is None and not self._requires_candidate_ids(scope_providers):
            return self._filter_spaces_by_scope_targeted(action, bk_tenant_id, mode)

        if space_list is None:
            space_list = Space.get_all_spaces(bk_tenant_id=bk_tenant_id)

        local_ids = {str(space["bk_biz_id"]) for space in space_list}
        scope = self._resolve_authorized_scope(action, mode, candidate_ids=frozenset(local_ids))
        allowed_ids = self._merge_authorized_scope_with_local(scope, local_ids)
        return self._keep_spaces_by_allowed_ids(space_list, allowed_ids)

    def _filter_spaces_by_scope_targeted(self, action: ActionMeta, bk_tenant_id: str, mode: AuthMode) -> list:
        """先查顶层授权范围，再按 bk_biz_id 定向加载本地 Space。"""
        from apps.log_search.models import Space

        scope = self._resolve_authorized_scope(action, mode, candidate_ids=None)
        if not scope.ok:
            raise IAMDependencyError(scope.reason or "IAM authorized-resources failed", provider=scope.provider_name)
        if scope.is_wildcard:
            return Space.get_all_spaces(bk_tenant_id=bk_tenant_id)

        query_ids = set(scope.ids)
        demo_biz_id = self._get_enabled_demo_biz_id()
        if demo_biz_id:
            query_ids.add(demo_biz_id)

        spaces = Space.get_spaces_by_bk_biz_ids(bk_tenant_id, query_ids)
        local_ids = {str(space["bk_biz_id"]) for space in spaces}
        self._log_scope_ids_missing_locally(scope, local_ids)
        return self._keep_spaces_by_allowed_ids(spaces, set(scope.ids))

    @staticmethod
    def _get_enabled_demo_biz_id() -> str:
        """仅正数业务 ID 表示启用了 demo 业务。"""
        try:
            demo_biz_id = int(settings.DEMO_BIZ_ID)
        except (TypeError, ValueError):
            return ""
        return str(demo_biz_id) if demo_biz_id > 0 else ""

    @classmethod
    def _keep_spaces_by_allowed_ids(cls, space_list: list, allowed_ids: set[str]) -> list:
        results = []
        demo_biz_id = cls._get_enabled_demo_biz_id()
        for space in space_list:
            biz_id = str(space["bk_biz_id"])
            if biz_id in allowed_ids or (demo_biz_id and demo_biz_id == biz_id):
                results.append(space)
        return results

    @staticmethod
    def _requires_candidate_ids(
        scope_providers: tuple[tuple[str, AuthorizedScopeProvider | None], ...],
    ) -> bool:
        """未配置的 Provider 不需要本地候选：查询阶段会返回错误范围并 fail-closed，没必要先扫全量 Space。"""
        return any(provider is not None and provider.requires_candidate_ids for _, provider in scope_providers)

    def _resolve_authorized_scope(
        self,
        action: ActionMeta,
        mode: AuthMode,
        *,
        candidate_ids: frozenset[str] | None,
    ) -> AuthorizedResourceScope:
        resolution = self.mode_router.list_authorized_scope(
            mode,
            action_id=action.id,
            resource_type=ResourceEnum.BUSINESS.id,
            subject={"type": "user", "id": self.username},
            candidate_ids=candidate_ids,
        )
        # 与 _union_divergence_patterns 对齐：单栈没有可比对的另一侧，不能打 union 分歧。
        if len(resolution.provider_scopes) < 2:
            return resolution.scope
        failed = [scope for scope in resolution.provider_scopes if not scope.ok]
        if failed:
            self._observe_scope_divergence(action.id, failed, total=len(resolution.provider_scopes))
        if failed and len(failed) < len(resolution.provider_scopes):
            logger.warning(
                "[IAM Decision] union space scope degraded: %s",
                "; ".join(f"{scope.provider_name or 'unknown'}_error={scope.reason}" for scope in failed),
            )
        return resolution.scope

    @staticmethod
    def _observe_scope_divergence(action_id: str, failed: list[AuthorizedResourceScope], *, total: int) -> None:
        """授权范围查询的单侧降级与双侧失败，pattern 口径与鉴权决策保持一致。"""
        patterns = (
            ("both_error",)
            if len(failed) == total
            else tuple(f"{scope.provider_name or 'unknown'}_error" for scope in failed)
        )
        for pattern in patterns:
            metrics.IAM_UNION_DIVERGENCE_COUNT.labels(
                action_id=action_id,
                api=metrics.AUTH_API_SPACE_SCOPE,
                pattern=pattern,
            ).inc()

    @staticmethod
    def _merge_authorized_scope_with_local(scope: AuthorizedResourceScope, local_ids: set[str]) -> set[str]:
        if not scope.ok:
            raise IAMDependencyError(scope.reason or "IAM authorized-resources failed", provider=scope.provider_name)
        if scope.is_wildcard:
            return set(local_ids)

        allowed_ids = {resource_id for resource_id in scope.ids if resource_id in local_ids}
        Permission._log_scope_ids_missing_locally(scope, local_ids)
        return allowed_ids

    @staticmethod
    def _log_scope_ids_missing_locally(scope: AuthorizedResourceScope, local_ids: set[str]) -> None:
        """记录 IAM 已授权但本地 Space 表没有的 ID。

        IAM 的授权范围覆盖平台上所有业务，本地 Space 表只有接入日志平台的空间，两者对不上是常态，
        按请求打 WARNING 只会淹没真实告警，所以降到 DEBUG，排查具体用户时再开。
        """
        missing_ids = sorted(resource_id for resource_id in scope.ids if resource_id not in local_ids)
        if not missing_ids:
            return
        logger.debug(
            "[IAM Space Scope] authorized ids missing in local Space cache: type=%s missing=%s",
            scope.resource_type,
            missing_ids[:20],
        )

    # ================================================================
    # 创建者授权 —— 双写；current 同步失败才回落 Celery
    # ================================================================

    def grant_creator_action(self, resource: Resource, creator: str = None, raise_exception=False):
        """
        新建实例关联权限授权
        :param resource: 资源实例
        :param creator: 资源创建者
        :param raise_exception: 是否抛出异常
        :return:
        """
        application = {
            "system": resource.system,
            "type": resource.type,
            "id": resource.id,
            "name": resource.attribute.get("name", resource.id) if resource.attribute else resource.id,
            "creator": creator or self.username,
        }

        # 任务模块会加载 Celery app，延迟到实际授权入口再导入，避免和权限模块相互引用。
        from apps.iam.tasks.grant import dispatch_v4_creator_grant

        stack = self.mode_router.stack
        retry_target = stack.current
        if retry_target is not AuthMode.V4:
            raise NotImplementedError(f"retry dispatcher is still V4-only, got {retry_target.value}")

        orchestrator = DualWriteGrantOrchestrator(
            writers=MigrationPolicy.resolve_authorization_writers(self.provider_bundles, stack=stack),
            tenant_id=self.bk_tenant_id,
            operator=self.username,
            dispatch_retry_grant=dispatch_v4_creator_grant,
            retry_target=retry_target.value,
            grant_observer=self._observe_grant,
        )
        return orchestrator.grant_creator_action(application, raise_exception=raise_exception)

    @staticmethod
    def _observe_grant(target_version: str, resource_type: str, result: str) -> None:
        """双写编排层的观测出口。

        指标注册在 bklog 侧，由这里注入而不是让 iam_engine 直接依赖 apps.iam.metrics。
        """
        metrics.IAM_GRANT_SYNC_COUNT.labels(
            target_version=target_version,
            resource_type=resource_type,
            result=result,
        ).inc()

    def grant_creator_action_batch(self, resource: Resource, creators: list = None, raise_exception=False):
        """
        为多个用户新建实例关联权限授权
        :param resource: 资源实例
        :param creators: 资源创建者列表
        :param raise_exception: 是否抛出异常
        :return: {creator: grant_result}
        """
        # 权限中心单次授权仅接受一个 creator，去重后逐个授权
        unique_creators = list(dict.fromkeys(creator for creator in (creators or []) if creator))

        return {
            creator: self.grant_creator_action(resource=resource, creator=creator, raise_exception=raise_exception)
            for creator in unique_creators
        }
