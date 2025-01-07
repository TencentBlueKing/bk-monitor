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


from django.urls import include, re_path

app_name = "monitor_web"

urlpatterns = [
    re_path(r"^", include("monitor_web.plugin.urls")),
    re_path(r"^uptime_check/", include("monitor_web.uptime_check.urls")),
    re_path(r"^", include("monitor_web.collecting.urls")),
    re_path(r"^commons/", include("monitor_web.commons.urls")),
    re_path(r"^overview/", include("monitor_web.overview.urls")),
    re_path(r"^performance/", include("monitor_web.performance.urls")),
    re_path(r"^ai_assistant/", include("monitor_web.ai_assistant.urls")),
    re_path(r"^", include("monitor_web.notice_group.urls")),
    re_path(r"^", include("monitor_web.user_group.urls")),
    re_path(r"^", include("monitor_web.strategies.urls")),
    re_path(r"^", include("monitor_web.alert_events.urls")),
    re_path(r"^", include("monitor_web.service_classify.urls")),
    re_path(r"^", include("monitor_web.shield.urls")),
    re_path(r"^", include("monitor_web.config.urls")),
    re_path(r"^", include("monitor_web.export_import.urls")),
    re_path(r"^", include("monitor_web.custom_report.urls")),
    re_path(r"^", include("monitor_web.grafana.urls")),
    re_path(r"^", include("monitor_web.iam.urls")),
    re_path(r"^", include("monitor_web.data_explorer.urls")),
    re_path(r"^", include("monitor_web.report.urls")),
    re_path(r"^", include("monitor_web.scene_view.urls")),
    re_path(r"^", include("monitor_web.search.urls")),
    re_path(r"^", include("monitor_web.as_code.urls")),
    re_path(r"^", include("monitor_web.share.urls")),
    re_path(r"^", include("monitor_web.promql_import.urls")),
    re_path(r"^", include("monitor_web.aiops.urls")),
    re_path(r"^", include("monitor_web.datalink.urls")),
    re_path(r"^", include("monitor_web.new_report.urls")),
    re_path(r"^", include("monitor_web.incident.urls")),
    re_path(r"^k8s/", include("monitor_web.k8s.urls")),
]
