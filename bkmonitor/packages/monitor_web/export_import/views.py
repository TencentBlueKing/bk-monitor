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
from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission
from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class ExportImportViewSet(ResourceViewSet):
    def get_permissions(self):
        if self.action in ["get_all_config_list", "export_package"]:
            return [BusinessActionPermission([ActionEnum.EXPORT_CONFIG])]
        if self.action in ["upload_package"]:
            # 仅用于解析配置，无需鉴权
            return []
        return [BusinessActionPermission([ActionEnum.IMPORT_CONFIG])]

    resource_routes = [
        # 获取所有采集配置、策略配置、视图配置列表
        ResourceRoute("GET", resource.export_import.get_all_config_list, endpoint="get_all_config_list"),
        # 导出配置文件包
        ResourceRoute("POST", resource.export_import.export_package, endpoint="export_package"),
        # 查看导入历史列表
        ResourceRoute("GET", resource.export_import.history_list, endpoint="history_list"),
        # 查看历史详情
        ResourceRoute("GET", resource.export_import.history_detail, endpoint="history_detail"),
        # 上传文件包
        ResourceRoute("POST", resource.export_import.upload_package, endpoint="upload_package"),
        # 配置导入
        ResourceRoute("POST", resource.export_import.import_config, endpoint="import_config"),
        # 添加统一监控目标
        ResourceRoute("POST", resource.export_import.add_monitor_target, endpoint="add_monitor_target"),
        # 导出配置到指定业务
        ResourceRoute("POST", resource.export_import.export_config_to_business, endpoint="export_config_to_business"),
    ]
