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
from apm_web.decorators import user_visit_record
from apm_web.models import Application
from apm_web.trace.resources import (
    ApplyTraceComparisonResource,
    DeleteTraceComparisonResource,
    GetFieldOptionValuesResource,
    ListOptionValuesResource,
    ListServiceStatisticsResource,
    ListSpanHostInstancesResource,
    ListSpanResource,
    ListSpanStatisticsResource,
    ListStandardFilterFieldsResource,
    ListTraceComparisonResource,
    ListTraceResource,
    ListTraceViewConfigResource,
    SpanDetailResource,
    TraceChatsResource,
    TraceDetailResource,
    TraceDiagramResource,
    TraceListByHostInstanceResource,
    TraceListByIdResource,
    TraceOptionsResource,
    TraceStatisticsResource,
    UserCustomConfigResource,
)
from bkmonitor.iam import ActionEnum, ResourceEnum
from bkmonitor.iam.drf import InstanceActionForDataPermission
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class TraceQueryViewSet(ResourceViewSet):
    INSTANCE_ID = "app_name"

    def get_permissions(self):
        if self.action in ["trace_option_value", "trace_charts", "list_traces", "trace_detail"]:
            return [
                InstanceActionForDataPermission(
                    self.INSTANCE_ID,
                    [ActionEnum.VIEW_APM_APPLICATION],
                    ResourceEnum.APM_APPLICATION,
                    get_instance_id=Application.get_application_id_by_app_name,
                )
            ]
        return []

    resource_routes = [
        ResourceRoute(
            "POST",
            ListTraceResource,
            endpoint="list_traces",
            decorators=[
                user_visit_record,
            ],
        ),
        ResourceRoute(
            "POST",
            ListSpanResource,
            endpoint="list_spans",
            decorators=[
                user_visit_record,
            ],
        ),
        ResourceRoute(
            "POST",
            TraceStatisticsResource,
            endpoint="trace_statistics",
            decorators=[
                user_visit_record,
            ],
        ),
        ResourceRoute(
            "POST",
            TraceDiagramResource,
            endpoint="trace_diagram",
            decorators=[
                user_visit_record,
            ],
        ),
        ResourceRoute(
            "POST",
            TraceDetailResource,
            endpoint="trace_detail",
            decorators=[
                user_visit_record,
            ],
        ),
        ResourceRoute(
            "POST",
            SpanDetailResource,
            endpoint="span_detail",
            decorators=[
                user_visit_record,
            ],
        ),
        ResourceRoute(
            "POST",
            ListSpanStatisticsResource,
            endpoint="list_span_statistics",
            decorators=[
                user_visit_record,
            ],
        ),
        ResourceRoute(
            "POST",
            ListServiceStatisticsResource,
            endpoint="list_service_statistics",
            decorators=[
                user_visit_record,
            ],
        ),
        ResourceRoute("GET", TraceChatsResource, "trace_charts"),
        ResourceRoute("GET", TraceOptionsResource, "trace_options"),
        ResourceRoute("GET", ListStandardFilterFieldsResource, "standard_fields"),
        ResourceRoute("GET", ListTraceViewConfigResource, "view_config"),
        ResourceRoute("POST", ListOptionValuesResource, "list_option_values"),
        ResourceRoute("POST", GetFieldOptionValuesResource, "get_field_option_values"),
        ResourceRoute("POST", TraceListByIdResource, "trace_list_by_id"),
        ResourceRoute("POST", TraceListByHostInstanceResource, "trace_list_by_host_instance"),
        ResourceRoute("POST", ApplyTraceComparisonResource, "apply_trace_comparison"),
        ResourceRoute("POST", DeleteTraceComparisonResource, "delete_trace_comparison"),
        ResourceRoute("POST", ListTraceComparisonResource, "list_trace_comparison"),
        ResourceRoute("GET", ListSpanHostInstancesResource, "list_span_host_instances"),
        ResourceRoute("POST", UserCustomConfigResource, "user_custom_config"),
    ]
