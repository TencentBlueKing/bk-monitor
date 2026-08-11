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

from django.conf import settings
from django.utils.translation import gettext as _
from iam import (
    MultiActionRequest,
    ObjectSet,
    Request,
    Resource,
    Subject,
    make_expression,
)
from iam.apply.models import (
    ActionWithoutResources,
    ActionWithResources,
    Application,
    RelatedResourceType,
    ResourceInstance,
    ResourceNode,
)
from iam.exceptions import AuthAPIError
from iam.meta import setup_action, setup_resource, setup_system

from apps.iam.backends.legacy_v3 import LegacyV3Adapter, LegacyV3AuthorizationWriter
from apps.iam.backends.v4 import V4AuthorizationWriter, V4PermissionProvider
from apps.iam.backends.v4.concurrency import run_pair_concurrently
from apps.iam.exceptions import (
    ActionNotExistError,
    GetSystemInfoError,
    IAMDependencyError,
    PermissionDeniedError,
)
from apps.iam.handlers.actions import ActionMeta, _all_actions, get_action_by_id
from apps.iam.handlers.compatible import CompatibleIAM, V4CallbackIAM
from apps.iam.handlers.resources import Business as BusinessResource
from apps.iam.handlers.resources import ResourceEnum, _all_resources, get_resource_by_id
from apps.iam.iam_engine.core.config import AuthMode
from apps.iam.iam_engine.core.exceptions import InvalidAuthModeError
from apps.iam.iam_engine.core.requests import (
    AuthRequest as EngineAuthRequest,
    BatchAuthRequest as EngineBatchAuthRequest,
    ResourceInstance as EngineResourceInstance,
    Subject as EngineSubject,
)
from apps.iam.iam_engine.core.types import AuthDecision, AuthStatus, AuthorizedResourceScope, BatchAuthDecision
from apps.iam.iam_engine.migration.policy import (
    ApplicationResolution,
    BoundPermissionApplicationAdapter,
    MigrationPolicy,
)
from apps.iam.iam_engine.provider.bundle import ProviderBundle
from apps.iam.iam_engine.provider.capabilities import AuthorizationWriter, PermissionApplicationProvider
from apps.iam.iam_engine.provider.router import ModeRouter
from apps.iam.mode import get_mode_provider
from apps.iam.utils import gen_perms_apply_data
from apps.utils.local import get_request, get_request_username, get_local_username, get_request_tenant_id
from apps.utils.log import logger


class Permission:
    """
    权限中心鉴权封装
    """

    def __init__(self, username: str = "", bk_tenant_id: str = "", request=None):
        if request is None and (not username or not bk_tenant_id):
            try:
                request = get_request(peaceful=True)
            except Exception:  # pylint: disable=broad-except
                request = None

        request_username = getattr(getattr(request, "user", None), "username", "") if request else ""
        self.username = username or request_username or get_local_username() or get_request_username()
        if not self.username:
            raise ValueError("must provide `username` or `request` param to init")

        request_tenant_id = ""
        if request:
            try:
                request_tenant_id = get_request_tenant_id()
            except Exception:  # pylint: disable=broad-except
                request_tenant_id = getattr(getattr(request, "user", None), "tenant_id", "")
        self.bk_tenant_id = bk_tenant_id or request_tenant_id or settings.BK_APP_TENANT_ID
        if not bk_tenant_id and not request_tenant_id:
            logger.warning("IAM Permission init with default bk_tenant_id: %s", self.bk_tenant_id)

        self.iam_client = self.get_iam_client(self.bk_tenant_id)
        # 是否跳过权限中心校验
        # 如果request header 中携带token，通过获取token中的鉴权类型type匹配action
        self.skip_check = getattr(settings, "SKIP_IAM_PERMISSION_CHECK", False)
        if request and getattr(request, "skip_check", False):
            self.skip_check = True

        self._mode_router = None
        self._provider_bundles = None
        self._v4_provider = None
        self._v4_authorization_writer = None

    @classmethod
    def get_iam_client(cls, bk_tenant_id: str):
        return CompatibleIAM(
            settings.APP_CODE, settings.SECRET_KEY, settings.BK_IAM_APIGATEWAY_URL, bk_tenant_id=bk_tenant_id
        )

    @classmethod
    def get_v4_callback_iam_client(cls, bk_tenant_id: str):
        return V4CallbackIAM(
            settings.APP_CODE, settings.SECRET_KEY, settings.BK_IAM_APIGATEWAY_URL, bk_tenant_id=bk_tenant_id
        )

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
            )
        return self._mode_router

    def _build_provider_bundles(self) -> dict[AuthMode, ProviderBundle]:
        return {
            AuthMode.V3: ProviderBundle(
                auth=LegacyV3Adapter(self.iam_client, settings.BK_IAM_SYSTEM_ID),
                application=BoundPermissionApplicationAdapter(self._get_v3_apply_data),
                writer=LegacyV3AuthorizationWriter(self.iam_client),
            ),
            AuthMode.V4: ProviderBundle(
                auth=self.get_v4_provider(),
                application=self.get_v4_permission_application_provider(),
                writer=self.get_v4_authorization_writer(),
            ),
        }

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
        if self._v4_authorization_writer is None:
            self._v4_authorization_writer = V4AuthorizationWriter.from_settings(
                username=self.username,
                bk_tenant_id=self.bk_tenant_id,
            )
        return self._v4_authorization_writer

    def make_request(self, action: ActionMeta | str, resources: list[Resource] = None) -> Request:
        """
        获取请求对象
        """
        action = get_action_by_id(action)
        resources = resources or []
        request = Request(
            system=settings.BK_IAM_SYSTEM_ID,
            subject=Subject("user", self.username),
            action=action,
            resources=resources,
            environment=None,
        )
        return request

    def make_multi_action_request(
        self, actions: list[ActionMeta | str], resources: list[Resource] = None
    ) -> MultiActionRequest:
        """
        获取多个动作请求对象
        """
        resources = resources or []
        actions = [get_action_by_id(action) for action in actions]
        request = MultiActionRequest(
            system=settings.BK_IAM_SYSTEM_ID,
            subject=Subject("user", self.username),
            actions=actions,
            resources=resources,
            environment=None,
        )
        return request

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

    def _make_application(
        self, action_ids: list[str], resources: list[Resource] = None, system_id: str = settings.BK_IAM_SYSTEM_ID
    ) -> Application:
        resources = resources or []
        actions = []

        for action_id in action_ids:
            # 对于没有关联资源的动作，则不传资源
            related_resources_types = []
            try:
                action = get_action_by_id(action_id)
                action_id = action.id
                related_resources_types = action.related_resource_types
            except ActionNotExistError:
                pass

            if not related_resources_types:
                actions.append(ActionWithoutResources(action_id))
            else:
                related_resources = []
                for related_resource in related_resources_types:
                    instances = []
                    for r in resources:
                        if r.system == related_resource.system_id and r.type == related_resource.id:
                            instances.append(
                                ResourceInstance(
                                    [ResourceNode(type=r.type, id=r.id, name=r.attribute.get("name", r.id))]
                                )
                            )

                    related_resources.append(
                        RelatedResourceType(
                            system_id=related_resource.system_id,
                            type=related_resource.id,
                            instances=instances,
                        )
                    )

                actions.append(ActionWithResources(action_id, related_resources))

        application = Application(system_id, actions=actions)
        return application

    def get_apply_url(
        self, action_ids: list[str], resources: list[Resource] = None, system_id: str = settings.BK_IAM_SYSTEM_ID
    ):
        """
        处理无权限 - 跳转申请列表
        """
        application = self._make_application(action_ids, resources, system_id)
        ok, message, url = self.iam_client.get_apply_url(application)
        if not ok:
            logger.error(f"iam generate apply url fail: {message}")
            return settings.BK_IAM_SAAS_HOST
        url = f"{url}&tab_key=independent" if "?" in url else f"{url}?tab_key=independent"
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
        application = MigrationPolicy.resolve_application(resolved_mode, self.provider_bundles)
        try:
            return self._call_application_provider(application, actions, resources)
        except Exception as error:  # pylint: disable=broad-except
            if application.source_mode is not AuthMode.V4:
                raise

            if resolved_mode is AuthMode.UNION:
                logger.warning(
                    "[IAM Apply] mode=%s v4 provider failed, fallback to v3: %s",
                    resolved_mode.value,
                    error,
                )
                v3_application = MigrationPolicy.resolve_application(AuthMode.V3, self.provider_bundles)
                return self._call_application_provider(v3_application, actions, resources)

            # 纯 V4 模式最终会不再保留 V3，这里不做“回退 V3”的迁移期兼容，
            # 只记录错误并返回退化的申请数据，保证鉴权拒绝流程不会因为申请数据生成失败而变成 500。
            logger.error(
                "[IAM Apply] mode=%s v4 apply data generation failed: %s",
                resolved_mode.value,
                error,
            )
            return {}, settings.BK_IAM_SAAS_HOST

    def _call_application_provider(
        self,
        application: ApplicationResolution,
        actions: list[ActionMeta | str],
        resources: list[Resource],
    ):
        if application.source_mode is AuthMode.V4:
            actions = [get_action_by_id(action) for action in actions]
            resources = [self._to_engine_resource(resource) for resource in resources]
        return application.provider.get_apply_data(actions, resources)

    def _resolve_safe_apply_mode(self, resources: list[Resource], mode: AuthMode | str | None) -> AuthMode:
        """统一"显式传入模式"与"自动读取模式"两条入口，任何非法值都安全回退 V3。

        调用方既可能显式传入 mode（例如 is_allowed 把 decision.mode 原样传回，可能是非法字符串），
        也可能不传 mode 走 FeatureToggle 自动解析（可能因配置非法抛出 InvalidAuthModeError）。
        这里统一兜底，避免任何一条路径把异常/非法值泄漏给直接调用 get_apply_data 的业务代码。
        """
        if mode is not None:
            resolved_mode = AuthMode.safe_coerce(mode)
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
                AuthMode.V3.value,
            )
            return AuthMode.V3

    def _resolve_auth_mode(self, resources: list[Resource]) -> AuthMode:
        engine_resources = tuple(self._to_engine_resource(resource) for resource in resources)
        return self.mode_router.mode_provider.get_mode(engine_resources)

    def _get_v3_apply_data(self, actions: list[ActionMeta | str], resources: list[Resource]):
        # # 获取关联的动作，如果没有权限就一同显示
        # related_actions = fetch_related_actions(actions)
        #
        # if related_actions:
        #     request = self.make_multi_action_request(list(related_actions.values()), resources)
        #     related_actions_result = self.iam_client.resource_multi_actions_allowed(request)
        #
        #     for action_id, is_allowed in related_actions_result.items():
        #         if not is_allowed and action_id in related_actions:
        #             actions.append(related_actions[action_id])

        action_to_resources_list = []
        for action in actions:
            action = get_action_by_id(action)

            if not action.related_resource_types:
                # 如果没有关联资源，则直接置空
                resources = []

            action_to_resources_list.append({"action": action, "resources_list": [resources]})

        self.setup_meta()

        data = gen_perms_apply_data(
            system=settings.BK_IAM_SYSTEM_ID,
            subject=Subject("user", self.username),
            action_to_resources_list=action_to_resources_list,
        )

        url = self.get_apply_url(actions, resources)
        return data, url

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
        self._record_decision(action.id, decision)
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
        self._record_batch_decision(decision)
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
    def _record_decision(action_id: str, decision: AuthDecision) -> None:
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

    @staticmethod
    def _record_batch_decision(decision: BatchAuthDecision) -> None:
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
        ok, message, data = self.iam_client._client.query(settings.BK_IAM_SYSTEM_ID)
        if not ok:
            raise GetSystemInfoError(_("获取系统信息错误：{message}").format(message))
        return data

    # IAM v1 策略在 CompatibleIAM 中已经转换为 space.id；这里只优化转换后的稳定形态。
    _FLATTENABLE_FIELD = "space.id"
    _FLATTENABLE_ANY_FIELDS = frozenset({_FLATTENABLE_FIELD, ""})

    @classmethod
    def _try_flatten_space_policy(cls, policies: dict) -> dict | None:
        """
        将仅包含 any、space.id eq/in 和 OR 的策略树转换为全量标记或 ID 集合。

        为保证与 IAM SDK 的类型比较语义一致，策略值必须已经是字符串；
        任一节点格式或算子不满足约束时，返回 None 交给原始表达式求值逻辑。

        返回：
          {"mode": "any"}                   -> 策略恒真，全放行
          {"mode": "flat", "allowed": set} -> 已抽取 biz_id 白名单
          None                              -> 无法平坦化，走兜底
        """

        def analyze(node):
            if not isinstance(node, dict):
                return None

            op = node.get("op")
            if op == "any":
                # IAM 的全量策略可能使用 space.id 或空 field；
                # 其他字段交回 SDK，避免改变异常和权限语义。
                if node.get("field") not in cls._FLATTENABLE_ANY_FIELDS or "value" not in node:
                    return None
                return {"mode": "any"}

            if op == "eq":
                value = node.get("value")
                if node.get("field") != cls._FLATTENABLE_FIELD or not isinstance(value, str):
                    return None
                return {"mode": "flat", "allowed": {value}}

            if op == "in":
                value = node.get("value")
                if (
                    node.get("field") != cls._FLATTENABLE_FIELD
                    or not isinstance(value, list | tuple)
                    or not all(isinstance(item, str) for item in value)
                ):
                    return None
                return {"mode": "flat", "allowed": set(value)}

            if op != "OR":
                return None

            content = node.get("content")
            if not isinstance(content, list | tuple):
                return None

            allowed = set()
            for child in content:
                result = analyze(child)
                if result is None:
                    return None
                if result["mode"] == "any":
                    return {"mode": "any"}
                allowed.update(result["allowed"])

            return {"mode": "flat", "allowed": allowed}

        return analyze(policies)

    def filter_space_list_by_action(
        self, action: ActionMeta | str, bk_tenant_id: str = "", space_list: list = None
    ) -> list:
        """
        根据动作过滤用户有权限的业务列表。

        V3：policy_query + 本地表达式求值。
        V4：未传入 space_list 时先 list_authorized_resource，再按 bk_biz_id 定向查库；
            传入 space_list 时与本地列表求交（兼容测试/内部调用）。
        UNION：两侧明确允许的空间取并集；双侧 Error 且无明确允许时 fail-closed。
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

        # 纯 V4 且调用方未预加载列表：IAM 先查 → 定向查库，避免先扫全量 Space。
        if mode is AuthMode.V4 and space_list is None:
            return self._filter_spaces_v4_targeted(action, bk_tenant_id)

        if space_list is None:
            space_list = Space.get_all_spaces(bk_tenant_id=bk_tenant_id)

        local_ids = {str(space["bk_biz_id"]) for space in space_list}
        if mode is AuthMode.V3:
            allowed_ids = self._authorized_space_ids_v3(action, local_ids)
        elif mode is AuthMode.V4:
            allowed_ids = self._authorized_space_ids_v4(action, local_ids)
        else:
            allowed_ids = self._authorized_space_ids_union(action, local_ids)

        return self._keep_spaces_by_allowed_ids(space_list, allowed_ids)

    def _filter_spaces_v4_targeted(self, action: ActionMeta, bk_tenant_id: str) -> list:
        """纯 V4：先查顶层授权范围，再按 bk_biz_id 定向加载本地 Space。"""
        from apps.log_search.models import Space

        scope = self._list_authorized_space_scope(action)
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
        missing_ids = sorted(resource_id for resource_id in scope.ids if resource_id not in local_ids)
        if missing_ids:
            logger.warning(
                "[IAM Space Scope] authorized ids missing in local Space cache: type=%s missing=%s",
                scope.resource_type,
                missing_ids[:20],
            )
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

    def _authorized_space_ids_v3(self, action: ActionMeta, local_ids: set[str]) -> set[str]:
        request = self.make_request(action=action)
        try:
            policies = self.iam_client._do_policy_query(request)
        except AuthAPIError as error:
            raise IAMDependencyError(str(error) or "IAM V3 policy query failed", provider="v3") from error

        if not policies:
            return set()

        # 平坦化快路径：只优化可证明等价的策略树，其他形态回退 IAM SDK。
        flat = self._try_flatten_space_policy(policies)
        if flat is not None and flat["mode"] == "any":
            return set(local_ids)

        if flat is not None and flat["mode"] == "flat":
            return {biz_id for biz_id in local_ids if biz_id in flat["allowed"]}

        # SDK 支持但无法安全平坦化的算子和树结构继续走原始求值逻辑。
        expr = make_expression(policies)
        allowed_ids = set()
        for biz_id in local_ids:
            obj_set = ObjectSet()
            obj_set.add_object(_type=ResourceEnum.BUSINESS.id, obj={"id": biz_id})
            if self.iam_client._eval_expr(expr, obj_set):
                allowed_ids.add(biz_id)
        return allowed_ids

    def _list_authorized_space_scope(self, action: ActionMeta) -> AuthorizedResourceScope:
        return self.get_v4_provider().list_authorized_resources(
            action_id=action.id,
            resource_type=ResourceEnum.BUSINESS.id,
            subject={"type": "user", "id": self.username},
        )

    def _authorized_space_ids_v4(self, action: ActionMeta, local_ids: set[str]) -> set[str]:
        scope = self._list_authorized_space_scope(action)
        return self._merge_authorized_scope_with_local(scope, local_ids)

    def _authorized_space_ids_union(self, action: ActionMeta, local_ids: set[str]) -> set[str]:
        def _safe_v3() -> tuple[set[str], IAMDependencyError | None]:
            try:
                return self._authorized_space_ids_v3(action, local_ids), None
            except IAMDependencyError as error:
                return set(), error

        def _safe_v4() -> tuple[set[str], IAMDependencyError | None]:
            try:
                return self._authorized_space_ids_v4(action, local_ids), None
            except IAMDependencyError as error:
                return set(), error

        (v3_ids, v3_error), (v4_ids, v4_error) = run_pair_concurrently(_safe_v3, _safe_v4)

        if v3_error and v4_error:
            raise IAMDependencyError(
                f"v3={v3_error.reason}; v4={v4_error.reason}",
                provider="union",
            )

        if v3_error or v4_error:
            logger.warning(
                "[IAM Decision] union space scope degraded: v3_error=%s v4_error=%s",
                getattr(v3_error, "reason", None),
                getattr(v4_error, "reason", None),
            )

        return v3_ids | v4_ids

    @staticmethod
    def _merge_authorized_scope_with_local(scope: AuthorizedResourceScope, local_ids: set[str]) -> set[str]:
        if not scope.ok:
            raise IAMDependencyError(scope.reason or "IAM authorized-resources failed", provider=scope.provider_name)
        if scope.is_wildcard:
            return set(local_ids)

        allowed_ids = {resource_id for resource_id in scope.ids if resource_id in local_ids}
        missing_ids = sorted(resource_id for resource_id in scope.ids if resource_id not in local_ids)
        if missing_ids:
            logger.warning(
                "[IAM Space Scope] authorized ids missing in local Space cache: type=%s missing=%s",
                scope.resource_type,
                missing_ids[:20],
            )
        return allowed_ids

    @classmethod
    def setup_meta(cls):
        """
        初始化权限中心实体
        """
        if getattr(cls, "__setup", False):
            return

        # 系统
        systems = [
            {"system_id": settings.BK_IAM_SYSTEM_ID, "system_name": settings.BK_IAM_SYSTEM_NAME},
            {"system_id": "bk_monitorv3", "system_name": _("监控平台")},
        ]

        for system in systems:
            setup_system(**system)

        # 资源
        for r in _all_resources.values():
            setup_resource(r.system_id, r.id, r.name)

        # 动作
        for action in _all_actions.values():
            setup_action(system_id=settings.BK_IAM_SYSTEM_ID, action_id=action.id, action_name=action.name)

        cls.__setup = True

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

        # apps.iam 在 Django App Registry 就绪前会导入 Permission，Model 编排器必须延迟加载。
        from apps.iam.iam_engine.migration.dual_write import DualWriteGrantOrchestrator

        orchestrator = DualWriteGrantOrchestrator(
            writers=MigrationPolicy.resolve_authorization_writers(self.provider_bundles),
            tenant_id=self.bk_tenant_id,
            operator=self.username,
        )
        return orchestrator.grant_creator_action(application, raise_exception=raise_exception)
