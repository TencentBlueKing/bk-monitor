# -*- coding: utf-8 -*-
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
import time

import requests
from blueapps.account.decorators import login_exempt
from django.conf import settings
from django.http import JsonResponse
from django.utils.translation import gettext_lazy as _
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.api import BKLoginApi
from apps.constants import ExternalPermissionActionEnum
from apps.generic import APIViewSet
from apps.log_commons.cc import get_maintainers
from apps.log_commons.exceptions import BaseCommonsException
from apps.log_commons.models import (
    AuthorizerSettings,
    ExternalPermission,
    ExternalPermissionApplyRecord,
)
from apps.log_commons.serializers import (
    CreateORUpdateExternalPermissionSLZ,
    CreateORUpdateMaintainersSLZ,
    DestroyExternalPermissionSLZ,
    FrontendEventSerializer,
    GetApplyRecordSLZ,
    GetAuthorizerSLZ,
    GetResourceByActionSLZ,
    ListExternalPermissionSLZ,
    ListMaintainersSLZ,
)
from apps.utils.drf import list_route

# 用户白皮书在文档中心的根路径
DOCS_USER_GUIDE_ROOT = "日志平台"

DOCS_LIST = ["产品白皮书", "应用运维文档", "开发架构文档"]

DEFAULT_DOC = DOCS_LIST[0]


@login_exempt
def get_docs_link(request):
    if settings.BK_DOC_STATIC_URL:
        return JsonResponse({"result": True, "code": 0, "message": "OK", "data": settings.BK_DOC_STATIC_URL})

    md_path = request.GET.get("md_path", "").strip("/")
    if not md_path:
        e = BaseCommonsException(_("md_path参数不能为空"))
        return JsonResponse({"result": False, "code": e.code, "message": str(e)})

    docs_list = [str(i) for i in DOCS_LIST]
    if md_path.split("/", 1)[0] in docs_list:
        if not md_path.startswith(DOCS_USER_GUIDE_ROOT):
            md_path = "/".join([DOCS_USER_GUIDE_ROOT, md_path])
    else:
        md_path = "/".join([DOCS_USER_GUIDE_ROOT, DEFAULT_DOC, md_path])

    doc_url = f"{settings.BK_DOC_URL.rstrip('/')}/markdown/{md_path.lstrip('/')}"
    return JsonResponse({"result": True, "code": 0, "message": "OK", "data": doc_url})


class ExternalPermissionViewSet(APIViewSet):
    def list(self, request):
        """
        @api {get} /external_permission/ 获取外部权限列表
        @apiName external_permission_list
        @apiGroup external_permission
        @apiParam {String} [space_uid] 空间ID
        @apiParam {String} [view_type] 视角, 枚举值: user, resource, default: user
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "code": 0,
            "message": "",
            "data": [
                {
                    "authorized_user": "external_user_1",
                    "space_uid": "space_uid",
                    "action_id": "log_search",
                    "resources": [
                        1,2,3,4
                    ],
                    "expire_time": "2024-10-25 01:22:50",
                    "authorizer": "authorizer_1",
                    "space_name": "space_name"
                },
            ]
        }
        """
        data = self.params_valid(ListExternalPermissionSLZ)
        return Response(ExternalPermission.list(**data))

    @list_route(methods=["get"], url_path="action")
    def list_action(self, request):
        """
        @api {get} /external_permission/action/ 获取操作类型枚举
        @apiName external_permission_list_action
        @apiGroup external_permission
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": [
                {
                    "id": "log_search",
                    "name": "日志检索"
                },
                {
                    "id": "log_extract",
                    "name": "日志提取"
                }
            ],
            "code": 0,
            "message": ""
        }
        """
        return Response(ExternalPermissionActionEnum.get_choices_list_dict())

    @list_route(methods=["get"], url_path="authorizer")
    def get_authorizer(self, request):
        """
        @api {get} /external_permission/authorizer/ 获取授权者
        @apiName external_permission_authorizer
        @apiGroup external_permission
        @apiParam {String} space_uid 空间ID
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": "authorizer_1",
            "code": 0,
            "message": ""
        }
        """
        data = self.params_valid(GetAuthorizerSLZ)
        return Response(ExternalPermission.get_authorizer(**data))

    @list_route(methods=["get"], url_path="get_maintainer")
    def list_maintainers(self, request):
        """
        @api {get} /external_permission/get_maintainer/ 获取运维人员
        @apiName external_permission_maintainer
        @apiGroup external_permission
        @apiParam {String} space_uid 空间ID
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": [
                "maintainer_1",
                "maintainer_2"
            ],
            "code": 0,
            "message": ""
        }
        """
        data = self.params_valid(ListMaintainersSLZ)
        return Response(get_maintainers(**data))

    @list_route(methods=["post"], url_path="maintainer")
    def create_or_update_maintainers(self, request):
        """
        @api {post} /external_permission/maintainer/ 修改运维人员
        @apiName external_permission_maintainer
        @apiGroup external_permission
        @apiParam {String} space_uid 空间ID
        @apiParam {String} maintainer 运维人员
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": "maintainer",
            "code": 0,
            "message": ""
        }
        """
        data = self.params_valid(CreateORUpdateMaintainersSLZ)
        return Response(AuthorizerSettings.create_or_update(**data))

    @list_route(methods=["post"], url_path="create_or_update")
    def create_or_update(self, request):
        """
        @api {post} /external_permission/create_or_update/ 创建或更新外部权限
        @apiName external_permission_create_or_update
        @apiGroup external_permission
        @apiParam {String} authorized_users 被授权人
        @apiParam {String} view_type 视角类型, 枚举值: user, resource, default: user
        @apiParam {String} operate_type 操作类型, 枚举值: create, update, default: create
        @apiParam {String} space_uid 空间ID
        @apiParam {String} action_id 操作类型
        @apiParam {List} resources 资源列表
        @apiParam {String} expire_time 过期时间
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "code": 0,
            "message": "",
            "data": {"need_approval": True}
        }
        """
        data = self.params_valid(CreateORUpdateExternalPermissionSLZ)
        return Response(ExternalPermission.create_or_update(validated_request_data=data))

    @list_route(methods=["get"], url_path="resource_by_action")
    def get_resource_by_action(self, request):
        """
        @api {get} /external_permission/resource_by_action/ 获取操作类型对应的资源列表
        @apiName external_permission_resource_by_action
        @apiGroup external_permission
        @apiParam {String} space_uid 空间ID
        @apiParam {String} action_id 操作类型
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": [
                "resource_id": 1,
                "resource_name": "x"
            ],
            "code": 0,
            "message": ""
        }
        """
        data = self.params_valid(GetResourceByActionSLZ)
        return Response(ExternalPermission.get_resource_by_action(**data))

    @list_route(methods=["get"], url_path="apply_record")
    def get_apply_record(self, request):
        """
        @api {get} /external_permission/apply_record/ 获取申请记录
        @apiName external_permission_apply_record
        @apiGroup external_permission
        @apiParam {String} space_uid 空间ID
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": [
                {
                    "authorized_users": "external_user_1, external_user_2",
                    "space_uid": "space_uid",
                    "action_id": "log_search",
                    "resources": [
                        1,2,3,4
                    ],
                    "expire_time": "2024-10-25 01:22:50",
                    "authorizer": "authorizer_1",
                    "status": "pending",
                    "approval_sn": "approval_sn_1",
                    "approval_url": "approval_url_1",
                },
            ],
            "code": 0,
            "message": ""
        }
        """
        data = self.params_valid(GetApplyRecordSLZ)
        return Response(ExternalPermissionApplyRecord.list(**data))

    @list_route(methods=["post"], url_path="drop")
    def drop(self, request):
        """
        @api {post} /external_permission/drop/ 删除外部权限
        @apiName external_permission_drop
        @apiGroup external_permission
        @apiParam {String} space_uid 空间ID
        @apiParam {String} action_id 操作类型
        @apiParam {List} resources 资源列表
        @apiParam {String} authorized_users 被授权人
        @apiParam {String} view_type 视角类型, 枚举值: user, resource, default: user
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "code": 0,
            "message": "",
            "data": {"delete_permission_ids": [1,2,3]}
        }
        """
        data = self.params_valid(DestroyExternalPermissionSLZ)
        return Response(ExternalPermission.destroy(validated_request_data=data))


class FrontendEventViewSet(APIViewSet):
    @action(detail=False, methods=["POST"], url_path="report")
    def report(self, request):
        params = self.params_valid(FrontendEventSerializer)
        if not settings.FRONTEND_REPORT_DATA_ID or not settings.FRONTEND_REPORT_DATA_TOKEN:
            return Response("report config does not set")

        host = settings.FRONTEND_REPORT_DATA_URL or settings.BKMONITOR_CUSTOM_PROXY_IP
        if not host:
            return Response("report config does not set")

        url = f"{host}/v2/push/"

        username = params["dimensions"]["user_name"]
        info = BKLoginApi.list_department_profiles({"id": username, "with_family": True})
        dept = info[0]
        family = dept["family"]
        departments = []
        for f in family:
            departments.append(f["name"])
        departments.append(dept["name"])
        # 当前组织架构暂定层级5
        while len(departments) < 5:
            departments.append("")

        for index, dept in enumerate(departments):
            params["dimensions"][f"department_{index}"] = dept
        params["dimensions"]["app_code"] = "bklog"
        params["target"] = settings.ENVIRONMENT_CODE
        report_data = {
            "data_id": int(settings.FRONTEND_REPORT_DATA_ID),
            "access_token": settings.FRONTEND_REPORT_DATA_TOKEN,
            "data": [
                {
                    "dimension": params["dimensions"],
                    "event_name": params["event_name"],
                    "event": {"content": params["event_content"]},
                    "target": params["target"],
                    "timestamp": params.get("timestamp", int(time.time() * 1000)),
                }
            ],
        }
        r = requests.post(url, json=report_data, timeout=3)
        return Response(r.json())
