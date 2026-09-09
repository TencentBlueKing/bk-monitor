"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2026 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import pytest
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apm_web.trace.views import TraceQueryViewSet
from bkmonitor.iam.drf import InstanceActionForDataPermission, ViewBusinessPermission

BK_BIZ_ID = 2


def build_viewset(params: dict, method: str = "post"):
    factory = APIRequestFactory()
    if method == "get":
        raw_request = factory.get("/", params)
    else:
        raw_request = factory.post("/", params, format="json")

    viewset = TraceQueryViewSet()
    viewset.request = Request(raw_request)
    return viewset


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        # 带 app_name 的接口按 APM 应用实例鉴权
        ({"bk_biz_id": BK_BIZ_ID, "app_name": "demo"}, InstanceActionForDataPermission),
        # trace_list_by_id 等接口只有 bk_biz_id，退到业务鉴权
        ({"bk_biz_id": BK_BIZ_ID}, ViewBusinessPermission),
        # 静态选项类接口没有任何业务参数
        ({}, ViewBusinessPermission),
    ],
)
def test_get_permissions_never_returns_empty(params, expected):
    permissions = build_viewset(params).get_permissions()

    assert len(permissions) == 1
    assert isinstance(permissions[0], expected)


def test_get_permissions_covers_get_requests():
    permissions = build_viewset({"bk_biz_id": BK_BIZ_ID, "app_name": "demo"}, method="get").get_permissions()

    assert [type(permission) for permission in permissions] == [InstanceActionForDataPermission]


@pytest.mark.parametrize(
    "action",
    [
        # 这些 action 此前不在白名单内，完全没有权限校验
        "trace_statistics",
        "trace_list_by_id",
        "fields_topk",
        "field_statistics_info",
        "field_statistics_graph",
        "trace_diagram",
        "apply_trace_comparison",
        "delete_trace_comparison",
        "list_trace_comparison",
    ],
)
def test_previously_unguarded_actions_are_now_guarded(action):
    viewset = build_viewset({"bk_biz_id": BK_BIZ_ID, "app_name": "demo"})
    viewset.action = action

    assert viewset.get_permissions()
