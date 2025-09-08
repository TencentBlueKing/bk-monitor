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

from django.urls import include, re_path

from core.drf_resource.routers import ResourceRouter
from monitor_web.user_group.views import (
    BkchatGroupViewSet,
    DutyPlanViewSet,
    DutyRuleViewSet,
    UserGroupViewSet,
)

router = ResourceRouter()
router.register(r"user_groups", UserGroupViewSet, basename="user_group")
router.register(r"duty_rules", DutyRuleViewSet, basename="duty_rule")
router.register(r"bkchat_group", BkchatGroupViewSet, basename="bkchat_group")
router.register(r"duty_plan", DutyPlanViewSet, basename="duty_plan")


urlpatterns = [re_path(r"^", include(router.urls))]
