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


from django.conf.urls import include, url

app_name = "monitor_web"

urlpatterns = [
    url(r"^", include("monitor_web.plugin.urls")),
    url(r"^uptime_check/", include("monitor_web.uptime_check.urls")),
    url(r"^", include("monitor_web.collecting.urls")),
    url(r"^commons/", include("monitor_web.commons.urls")),
    url(r"^overview/", include("monitor_web.overview.urls")),
    url(r"^performance/", include("monitor_web.performance.urls")),
    url(r"^", include("monitor_web.notice_group.urls")),
    url(r"^", include("monitor_web.user_group.urls")),
    url(r"^", include("monitor_web.strategies.urls")),
    url(r"^", include("monitor_web.alert_events.urls")),
    url(r"^", include("monitor_web.service_classify.urls")),
    url(r"^", include("monitor_web.shield.urls")),
    url(r"^", include("monitor_web.config.urls")),
    url(r"^", include("monitor_web.export_import.urls")),
    url(r"^", include("monitor_web.custom_report.urls")),
    url(r"^", include("monitor_web.grafana.urls")),
    url(r"^", include("monitor_web.iam.urls")),
    url(r"^", include("monitor_web.data_explorer.urls")),
    url(r"^", include("monitor_web.report.urls")),
    url(r"^", include("monitor_web.scene_view.urls")),
    url(r"^", include("monitor_web.search.urls")),
    url(r"^", include("monitor_web.as_code.urls")),
    url(r"^", include("monitor_web.share.urls")),
    url(r"^", include("monitor_web.promql_import.urls")),
    url(r"^", include("monitor_web.aiops.urls")),
    url(r"^", include("monitor_web.datalink.urls")),
    url(r"^", include("monitor_web.new_report.urls")),
]
