"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest.mock import Mock, patch

import pytest

from bk_dataview.settings import grafana_settings
from bk_dataview.views import ProxyBaseView


@pytest.mark.parametrize(("user_settings", "expected_timeout"), [({}, 30), ({"TIMEOUT": 45}, 45)])
def test_proxy_request_uses_configured_timeout(user_settings, expected_timeout):
    request = Mock()
    request.method = "POST"
    request.GET = {"orgId": "2", "orgName": "demo", "query": "value"}
    request.body = b"{}"

    view = ProxyBaseView()
    with (
        patch.object(grafana_settings, "user_settings", user_settings),
        patch.object(view, "get_request_url", return_value="http://grafana/api/ds/query"),
        patch.object(view, "get_request_headers", return_value={"X-Test": "value"}),
        patch("bk_dataview.views.rpool.request") as request_proxy,
    ):
        view._created_proxy_response(request)

    assert request_proxy.call_args.kwargs["timeout"] == expected_timeout
