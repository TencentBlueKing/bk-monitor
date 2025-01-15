# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
from collections import defaultdict
from typing import Dict, List, Union

from django.conf import settings
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
from iam.eval.expression import OP
from iam.exceptions import AuthAPIError
from iam.meta import setup_action, setup_resource, setup_system
from iam.utils import gen_perms_apply_data

from bkm_space.api import SpaceApi
from bkm_space.utils import bk_biz_id_to_space_uid, is_bk_saas_space
from bkmonitor.iam import ResourceEnum
from bkmonitor.iam.action import (
    MINI_ACTION_IDS,
    ActionEnum,
    ActionMeta,
    _all_actions,
    get_action_by_id,
)
from bkmonitor.iam.compatible import CompatibleIAM
from bkmonitor.iam.resource import Business as BusinessResource
from bkmonitor.iam.resource import _all_resources, get_resource_by_id
from bkmonitor.models import ApiAuthToken
from bkmonitor.utils.request import get_request
from core.errors.api import BKAPIError
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
}

api_paths = ["/time_series/unify_query/", "log/query/", "time_series/unify_trace_query/"]


class Permission(object):
    """
    权限中心鉴权封装
    """

    def __init__(self, username: str = "", request=None):
        self.bk_token = ""
        if username:
            # 指定用户
            self.username = username
        else:
            request = request or get_request(peaceful=True)
            # web请求
            if request:
                self.bk_token = request.COOKIES.get("bk_token", "")
                self.username = request.user.username
            else:
                # 后台设置
                from bkmonitor.utils.user import get_local_username

                self.username = get_local_username()
                if self.username is None:
                    raise ValueError("must provide `username` or `request` param to init")

        self.iam_client = self.get_iam_client()
        self.token = getattr(request, "token", None)

        # 是否跳过权限中心校验
        # 如果request header 中携带token，通过获取token中的鉴权类型type匹配action
        self.skip_check = getattr(settings, "SKIP_IAM_PERMISSION_CHECK", False)
        if request and getattr(request, "skip_check", False):
            self.skip_check = True

    @classmethod
    def get_iam_client(cls):
        app_code, secret_key = settings.APP_CODE, settings.SECRET_KEY
        if settings.ROLE in ["api", "worker"]:
            # 后台api模式下使用SaaS身份
            app_code, secret_key = settings.SAAS_APP_CODE, settings.SAAS_SECRET_KEY

        bk_apigateway_url = (
            settings.IAM_API_BASE_URL
            if settings.IAM_API_BASE_URL
            else f"{settings.BK_COMPONENT_API_URL}/api/bk-iam/prod/"
        )
        return CompatibleIAM(app_code, secret_key, settings.BK_IAM_INNER_HOST, None, bk_apigateway_url)

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

        grant_result = None

        try:
            grant_result = self.iam_client.grant_resource_creator_actions(application, self.bk_token, self.username)
            logger.info(f"[grant_creator_action] Success! resource: {resource.to_dict()}, result: {grant_result}")
        except Exception as e:  # pylint: disable=broad-except
            logger.exception(f"[grant_creator_action] Failed! resource: {resource.to_dict()}, result: {e}")
            if raise_exception:
                raise e

        return grant_result

    def make_request(self, action: Union[ActionMeta, str], resources: List[Resource] = None) -> Request:
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
        self, actions: List[Union[ActionMeta, str]], resources: List[Resource] = None
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

    def _make_application(
        self, action_ids: List[str], resources: List[Resource] = None, system_id: str = settings.BK_IAM_SYSTEM_ID
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
                        if r.system == related_resource["system_id"] and r.type == related_resource["id"]:
                            instances.append(
                                ResourceInstance(
                                    [ResourceNode(type=r.type, id=r.id, name=r.attribute.get("name", r.id))]
                                )
                            )

                    related_resources.append(
                        RelatedResourceType(
                            system_id=related_resource["system_id"],
                            type=related_resource["id"],
                            instances=instances,
                        )
                    )

                actions.append(ActionWithResources(action_id, related_resources))

        application = Application(system_id, actions=actions)
        return application

    def get_apply_url(
        self, action_ids: List[str], resources: List[Resource] = None, system_id: str = settings.BK_IAM_SYSTEM_ID
    ):
        """
        处理无权限 - 跳转申请列表
        """
        # 获取每个操作的依赖操作，一并申请
        # related_actions = []
        # for action_id in action_ids:
        #     # 对于没有关联资源的动作，则不传资源
        #     try:
        #         action = get_action_by_id(action_id)
        #     except ActionNotExistError:
        #         continue
        #     related_actions.append(action_id)
        #     related_actions.extend(action.related_actions)
        # application = self._make_application(related_actions, resources, system_id)

        application = self._make_application(action_ids, resources, system_id)
        ok, message, url = self.iam_client.get_apply_url(application, self.bk_token, self.username)
        if not ok:
            logger.error("iam generate apply url fail: %s", message)
            return settings.BK_IAM_SAAS_HOST
        return url

    def get_apply_data(self, actions: List[Union[ActionMeta, str]], resources: List[Resource] = None):
        """
        生成本系统无权限数据
        """

        # # 获取关联的动作，如果没有权限就一同显示
        # related_actions = fetch_related_actions(actions)
        # request = self.make_multi_action_request(list(related_actions.values()), resources)
        # related_actions_result = self.iam_client.resource_multi_actions_allowed(request)
        #
        # for action_id, is_allowed in related_actions_result.items():
        #     if not is_allowed and action_id in related_actions:
        #         actions.append(related_actions[action_id])

        resources = resources or []

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

    def is_allowed(
        self, action: Union[ActionMeta, str], resources: List[Resource] = None, raise_exception: bool = False
    ):
        """
        校验用户是否有动作的权限
        :param action: 动作
        :param resources: 依赖的资源实例列表
        :param raise_exception: 鉴权失败时是否需要抛出异常
        """
        request = get_request(peaceful=True)
        # 如果request header 中携带token，通过获取token中的鉴权类型type匹配action
        if self.token:
            try:
                record = ApiAuthToken.objects.get(token=self.token)
            except ApiAuthToken.DoesNotExist:
                record = None
            if isinstance(action, ActionMeta):
                action_id = action.id
            else:
                action_id = action
            # 业务查看权限校验/操作对应类型action/graph_unify_query跳过，在auth中间件中已校验
            if (
                action_id == ActionEnum.VIEW_BUSINESS.id
                or (record and action in ActionIdMap[record.type])
                or path in request.path
                for path in api_paths
            ):
                return True

        if self.skip_check:
            return True

        resources = resources or []

        action = get_action_by_id(action)
        if not action.related_resource_types:
            resources = []

        request = self.make_request(action, resources)

        try:
            if action.is_read_action():
                # 仅对读权限做缓存
                result = self.iam_client.is_allowed_with_cache(request)
            else:
                result = self.iam_client.is_allowed(request)
        except AuthAPIError as e:
            logger.exception("[IAM AuthAPI Error]: %s", e)
            result = False

        if not result and raise_exception:
            # 对资源信息(如资源名称)进行补全
            # 先判断是否是SaaS空间
            actions, detail_resources = self.prepare_apply_for_saas(resources)
            if not actions:
                # 非SaaS空间
                detail_resources = []
                for resource in resources:
                    resource_mata = get_resource_by_id(resource.type)
                    detail_resources.append(resource_mata.create_instance(resource.id))
                actions = [action]
            apply_data, apply_url = self.get_apply_data(actions, detail_resources)

            raise PermissionDeniedError(
                context={"action_name": action.name},
                data={"apply_url": apply_url},
                extra={"permission": apply_data},
            )

        return result

    def prepare_apply_for_saas(self, resources):
        # PAAS空间下权限申请全家桶
        # APM相关权限暂时无法一并处理，因为空间权限申请时，不一定有APM应用
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

    def is_allowed_by_biz(self, bk_biz_id: int, action: Union[ActionMeta, str], raise_exception: bool = False):
        """
        判断用户对当前动作在该业务下是否有权限
        """
        if self.skip_check:
            return True

        resources = [ResourceEnum.BUSINESS.create_simple_instance(bk_biz_id)]
        return self.is_allowed(action, resources, raise_exception)

    def batch_is_allowed(self, actions: List[ActionMeta], resources: List[List[Resource]]):
        """
        查询某批资源某批操作是否有权限
        """
        result = defaultdict(dict)
        # 请求头携带token，临时分享模式权限豁免
        if self.token:
            try:
                record = ApiAuthToken.objects.get(token=self.token)
            except ApiAuthToken.DoesNotExist:
                raise TokenValidatedError
            for action in actions:
                for resource in resources:
                    resource_id = resource[0].id
                    action_id = action.id
                    if action_id == "view_business" or (record and action in ActionIdMap[record.type]):
                        result[resource_id][action_id] = True
                    else:
                        result[resource_id][action_id] = False
            return result

        # 开发环境变量配置权限豁免
        if self.skip_check:
            for action in actions:
                for resource in resources:
                    resource_id = resource[0].id
                    action_id = action.id
                    result[resource_id][action_id] = True

            return result

        request = self.make_multi_action_request(actions)
        result = self.iam_client.batch_resource_multi_actions_allowed(request, resources)

        return result

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
    def batch_make_resource(cls, resources: List[Dict]):
        """
        批量构造resource对象
        """
        return [cls.make_resource(r["type"], r["id"]) for r in resources]

    def list_actions(self):
        """
        获取权限中心注册的动作列表
        """
        ok, message, data = self.iam_client._client.query(settings.BK_IAM_SYSTEM_ID)
        if not ok:
            raise BKAPIError(
                system_name=settings.BK_IAM_APP_CODE,
                url="/api/v1/model/systems/{system_id}/query".format(system_id=settings.BK_IAM_SYSTEM_ID),
                result={"message": message},
            )
        return data["actions"]

    def filter_space_list_by_action(self, action: Union[ActionMeta, str], using_cache=True) -> List[dict]:
        """
        获取有对应action权限的空间列表
        """
        space_list = SpaceApi.list_spaces_dict(using_cache)
        # 对后台API进行权限豁免
        if self.skip_check:
            return space_list

        # 拉取策略
        request = self.make_request(action=action)

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

        # 生成表达式
        expr = make_expression(policies)

        results = []
        for space in space_list:
            obj_set = ObjectSet()
            obj_set.add_object(ResourceEnum.BUSINESS.id, {"id": str(space["bk_biz_id"])})

            if self.iam_client._eval_expr(expr, obj_set):
                results.append(space)

        return results

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
