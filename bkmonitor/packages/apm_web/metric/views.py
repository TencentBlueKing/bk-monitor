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
from apm_web.metric.resources import (
    AlertQueryResource,
    ApdexQueryResource,
    CollectServiceResource,
    DynamicUnifyQueryResource,
    EndpointDetailListResource,
    EndpointListResource,
    ErrorListByTraceIdsResource,
    ErrorListResource,
    ExceptionDetailListResource,
    HostInstanceDetailListResource,
    InstanceListResource,
    MetricDetailStatisticsResource,
    ServiceInstancesResource,
    ServiceListAsyncResource,
    ServiceListResource,
    ServiceQueryExceptionResource,
    TopNQueryResource,
    UnifyQueryResource,
)
from apm_web.models import Application
from bkmonitor.iam import ActionEnum, ResourceEnum
from bkmonitor.iam.drf import BusinessActionPermission, InstanceActionForDataPermission
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class MetricEventViewSet(ResourceViewSet):
    """告警中心APM接口"""

    def get_permissions(self):
        return [BusinessActionPermission([ActionEnum.VIEW_EVENT])]

    resource_routes = [
        ResourceRoute("POST", ErrorListByTraceIdsResource, "error_list_by_trace_ids"),
    ]


class MetricViewSet(ResourceViewSet):
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
            "POST",
            ServiceListResource,
            endpoint="service_list",
            decorators=[
                user_visit_record,
            ],
        ),
        ResourceRoute(
            "POST",
            ServiceInstancesResource,
            endpoint="service_instances",
            decorators=[
                user_visit_record,
            ],
        ),
        ResourceRoute(
            "POST",
            ErrorListResource,
            endpoint="error_list",
            decorators=[
                user_visit_record,
            ],
        ),
        ResourceRoute(
            "POST",
            EndpointListResource,
            endpoint="endpoint_list",
            decorators=[
                user_visit_record,
            ],
        ),
        ResourceRoute(
            "POST",
            HostInstanceDetailListResource,
            endpoint="host_instance_detail_list",
            decorators=[
                user_visit_record,
            ],
        ),
        ResourceRoute("GET", ApdexQueryResource, "apdex_query"),
        ResourceRoute("GET", AlertQueryResource, "alert_query"),
        ResourceRoute("POST", UnifyQueryResource, "unify_query"),
        ResourceRoute("POST", DynamicUnifyQueryResource, "dynamic_unify_query"),
        ResourceRoute("POST", ServiceListAsyncResource, "service_list_async"),
        ResourceRoute("POST", TopNQueryResource, "top_n_query"),
        ResourceRoute("POST", InstanceListResource, "instance_list"),
        ResourceRoute("POST", CollectServiceResource, "collect_service"),
        ResourceRoute("POST", EndpointDetailListResource, "endpoint_detail_list"),
        ResourceRoute("POST", ExceptionDetailListResource, "exception_detail_list"),
        ResourceRoute("POST", ServiceQueryExceptionResource, "service_query_exception"),
        ResourceRoute("GET", MetricDetailStatisticsResource, "metric_statistics"),
    ]
