"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

import json
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.constants import ExternalPermissionActionEnum
from apps.log_commons.external_auth import (
    DecisionSource,
    IdentityContext,
    has_space_access,
    list_authorized_space_actions,
    list_authorized_space_uids,
)
from apps.log_commons.external_auth.space_access import LEGACY_SPACE_ACCESS_SOURCE, SpaceAccessSource
from apps.log_commons.models import ExternalPermission
from apps.log_search.models import Space

SPACE_UID = "bkcc__100605"
OTHER_SPACE_UID = "bkcc__100606"
EXTERNAL_USER = "po_external_user"


class StubSpaceAccessSource:
    """外部实现的空间级来源，用来验证追加来源不需要改调用方。"""

    name = DecisionSource.IAM

    def __init__(self, space_actions):
        self.space_actions = space_actions

    def list_space_actions(self, identity):
        return self.space_actions

    def list_space_uids(self, identity):
        return list(self.space_actions)

    def has_access(self, identity, space_uid):
        return space_uid in self.space_actions


@override_settings(BK_APP_TENANT_ID="system", ENABLE_MULTI_TENANT_MODE=False)
class SpaceAccessTest(TestCase):
    def setUp(self):
        self.identity = IdentityContext.for_external_request(external_user=EXTERNAL_USER, authorizer="")

    def _create_ticket(self, space_uid, action_id, expired=False):
        ExternalPermission.objects.create(
            authorized_user=EXTERNAL_USER,
            space_uid=space_uid,
            action_id=action_id,
            resources=[],
            expire_time=timezone.now() + timedelta(days=-1 if expired else 30),
        )

    def test_legacy_source_satisfies_the_space_access_protocol(self):
        self.assertIsInstance(LEGACY_SPACE_ACCESS_SOURCE, SpaceAccessSource)
        self.assertIsInstance(StubSpaceAccessSource({}), SpaceAccessSource)

    def test_lists_spaces_and_actions_from_legacy_tickets(self):
        self._create_ticket(SPACE_UID, ExternalPermissionActionEnum.LOG_SEARCH.value)
        self._create_ticket(SPACE_UID, ExternalPermissionActionEnum.LOG_EXTRACT.value)
        self._create_ticket(OTHER_SPACE_UID, ExternalPermissionActionEnum.CLIENT_LOG.value)

        actions = list_authorized_space_actions(self.identity)

        self.assertEqual(set(actions), {SPACE_UID, OTHER_SPACE_UID})
        self.assertEqual(
            set(actions[SPACE_UID]),
            {ExternalPermissionActionEnum.LOG_SEARCH.value, ExternalPermissionActionEnum.LOG_EXTRACT.value},
        )
        self.assertEqual(set(list_authorized_space_uids(self.identity)), {SPACE_UID, OTHER_SPACE_UID})

    def test_expired_tickets_grant_neither_listing_nor_access(self):
        self._create_ticket(SPACE_UID, ExternalPermissionActionEnum.LOG_SEARCH.value, expired=True)

        self.assertEqual(list_authorized_space_actions(self.identity), {})
        self.assertEqual(list_authorized_space_uids(self.identity), [])
        self.assertFalse(has_space_access(self.identity, SPACE_UID))

    def test_access_is_scoped_to_the_authorized_space(self):
        self._create_ticket(SPACE_UID, ExternalPermissionActionEnum.LOG_SEARCH.value)

        self.assertTrue(has_space_access(self.identity, SPACE_UID))
        self.assertFalse(has_space_access(self.identity, OTHER_SPACE_UID))

    def test_additional_source_widens_access_without_touching_callers(self):
        self._create_ticket(SPACE_UID, ExternalPermissionActionEnum.LOG_SEARCH.value)
        sources = (
            LEGACY_SPACE_ACCESS_SOURCE,
            StubSpaceAccessSource({OTHER_SPACE_UID: [ExternalPermissionActionEnum.CLIENT_LOG.value]}),
        )

        self.assertTrue(has_space_access(self.identity, OTHER_SPACE_UID, sources=sources))
        self.assertEqual(list_authorized_space_uids(self.identity, sources=sources), [SPACE_UID, OTHER_SPACE_UID])

    def test_actions_of_the_same_space_are_merged_without_duplicates(self):
        self._create_ticket(SPACE_UID, ExternalPermissionActionEnum.LOG_SEARCH.value)
        sources = (
            LEGACY_SPACE_ACCESS_SOURCE,
            StubSpaceAccessSource(
                {
                    SPACE_UID: [
                        ExternalPermissionActionEnum.LOG_SEARCH.value,
                        ExternalPermissionActionEnum.CLIENT_LOG.value,
                    ]
                }
            ),
        )

        actions = list_authorized_space_actions(self.identity, sources=sources)

        self.assertEqual(
            actions[SPACE_UID],
            [ExternalPermissionActionEnum.LOG_SEARCH.value, ExternalPermissionActionEnum.CLIENT_LOG.value],
        )


@override_settings(BK_APP_TENANT_ID="system", ENABLE_MULTI_TENANT_MODE=False)
class FrontEntrypointSpaceAccessTest(TestCase):
    """页面入口与空间列表接口的空间级放行行为，接入空间来源后必须保持不变。"""

    def _create_ticket(self, space_uid, action_id=ExternalPermissionActionEnum.LOG_SEARCH.value):
        ExternalPermission.objects.create(
            authorized_user=EXTERNAL_USER,
            space_uid=space_uid,
            action_id=action_id,
            resources=[],
            expire_time=timezone.now() + timedelta(days=30),
        )

    def _get(self, path, query=""):
        return self.client.get(f"{path}{query}", HTTP_USER=json.dumps({"username": EXTERNAL_USER}))

    def test_page_entry_rejects_a_user_without_any_authorized_space(self):
        response = self._get("/external/")

        self.assertEqual(response.status_code, 403)
        self.assertIn("无访问权限", response.content.decode())

    def test_page_entry_rejects_a_space_the_user_is_not_authorized_for(self):
        self._create_ticket(SPACE_UID)

        with patch("log_adapter.home.views.SpaceApi.get_space_detail", return_value={}):
            response = self._get("/external/", f"?space_uid={OTHER_SPACE_UID}")

        self.assertEqual(response.status_code, 403)
        self.assertIn(OTHER_SPACE_UID, response.content.decode())

    def test_space_list_rejects_a_user_without_any_ticket(self):
        response = self._get("/dispatch_list_user_spaces/")

        self.assertEqual(response.status_code, 403)

    def test_space_list_requires_the_external_user_header(self):
        response = self.client.get("/dispatch_list_user_spaces/")

        self.assertEqual(response.status_code, 403)

    def test_space_list_returns_authorized_spaces_with_their_actions(self):
        self._create_ticket(SPACE_UID)
        Space.objects.create(
            space_uid=SPACE_UID,
            bk_biz_id=100605,
            space_type_id="bkcc",
            space_type_name="业务",
            space_id="100605",
            space_name="测试空间",
            space_code="",
            properties={},
        )

        response = self._get("/dispatch_list_user_spaces/")
        body = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(body["result"])
        self.assertEqual([item["space_uid"] for item in body["data"]], [SPACE_UID])
        self.assertEqual(
            body["data"][0]["external_permission"],
            [ExternalPermissionActionEnum.LOG_SEARCH.value],
        )
