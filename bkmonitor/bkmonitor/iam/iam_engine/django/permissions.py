"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from __future__ import annotations

from collections.abc import Callable

from rest_framework import permissions as drf_permissions

from bkmonitor.iam.iam_engine.core.types import (
    AuthRequest,
    BatchByResourceRequest,
    ResourceInstance,
    Subject,
    SubjectType,
)
from bkmonitor.iam.iam_engine.django.facade import get_framework

# ---------------------------------------------------------------------------
# IAMPermission —— 底层积木
#
# 一个类覆盖所有现有 DRF 权限场景：
#   - 无资源：         IAMPermission(actions=["manage_global_setting"])
#   - 从 URL 取资源ID： IAMPermission(actions=["view_space"], resource_type="space")
#   - 自定义取资源ID：   IAMPermission(actions=["view_rule"], resource_type="business",
#                                     get_resource_id=lambda r,v: str(r.biz_id))
#
# 项目可封装子类做语义化（如 BusinessActionPermission）——框架不内置业务概念。
# ---------------------------------------------------------------------------


class IAMPermission(drf_permissions.BasePermission):
    """IAM 鉴权 DRF Permission。

    多个 action 为 OR 语义：任一 action 通过即放行。

    典型用法::

        # 全局权限（无资源）
        permission_classes = [IAMPermission(actions=["manage_global_setting"])]

        # 从 view.kwargs["pk"] 自动取资源 ID（默认行为）
        permission_classes = [
            IAMPermission(
                actions=["view_space"],
                resource_type="space",
            )
        ]

        # 自定义资源 ID 解析
        permission_classes = [
            IAMPermission(
                actions=["view_rule", "manage_rule"],
                resource_type="business",
                get_resource_id=lambda request, view: str(request.biz_id),
            )
        ]
    """

    def __init__(
        self,
        actions: list[str],
        resource_type: str = "",
        get_resource_id: Callable | str | None = None,
    ) -> None:
        super().__init__()
        self._actions = list(actions)
        self._resource_type = resource_type
        self._get_resource_id = get_resource_id

    # ------------------------------------------------------------------
    # has_permission
    # ------------------------------------------------------------------

    def has_permission(self, request, view) -> bool:
        resource_id = self._resolve_resource_id(request, view)
        resource = ResourceInstance(type=self._resource_type, id=resource_id) if resource_id else None
        return self._is_any_action_allowed(request, resource)

    # ------------------------------------------------------------------
    # has_object_permission
    # ------------------------------------------------------------------

    def has_object_permission(self, request, view, obj) -> bool:
        resource_id = self._resolve_object_resource_id(obj)
        if resource_id is None:
            return self.has_permission(request, view)
        resource = ResourceInstance(type=self._resource_type, id=resource_id) if resource_id else None
        return self._is_any_action_allowed(request, resource)

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _is_any_action_allowed(self, request, resource: ResourceInstance | None) -> bool:
        """逐个 action 鉴权，任一通过即放行（OR 语义）。"""
        fw = get_framework()
        for action_id in self._actions:
            allowed = fw.is_allowed(
                AuthRequest(
                    subject=Subject(id=request.user.username, type=SubjectType.USER),
                    action_id=action_id,
                    resource=resource,
                )
            )
            if allowed:
                return True
        return False

    def _resolve_resource_id(self, request, view) -> str | None:
        """解析资源 ID。优先级：callable > str(方法名) > view.kwargs["pk"]。"""
        if not self._resource_type:
            return None

        resolver = self._get_resource_id
        if resolver is None:
            return str(view.kwargs.get("pk", "")) or None
        if callable(resolver):
            return resolver(request, view)
        # str → view 上的方法名
        method = getattr(view, resolver, None)
        if method is None:
            raise AttributeError(
                f"View {view.__class__.__name__} has no method {resolver!r} (specified as get_resource_id)"
            )
        return method(request, view)

    def _resolve_object_resource_id(self, obj) -> str | None:
        """从 obj 上取资源 ID。默认取 obj.pk。"""
        if not self._resource_type:
            return None
        return str(getattr(obj, "pk", ""))


# ---------------------------------------------------------------------------
# IamActionMapMixin —— 声明式 action→permission 映射
#
# 不再手写 get_permissions() 的 if/elif 链。用法::
#
#   class SpaceViewSet(IamActionMapMixin, ModelViewSet):
#       iam_action_map = {
#           "list":     ["view_space"],
#           "retrieve": ["view_space"],
#           "create":   ["manage_space"],
#           "update":   ["manage_space"],
#           "destroy":  ["manage_space"],
#           "export":   [],                     # 空列表 = 公开接口
#       }
#       iam_resource_type = "space"
#       iam_get_resource_id = "resolve_space_id"
#
#       def resolve_space_id(self, request, view):
#           return str(view.kwargs.get("space_id", request.biz_id))
# ---------------------------------------------------------------------------


class IamActionMapMixin:
    """声明式 action→permission 映射 Mixin。

    自动实现 get_permissions()：读 self.action，从 iam_action_map 查对应的
    action_id 列表，构建 IAMPermission 实例。

    属性：
        iam_action_map: dict[str, list[str]]
            action → action_id 列表。支持三种 key：
              - 具体 action 名（"list", "create", ...）
              - "*" 通配符（所有 action）
              - "_methods": dict[str, list[str]] HTTP method→action_id 映射
        iam_resource_type: str
            资源类型 ID（所有 action 共用）
        iam_get_resource_id: callable | str | None
            自定义资源 ID 解析器；None 时默认 view.kwargs["pk"]
    """

    iam_action_map: dict = {}
    iam_resource_type: str = ""
    iam_get_resource_id: Callable | str | None = None

    def get_permissions(self):
        action = getattr(self, "action", None)
        if action is None:
            return super().get_permissions()

        action_ids = self._lookup_action_ids(action)
        if action_ids is not None:
            return self._build(action_ids)

        return super().get_permissions()

    def _lookup_action_ids(self, action: str) -> list[str] | None:
        """查 iam_action_map。优先级：精确匹配 > "*" 通配 > _methods。"""
        action_map = self.iam_action_map
        if action in action_map:
            val = action_map[action]
            if isinstance(val, list):
                return val
        if "*" in action_map:
            val = action_map["*"]
            if isinstance(val, list):
                return val
        method_map = action_map.get("_methods", {})
        method = getattr(self, "request", None) and self.request.method
        if method and method in method_map:
            val = method_map[method]
            if isinstance(val, list):
                return val
        return None

    def _build(self, action_ids: list[str]) -> list:
        if not action_ids:
            return []
        return [
            IAMPermission(
                actions=action_ids,
                resource_type=self.iam_resource_type,
                get_resource_id=self.iam_get_resource_id,
            )
        ]


# ---------------------------------------------------------------------------
# insert_permission_field —— 响应式权限标注
#
# 装饰器 / 工具函数：给列表接口返回的每行数据注入权限字段。
#
# 用法::
#
#   @insert_permission_field(
#       actions=["view_space", "manage_space"],
#       resource_type="space",
#       get_resource_id=lambda r, v: str(r.biz_id),
#   )
#   def list(self, request): ...
#
# 每行数据会增加:
#   {"permission": {"view_space": true, "manage_space": false, ...}}
# ---------------------------------------------------------------------------


def insert_permission_field(
    actions: list[str],
    resource_type: str = "",
    get_resource_id: Callable | str | None = None,
    field_name: str = "permission",
):
    """装饰器：给 view 返回的列表数据每行注入权限字段。

    Args:
        actions: 要检查的 action_id 列表
        resource_type: 资源类型
        get_resource_id: 资源 ID 解析器（callable 或 view 上的方法名）
        field_name: 注入的字段名，默认 "permission"

    Returns:
        装饰器
    """
    import functools

    def decorator(view_method):
        @functools.wraps(view_method)
        def wrapper(view, request, *args, **kwargs):
            response = view_method(view, request, *args, **kwargs)
            data = response.data if hasattr(response, "data") else response

            if not isinstance(data, dict):
                return response

            results = data.get("results") if "results" in data else data
            if not isinstance(results, list) or not results:
                return response

            fw = get_framework()
            resolver = _build_id_resolver(get_resource_id)
            subject = Subject(id=request.user.username, type=SubjectType.USER)

            # 收集所有资源实例
            resource_by_id: dict[str, ResourceInstance] = {}
            item_resource_ids: list[tuple[int, str | None]] = []
            for idx, item in enumerate(results):
                rid = resolver(request, view, item) if resource_type else None
                item_resource_ids.append((idx, rid))
                if rid and rid not in resource_by_id:
                    resource_by_id[rid] = ResourceInstance(type=resource_type, id=rid)

            # 每条 action 调一次 batch_by_resource，构建 (action_id, resource_id) → allowed
            allowed_map: dict[tuple[str, str], bool] = {}
            for action_id in actions:
                if not resource_by_id:
                    # 无资源 — 单次 is_allowed
                    allowed = fw.is_allowed(AuthRequest(subject=subject, action_id=action_id))
                    for idx, _rid in item_resource_ids:
                        allowed_map[(action_id, "")] = allowed
                else:
                    batch_result = fw.batch_by_resource(
                        BatchByResourceRequest(
                            subject=subject,
                            action_id=action_id,
                            resources=tuple(resource_by_id.values()),
                        )
                    )
                    for item_result in batch_result.items:
                        allowed_map[(action_id, item_result.resource_id)] = item_result.allowed

            # 回填每行数据
            for idx, rid in item_resource_ids:
                perm = {}
                for action_id in actions:
                    key = (action_id, rid or "")
                    perm[action_id] = allowed_map.get(key, False)
                results[idx][field_name] = perm

            return response

        return wrapper

    return decorator


def _build_id_resolver(resolver):
    """构建 (request, view, item) → str | None 的解析器。"""
    if resolver is None:

        def _default(_request, _view, item):
            return str(item.get("id", item.get("pk", ""))) or None

        return _default
    if callable(resolver):

        def _callable(request, view, item):
            return resolver(request, view, item)

        return _callable

    # str → view method
    def _method(request, view, item):
        method = getattr(view, resolver)
        return method(request, view, item)

    return _method
