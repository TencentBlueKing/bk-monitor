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

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc.functions.admin import space as admin_space


def test_space_list_by_user_scopes_the_monitor_iam_result(monkeypatch):
    from monitor_web.commons.biz.resources import ListSpacesResource

    row = {"bk_tenant_id": "tenant", "bk_biz_id": -7, "space_uid": "bkci__demo", "space_name": "Demo"}

    def grants(tenant, username):
        assert tenant == "tenant"
        if username == "viewer":
            return [dict(row, internal=True), dict(row, bk_biz_id=2), dict(row, bk_tenant_id="other")]
        assert username == "denied"
        return []

    monkeypatch.setattr(ListSpacesResource, "get_space_by_user", grants)
    scope = {"bk_tenant_id": "tenant", "bk_biz_id": -7}
    for username, expected in (("viewer", [row]), ("denied", [])):
        result = admin_space.list_spaces_by_user({**scope, "username": username})
        assert result["data"]["items"] == expected
    for field in ("username", "bk_tenant_id", "bk_biz_id"):
        params = {**scope, "username": "viewer"}
        del params[field]
        with pytest.raises(CustomException, match=field):
            admin_space.list_spaces_by_user(params)
