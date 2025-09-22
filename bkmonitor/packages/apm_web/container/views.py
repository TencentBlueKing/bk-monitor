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
from apm_web.container.resources import ListServicePodsResource, PodDetailResource
from apm_web.decorators import user_visit_record
from apm_web.models import Application
from bkmonitor.iam import ActionEnum, ResourceEnum
from bkmonitor.iam.drf import BusinessActionPermission, InstanceActionForDataPermission
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class K8sViewSet(ResourceViewSet):
    """APM K8S 接口"""

    INSTANCE_ID = "app_name"

    def get_permissions(self):
        if self.action in ["pod_detail"]:
            return [BusinessActionPermission([ActionEnum.VIEW_BUSINESS])]

        return [
            InstanceActionForDataPermission(
                self.INSTANCE_ID,
                [ActionEnum.VIEW_APM_APPLICATION],
                ResourceEnum.APM_APPLICATION,
                get_instance_id=Application.get_application_id_by_app_name,
            )
        ]

    resource_routes = [
        ResourceRoute(
            "POST",
            ListServicePodsResource,
            endpoint="list_service_pods",
            decorators=[user_visit_record],
        ),
        ResourceRoute("POST", PodDetailResource, "pod_detail"),
    ]
