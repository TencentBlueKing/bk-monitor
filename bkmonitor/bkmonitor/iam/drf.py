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

from bkmonitor.iam.definitions.actions import Actions
from bkmonitor.iam.definitions.resource_types import ResourceTypes
from bkmonitor.iam.iam_engine.core.types import (
    ApplyURLRequest,
    AuthRequest,
    BatchByResourceRequest,
    ResourceInstance as FwResource,
    Subject as FwSubject,
    SubjectType,
)
from bkmonitor.iam.iam_engine.django.facade import get_framework
from core.errors.iam import PermissionDeniedError

logger = logging.getLogger("apm")


# ============================================================================
# 内部辅助
# ============================================================================


def _fw_check_any(request, action_ids, resources=None):
    """逐个 action 鉴权，任一通过即放行（OR 语义）。全部拒绝时抛 PermissionDeniedError。"""
    fw = get_framework()
    subject = FwSubject(id=request.user.username, type=SubjectType.USER, tenant_id=request.user.tenant_id)

    fw_resources = tuple(resources) if resources else ()

    for aid in action_ids:
        fw_resource = fw_resources[0] if fw_resources else None
        allowed = fw.is_allowed(AuthRequest(subject=subject, action_id=aid, resource=fw_resource))
        if allowed:
            return True

    apply_url = fw.get_apply_url(
        ApplyURLRequest(
            subject=subject,
            action_ids=tuple(action_ids),
            resources=fw_resources,
        )
    )
    raise PermissionDeniedError(
        context={"action_name": action_ids[-1] if action_ids else ""},
        data={"apply_url": apply_url},
    )


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
        self._action_ids = _to_action_ids(actions)
        self.resources = resources or []  # 兼容旧 IAMPermission 接口

    def has_permission(self, request, view):
        if not self._action_ids:
            return True

        fw_resources = _to_fw_resources(self.resources)
        _fw_check_any(request, self._action_ids, fw_resources)
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
        self.resources = [FwResource(type=ResourceTypes.SPACE.id, id=str(request.biz_id))]
        return super().has_permission(request, view)

    def has_object_permission(self, request, view, obj):
        bk_biz_id = getattr(obj, "bk_biz_id", None)
        if bk_biz_id:
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


def insert_permission_field(
    actions: list,
    resource_meta,
    id_field: Callable = lambda item: item["id"],
    data_field: Callable = lambda data_list: data_list,
    always_allowed: Callable = lambda item: False,
    many: bool = True,
    instance_create_func: Callable | None = None,
    batch_create: bool = False,
):
    """数据返回后，注入权限字段（内部委托 IAMFramework）。

    保留旧签名兼容，但不再创建 iam.Resource 或调用 Permission()。
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

            # 批量鉴权
            fw = get_framework()
            subject = FwSubject(id=request.user.username, type=SubjectType.USER, tenant_id=request.user.tenant_id)
            allowed_map: dict[tuple[str, str], bool] = {}

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
                    perm[aid] = allowed_map.get((aid, rid), False)
                result_list[idx].setdefault("permission", {})
                result_list[idx]["permission"].update(perm)

                if always_allowed(result_list[idx]):
                    for k in perm:
                        perm[k] = True

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
    subject = FwSubject(id=username or "", type=SubjectType.USER, tenant_id=bk_tenant_id or "")
    allowed_map: dict[tuple[str, str], bool] = {}

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
