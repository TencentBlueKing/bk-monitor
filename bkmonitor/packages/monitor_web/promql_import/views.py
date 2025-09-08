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
from monitor_web.grafana.permissions import GrafanaWritePermission

from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission, ViewBusinessPermission
from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet

SCHEMA_CONFIGS = {}


class PromqlImportViewSet(ResourceViewSet):
    def get_permissions(self):
        if self.action in ["import_grafana_dashboard"]:
            return [GrafanaWritePermission()]
        elif self.action in ["import_alert_rule"]:
            return [BusinessActionPermission([ActionEnum.MANAGE_RULE])]
        return [ViewBusinessPermission()]

    resource_routes = [
        # 创建迁移规则
        ResourceRoute("POST", resource.promql_import.create_mapping_config, endpoint="create_mapping_config"),
        # 获取迁移规则
        ResourceRoute("POST", resource.promql_import.get_mapping_config, endpoint="get_mapping_config"),
        # 删除迁移规则
        ResourceRoute("POST", resource.promql_import.delete_mapping_config, endpoint="delete_mapping_config"),
        # 导入grafana配置
        ResourceRoute("POST", resource.promql_import.import_grafana_dashboard, endpoint="import_grafana_dashboard"),
        # 导入策略配置
        ResourceRoute("POST", resource.promql_import.import_alert_rule, endpoint="import_alert_rule"),
        # 上传文件入口
        ResourceRoute("POST", resource.promql_import.upload_file, endpoint="upload_file"),
    ]
