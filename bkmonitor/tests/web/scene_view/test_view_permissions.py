"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from types import SimpleNamespace

import pytest
from django.urls import resolve

from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission
from bkmonitor.iam.permission import ActionIdMap
from bkmonitor.models import ApiAuthToken, AuthType


HOST_SCENE_ACTION_PATHS = [
    "/rest/v2/scene_view/get_host_process_port_status/",
    "/rest/v2/scene_view/get_host_or_topo_node_detail/",
    "/rest/v2/scene_view/get_host_process_uptime/",
    "/rest/v2/scene_view/get_host_process_list/",
    "/rest/v2/scene_view/get_host_views_panels/",
    "/rest/v2/scene_view/get_host_metric_group_panel_order/",
    "/rest/v2/scene_view/get_process_views_panels/",
    "/rest/v2/scene_view/get_process_metric_group_panel_order/",
]


def get_view_and_action(path, method="post"):
    resolved = resolve(path)
    action = resolved.func.actions[method]
    view = resolved.func.cls()
    view.action = action
    view.request = SimpleNamespace(method=method.upper())
    return resolved.func, view, action


@pytest.mark.parametrize("path", HOST_SCENE_ACTION_PATHS)
def test_new_host_scene_read_actions_require_view_host(path):
    _, view, _ = get_view_and_action(path)

    permissions = view.get_permissions()

    assert len(permissions) == 1
    assert isinstance(permissions[0], BusinessActionPermission)
    assert permissions[0].actions == [ActionEnum.VIEW_HOST]


@pytest.mark.parametrize(
    ("path", "method"),
    [
        ("/rest/v2/scene_view/get_scene_view/", "get"),
        ("/rest/v2/scene_view/get_kubernetes_cluster_list/", "post"),
        ("/rest/v2/scene_view/get_custom_metric_target_list/", "post"),
    ],
)
def test_other_scene_view_actions_keep_view_business(path, method):
    _, view, _ = get_view_and_action(path, method)

    permissions = view.get_permissions()

    assert len(permissions) == 1
    assert isinstance(permissions[0], BusinessActionPermission)
    assert permissions[0].actions == [ActionEnum.VIEW_BUSINESS]


@pytest.mark.parametrize("path", HOST_SCENE_ACTION_PATHS)
def test_host_share_token_contract_remains_compatible_with_view_host_actions(path):
    resolved_view, _, action = get_view_and_action(path)
    token = ApiAuthToken(type=AuthType.Host)

    assert token.is_allowed_view(resolved_view) is True
    assert action in resolved_view.actions.values()
    assert ActionEnum.VIEW_HOST in ActionIdMap[token.type]
