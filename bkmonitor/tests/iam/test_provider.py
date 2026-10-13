"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

# Live V4 capability tests; never executed by offline verification.

import os
import time

import pytest
from django.conf import settings

from iam_engine.provider.requests import (
    ApplyURLRequest,
    AuthRequest,
    BatchByActionRequest,
    BatchByResourceRequest,
    ResourceInstance,
    Subject,
)
from bkmonitor.iam.permission import Permission
from bkmonitor.iam.action import ActionEnum as Actions
from bkmonitor.iam.definitions.resource_types import ResourceTypes
from bkmonitor.iam.definitions.roles import Roles

_MISSING_CONFIG = (
    os.getenv("BK_IAM_LIVE", "").lower() not in ("1", "true", "yes")
    or not getattr(settings, "BK_IAM_V4_APIGATEWAY_URL", "")
    or not getattr(settings, "SAAS_APP_CODE", "")
    or not getattr(settings, "SAAS_SECRET_KEY", "")
)
SKIP_REASON = "IAM v4 API 未配置（BKAPP_IAM_V4_API_BASE_URL / SAAS_APP_CODE / SAAS_SECRET_KEY）"

TEST_USER = os.getenv("IAM_V4_TEST_USER", "admin")
TEST_SPACE_ID = os.getenv("IAM_V4_TEST_SPACE_ID", "2")

_APPLY_ENABLED = os.getenv("IAM_V4_APPLY", "").lower() in ("1", "true", "yes")
APPLY_SKIP_REASON = "未开启真实 apply（设置 IAM_V4_APPLY=1 才会执行）"


@pytest.mark.live
@pytest.mark.skipif(_MISSING_CONFIG, reason=SKIP_REASON)
class TestIAMv4AuthCapabilities:
    """V4 全能力测试 —— 不依赖迁移状态，只验证鉴权 API 可用性。"""

    @pytest.fixture(autouse=True)
    def v4_mode(self, monkeypatch):
        monkeypatch.setenv("BKAPP_IAM_PERMISSION_MODE", "v4")

    # ------- 批量资源鉴权 -------

    def test_batch_by_resource(self):
        fw = Permission(username="offline", bk_tenant_id="system")
        space_ids = [str(i) for i in range(1, 6)]
        result = fw.batch_by_resource(
            BatchByResourceRequest(
                subject=Subject(id=TEST_USER),
                action_id=Actions.VIEW_BUSINESS.id,
                resources=tuple(ResourceInstance(type=ResourceTypes.SPACE, id=sid) for sid in space_ids),
            )
        )
        print(f"\n  batch_by_resource: {len(result.items)} 条结果")
        for item in result.items:
            print(f"    space={item.resource_id} allowed={item.allowed}")
        assert len(result.items) == len(space_ids)

    # ------- 批量 action 鉴权 -------

    def test_batch_by_action(self):
        fw = Permission(username="offline", bk_tenant_id="system")
        result = fw.batch_by_action(
            BatchByActionRequest(
                subject=Subject(id=TEST_USER),
                action_ids=[
                    Actions.VIEW_BUSINESS.id,
                    Actions.EXPLORE_METRIC.id,
                    Actions.VIEW_RULE.id,
                    Actions.VIEW_EVENT.id,
                    Actions.VIEW_DASHBOARD.id,
                ],
                resource=ResourceInstance(type=ResourceTypes.SPACE, id=TEST_SPACE_ID),
            )
        )
        print(f"\n  batch_by_action: {len(result.items)} 条结果")
        for item in result.items:
            print(f"    {item.action_id}: allowed={item.allowed}")
        assert len(result.items) == 5

    def test_batch_by_action_resource_free(self):
        fw = Permission(username="offline", bk_tenant_id="system")
        result = fw.batch_by_action(
            BatchByActionRequest(
                subject=Subject(id=TEST_USER),
                action_ids=[
                    Actions.VIEW_GLOBAL_SETTING.id,
                    Actions.VIEW_SELF_STATE.id,
                    Actions.MANAGE_CALENDAR.id,
                ],
            )
        )
        print(f"\n  batch_by_action (resource-free): {len(result.items)} 条结果")
        for item in result.items:
            print(f"    {item.action_id}: allowed={item.allowed}")
        assert len(result.items) == 3

    # ------- 权限申请 URL -------

    def test_get_apply_url(self):
        fw = Permission(username="offline", bk_tenant_id="system")
        url = fw.get_apply_url(
            ApplyURLRequest(
                subject=Subject(id=TEST_USER),
                action_ids=[Actions.VIEW_BUSINESS.id],
                resources=(ResourceInstance(type=ResourceTypes.SPACE, id=TEST_SPACE_ID),),
            )
        )
        print(f"\n  apply_url: {url}")
        assert isinstance(url, str)
        if url:
            assert url.startswith("http")

    # ------- 有权限的资源列表 -------

    def test_get_authorized_resources_resource_free(self):
        fw = Permission(username="offline", bk_tenant_id="system")
        provider = fw.providers["v4"]
        result = provider.get_authorized_resources(
            subject=Subject(id=TEST_USER),
            action_id=Actions.VIEW_GLOBAL_SETTING.id,
        )
        print(f"\n  get_authorized_resources({Actions.VIEW_GLOBAL_SETTING.id}) = {result}")
        assert result == []

    def test_get_authorized_resources_view_business(self):
        fw = Permission(username="offline", bk_tenant_id="system")
        provider = fw.providers["v4"]
        result = provider.get_authorized_resources(
            subject=Subject(id=TEST_USER),
            action_id=Actions.VIEW_BUSINESS.id,
        )
        print(f"\n  get_authorized_resources({Actions.VIEW_BUSINESS.id}):")
        for item in result:
            print(f"    type={item['type']} ids={item['ids']}")
        assert isinstance(result, list)
        for item in result:
            if item["type"] == ResourceTypes.SPACE.id:
                for rid in item["ids"]:
                    assert not rid.startswith("space|"), f"space id 应已 decode: {rid}"

    # ------- 角色授权参数校验 -------

    def test_add_authorization_invalid_args(self):
        fw = Permission(username="offline", bk_tenant_id="system")
        provider = fw.providers["v4"]
        with pytest.raises(ValueError):
            provider.add_authorization(
                subject=Subject(id=TEST_USER),
                role=Roles.SPACE_VIEWER,
                resource_type=None,
                resource_ids=["2"],
                expired_at=int(time.time()) + 3600,
                operator=TEST_USER,
            )
        with pytest.raises(ValueError):
            provider.add_authorization(
                subject=Subject(id=TEST_USER),
                role=Roles.SPACE_VIEWER,
                resource_type=ResourceTypes.SPACE,
                resource_ids=[],
                expired_at=int(time.time()) + 3600,
                operator=TEST_USER,
            )
        print("\n  ✓ 参数校验生效")

    @pytest.mark.skipif(not _APPLY_ENABLED, reason=APPLY_SKIP_REASON)
    def test_add_authorization_space_viewer(self):
        fw = Permission(username="offline", bk_tenant_id="system")
        provider = fw.providers["v4"]
        expired_at = int(time.time()) + 3600
        provider.add_authorization(
            subject=Subject(id=TEST_USER),
            role=Roles.SPACE_VIEWER,
            resource_type=ResourceTypes.SPACE,
            resource_ids=[TEST_SPACE_ID],
            expired_at=expired_at,
            operator=TEST_USER,
        )
        print(f"\n  ✓ 已授权: user={TEST_USER} space={TEST_SPACE_ID} role={Roles.SPACE_VIEWER.id}")
        allowed = fw.is_allowed(
            AuthRequest(
                subject=Subject(id=TEST_USER),
                action_id=Actions.VIEW_BUSINESS.id,
                resource=ResourceInstance(type=ResourceTypes.SPACE, id=TEST_SPACE_ID),
            )
        )
        print(f"  is_allowed(view_business, space={TEST_SPACE_ID}) = {allowed}")
        assert allowed is True
