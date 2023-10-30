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
from apps.generic import APIViewSet
from apps.log_commons.exceptions import BaseCommonsException
from apps.log_commons.models import ExternalPermission, ExternalPermissionApplyRecord
from apps.log_commons.serializers import (
    CreateORUpdateExternalPermissionSLZ,
    DestroyExternalPermissionSLZ,
    GetApplyRecordSLZ,
    GetAuthorizerSLZ,
    GetResourceByActionSLZ,
    ListExternalPermissionSLZ,
)
from apps.utils.drf import list_route
from blueapps.account.decorators import login_exempt
from django.conf import settings
from django.http import JsonResponse
from django.utils.translation import ugettext_lazy as _
from rest_framework.response import Response

# 用户白皮书在文档中心的根路径
DOCS_USER_GUIDE_ROOT = "日志平台"

DOCS_LIST = ["产品白皮书", "应用运维文档", "开发架构文档"]

DEFAULT_DOC = DOCS_LIST[0]


@login_exempt
def get_docs_link(request):
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
        data = self.params_valid(ListExternalPermissionSLZ)
        return Response(ExternalPermission.list(**data))

    @list_route(methods=["get"], url_path="get_authorizer")
    def get_authorizer(self, request):
        data = self.params_valid(GetAuthorizerSLZ)
        return Response(ExternalPermission.get_authorizer(**data))

    @list_route(methods=["post"], url_path="create_or_update")
    def create_or_update(self, request):
        data = self.params_valid(CreateORUpdateExternalPermissionSLZ)
        return Response(ExternalPermission.create_or_update(validated_request_data=data))

    @list_route(methods=["get"], url_path="get_resource_by_action")
    def get_resource_by_action(self, request):
        data = self.params_valid(GetResourceByActionSLZ)
        return Response(ExternalPermission.get_resource_by_action(**data))

    @list_route(methods=["get"], url_path="get_apply_record")
    def get_apply_record(self, request):
        data = self.params_valid(GetApplyRecordSLZ)
        return Response(ExternalPermissionApplyRecord.list(**data))

    @list_route(methods=["post"], url_path="drop")
    def drop(self, request):
        data = self.params_valid(DestroyExternalPermissionSLZ)
        return Response(ExternalPermission.destroy(**data))
