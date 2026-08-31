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
# DRF 权限插件 — 委托 IAMFramework
#
# 改造说明
#   所有权限类保留旧签名（外部调用者零改动），内部直接调 get_framework()。
#   iam.Resource 对象在本文件中已彻底消除，切换 V3/V4 drf.py 零改动。
# ---------------------------------------------------------------------------

from __future__ import annotations

import logging
from collections.abc import Callable
from functools import wraps
from typing import Literal

from rest_framework import permissions

from bkmonitor.iam.action import canonicalize_action_id, get_action_by_id, get_legacy_action_ids
from bkmonitor.iam.definitions.actions import Actions
from bkmonitor.iam.definitions.resource_types import ResourceTypes
from bkmonitor.utils.request import get_request
from bkmonitor.utils.tenant import is_biz_in_tenant
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
from bkmonitor.iam.iam_engine.core.exceptions import ProviderUnavailable
from bkmonitor.iam.errors import build_legacy_permission_denied
from core.errors.iam import ActionNotExistError, PermissionDeniedError
from bkmonitor.iam.permission import check_iam_preflight, check_iam_batch_preflight

logger = logging.getLogger("apm")


# ============================================================================
# 内部辅助
# ============================================================================


def _to_business_action_id(action_ref) -> str:
    """归一化为框架业务 action ID，兼容已登记的 V3 历史方言 ID。"""
    return canonicalize_action_id(to_action_id(action_ref))


def _get_action_display_name(action_ref) -> str:
    """返回用户可见的动作名称，绝不把 V3/V4 方言 ID 暴露给旧前端。"""
    name = getattr(action_ref, "name", "")
    if name:
        return str(name)

    action_id = _to_business_action_id(action_ref)
    try:
        return str(get_action_by_id(action_id).name)
    except ActionNotExistError:
        # 未登记 action 保持旧行为：无法解析展示名时才回退为原始业务 ID。
        return action_id


def _build_drf_permission_denied(fw, subject, action_ref, resources, *, backend_unavailable: bool):
    """尽力补齐旧 PermissionDeniedError 所需的申请信息，绝不让二次查询变成 500。"""
    action_id = _to_business_action_id(action_ref)
    action_name = _get_action_display_name(action_ref)
    permission = None
    try:
        # V4 的 get_apply_data 为本地构造；即使鉴权 API 超时，通常仍能提供
        # 老前端权限弹窗需要的 permission 数据。
        permission = fw.get_apply_data([action_id], list(resources), subject)
    except ProviderUnavailable as exc:
        logger.exception("[IAMPermission] generate apply data unavailable: %s", exc)

    apply_url = ""
    try:
        apply_url = fw.get_apply_url(
            ApplyURLRequest(
                subject=subject,
                action_ids=(action_id,),
                resources=resources,
            )
        )
    except ProviderUnavailable as exc:
        logger.exception("[IAMPermission] generate apply url unavailable: %s", exc)

    return build_legacy_permission_denied(
        action_name=action_name,
        apply_url=apply_url,
        permission=permission,
        backend_unavailable=backend_unavailable,
    )


def _fw_check_any(request, action_refs, resources=None):
    """逐个 action 鉴权，任一通过即放行（OR 语义）。全部失败时返回旧鉴权错误协议。

    每个 action 先走前置豁免（token 临时分享 / skip_check），与旧版
    IAMPermission → Permission().is_allowed 的豁免语义一致。
    """
    fw = get_framework()
    subject = FwSubject(id=request.user.username, type=SubjectType.USER, tenant_id=request.user.tenant_id)

    fw_resources = tuple(resources) if resources else ()

    last_unavailable = None
    for action in action_refs:
        # 前置豁免（token 临时分享 / skip_check，与旧版一致）
        if check_iam_preflight(request, action):
            return True

        fw_resource = fw_resources[0] if fw_resources else None
        try:
            allowed = fw.is_allowed(
                AuthRequest(subject=subject, action_id=_to_business_action_id(action), resource=fw_resource)
            )
        except ProviderUnavailable as exc:
            # 不能在 Provider 层提前降级为 False：这会破坏组合策略的 fallback。
            # 这里已是 DRF 边界，仍继续尝试其它 OR action；若存在任一可用的
            # allow 结果则照常放行。
            logger.exception("[IAMPermission] auth provider unavailable: %s", exc)
            last_unavailable = exc
            continue
        if allowed:
            return True

    # 旧 IAMPermission 会抛出“最后一个 action”的 PermissionDeniedError；申请
    # 数据也只对应该 action。沿用此语义，而不是把多个 OR action 合并进申请单。
    denied_action = action_refs[-1] if action_refs else ""
    error = _build_drf_permission_denied(
        fw,
        subject,
        denied_action,
        fw_resources,
        backend_unavailable=last_unavailable is not None,
    )
    if last_unavailable is not None:
        raise error from last_unavailable
    raise error


def _to_action_ids(actions) -> list[str]:
    """将 ActionDef / str 列表统一为 business ID 字符串列表。"""
    return [a.id if hasattr(a, "id") else str(a) for a in (actions or [])]


def _to_fw_resources(resources) -> list[FwResource]:
    """将 iam.Resource 或 FwResource 列表统一为 FwResource 列表。"""
    result = []
    for r in resources or []:
        if isinstance(r, FwResource):
            result.append(r)
        elif hasattr(r, "type") and hasattr(r, "id"):
            result.append(FwResource(type=r.type, id=r.id))
    return result


# ============================================================================
# IAMPermission — 底层基类（兼容旧 fta_web 子类）
# ============================================================================


class IAMPermission(permissions.BasePermission):
    """IAM 鉴权 DRF Permission 基类。

    支持：
      1. IAMPermission(actions=[ActionEnum.XXX]) — 直接实例化
      2. 子类覆盖 / 设 self.resources 后调 super()（兼容 fta_web）
    """

    def __init__(self, actions=None, resources=None):
        super().__init__()
        # 保留原始引用（ActionEnum 成员或 str），供前置豁免的 ActionIdMap 判定使用
        self._action_refs = list(actions or [])
        self._action_ids = _to_action_ids(actions)
        self.resources = resources or []  # 兼容旧 IAMPermission 接口

    def has_permission(self, request, view):
        if not self._action_ids:
            return True

        fw_resources = _to_fw_resources(self.resources)
        _fw_check_any(request, self._action_refs, fw_resources)
        return True

    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


# ============================================================================
# BusinessActionPermission — 关联业务的动作权限
# ============================================================================


class BusinessActionPermission(IAMPermission):
    """业务级权限检查。从 request.biz_id 取空间 ID，不再创建 iam.Resource。"""

    def __init__(self, actions):
        super().__init__(actions)

    def has_permission(self, request, view):
        if not request.biz_id:
            return True
        if not is_biz_in_tenant(request.biz_id, getattr(request.user, "tenant_id", None)):
            return False
        self.resources = [FwResource(type=ResourceTypes.SPACE.id, id=str(request.biz_id))]
        return super().has_permission(request, view)

    def has_object_permission(self, request, view, obj):
        bk_biz_id = getattr(obj, "bk_biz_id", None)
        if bk_biz_id:
            if not is_biz_in_tenant(bk_biz_id, getattr(request.user, "tenant_id", None)):
                return False
            self.resources = [FwResource(type=ResourceTypes.SPACE.id, id=str(bk_biz_id))]
            return super().has_object_permission(request, view, obj)
        return self.has_permission(request, view)


# ============================================================================
# ViewBusinessPermission — 固定 VIEW_BUSINESS
# ============================================================================


class ViewBusinessPermission(BusinessActionPermission):
    def __init__(self):
        super().__init__([Actions.VIEW_BUSINESS])


# ============================================================================
# MCPPermission — MCP 协议动态权限
# ============================================================================


class MCPPermission(BusinessActionPermission):
    """
    MCP权限检查 - 支持动态权限加载
    根据请求头中的 X-Bkapi-Permission-Action 动态选择对应的权限动作
    """

    def __init__(self, action=None):
        """
        初始化MCP权限检查
        :param action: 权限动作，如果不提供则使用默认的 USING_DASHBOARD_MCP
        """
        action = action if action is not None else Actions.USING_DASHBOARD_MCP
        logger.info(f"MCPPermission: action: {action.id}")
        super().__init__([action])

    def has_permission(self, request, view):
        # 尝试从request中读取bk_biz_id / biz_id
        if not hasattr(request, "biz_id") or not request.biz_id:
            # 如果没有 biz_id，抛出异常
            logger.error("MCPPermission: Missing biz_id for MCP permission check")
            raise PermissionDeniedError("Missing biz_id for MCP permission check")
        logger.info(f"MCPPermission: biz_id: {request.biz_id},skip_check: {request.skip_check}")
        self.resources = [FwResource(type=ResourceTypes.SPACE.id, id=str(request.biz_id))]
        logger.info("MCPPermission: Calling IAMPermission.has_permission")
        return IAMPermission.has_permission(self, request, view)


# ============================================================================
# InstanceActionPermission — URL 路径参数取资源 ID（0 外部，作为 InstanceActionForDataPermission 基类）
# ============================================================================


class InstanceActionPermission(IAMPermission):
    """
    关联其他资源的权限检查
    """

    def __init__(self, actions, resource_meta):
        self.resource_type_id = resource_meta.id if hasattr(resource_meta, "id") else resource_meta
        super().__init__(actions)

    def has_permission(self, request, view):
        instance_id = view.kwargs[self._get_look_url_kwarg(view)]
        self.resources = [FwResource(type=self.resource_type_id, id=str(instance_id))]
        return super().has_permission(request, view)

    def _get_look_url_kwarg(self, view):
        lookup_url_kwarg = view.lookup_url_kwarg or view.lookup_field
        assert lookup_url_kwarg in view.kwargs, (
            f"Expected view {self.__class__.__name__} to be called with a URL keyword argument "
            f'named "{lookup_url_kwarg}". Fix your URL conf, or set the `.lookup_field` '
            "attribute on the view correctly."
        )
        return lookup_url_kwarg


# ============================================================================
# InstanceActionForDataPermission — 从请求 body/params 取资源 ID
# ============================================================================


class InstanceActionForDataPermission(InstanceActionPermission):
    def __init__(
        self,
        iam_instance_id_key,
        *args,
        get_instance_id: Callable = lambda _id: _id,
    ):
        self.iam_instance_id_key = iam_instance_id_key
        self.get_instance_id = get_instance_id
        super().__init__(*args)

    def has_permission(self, request, view):
        if request.method == "GET":
            data = request.query_params
        else:
            data = request.data
        instance_id = data.get(self.iam_instance_id_key) or view.kwargs.get(self._get_look_url_kwarg(view))
        if instance_id is None:
            raise ValueError("instance_id must have")
        self.resources = [FwResource(type=self.resource_type_id, id=str(self.get_instance_id(instance_id)))]
        return IAMPermission.has_permission(self, request, view)


# ============================================================================
# insert_permission_field — 响应注入权限字段
# ============================================================================


def _is_read_action(action) -> bool:
    """兼容旧 ActionMeta 与框架 ActionDef 的读取动作判定。"""
    if hasattr(action, "is_read_action"):
        return action.is_read_action()

    extensions = getattr(action, "extensions", {})
    v3_extensions = extensions.get("v3", {}) if hasattr(extensions, "get") else {}
    return v3_extensions.get("type") == "view"


def _resolve_sort_action(actions: list, sort_action=None):
    """解析用于「有权限前置」排序的动作。"""
    if sort_action is not None:
        return sort_action
    for action in actions:
        if _is_read_action(action):
            return action
    return actions[-1] if actions else None


def sort_result_list_allowed_first(
    result_list: list[dict],
    actions: list,
    sort_action=None,
) -> None:
    """将有权限的记录稳定排到列表前面，保持同组内原有相对顺序。

    :param result_list: 已写入 permission 字段的结果列表，原地排序
    :param actions: 本次批量鉴权的动作列表
    :param sort_action: 用于判断「有权限」的动作；未指定时优先使用查看类动作
    """
    action = _resolve_sort_action(actions, sort_action)
    if action is None:
        return

    action_id = to_action_id(action)
    result_list.sort(key=lambda item: not bool((item.get("permission") or {}).get(action_id, False)))


def insert_permission_field(
    actions: list,
    resource_meta,
    id_field: Callable = lambda item: item["id"],
    data_field: Callable = lambda data_list: data_list,
    always_allowed: Callable = lambda item: False,
    many: bool = True,
    instance_create_func: Callable | None = None,
    batch_create: bool = False,
    sort_allowed_first: bool = False,
    sort_action=None,
    include_legacy_action_keys: bool = False,
):
    """数据返回后，注入权限字段（内部委托 IAMFramework）。

    保留旧签名兼容，但不再创建 iam.Resource 或调用 Permission()。

    兼容说明：instance_create_func / batch_create 参数仅为兼容旧调用方签名保留，
    当前实现不再使用（实例统一构造为 FwResource）。

    Args:
        sort_allowed_first: 是否将有权限记录稳定排到列表前面。
        sort_action: 排序依据的动作；未指定时优先使用查看类动作。
        include_legacy_action_keys: 是否在 permission 字典中同时写入已登记的历史 Action ID；
            兼容键复用同一次鉴权结果，不会增加 IAM 请求。
    """
    action_ids = _to_action_ids(actions)
    resource_type = resource_meta.id if hasattr(resource_meta, "id") else resource_meta

    def wrapper(view_func):
        @wraps(view_func)
        def wrapped_view(*args, **kwargs):
            request = args[0] if args else None
            response = view_func(*args, **kwargs)

            result_list = data_field(response.data)
            if not many:
                result_list = [result_list]

            # 收集资源实例
            resource_by_id: dict[str, FwResource] = {}
            item_resource_ids: list[tuple[int, str | None]] = []
            for idx, item in enumerate(result_list):
                rid = id_field(item)
                if not rid:
                    item_resource_ids.append((idx, None))
                    continue
                rid_str = str(rid)
                item_resource_ids.append((idx, rid_str))
                if rid_str not in resource_by_id:
                    resource_by_id[rid_str] = FwResource(type=resource_type, id=rid_str)

            if not resource_by_id:
                return response

            # 前置豁免（复刻旧 Permission().batch_is_allowed 语义：token 分享 / skip_check）
            allowed_map: dict[tuple[str, str], bool] = {}
            exemption = check_iam_batch_preflight(request, actions) if request is not None else None
            if exemption is not None:
                for aid in action_ids:
                    for rid in resource_by_id:
                        allowed_map[(aid, rid)] = exemption.get(aid, False)
            else:
                # 批量鉴权
                fw = get_framework()
                subject = FwSubject(id=request.user.username, type=SubjectType.USER, tenant_id=request.user.tenant_id)
                for aid in action_ids:
                    batch_result = fw.batch_by_resource(
                        BatchByResourceRequest(
                            subject=subject,
                            action_id=aid,
                            resources=tuple(resource_by_id.values()),
                        )
                    )
                    for item_result in batch_result.items:
                        allowed_map[(aid, item_result.resource_id)] = item_result.allowed

            # 回填
            for idx, rid in item_resource_ids:
                if rid is None:
                    continue
                perm = {}
                for aid in action_ids:
                    allowed = allowed_map.get((aid, rid), False)
                    perm[aid] = allowed
                    if include_legacy_action_keys:
                        for legacy_action_id in get_legacy_action_ids(aid):
                            perm[legacy_action_id] = allowed
                # 注意：dict.update 是浅拷贝，always_allowed 豁免必须作用于已写入的
                # permission dict 本身（与旧版 item["permission"] 原地修改语义一致），
                # 否则修改局部 perm 不会反映到响应数据上。
                permission_dict = result_list[idx].setdefault("permission", {})
                permission_dict.update(perm)

                if always_allowed(result_list[idx]):
                    for k in permission_dict:
                        permission_dict[k] = True

            if sort_allowed_first and many:
                sort_result_list_allowed_first(result_list, actions, sort_action)

            return response

        return wrapped_view

    return wrapper


# ============================================================================
# filter_data_by_permission — 按权限过滤/标注数据
# ============================================================================


def filter_data_by_permission(
    bk_tenant_id: str,
    data: list[dict] | dict,
    actions: list,
    resource_meta,
    id_field: Callable[[dict], str] = lambda item: item["id"],
    always_allowed: Callable[[dict], bool] = lambda item: False,
    instance_create_func: Callable | None = None,
    mode: Literal["any", "all", "insert"] = "any",
    username: str | None = None,
) -> list[dict]:
    """根据权限过滤/标注数据（内部委托 IAMFramework）。

    保留旧签名兼容。mode: "any"=任一通过/"all"=全部通过/"insert"=插入不删。

    兼容说明：instance_create_func 参数仅为兼容旧调用方签名保留，
    当前实现不再使用（实例统一构造为 FwResource）。
    """
    if isinstance(data, dict):
        data = [data]

    action_ids = _to_action_ids(actions)
    resource_type = resource_meta.id if hasattr(resource_meta, "id") else resource_meta

    # 收集资源实例
    resource_by_id: dict[str, FwResource] = {}
    item_resource_ids: list[tuple[int, str | None]] = []
    for idx, item in enumerate(data):
        rid = id_field(item)
        if not rid:
            item_resource_ids.append((idx, None))
            continue
        rid_str = str(rid)
        item_resource_ids.append((idx, rid_str))
        if rid_str not in resource_by_id:
            resource_by_id[rid_str] = FwResource(type=resource_type, id=rid_str)

    if not resource_by_id:
        return []

    # 批量鉴权
    fw = get_framework()
    request = None
    if not username:
        # 未显式传 username：与 Permission.__init__ 的解析链对齐，从当前请求解析用户。
        # 旧版 Permission() 由此拿到 request，进而生效 token / request.skip_check 豁免，
        # 因此这里保留解析出的 request 供前置豁免使用。
        request = get_request(peaceful=True)
        username = request.user.username if request else ""
    subject = FwSubject(id=username, type=SubjectType.USER, tenant_id=bk_tenant_id or "")
    allowed_map: dict[tuple[str, str], bool] = {}

    # 前置豁免（复刻旧 Permission(...).batch_is_allowed 语义：username 显式传入时
    # 旧版不读 request，仅 settings 级 skip_check 生效；未传时读当前请求的 token/skip_check）
    exemption = check_iam_batch_preflight(request, actions)
    if exemption is not None:
        for aid in action_ids:
            for rid in resource_by_id:
                allowed_map[(aid, rid)] = exemption.get(aid, False)
    else:
        for aid in action_ids:
            batch_result = fw.batch_by_resource(
                BatchByResourceRequest(
                    subject=subject,
                    action_id=aid,
                    resources=tuple(resource_by_id.values()),
                )
            )
            for item_result in batch_result.items:
                allowed_map[(aid, item_result.resource_id)] = item_result.allowed

    # 过滤/标注
    allowed_data = []
    for idx, rid in item_resource_ids:
        if rid is None:
            continue
        item = data[idx]

        perm = {}
        for aid in action_ids:
            perm[aid] = allowed_map.get((aid, rid), False)

        if always_allowed(item):
            for k in perm:
                perm[k] = True

        if mode == "insert":
            item["permission"] = perm
            allowed_data.append(item)
        elif mode == "any":
            if any(perm.values()):
                allowed_data.append(item)
        elif mode == "all":
            if all(perm.values()):
                allowed_data.append(item)

    return allowed_data
