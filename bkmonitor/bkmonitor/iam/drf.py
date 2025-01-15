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

from typing_extensions import Literal

from bkmonitor.utils.thread_backend import ThreadPool

"""
DRF 插件
"""
from functools import wraps
from typing import Callable, List, Optional

from iam import Resource
from rest_framework import permissions

from core.errors.iam import PermissionDeniedError

from . import Permission
from .action import ActionEnum, ActionMeta
from .resource import ResourceEnum, ResourceMeta

logger = logging.getLogger("apm")


class IAMPermission(permissions.BasePermission):
    def __init__(self, actions: List[ActionMeta], resources: List[Resource] = None):
        self.actions = actions
        self.resources = resources or []

    def has_permission(self, request, view):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        if not self.actions:
            return True

        client = Permission()
        for index, action in enumerate(self.actions):
            try:
                client.is_allowed(
                    action=action,
                    resources=self.resources,
                    raise_exception=True,
                )
            except PermissionDeniedError as e:
                # 最后一个异常才抛出，否则不处理
                if index == len(self.actions) - 1:
                    raise e
            else:
                # 没抛出异常，则鉴权通过
                return True
        return True

    def has_object_permission(self, request, view, obj):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        return self.has_permission(request, view)


class BusinessActionPermission(IAMPermission):
    """
    关联业务的动作权限检查
    """

    def __init__(self, actions: List[ActionMeta]):
        super(BusinessActionPermission, self).__init__(actions)

    def has_permission(self, request, view):
        if not request.biz_id:
            return True
        self.resources = [ResourceEnum.BUSINESS.create_instance(request.biz_id)]
        return super(BusinessActionPermission, self).has_permission(request, view)

    def has_object_permission(self, request, view, obj):
        # 先查询对象中有没有业务ID相关属性
        bk_biz_id = None
        if hasattr(obj, "bk_biz_id"):
            bk_biz_id = obj.bk_biz_id
        if bk_biz_id:
            self.resources = [ResourceEnum.BUSINESS.create_instance(bk_biz_id)]
            return super(BusinessActionPermission, self).has_object_permission(request, view, obj)
        # 没有就尝试取请求的业务ID
        return self.has_permission(request, view)


class ViewBusinessPermission(BusinessActionPermission):
    """
    业务访问权限检查
    """

    def __init__(self):
        super(ViewBusinessPermission, self).__init__([ActionEnum.VIEW_BUSINESS])


class InstanceActionPermission(IAMPermission):
    """
    关联其他资源的权限检查
    """

    def __init__(self, actions: List[ActionMeta], resource_meta: ResourceMeta):
        self.resource_meta = resource_meta
        super(InstanceActionPermission, self).__init__(actions)

    def has_permission(self, request, view):
        instance_id = view.kwargs[self.get_look_url_kwarg(view)]
        resource = self.resource_meta.create_instance(instance_id)
        self.resources = [resource]
        return super(InstanceActionPermission, self).has_permission(request, view)

    def get_look_url_kwarg(self, view):
        # Perform the lookup filtering.
        lookup_url_kwarg = view.lookup_url_kwarg or view.lookup_field

        assert lookup_url_kwarg in view.kwargs, (
            "Expected view %s to be called with a URL keyword argument "
            'named "%s". Fix your URL conf, or set the `.lookup_field` '
            "attribute on the view correctly." % (self.__class__.__name__, lookup_url_kwarg)
        )
        return lookup_url_kwarg


class InstanceActionForDataPermission(InstanceActionPermission):
    def __init__(
        self,
        iam_instance_id_key,
        *args,
        get_instance_id: Callable = lambda _id: _id,
    ):
        self.iam_instance_id_key = iam_instance_id_key
        self.get_instance_id = get_instance_id
        super(InstanceActionForDataPermission, self).__init__(*args)

    def has_permission(self, request, view):
        if request.method == "GET":
            data = request.query_params
        else:
            data = request.data
        instance_id = data.get(self.iam_instance_id_key) or view.kwargs.get(self.get_look_url_kwarg(view))
        if instance_id is None:
            raise ValueError("instance_id must have")
        resource = self.resource_meta.create_instance(self.get_instance_id(instance_id))
        self.resources = [resource]
        return super(InstanceActionPermission, self).has_permission(request, view)


def insert_permission_field(
    actions: List[ActionMeta],
    resource_meta: ResourceMeta,
    id_field: Callable = lambda item: item["id"],
    data_field: Callable = lambda data_list: data_list,
    always_allowed: Callable = lambda item: False,
    many: bool = True,
    instance_create_func: Optional[Callable[[dict], Resource]] = None,
    batch_create: bool = False,
):
    """
    数据返回后，插入权限相关字段
    :param actions: 动作列表
    :param resource_meta: 资源类型
    :param id_field: 从结果集获取ID字段的方式
    :param data_field: 从response.data中获取结果集的方式
    :param instance_create_func: 自定义创建资源实例的函数
    :param always_allowed: 满足一定条件进行权限豁免
    :param many: 是否为列表数据
    :param batch_create: 是否批量创建资源实例
    """

    def wrapper(view_func):
        @wraps(view_func)
        def wrapped_view(*args, **kwargs):
            response = view_func(*args, **kwargs)

            result_list = data_field(response.data)
            if not many:
                result_list = [result_list]

            if batch_create:
                resources = batch_create_instance(result_list, resource_meta, id_field, instance_create_func)
            else:
                resources = []
                for item in result_list:
                    if not id_field(item):
                        continue
                    attribute = extract_attribute(item)

                    if instance_create_func:
                        resources.append([instance_create_func(item)])
                    else:
                        resources.append(
                            [resource_meta.create_simple_instance(instance_id=id_field(item), attribute=attribute)]
                        )

            if not resources:
                return response

            permission_result = Permission().batch_is_allowed(actions, resources)

            for item in result_list:
                origin_instance_id = id_field(item)
                if not origin_instance_id:
                    # 如果拿不到实例ID，则不处理
                    continue
                instance_id = str(origin_instance_id)
                item.setdefault("permission", {})
                item["permission"].update(permission_result[instance_id])

                if always_allowed(item):
                    # 权限豁免
                    for action_id in item["permission"]:
                        item["permission"][action_id] = True

            return response

        return wrapped_view

    return wrapper


def batch_create_instance(
    result_list: list,
    resource_meta: ResourceMeta,
    id_field: Callable = lambda item: item["id"],
    instance_create_func: Optional[Callable[[dict], Resource]] = None,
):
    """
    批量创建实例
    :param result_list: 结果列表
    :param resource_meta: 资源类型
    :param id_field: 从结果集获取ID字段的方式
    :param instance_create_func: 自定义创建资源实例的函数
    """
    resources = []
    futures = []
    pool = ThreadPool()
    for item in result_list:
        if not id_field(item):
            continue
        attribute = extract_attribute(item)
        if instance_create_func:
            future = futures.append(pool.apply_async(instance_create_func, kwds=item))
        else:
            kwargs = {"instance_id": id_field(item), "attribute": attribute}
            future = futures.append(pool.apply_async(resource_meta.create_simple_instance, kwds=kwargs))
        futures.append(future)

    for future in futures:
        try:
            resources.append([future.get()])
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"[APM] batch_create_instance error: {e}")

    return resources


def extract_attribute(item):
    attribute = {}
    if "bk_biz_id" in item:
        attribute["bk_biz_id"] = item["bk_biz_id"]
    if "space_uid" in item:
        attribute["space_uid"] = item["space_uid"]
    return attribute


def filter_data_by_permission(
    data: List[dict],
    actions: List[ActionMeta],
    resource_meta: ResourceMeta,
    id_field: Callable[[dict], str] = lambda item: item["id"],
    always_allowed: Callable[[dict], bool] = lambda item: False,
    instance_create_func: Optional[Callable[[dict], Resource]] = None,
    mode: Literal["any", "all", "insert"] = "any",
) -> List[dict]:
    """
    根据权限过滤数据
    :param mode: 过滤模式，"any" 表示只要有一个权限通过就返回，"all" 表示所有权限通过才返回, "insert" 表示插入权限信息，但不过滤数据
    """
    resources = batch_create_instance(data, resource_meta, id_field, instance_create_func)
    if not resources:
        return []

    # 批量鉴权
    permission_result = Permission().batch_is_allowed(actions, resources)

    allowed_data = []
    for item in data:
        # 获取实例ID
        origin_instance_id = id_field(item)
        if not origin_instance_id:
            continue
        instance_id = str(origin_instance_id)

        # 插入权限信息
        if mode == "insert":
            item["permission"] = permission_result[instance_id]
            if always_allowed(item):
                for action_id in item["permission"]:
                    item["permission"][action_id] = True
            allowed_data.append(item)
            continue

        # 过滤数据
        if mode == "any":
            filter_func = any
        else:
            filter_func = all

        if always_allowed(item) or filter_func(permission_result[instance_id].values()):
            allowed_data.append(item)

    return allowed_data
