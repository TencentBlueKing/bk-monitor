# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.http import JsonResponse
from django.utils.translation import ugettext_lazy as _
from rest_framework.views import APIView

from apm_web.decorators import user_visit_record
from apm_web.log.resources import ServiceLogInfoResource, ServiceRelationListResource
from apm_web.models import Application
from bkmonitor.iam import ActionEnum, ResourceEnum
from bkmonitor.iam.drf import InstanceActionForDataPermission
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class LogViewSet(ResourceViewSet):
    INSTANCE_ID = "app_name"

    def get_permissions(self):
        return [
            InstanceActionForDataPermission(
                self.INSTANCE_ID,
                [ActionEnum.VIEW_APM_APPLICATION],
                ResourceEnum.APM_APPLICATION,
                get_instance_id=Application.get_application_id_by_app_name,
            )
        ]

    resource_routes = [
        ResourceRoute("POST", ServiceLogInfoResource, endpoint="log_relation"),
        ResourceRoute(
            "POST",
            ServiceRelationListResource,
            endpoint="log_relation_list",
            decorators=[
                user_visit_record,
            ],
        ),
    ]


class BkLogForwardingView(APIView):
    """转发请求到日志平台"""

    def dispatch(self, request, *args, **kwargs):

        target_url = urljoin(settings.BKLOGSEARCH_HOST, request.path.split('bklog')[-1])

        try:
            response = requests.request(
                method=request.method,
                url=target_url,
                headers=request.headers,
                data=request.body if request.body else None,
                allow_redirects=False,
            )
            return JsonResponse(response.json(), status=response.status_code)
        except Exception as e:  # noqa
            return JsonResponse({'message': _("请求日志平台接口错误: ") + str(e)}, status=500)
