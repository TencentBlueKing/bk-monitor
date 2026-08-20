"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import pytest

from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission
from core.drf_resource.viewsets import ResourceViewSet
from monitor_web.performance.views import (
    HostListViewSet,
    HostPerformanceDetailViewSet,
    SearchHostInfoViewSet,
    SearchHostMetricViewSet,
)
from monitor_web.permissions import BusinessViewPermission


@pytest.mark.parametrize(
    "viewset_class",
    [
        HostListViewSet,
        HostPerformanceDetailViewSet,
        SearchHostInfoViewSet,
        SearchHostMetricViewSet,
    ],
)
def test_host_read_endpoints_require_view_host(viewset_class):
    permissions = viewset_class().get_permissions()

    assert len(permissions) == 1
    assert isinstance(permissions[0], BusinessActionPermission)
    assert permissions[0].actions == [ActionEnum.VIEW_HOST]


def test_plain_resource_viewset_keeps_default_business_permission():
    permissions = ResourceViewSet().get_permissions()

    assert len(permissions) == 1
    assert isinstance(permissions[0], BusinessViewPermission)
