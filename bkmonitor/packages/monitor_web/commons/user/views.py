"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json

from django.http import HttpResponse
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from core.drf_resource import api, resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class UserViewSet(viewsets.GenericViewSet):
    """
    模拟用户管理查询用户数据接口
    """

    permission_classes = []

    class RequestSerializer(serializers.Serializer):
        fuzzy_lookups = serializers.CharField(label="查询关键字", default="")
        page = serializers.IntegerField(label="限制数量", default=1)
        page_size = serializers.IntegerField(label="限制数量", default=20)
        fields = serializers.CharField(label="返回字段", default="id,display_name,username,logo")
        callback = serializers.CharField(label="json回调函数", required=False)

    def get_serializer_class(self):
        return self.RequestSerializer

    @action(methods=["GET"], detail=False)
    def list_users(self, request: Request):
        params = dict(request.query_params)
        params.pop("callback", None)
        params.pop("app_code", None)

        all_user_result = api.bk_login.get_all_user(**params)
        result = {
            "code": 0,
            "data": {
                "count": all_user_result["count"],
                "results": [
                    {
                        "username": user["username"],
                        "display_name": user["display_name"],
                        "logo": user["logo"],
                    }
                    for user in all_user_result["results"]
                ],
            },
            "result": True,
            "message": "success",
        }
        if "callback" in request.query_params:
            result_str = f"{request.query_params['callback']}({json.dumps(result)})"
            return HttpResponse(content=result_str, content_type="application/x-javascript")
        else:
            return Response(result)


class UserDepartmentsViewSet(ResourceViewSet):
    permission_classes = ()
    resource_routes = [
        ResourceRoute("GET", resource.commons.get_user_departments, endpoint="get_user_departments"),
        ResourceRoute("GET", resource.commons.list_departments, endpoint="departments_list"),
    ]
