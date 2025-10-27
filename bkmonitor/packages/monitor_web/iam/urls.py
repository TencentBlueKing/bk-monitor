"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from blueapps.account.decorators import login_exempt
from django.conf import settings
from django.urls import include, re_path

from bkmonitor.iam.permission import Permission
from constants.common import DEFAULT_TENANT_ID
from core.drf_resource.routers import ResourceRouter
from monitor_web.iam import views

router = ResourceRouter()
router.register_module(views)

dispatcher = views.ResourceApiDispatcher(Permission.get_iam_client(DEFAULT_TENANT_ID), settings.BK_IAM_SYSTEM_ID)
dispatcher.register("apm_application", views.ApmApplicationProvider())
dispatcher.register("space", views.SpaceProvider())
dispatcher.register("grafana_dashboard", views.GrafanaDashboardProvider())

urlpatterns = [re_path(r"^", include(router.urls)), re_path(r"^iam/resource/$", dispatcher.as_view([login_exempt]))]
