"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from apm_web.models import Application
from apm_web.service.resources import (
    ApplicationListResource,
    AppQueryByIndexSetResource,
    CMDBServiceTemplateResource,
    LogServiceChoiceListResource,
    LogServiceRelationBkLogIndexSet,
    ServiceConfigResource,
    ServiceInfoResource,
    ServiceUrlListResource,
    UriregularVerifyResource,
    PipelineOverviewResource,
    ListPipelineResource,
    ListCodeRedefinedRuleResource,
    SetCodeRedefinedRuleResource,
    DeleteCodeRedefinedRuleResource,
    GetCodeRemarksResource,
    SetCodeRemarkResource,
)

from bkmonitor.iam import ActionEnum, ResourceEnum
from bkmonitor.iam.drf import InstanceActionForDataPermission, ViewBusinessPermission
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class ServiceViewSet(ResourceViewSet):
    INSTANCE_ID = "app_name"

    def get_permissions(self):
        if self.action in ["app_query_by_index_set"]:
            return []

        return [
            InstanceActionForDataPermission(
                self.INSTANCE_ID,
                [ActionEnum.VIEW_APM_APPLICATION],
                ResourceEnum.APM_APPLICATION,
                get_instance_id=Application.get_application_id_by_app_name,
            )
        ]

    resource_routes = [
        # 修改服务配置
        ResourceRoute("POST", ServiceConfigResource, "service_config"),
        # 获取服务配置
        ResourceRoute("POST", ServiceInfoResource, "service_info"),
        # 返回码重定义：查询/设置/删除
        ResourceRoute("POST", ListCodeRedefinedRuleResource, "list_code_redefined_rule"),
        ResourceRoute("POST", SetCodeRedefinedRuleResource, "set_code_redefined_rule"),
        ResourceRoute("POST", DeleteCodeRedefinedRuleResource, "delete_code_redefined_rule"),
        # 返回码备注：获取/设置
        ResourceRoute("POST", GetCodeRemarksResource, "get_code_remarks"),
        ResourceRoute("POST", SetCodeRemarkResource, "set_code_remark"),
        ResourceRoute("POST", CMDBServiceTemplateResource, "cmdb_service_template"),
        ResourceRoute("POST", LogServiceChoiceListResource, "log_service_relation_choices"),
        ResourceRoute("POST", AppQueryByIndexSetResource, "app_query_by_index_set"),
        ResourceRoute("POST", UriregularVerifyResource, "uri_regular"),
        ResourceRoute("POST", ServiceUrlListResource, "service_url_list"),
        ResourceRoute("POST", PipelineOverviewResource, "pipeline_overview"),
        ResourceRoute("POST", ListPipelineResource, "list_pipeline"),
    ]


class ApplicationViewSet(ResourceViewSet):
    INSTANCE_ID = "bk_biz_id"

    def get_permissions(self):
        return [ViewBusinessPermission()]

    resource_routes = [
        ResourceRoute("POST", ApplicationListResource, "application_list"),
        ResourceRoute("POST", LogServiceRelationBkLogIndexSet, "log_service_relation_bk_log_index_set"),
    ]
