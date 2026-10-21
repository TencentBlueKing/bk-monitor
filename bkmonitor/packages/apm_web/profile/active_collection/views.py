"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from apm_web.decorators import user_visit_record
from apm_web.profile.active_collection.resources import (
    ActiveProfilingMetaConfigResource,
    CancelExecutionResource,
    DeleteTaskResource,
    EditTaskResource,
    EnableActiveCollectionResource,
    ExecutionDetailResource,
    ExportResultsResource,
    ListExecutionsResource,
    ListTasksResource,
    PreviewProcessesResource,
    QueryHostsResource,
    QueryResultDataTypesResource,
    QueryResultsResource,
    QueryTopKResource,
    SubmitTaskResource,
    SwitchTaskResource,
)
from bkmonitor.iam.drf import ViewBusinessPermission
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class ActiveProfilingViewSet(ResourceViewSet):
    """与 Profiling 检索页面权限一致：有业务查看权限即可使用主动采集"""

    def get_permissions(self):
        return [ViewBusinessPermission()]


class ActiveProfilingMetaConfigViewSet(ActiveProfilingViewSet):
    resource_routes = [ResourceRoute("GET", ActiveProfilingMetaConfigResource)]


class EnableViewSet(ActiveProfilingViewSet):
    resource_routes = [ResourceRoute("POST", EnableActiveCollectionResource)]


class ProcessesViewSet(ActiveProfilingViewSet):
    resource_routes = [ResourceRoute("POST", PreviewProcessesResource, endpoint="preview")]


class TasksViewSet(ActiveProfilingViewSet):
    resource_routes = [
        ResourceRoute("GET", ListTasksResource, decorators=[user_visit_record]),
        ResourceRoute("POST", SubmitTaskResource),
        ResourceRoute("POST", EditTaskResource, endpoint="edit"),
        ResourceRoute("POST", DeleteTaskResource, endpoint="delete"),
        ResourceRoute("POST", SwitchTaskResource, endpoint="switch"),
    ]


class HostsViewSet(ActiveProfilingViewSet):
    resource_routes = [ResourceRoute("POST", QueryHostsResource, endpoint="query", decorators=[user_visit_record])]


class ExecutionsListViewSet(ActiveProfilingViewSet):
    resource_routes = [ResourceRoute("POST", ListExecutionsResource, decorators=[user_visit_record])]


class TopKViewSet(ActiveProfilingViewSet):
    resource_routes = [ResourceRoute("GET", QueryTopKResource)]


class ExecutionsViewSet(ActiveProfilingViewSet):
    resource_routes = [
        ResourceRoute("POST", ExecutionDetailResource, endpoint="detail", decorators=[user_visit_record]),
        ResourceRoute("POST", CancelExecutionResource, endpoint="cancel"),
    ]


class ResultsViewSet(ActiveProfilingViewSet):
    resource_routes = [
        ResourceRoute("POST", QueryResultsResource, endpoint="query", decorators=[user_visit_record]),
        ResourceRoute("POST", QueryResultDataTypesResource, endpoint="data_types"),
        ResourceRoute("POST", ExportResultsResource, endpoint="export", decorators=[user_visit_record]),
    ]
