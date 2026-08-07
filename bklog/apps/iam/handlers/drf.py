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

from bkm_space.utils import space_uid_to_bk_biz_id

"""
DRF 插件
"""
from functools import wraps  # noqa
from typing import List  # noqa
from collections.abc import Callable

from django.conf import settings  # noqa
from iam import Resource  # noqa
from rest_framework import permissions  # noqa

from ..exceptions import NotHaveInstanceIdError  # noqa
from . import Permission  # noqa
from .actions import ActionEnum, ActionMeta  # noqa
from .resources import ResourceEnum, ResourceMeta  # noqa


class IAMPermission(permissions.BasePermission):
    def __init__(self, actions: list[ActionMeta], resources: list[Resource] = None):
        self.actions = actions
        self.resources = resources or []

    def has_permission(self, request, view):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        # 跳过权限校验
        if settings.IGNORE_IAM_PERMISSION:
            return True

        if not self.actions:
            return True

        client = Permission()
        for action in self.actions:
            client.is_allowed(
                action=action,
                resources=self.resources,
                raise_exception=True,
            )
        return True

    def has_object_permission(self, request, view, obj):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        # 跳过权限校验
        if settings.IGNORE_IAM_PERMISSION:
            return True
        return self.has_permission(request, view)


class BusinessActionPermission(IAMPermission):
    """
    关联业务的动作权限检查
    """

    def __init__(self, actions: list[ActionMeta], space_uid=None):
        self.space_uid = space_uid
        super().__init__(actions)

    @classmethod
    def fetch_biz_id_by_request(cls, request):
        bk_biz_id = request.data.get("bk_biz_id", 0) or request.query_params.get("bk_biz_id", 0)
        return bk_biz_id

    def has_permission(self, request, view):
        if self.space_uid:
            bk_biz_id = space_uid_to_bk_biz_id(self.space_uid)
        else:
            bk_biz_id = self.fetch_biz_id_by_request(request)
        if not bk_biz_id:
            return True
        self.resources = [ResourceEnum.BUSINESS.create_instance(bk_biz_id)]
        return super().has_permission(request, view)

    def has_object_permission(self, request, view, obj):
        # 先查询对象中有没有业务ID相关属性
        bk_biz_id = None
        if hasattr(obj, "space_uid"):
            bk_biz_id = space_uid_to_bk_biz_id(obj.space_uid)
        elif hasattr(obj, "bk_biz_id"):
            bk_biz_id = obj.bk_biz_id
        if bk_biz_id:
            self.resources = [ResourceEnum.BUSINESS.create_instance(bk_biz_id)]
            return super().has_object_permission(request, view, obj)
        # 没有就尝试取请求的业务ID
        return self.has_permission(request, view)


class ViewBusinessPermission(BusinessActionPermission):
    """
    业务访问权限检查
    """

    def __init__(self):
        super().__init__([ActionEnum.VIEW_BUSINESS])


class InstanceActionPermission(IAMPermission):
    """
    关联其他资源的权限检查
    """

    def __init__(self, actions: list[ActionMeta], resource_meta: ResourceMeta):
        self.resource_meta = resource_meta
        super().__init__(actions)

    def has_permission(self, request, view):
        # 跳过权限校验
        if settings.IGNORE_IAM_PERMISSION:
            return True
        instance_id = view.kwargs[self.get_look_url_kwarg(view)]
        resource = self.resource_meta.create_instance(instance_id)
        # 本地资源不存在时拒绝，避免伪造 ID 仅依赖远端误放
        if not self._resource_exists_locally(resource):
            return False
        self.resources = [resource]
        return super().has_permission(request, view)

    @staticmethod
    def _resource_exists_locally(resource: Resource) -> bool:
        attribute = getattr(resource, "attribute", None) or {}
        # create_simple_instance 在本地命中时会写入 name / _bk_iam_path_ / bk_biz_id
        return bool(attribute.get("name") or attribute.get("_bk_iam_path_") or attribute.get("bk_biz_id"))

    def get_look_url_kwarg(self, view):
        # Perform the lookup filtering.
        lookup_url_kwarg = view.lookup_url_kwarg or view.lookup_field

        assert lookup_url_kwarg in view.kwargs, (
            f"Expected view {self.__class__.__name__} to be called with a URL keyword argument "
            f'named "{lookup_url_kwarg}". Fix your URL conf, or set the `.lookup_field` '
            "attribute on the view correctly."
        )
        return lookup_url_kwarg


class InstanceActionForDataPermission(InstanceActionPermission):
    def __init__(self, iam_instance_id_key, *args, get_instance_id: Callable = lambda _id: _id):
        self.iam_instance_id_key = iam_instance_id_key
        self.get_instance_id = get_instance_id
        super().__init__(*args)

    def has_permission(self, request, view):
        if request.method == "GET":
            data = request.query_params
        else:
            data = request.data
        instance_id = data.get(self.iam_instance_id_key) or view.kwargs.get(self.get_look_url_kwarg(view))
        if instance_id is None:
            raise NotHaveInstanceIdError
        resource = self.resource_meta.create_instance(self.get_instance_id(instance_id))
        if not self._resource_exists_locally(resource):
            return False
        self.resources = [resource]
        return super(InstanceActionPermission, self).has_permission(request, view)


class BatchIAMPermission(IAMPermission):
    """IAM实例列表批量鉴权"""

    def __init__(self, iam_instance_ids_key, actions: list[ActionMeta], resource_meta: ResourceMeta):
        self.resource_meta = resource_meta
        self.iam_instance_ids_key = iam_instance_ids_key
        super().__init__(actions)

    def has_permission(self, request, view):
        # 跳过权限校验
        if settings.IGNORE_IAM_PERMISSION:
            return True

        if request.method == "GET":
            data = request.query_params
        else:
            data = request.data

        instance_ids = data.get(self.iam_instance_ids_key) or view.kwargs.get(self.iam_instance_ids_key)
        if not instance_ids:
            raise NotHaveInstanceIdError

        self.resources = [self.resource_meta.create_instance(instance_id) for instance_id in instance_ids]
        return super().has_permission(request, view)


def insert_permission_field(
    actions: list[ActionMeta],
    resource_meta: ResourceMeta,
    id_field: Callable = lambda item: item["id"],
    data_field: Callable = lambda data_list: data_list,
    always_allowed: Callable = lambda item: False,
    many: bool = True,
    deny_filter: bool = False,
    deny_filter_action: ActionMeta | None = None,
    ownership_resolve: Callable | None = None,
    ownership_expected: Callable | None = None,
    ownership_allow_platform: bool = False,
):
    """
    数据返回后，插入权限相关字段
    :param actions: 动作列表
    :param resource_meta: 资源类型
    :param id_field: 从结果集获取ID字段的方式
    :param data_field: 从response.data中获取结果集的方式
    :param always_allowed: 满足一定条件进行权限豁免
    :param many: 是否为列表数据
    :param deny_filter: 是否剔除无权限实例（Deny-Filter）
    :param deny_filter_action: 用于可见性判断的 Action；默认取 actions[0]
    :param ownership_resolve: 从列表项解析本地归属 bk_biz_id；与 ownership_expected 同时配置时，
        在 IAM 批量鉴权前剔除跨空间/归属缺失候选
    :param ownership_expected: 从 request 解析当前空间期望 bk_biz_id（或可迭代集合）
    :param ownership_allow_platform: 是否允许 platform 资源（bk_biz_id=0）豁免归属校验
    """

    def wrapper(view_func):
        @wraps(view_func)
        def wrapped_view(*args, **kwargs):
            response = view_func(*args, **kwargs)

            result_list = data_field(response.data)
            is_single = not many
            if is_single:
                result_list = [result_list]

            if ownership_resolve and ownership_expected:
                from apps.iam.handlers.scope import resource_belongs_to_space

                request = _extract_request(args, kwargs)
                expected = ownership_expected(request) if request is not None else None
                if expected is not None and expected != "":
                    expected_ids = expected if isinstance(expected, list | tuple | set | frozenset) else [expected]
                    owned_items = []
                    for item in result_list:
                        if not id_field(item) or always_allowed(item):
                            owned_items.append(item)
                            continue
                        if resource_belongs_to_space(
                            resource_bk_biz_id=ownership_resolve(item),
                            expected_bk_biz_ids=expected_ids,
                            allow_platform=ownership_allow_platform,
                        ):
                            owned_items.append(item)
                    result_list = owned_items
                    if not is_single:
                        _replace_data_field_result(response, data_field, result_list, many=True)
                    elif result_list:
                        _replace_data_field_result(response, data_field, result_list[0], many=False)

            resources = []
            kept_items = []
            for item in result_list:
                if not id_field(item):
                    kept_items.append(item)
                    continue
                attribute = {}
                if "bk_biz_id" in item:
                    attribute["bk_biz_id"] = item["bk_biz_id"]
                if "space_uid" in item:
                    attribute["space_uid"] = item["space_uid"]

                resources.append(
                    [resource_meta.create_simple_instance(instance_id=id_field(item), attribute=attribute)]
                )
                kept_items.append(item)

            if not resources:
                if ownership_resolve and ownership_expected and deny_filter and not is_single:
                    _replace_data_field_result(response, data_field, kept_items, many=True)
                return response

            if settings.IGNORE_IAM_PERMISSION:
                for item in kept_items:
                    item.setdefault("permission", {})
                    item["permission"].update({action.id: True for action in actions})
                return response

            permission_result = Permission().batch_is_allowed(actions, resources)
            visibility_action = deny_filter_action or actions[0]
            filtered_items = []

            for item in kept_items:
                origin_instance_id = id_field(item)
                if not origin_instance_id:
                    filtered_items.append(item)
                    continue
                instance_id = str(origin_instance_id)
                item.setdefault("permission", {})
                item["permission"].update(permission_result.get(instance_id, {}))

                if always_allowed(item):
                    for action_id in item["permission"]:
                        item["permission"][action_id] = True

                if deny_filter and not item["permission"].get(visibility_action.id, False) and not always_allowed(item):
                    continue
                filtered_items.append(item)

            if deny_filter:
                if is_single:
                    # 单对象场景下若被剔除，保持原结构由上层对象鉴权处理
                    if filtered_items:
                        _replace_data_field_result(response, data_field, filtered_items[0], many=False)
                else:
                    _replace_data_field_result(response, data_field, filtered_items, many=True)

            return response

        return wrapped_view

    return wrapper


def _extract_request(args, kwargs):
    request = kwargs.get("request")
    if request is not None:
        return request
    for arg in args:
        if hasattr(arg, "query_params") or hasattr(arg, "GET"):
            return arg
    return None


def _replace_data_field_result(response, data_field: Callable, new_value, *, many: bool) -> None:
    """将 deny-filter 后的结果写回 response.data。

    仅覆盖常见 list / 直接列表两种结构；复杂嵌套由调用方自行处理。
    """
    data = response.data
    if many and isinstance(data, dict) and "list" in data and data_field(data) is data.get("list"):
        data["list"] = new_value
        if "count" in data and isinstance(data["count"], int):
            data["count"] = len(new_value)
        return
    if many and data_field(data) is data:
        response.data = new_value
        return
    if not many and data_field(data) is data:
        response.data = new_value
