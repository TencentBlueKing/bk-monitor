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
from typing import List

from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views.decorators.cache import cache_control
from drf_yasg.utils import swagger_auto_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.serializers import Serializer

from core.drf_resource.base import Resource

"""
Resource的ViewSet定义
"""


class ResourceRoute(object):
    """
    Resource的视图配置，应用于viewsets
    """

    def __init__(
        self,
        method,
        resource_class,
        endpoint="",
        pk_field=None,
        enable_paginate=False,
        content_encoding=None,
        decorators=None,
    ):
        """
        :param method: 请求方法，目前仅支持GET和POST
        :param resource_class: 所用到的Resource类
        :param endpoint: 端点名称，不提供则为list或create
        :param pk_field: 主键名称，如果不为空，则该视图为 detail route
        :param enable_paginate: 是否对结果进行分页
        :param content_encoding: 返回数据内容编码类型
        :params decorators: 给view_func添加的装饰器列表
        """
        # if method.upper() not in ["GET", "POST"]:
        #     raise ValueError(_("method参数错误，目前仅支持GET或POST方法"))

        self.method = method.upper()

        if isinstance(resource_class, Resource):
            resource_class = resource_class.__class__
        if not issubclass(resource_class, Resource):
            raise ValueError(_("resource_class参数必须提供Resource的子类, 当前类型: %s" % resource_class))

        self.resource_class = resource_class

        self.endpoint = endpoint

        self.enable_paginate = enable_paginate

        self.content_encoding = content_encoding

        self.pk_field = pk_field

        self.decorators = decorators


class ResourceViewSet(viewsets.GenericViewSet):
    EMPTY_ENDPOINT_METHODS = {
        "GET": "list",
        "POST": "create",
        "PUT": "update",
        "PATCH": "partial_update",
        "DELETE": "destroy",
    }

    # 用于执行请求的Resource类
    resource_routes: List[ResourceRoute] = []
    filter_backends = []
    pagination_class = None
    resource_mapping = {}

    def get_serializer_class(self):
        """
        获取序列化器
        """
        serializer_class = None
        for route in self.resource_routes:
            if self.action == route.endpoint:
                serializer_class = route.resource_class.RequestSerializer
                break

        if not serializer_class:
            serializer_class = Serializer

        class Meta:
            ref_name = None

        # 如果serializer_class没有Meta属性，则添加Meta属性
        if not getattr(serializer_class, "Meta", None):
            serializer_class.Meta = Meta

        return serializer_class

    def get_queryset(self):
        """
        添加默认函数，避免swagger生成报错
        """
        return

    @classmethod
    def generate_endpoint(cls):
        if issubclass(cls, ResourceViewSet):
            view_set_path = f"{cls.__module__}.{cls.__name__}"
        else:
            view_set_path = f"{type(cls).__module__}.{type(cls).__name__}"

        for resource_route in cls.resource_routes:
            # 生成方法模版
            function = cls._generate_function_template(resource_route)

            # 配置swagger装饰器
            request_serializer_class = resource_route.resource_class.RequestSerializer or Serializer
            request_serializer = request_serializer_class(many=resource_route.resource_class.many_request_data)
            response_serializer_class = resource_route.resource_class.ResponseSerializer or Serializer
            response_serializer = response_serializer_class(many=resource_route.resource_class.many_response_data)
            decorator_function = swagger_auto_schema(
                responses={200: response_serializer},
                operation_description=resource_route.resource_class.__doc__,
                query_serializer=request_serializer if resource_route.method == "GET" else None,
            )

            # 添加装饰器
            if resource_route.decorators:
                for decorator in resource_route.decorators:
                    function = decorator(function)

            # 为Viewset设置方法
            if not resource_route.endpoint:
                function = decorator_function(function)
                # 默认方法无需加装饰器，否则会报错
                if resource_route.method == "GET":
                    if resource_route.pk_field:
                        cls.retrieve = function
                    else:
                        cls.list = function
                elif resource_route.method == "POST":
                    if resource_route.pk_field:
                        raise AssertionError(_("当请求方法为 %s，且 endpoint 为空时，禁止设置 pk_field 参数") % resource_route.method)
                    cls.create = function
                elif resource_route.method in cls.EMPTY_ENDPOINT_METHODS:
                    if not resource_route.pk_field:
                        raise AssertionError(_("当请求方法为 %s，且 endpoint 为空时，必须提供 pk_field 参数") % resource_route.method)
                    setattr(cls, cls.EMPTY_ENDPOINT_METHODS[resource_route.method], function)
                else:
                    raise AssertionError(_("不支持的请求方法: %s，请确认resource_routes配置是否正确!") % resource_route.method)

                cls.resource_mapping[
                    (resource_route.method, f"{view_set_path}-{cls.EMPTY_ENDPOINT_METHODS[resource_route.method]}")
                ] = resource_route.resource_class
            else:
                function.__name__ = (
                    f"api_func_{resource_route.endpoint}"
                    if resource_route.endpoint == "detail"
                    else resource_route.endpoint
                )
                function = method_decorator(cache_control(max_age=0, private=True))(function)
                function = action(
                    detail=bool(resource_route.pk_field),
                    methods=[resource_route.method],
                    url_path=resource_route.endpoint,
                    url_name=resource_route.endpoint.replace("_", "-"),
                )(function)

                function = decorator_function(function)
                setattr(cls, function.__name__, function)
                cls.resource_mapping[
                    (resource_route.method, f"{view_set_path}-{resource_route.endpoint}")
                ] = resource_route.resource_class

    @classmethod
    def _generate_function_template(cls, resource_route: ResourceRoute):
        """
        生成方法模版
        """

        def template(self, request, *args, **kwargs):
            resource = resource_route.resource_class()
            params = request.query_params.copy() if resource_route.method == "GET" else request.data

            if resource_route.pk_field:
                # 如果是detail route，需要重url参数中获取主键，并塞到请求参数中
                params.update({resource_route.pk_field: kwargs[cls.lookup_field]})

            is_async_task = "HTTP_X_ASYNC_TASK" in request.META
            if is_async_task:
                # 执行异步任务
                data = resource.delay(params)
                response = Response(data)
            else:
                data = resource.request(params)
                if isinstance(data, HttpResponse):
                    return data
                if resource_route.enable_paginate:
                    page = self.paginate_queryset(data)
                    response = self.get_paginated_response(page)
                else:
                    response = Response(data)
            if resource_route.content_encoding:
                response.content_encoding = resource_route.content_encoding
            return response

        template.__name__ = resource_route.endpoint
        return template
