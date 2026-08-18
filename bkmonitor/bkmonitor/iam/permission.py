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
#   鉴权核心已委托给 IAMFramework（is_allowed / batch_is_allowed / get_apply_url /
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

from bkm_space.api import SpaceApi
from bkm_space.utils import bk_biz_id_to_space_uid, is_bk_saas_space
from bkmonitor.iam import ResourceEnum
from bkmonitor.iam.action import MINI_ACTION_IDS, ActionEnum, get_action_by_id
from bkmonitor.iam.adapters.v3.codec import MonitorV3Codec
from bkmonitor.iam.definitions.resource_types import ResourceTypes
from bkmonitor.iam.iam_engine.core.exceptions import PermissionDenied, ProviderError
from bkmonitor.iam.iam_v3.client import V3Client
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
from bkmonitor.models import ApiAuthToken
from bkmonitor.utils.request import get_request
from constants.common import DEFAULT_TENANT_ID
from core.errors.iam import ActionNotExistError, PermissionDeniedError
from core.errors.share import TokenValidatedError

logger = logging.getLogger(__name__)

# ActionIdMap 使用 ActionEnum 而非 definitions.Actions：
# 外部调用方（通过 Permission 的 token 机制）传入的是 ActionEnum 成员，
# 这里的 in 检查需要和外部传入值做 identity 匹配，因此必须用相同的 ActionEnum 成员。
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


def _skip_check_enabled(request) -> bool:
    """skip_check 解析：request 级覆盖 settings 级（与 Permission.__init__ 的合并逻辑一致）。"""
    if request is not None and hasattr(request, "skip_check"):
        return bool(request.skip_check)
    return bool(getattr(settings, "SKIP_IAM_PERMISSION_CHECK", False))


def check_iam_preflight(request, action_ref, skip_check=None) -> bool:
    """直连框架的调用方（DRF 权限类等）使用的前置豁免判定。

    复刻旧版 Permission.is_allowed 的豁免顺序，命中任一即放行（返回 True），
    否则返回 False 进入真实鉴权：
      1. token 临时分享豁免（ApiAuthToken + ActionIdMap + api_paths；
         含历史遗留的 generator 恒真行为，与旧版逐字一致，不做修改）
      2. skip_check 豁免（request 级覆盖 settings 级）

    Args:
        request: Django request；None 表示后台/无请求上下文（只认 settings 级）
        action_ref: ActionDef 成员或 action_id 字符串（token 分支的 ActionIdMap 判定需要成员引用）
        skip_check: 调用方已解析好的 skip 值（如 Permission 实例的 self.skip_check）；
                    为 None 时按 request 级覆盖 settings 级自动解析。
    """
    # token 临时分享权限豁免
    #
    # 与旧版 Permission.is_allowed 的语义对齐（旧版此处存在生成器表达式恒真 bug，
    # 使得任何携带 token 的请求对所有 action 直接放行；本次修复用 any(...) 显式求值，
    # 恢复原始意图：view_business / ActionIdMap 场景命中 / api_paths 路径命中 才放行）。
    # 同步用 ActionIdMap.get(record.type, []) 兜底，避免 entity/user 等未登记 token 类型触发 KeyError。
    if request is not None and getattr(request, "token", None):
        try:
            record = ApiAuthToken.objects.get(token=request.token, bk_tenant_id=request.user.tenant_id)
        except ApiAuthToken.DoesNotExist:
            record = None

        action_id = action_ref.id if hasattr(action_ref, "id") else action_ref
        if (
            action_id == ActionEnum.VIEW_BUSINESS.id
            or (record and action_ref in ActionIdMap.get(record.type, []))
            or any(path in request.path for path in api_paths)
        ):
            return True

    if skip_check is not None:
        return bool(skip_check)
    return _skip_check_enabled(request)


def check_iam_batch_preflight(request, actions) -> dict | None:
    """直连框架的批量调用方（insert_permission_field / filter_data_by_permission）使用的前置豁免。

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
        for action in actions:
            action_id = action.id if hasattr(action, "id") else str(action)
            result[action_id] = action_id == "view_business" or (record and action in ActionIdMap.get(record.type, []))
        return result

    if _skip_check_enabled(request):
        return {a.id if hasattr(a, "id") else str(a): True for a in actions}

    return None


class Permission:
    """
    权限中心鉴权封装 — IAMFramework 适配层。
    """

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

        self.request = request

        # 新框架引用
        self._fw = get_framework()

        self.skip_check = getattr(settings, "SKIP_IAM_PERMISSION_CHECK", False)
        if request and hasattr(request, "skip_check"):
            logger.info(f"Permission: request.skip_check: {request.skip_check}")
            self.skip_check = request.skip_check

    # ================================================================
    # V3 平台 SDK 客户端（仅 v3 平台集成点使用，非 provider 中立鉴权入口）
    # ================================================================

    @classmethod
    def get_iam_client(cls, bk_tenant_id: str):
        """获取 V3 平台 SDK 客户端。

        仅限 v3 平台集成点使用：
          * IAM v3 平台反向回调端点（ResourceApiDispatcher，平台调我们）
          * V1 遗留数据的迁移/清理历史工具（migrate.py / iam_upgrade_action_v2 / iam_delete_action_v1）

        非 provider 中立鉴权入口——业务鉴权一律走框架（is_allowed /
        filter_visible_resources 等），禁止新增调用方。
        """
        app_code, secret_key = settings.APP_CODE, settings.SECRET_KEY
        if settings.ROLE in ["api", "worker"]:
            # 后台api模式下使用SaaS身份
            app_code, secret_key = settings.SAAS_APP_CODE, settings.SAAS_SECRET_KEY

        return V3Client(
            app_code,
            secret_key,
            settings.BK_IAM_APIGATEWAY_URL,
            system_id=settings.BK_IAM_SYSTEM_ID,
            codec=MonitorV3Codec(),
            bk_tenant_id=bk_tenant_id,
        )

    # ================================================================
    # 鉴权 — 框架委托
    # ================================================================

    def is_allowed(self, action, resources: list = None, raise_exception: bool = False):
        """
        校验用户是否有动作的权限（委托 IAMFramework）。
        """
        # token 临时分享 / skip_check 前置豁免（与旧版逻辑一致；skip_check 传实例值，
        # 兼容调用方构造后修改 permission.skip_check 的既有用法）
        if check_iam_preflight(self.request, action, skip_check=self.skip_check):
            return True

        # 构建 FwResource（兼容 iam.Resource 旧调用方）
        resources = resources or []
        fw_resource = None
        if resources:
            r = resources[0]
            fw_resource = FwResource(type=r.type, id=r.id)

        return self._is_allowed_fw(action, fw_resource, raise_exception)

    def _is_allowed_fw(self, action, fw_resource: FwResource | None, raise_exception: bool):
        """内部：直接接受 FwResource 的鉴权方法。"""
        action_id_biz = to_action_id(action)

        try:
            result = self._fw.is_allowed(
                AuthRequest(
                    subject=FwSubject(id=self.username, type=SubjectType.USER, tenant_id=self.bk_tenant_id),
                    action_id=action_id_biz,
                    resource=fw_resource,
                )
            )
        except PermissionDenied as e:
            if raise_exception:
                raise self._build_permission_denied(action_id_biz, fw_resource) from e
            return False

        if not result and raise_exception:
            raise self._build_permission_denied(action_id_biz, fw_resource)

        return result

    def _build_permission_denied(self, action_id_biz: str, fw_resource: FwResource | None):
        """构建 PermissionDeniedError（含 SaaS 全家桶 + apply 数据）。"""
        resources = []
        if fw_resource:
            resources = [ResourceEnum.BUSINESS.create_instance(fw_resource.id)]
        actions, detail_resources = self.prepare_apply_for_saas(resources)
        if not actions:
            detail_resources = []
            if fw_resource:
                detail_resources = [fw_resource]
            try:
                actions = [get_action_by_id(action_id_biz)]
            except ActionNotExistError:
                actions = []
        apply_data, apply_url = self.get_apply_data(
            [a.id for a in actions] if actions else [action_id_biz],
            detail_resources,
        )
        return PermissionDeniedError(
            context={"action_name": action_id_biz},
            data={"apply_url": apply_url},
            extra={"permission": apply_data},
        )

    def is_allowed_by_biz(self, bk_biz_id: int, action, raise_exception: bool = False):
        """
        判断用户对当前动作在该业务下是否有权限（委托 IAMFramework）。
        """
        if self.skip_check:
            return True

        fw_resource = FwResource(type=ResourceTypes.SPACE.id, id=str(bk_biz_id))
        return self._is_allowed_fw(action, fw_resource, raise_exception)

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
                    if action_id == "view_business" or (record and action in ActionIdMap.get(record.type, [])):
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

        # 按资源类型分组（框架批量契约：同批同类型），
        # 每个 (action, 类型组) 一次批量调用（替代 N×M 次单资源调用）
        subject = FwSubject(id=self.username, type=SubjectType.USER, tenant_id=self.bk_tenant_id)
        grouped: dict[str, list[FwResource]] = {}
        for resource_list in resources:
            resource = resource_list[0]
            grouped.setdefault(str(resource.type), []).append(FwResource(type=resource.type, id=resource.id))

        for action_id_biz in action_ids_biz:
            for fw_resources in grouped.values():
                batch_result = self._fw.batch_by_resource(
                    BatchByResourceRequest(subject=subject, action_id=action_id_biz, resources=tuple(fw_resources))
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
                subject=FwSubject(id=self.username, type=SubjectType.USER, tenant_id=self.bk_tenant_id),
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
            FwSubject(id=self.username, type=SubjectType.USER, tenant_id=self.bk_tenant_id),
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
                tenant_id=self.bk_tenant_id,
            )
            logger.info(f"[grant_creator_action] Success! resource: {resource}")
        except Exception as e:  # pylint: disable=broad-except
            logger.exception(f"[grant_creator_action] Failed! resource: {resource}, result: {e}")
            if raise_exception:
                raise e

        return grant_result

    # ================================================================
    # SaaS 空间全家桶 — V3 业务逻辑，框架无关
    # ================================================================

    def prepare_apply_for_saas(self, resources):
        if not resources or resources[0].type != BusinessResource.id:
            return [], []
        bk_biz_id = resources[0].id
        space_uid = bk_biz_id_to_space_uid(bk_biz_id)
        if not is_bk_saas_space(space_uid):
            return [], []
        actions = [get_action_by_id(a_id) for a_id in MINI_ACTION_IDS]
        return actions, [BusinessResource.create_instance(bk_biz_id)]

    # ================================================================
    # 空间列表过滤 — 走框架 filter_visible_resources（provider 中立）
    # ================================================================

    def filter_space_list_by_action(self, action, using_cache=True) -> list[dict]:
        space_list = SpaceApi.list_spaces_dict(bk_tenant_id=self.bk_tenant_id, using_cache=using_cache)
        if self.skip_check:
            return space_list

        action_id_biz = to_action_id(action)
        subject = FwSubject(id=self.username, type=SubjectType.USER, tenant_id=self.bk_tenant_id)
        candidates = tuple(FwResource(type="space", id=str(s["bk_biz_id"])) for s in space_list)

        try:
            result = self._fw.filter_visible_resources(subject, action_id_biz, candidates)
        except ProviderError as e:
            logger.exception("[IAM Policy Query Error]: %s", e)
            return []

        if result.all_granted:
            return space_list

        visible_ids = set(result.visible_ids)
        return [s for s in space_list if str(s["bk_biz_id"]) in visible_ids]

    # ================================================================
    # Resource 构造 — 保留（monitor_web/iam/ 回调使用）
    # ================================================================

    @classmethod
    def make_resource(cls, resource_type: str, instance_id: str):
        return FwResource(type=resource_type, id=str(instance_id))

    @classmethod
    def batch_make_resource(cls, resources: list[dict]):
        return [cls.make_resource(r["type"], r["id"]) for r in resources]

    # ================================================================
    # list_actions — 已弃用（有一个端点依旧在调用）
    # ================================================================
    def list_actions(self):
        raise NotImplementedError("list_actions is deprecated. Use IAMFramework to query actions from schema.")
