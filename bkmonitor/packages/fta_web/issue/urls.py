"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.urls import include, re_path

from core.drf_resource.routers import ResourceRouter
from fta_web.issue.resources import tapd_app_install_callback, tapd_user_oauth_callback
from fta_web.issue.views import IssueViewSet

router = ResourceRouter()
router.register(r"", IssueViewSet, basename="issue")

urlpatterns = [
    re_path(r"^tapd/oauth_callback/$", tapd_user_oauth_callback, name="tapd_user_oauth_callback"),
    re_path(r"^tapd/app_install_callback/$", tapd_app_install_callback, name="tapd_app_install_callback"),
    re_path(r"^", include(router.urls)),
]
