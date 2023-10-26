# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


from django.shortcuts import render

from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class HealthzViewSet(ResourceViewSet):
    """
    告警配置页面的告警策略
    """

    # 自监控权限豁免
    permission_classes = []

    resource_routes = [
        ResourceRoute("GET", resource.healthz.get_global_status),
        ResourceRoute("GET", resource.healthz.server_graph_point, endpoint="graph_point"),
        ResourceRoute("GET", resource.healthz.server_host_alarm, endpoint="host_alarm"),
        ResourceRoute("POST", resource.healthz.job_test_root_api, endpoint="job_test_root"),
        ResourceRoute("POST", resource.healthz.job_test_non_root_api, endpoint="job_test_non_root"),
        ResourceRoute("POST", resource.healthz.cc_test_root_api, endpoint="cc_test_root"),
        ResourceRoute("POST", resource.healthz.cc_test_non_root_api, endpoint="cc_test_non_root"),
        ResourceRoute("POST", resource.healthz.metadata_test_root_api, endpoint="metadata_test_root"),
        ResourceRoute("POST", resource.healthz.nodeman_test_root_api, endpoint="nodeman_test_root"),
        ResourceRoute("POST", resource.healthz.bk_data_test_root_api, endpoint="bk_data_test_root"),
        ResourceRoute("POST", resource.healthz.gse_test_root_api, endpoint="gse_test_root"),
    ]


def index(request, cc_biz_id):
    return render(request, "/monitor/healthz/dashboard.html", {"cc_biz_id": cc_biz_id})


class AlarmConfig(ResourceViewSet):
    resource_routes = [
        ResourceRoute("GET", resource.healthz.get_alarm_config),
        ResourceRoute("POST", resource.healthz.update_alarm_config),
    ]
