# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import os

from blueapps.account.decorators import login_exempt
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.http import require_GET
from rest_framework.authentication import SessionAuthentication

from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission
from bkmonitor.middlewares.authentication import NoCsrfSessionAuthentication
from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet

SCHEMA_CONFIGS = {}


class AsCodeViewSet(ResourceViewSet):
    def get_authenticators(self):
        authenticators = super(AsCodeViewSet, self).get_authenticators()
        authenticators = [
            authenticator for authenticator in authenticators if not isinstance(authenticator, SessionAuthentication)
        ]
        authenticators.append(NoCsrfSessionAuthentication())
        return authenticators

    def get_permissions(self):
        if self.action == "import_config":
            return [BusinessActionPermission([ActionEnum.MANAGE_RULE, ActionEnum.MANAGE_NOTIFY_TEAM])]
        else:
            return [BusinessActionPermission([ActionEnum.VIEW_RULE, ActionEnum.VIEW_NOTIFY_TEAM])]

    resource_routes = [
        ResourceRoute("POST", resource.as_code.import_config, endpoint="import_config"),
        ResourceRoute("POST", resource.as_code.export_config, endpoint="export_config_json"),
        ResourceRoute("GET", resource.as_code.export_all_config_file, endpoint="export_config"),
        ResourceRoute("POST", resource.as_code.export_config_file, endpoint="export_config_file"),
        ResourceRoute("POST", resource.as_code.import_config_file, endpoint="import_config_file"),
    ]


@require_GET
@login_exempt
def schema(request, schema_type):
    if schema_type not in SCHEMA_CONFIGS:
        with open(os.path.join(settings.BASE_DIR, f"bkmonitor/as_code/json_schema/{schema_type}.json")) as f:
            SCHEMA_CONFIGS[schema_type] = f.read()
    return HttpResponse(content=SCHEMA_CONFIGS[schema_type], content_type="application/json")
