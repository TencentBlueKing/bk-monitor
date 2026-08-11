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
# 改造说明 (2026-08, Step 3):
#   鉴权核心已委托给 IAMFramework（is_allowed / batch_is_allowed / get_apply_url）。
#   Permission 保留：Django 身份解析、token 分享检查、skip_check 绕过、
#   SaaS 空间全家桶、Grafana/Kernel API 兼容路径。
#
#   仍保留的旧依赖方法（等框架能力补齐后迁移）：
#     - grant_creator_action  → 已委托框架 _fw.grant_creator_action()
#     - filter_space_list_by_action → 需框架 query_policy 能力
#     - make_request → Grafana 穿透（收口后删）
#     - get_iam_client → Grafana/Kernel API 穿透
#     - make_resource / batch_make_resource → 等 resource.py 改造
# ---------------------------------------------------------------------------

from __future__ import annotations

import logging
from collections import defaultdict

from django.conf import settings
from iam import Action, ObjectSet, make_expression
from iam.eval.expression import OP
from iam.exceptions import AuthAPIError

from bkm_space.api import SpaceApi
from bkm_space.utils import bk_biz_id_to_space_uid, is_bk_saas_space
from bkmonitor.iam import ResourceEnum
from bkmonitor.iam.action import MINI_ACTION_IDS, ActionEnum, get_action_by_id
from bkmonitor.iam.compatible import CompatibleIAM
from bkmonitor.iam.definitions.codec_v3 import MonitorV3Codec
from bkmonitor.iam.iam_engine.core.exceptions import PermissionDenied
from bkmonitor.iam.iam_engine.core.types import (
    ApplyURLRequest,
    AuthRequest,
    BatchByResourceRequest,
    ResourceInstance as FwResource,
    Subject as FwSubject,
    SubjectType,
    to_action_id,
)
from bkmonitor.iam.iam_engine.django.facade import get_framework
from bkmonitor.iam.resource import Business as BusinessResource
from bkmonitor.iam.resource import get_resource_by_id
from bkmonitor.models import ApiAuthToken
from bkmonitor.utils.request import get_request
from constants.common import DEFAULT_TENANT_ID
from core.errors.iam import ActionNotExistError, PermissionDeniedError
from core.errors.share import TokenValidatedError

logger = logging.getLogger(__name__)

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


class Permission:
    """
    权限中心鉴权封装 — IAMFramework 适配层。
    """

    _codec = MonitorV3Codec()

    def __init__(self, username: str = "", bk_tenant_id: str = "", request=None):
        if username and bk_tenant_id:
            # 指定用户
            self.username = username
            self.bk_tenant_id = bk_tenant_id
        else:
            request = request or get_request(peaceful=True)
            # web请求
            if request:
                self.username = request.user.username
                self.bk_tenant_id = request.user.tenant_id
            else:
                logger.warning("IAM Permission init with local username, use default bk_tenant_id")
                # 后台设置
                from bkmonitor.utils.user import get_local_username

                self.username = get_local_username()
                if self.username is None:
                    raise ValueError("must provide `username` or `request` param to init")
                self.bk_tenant_id = DEFAULT_TENANT_ID

        # 旧 CompatibleIAM（Grafana/Kernel API 穿透 + filter_space_list_by_action）
        self.iam_client = self.get_iam_client(self.bk_tenant_id)
        self.request = request

        # 新框架引用
        self._fw = get_framework()

        self.skip_check = getattr(settings, "SKIP_IAM_PERMISSION_CHECK", False)
        if request and hasattr(request, "skip_check"):
            logger.info(f"Permission: request.skip_check: {request.skip_check}")
            self.skip_check = request.skip_check

    # ================================================================
    # 身份 + CompatibleIAM 客户端（Grafana/Kernel API 穿透用）
    # ================================================================

    @classmethod
    def get_iam_client(cls, bk_tenant_id: str):
        app_code, secret_key = settings.APP_CODE, settings.SECRET_KEY
        if settings.ROLE in ["api", "worker"]:
            # 后台api模式下使用SaaS身份
            app_code, secret_key = settings.SAAS_APP_CODE, settings.SAAS_SECRET_KEY

        return CompatibleIAM(app_code, secret_key, settings.BK_IAM_APIGATEWAY_URL, bk_tenant_id=bk_tenant_id)

    # ================================================================
    # 鉴权 — 框架委托
    # ================================================================

    def is_allowed(self, action, resources: list = None, raise_exception: bool = False):
        """
        校验用户是否有动作的权限（委托 IAMFramework）。
        """
        # token 临时分享权限豁免
        if self.request and getattr(self.request, "token", None):
            try:
                record = ApiAuthToken.objects.get(token=self.request.token, bk_tenant_id=self.request.user.tenant_id)
            except ApiAuthToken.DoesNotExist:
                record = None

            action_id = action.id if hasattr(action, "id") else action
            if (
                action_id == ActionEnum.VIEW_BUSINESS.id
                or (record and action in ActionIdMap[record.type])
                or path in self.request.path
                for path in api_paths
            ):
                return True

        if self.skip_check:
            return True

        resources = resources or []

        action_id_biz = to_action_id(action)

        # 构建框架 resource
        fw_resource = None
        if resources:
            fw_resource = FwResource(type=resources[0].type, id=resources[0].id)

        try:
            result = self._fw.is_allowed(
                AuthRequest(
                    subject=FwSubject(id=self.username, type=SubjectType.USER),
                    action_id=action_id_biz,
                    resource=fw_resource,
                )
            )
        except PermissionDenied as e:
            if raise_exception:
                actions, detail_resources = self.prepare_apply_for_saas(resources)
                if not actions:
                    detail_resources = [get_resource_by_id(r.type).create_instance(r.id) for r in resources]
                    try:
                        actions = [get_action_by_id(action_id_biz)]
                    except ActionNotExistError:
                        actions = []
                apply_data, apply_url = self.get_apply_data(
                    [a.id for a in actions] if actions else [action_id_biz],
                    detail_resources,
                )
                raise PermissionDeniedError(
                    context={"action_name": action_id_biz},
                    data={"apply_url": apply_url},
                    extra={"permission": apply_data},
                ) from e
            return False

        if not result and raise_exception:
            actions, detail_resources = self.prepare_apply_for_saas(resources)
            if not actions:
                detail_resources = [get_resource_by_id(r.type).create_instance(r.id) for r in resources]
                try:
                    actions = [get_action_by_id(action_id_biz)]
                except ActionNotExistError:
                    actions = []
            apply_data, apply_url = self.get_apply_data(
                [a.id for a in actions] if actions else [action_id_biz],
                detail_resources,
            )
            raise PermissionDeniedError(
                context={"action_name": action_id_biz},
                data={"apply_url": apply_url},
                extra={"permission": apply_data},
            )

        return result

    def is_allowed_by_biz(self, bk_biz_id: int, action, raise_exception: bool = False):
        """
        判断用户对当前动作在该业务下是否有权限（委托 IAMFramework）。
        """
        if self.skip_check:
            return True

        resources = [ResourceEnum.BUSINESS.create_simple_instance(bk_biz_id)]
        return self.is_allowed(action, resources, raise_exception)

    def batch_is_allowed(self, actions: list, resources: list[list]):
        """
        查询某批资源某批操作是否有权限（委托 IAMFramework）。
        """
        result = defaultdict(dict)
        # token 临时分享权限豁免
        if self.request and getattr(self.request, "token", None):
            try:
                record = ApiAuthToken.objects.get(token=self.request.token, bk_tenant_id=self.request.user.tenant_id)
            except ApiAuthToken.DoesNotExist:
                raise TokenValidatedError
            for action in actions:
                for resource in resources:
                    resource_id = resource[0].id
                    action_id = action.id if hasattr(action, "id") else action
                    if action_id == "view_business" or (record and action in ActionIdMap[record.type]):
                        result[resource_id][action_id] = True
                    else:
                        result[resource_id][action_id] = False
            return result

        if self.skip_check:
            for action in actions:
                for resource in resources:
                    resource_id = resource[0].id
                    action_id = action.id if hasattr(action, "id") else action
                    result[resource_id][action_id] = True
            return result

        action_ids_biz = [to_action_id(a) for a in actions]

        # 构建批量请求：每种资源列表一个请求
        for resource_list in resources:
            resource_id = resource_list[0].id
            rtype = resource_list[0].type

            for action_id_biz in action_ids_biz:
                batch_result = self._fw.batch_by_resource(
                    BatchByResourceRequest(
                        subject=FwSubject(id=self.username, type=SubjectType.USER),
                        action_id=action_id_biz,
                        resources=(FwResource(type=rtype, id=resource_id),),
                    )
                )
                for item in batch_result.items:
                    result[item.resource_id][action_id_biz] = item.allowed

        return result

    # ================================================================
    # 申请 URL / 申请数据 — 框架委托
    # ================================================================

    def get_apply_url(self, action_ids: list[str], resources: list = None, system_id: str = settings.BK_IAM_SYSTEM_ID):
        action_ids_biz = [to_action_id(a) for a in action_ids]
        fw_resources = tuple(FwResource(type=r.type, id=r.id) for r in (resources or []))
        return self._fw.get_apply_url(
            ApplyURLRequest(
                subject=FwSubject(id=self.username, type=SubjectType.USER),
                action_ids=tuple(action_ids_biz),
                resources=fw_resources,
            )
        )

    def get_apply_data(self, actions, resources: list = None):
        resources = resources or []

        action_ids_biz = [to_action_id(a) for a in actions]
        fw_resources = [FwResource(type=r.type, id=r.id) for r in resources]

        return self._fw.get_apply_data(
            action_ids_biz,
            fw_resources,
            FwSubject(id=self.username, type=SubjectType.USER),
        ), self.get_apply_url(action_ids_biz, resources)

    # ================================================================
    # 创建者授权 — 框架委托
    # ================================================================

    def grant_creator_action(self, resource, creator: str = None, raise_exception=False):
        """
        新建实例关联权限授权（委托 IAMFramework）。
        """
        grant_result = None
        try:
            self._fw.grant_creator_action(
                resource_type=resource.type,
                resource_id=resource.id,
                creator=creator or self.username,
            )
            logger.info(f"[grant_creator_action] Success! resource: {resource.to_dict()}")
        except Exception as e:  # pylint: disable=broad-except
            logger.exception(f"[grant_creator_action] Failed! resource: {resource.to_dict()}, result: {e}")
            if raise_exception:
                raise e

        return grant_result

    # ================================================================
    # SaaS 空间全家桶 — V3 业务逻辑，框架无关
    # ================================================================

    def prepare_apply_for_saas(self, resources):
        if not resources or (resources[0].system, resources[0].type) != (
            BusinessResource.system_id,
            BusinessResource.id,
        ):
            return [], []
        bk_biz_id = resources[0].id
        space_uid = bk_biz_id_to_space_uid(bk_biz_id)
        if not is_bk_saas_space(space_uid):
            return [], []
        actions = [get_action_by_id(a_id) for a_id in MINI_ACTION_IDS]
        return actions, [BusinessResource.create_instance(bk_biz_id)]

    # ================================================================
    # 空间列表过滤 — 保留旧 CompatibleIAM 路径（框架 query_policy 未实现）
    # ================================================================

    def filter_space_list_by_action(self, action, using_cache=True) -> list[dict]:
        space_list = SpaceApi.list_spaces_dict(bk_tenant_id=self.bk_tenant_id, using_cache=using_cache)
        if self.skip_check:
            return space_list

        action_id_biz = to_action_id(action)
        v3_action_id = self._codec.encode_action(action_id_biz)
        from iam import Request, Subject

        request = Request(
            system=settings.BK_IAM_SYSTEM_ID,
            subject=Subject("user", self.username),
            action=Action(id=v3_action_id),
            resources=[],
            environment=None,
        )

        try:
            policies = self.iam_client._do_policy_query(request)
        except AuthAPIError as e:
            logger.exception("[IAM AuthAPI Error]: %s", e)
            return []

        if not policies:
            return []

        op = policies["op"]
        if op == OP.ANY:
            return space_list
        elif op == OP.IN:
            value = policies["value"]
            return list(filter(lambda x: str(x["bk_biz_id"]) in value, space_list))

        expr = make_expression(policies)

        results = []
        for space in space_list:
            obj_set = ObjectSet()
            obj_set.add_object(ResourceEnum.BUSINESS.id, {"id": str(space["bk_biz_id"])})

            if self.iam_client._eval_expr(expr, obj_set):
                results.append(space)

        return results

    # ================================================================
    # Resource 构造 — 保留（monitor_web/iam/ 回调使用，等 resource.py 改造）
    # ================================================================

    @classmethod
    def make_resource(cls, resource_type: str, instance_id: str):
        resource_meta = get_resource_by_id(resource_type)
        return resource_meta.create_instance(instance_id)

    @classmethod
    def batch_make_resource(cls, resources: list[dict]):
        return [cls.make_resource(r["type"], r["id"]) for r in resources]

    # ================================================================
    # Grafana 穿透兼容 — 保留（收口后删除）
    # ================================================================

    def make_request(self, action, resources: list = None):
        """构造 IAM SDK Request（仅 Grafana permissions.py 使用）。

        Grafana 通过 Permission().iam_client._do_policy_query(make_request(...))
        直接查询策略表达式。收口到框架后，此方法可删除。
        """
        action_id_biz = to_action_id(action)
        v3_action_id = self._codec.encode_action(action_id_biz)
        from iam import Request, Subject

        return Request(
            system=settings.BK_IAM_SYSTEM_ID,
            subject=Subject("user", self.username),
            action=Action(id=v3_action_id),
            resources=resources or [],
            environment=None,
        )

    # ================================================================
    # list_actions — 已弃用
    # ================================================================

    def list_actions(self):
        """[DEPRECATED] 获取权限中心注册的动作列表。

        调用方 GetAuthorityMetaResource 未注册到 URL，此方法无实际调用。
        如需列出 actions，请使用 IAMFramework。
        """
        raise NotImplementedError("list_actions is deprecated. Use IAMFramework to query actions from schema.")
