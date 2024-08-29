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
from apm_web.models import Application
from apm_web.topo.resources import (
    DataTypeBarQueryResource,
    NodeRelationResource,
    TopoViewResource,
)
from bkmonitor.iam import ActionEnum, ResourceEnum
from bkmonitor.iam.drf import InstanceActionForDataPermission
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class GlobalViewSet(ResourceViewSet):
    """
    全局拓扑视图
    """

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
        ResourceRoute("GET", DataTypeBarQueryResource, endpoint="bar"),
        ResourceRoute("GET", TopoViewResource, endpoint="topo"),
        ResourceRoute("GET", NodeRelationResource, endpoint="relation"),
    ]
