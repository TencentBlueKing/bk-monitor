"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from apm_web.custom_metric.resources import (
    ApmCreateOrUpdateGroupingRule,
    ApmCustomTsGroupingRuleList,
    ApmDeleteGroupingRule,
    ApmExportCustomTimeSeriesFields,
    ApmGetCustomTsFields,
    ApmImportCustomTimeSeriesFields,
    ApmModifyCustomTsFields,
    ApmPreviewGroupingRule,
)
from apm_web.decorators import user_visit_record
from apm_web.models import Application
from bkmonitor.iam import ActionEnum, ResourceEnum
from bkmonitor.iam.drf import InstanceActionForDataPermission
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class CustomMetricViewSet(ResourceViewSet):
    """APM 自定义指标接口"""

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
        ResourceRoute(
            "GET",
            ApmGetCustomTsFields,
            endpoint="get_custom_ts_fields",
            decorators=[user_visit_record],
        ),
        ResourceRoute(
            "POST",
            ApmModifyCustomTsFields,
            endpoint="modify_custom_ts_fields",
            decorators=[user_visit_record],
        ),
        ResourceRoute(
            "GET",
            ApmCustomTsGroupingRuleList,
            endpoint="custom_ts_grouping_rule_list",
            decorators=[user_visit_record],
        ),
        ResourceRoute(
            "POST",
            ApmCreateOrUpdateGroupingRule,
            endpoint="create_or_update_grouping_rule",
            decorators=[user_visit_record],
        ),
        ResourceRoute(
            "POST",
            ApmPreviewGroupingRule,
            endpoint="preview_grouping_rule",
            decorators=[user_visit_record],
        ),
        ResourceRoute(
            "POST",
            ApmDeleteGroupingRule,
            endpoint="delete_grouping_rule",
            decorators=[user_visit_record],
        ),
        ResourceRoute(
            "POST",
            ApmImportCustomTimeSeriesFields,
            endpoint="import_custom_time_series_fields",
            decorators=[user_visit_record],
        ),
        ResourceRoute(
            "GET",
            ApmExportCustomTimeSeriesFields,
            endpoint="export_custom_time_series_fields",
            decorators=[user_visit_record],
        ),
    ]
