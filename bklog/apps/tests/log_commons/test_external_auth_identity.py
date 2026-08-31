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
from contextlib import ExitStack
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.http import JsonResponse
from django.test import TestCase, override_settings
from django.urls import resolve as real_resolve
from django.utils import timezone

from apps.constants import ExternalPermissionActionEnum
from apps.log_audit.external import ExternalAuditRecorder
from apps.log_commons.external_auth import DecisionSource, IdentityContext, SourceResult
from apps.log_commons.external_auth.capability import Capability
from apps.log_commons.models import ExternalPermission
from apps.utils.local import _local, activate_request

SPACE_UID = "bkcc__100605"
EXTERNAL_USER = "po_external_user"
AUTHORIZER = "authorizer_zhang"
INDEX_SET_ID = 628108


class RecordingRecorder(ExternalAuditRecorder):
    """复用生产审计收集器，只拦住上报，把审计取到的身份留给断言。"""

    instances = []

    def __init__(self, request):
        super().__init__(request)
        type(self).instances.append(self)

    def push(self):
        return


class SubjectCapturingSource:
    """记录鉴权来源实际拿到的判权主体与租户，模拟【03】起接入的新侧。"""

    name = DecisionSource.IAM

    def __init__(self):
        self.identities = []

    def check(self, ctx):
        self.identities.append(ctx.identity)
        return SourceResult.allow(matched_action_id=ExternalPermissionActionEnum.LOG_SEARCH.value)


@override_settings(BK_APP_TENANT_ID="system", ENABLE_MULTI_TENANT_MODE=False)
class IdentityContextTest(TestCase):
    def test_three_identities_are_distinct_for_an_external_request(self):
        identity = IdentityContext.for_external_request(external_user=EXTERNAL_USER, authorizer=AUTHORIZER)

        self.assertEqual(identity.authorization_subject, EXTERNAL_USER)
        self.assertEqual(identity.execution_user, AUTHORIZER)
        self.assertEqual(identity.audit_user, EXTERNAL_USER)
        self.assertNotEqual(identity.authorization_subject, identity.execution_user)

    def test_tenant_defaults_to_the_app_tenant_when_not_multi_tenant(self):
        identity = IdentityContext.for_external_request(external_user=EXTERNAL_USER, authorizer=AUTHORIZER)

        self.assertEqual(identity.bk_tenant_id, "system")

    @override_settings(ENABLE_MULTI_TENANT_MODE=True)
    def test_tenant_comes_from_the_request_header_in_multi_tenant_mode(self):
        activate_request(SimpleNamespace(META={"HTTP_X_BK_TENANT_ID": "tenant_a"}, user=SimpleNamespace()))
        self.addCleanup(lambda: _local.__dict__.pop("request", None))

        identity = IdentityContext.for_external_request(external_user=EXTERNAL_USER, authorizer=AUTHORIZER)

        self.assertEqual(identity.bk_tenant_id, "tenant_a")

    def test_permission_is_built_with_the_external_subject_not_the_logged_in_authorizer(self):
        """Permission 只在 username 与 tenant 同时给出时才认显式身份，这里锁住判权主体不被换掉。"""
        activate_request(SimpleNamespace(META={}, user=SimpleNamespace(username=AUTHORIZER)))
        self.addCleanup(lambda: _local.__dict__.pop("request", None))
        identity = IdentityContext.for_external_request(external_user=EXTERNAL_USER, authorizer=AUTHORIZER)

        permission = identity.permission_for_subject()

        self.assertEqual(permission.username, EXTERNAL_USER)
        self.assertEqual(permission.bk_tenant_id, "system")


@override_settings(BK_APP_TENANT_ID="system", ENABLE_MULTI_TENANT_MODE=False)
class ProxyIdentitySeparationTest(TestCase):
    """把请求打进真实 dispatch_external_proxy，验证三种身份各自落到了正确的位置。"""

    SEARCH_URL = f"/api/v1/search/index_set/{INDEX_SET_ID}/search/"

    def setUp(self):
        RecordingRecorder.instances = []
        ExternalPermission.objects.create(
            authorized_user=EXTERNAL_USER,
            space_uid=SPACE_UID,
            action_id=ExternalPermissionActionEnum.LOG_SEARCH.value,
            resources=[INDEX_SET_ID],
            expire_time=timezone.now() + timedelta(days=30),
        )

    def _call_proxy(self, captured, capability=None):
        def wrapped_resolve(path, urlconf=None):
            match = real_resolve(path, urlconf=urlconf)

            def stub_view(request, **kwargs):
                captured["execution_user"] = getattr(getattr(request, "user", None), "username", "")
                captured["external_user_on_fake_request"] = getattr(request, "external_user", "")
                return JsonResponse({"result": True, "data": []})

            stub_view.cls = match.func.cls
            stub_view.actions = match.func.actions
            return SimpleNamespace(func=stub_view, kwargs=match.kwargs)

        def fake_authenticate(username=None, **kwargs):
            captured["authenticated_username"] = username
            return SimpleNamespace(username=username, is_authenticated=True, pk=1, id=1)

        def fake_login(request, user):
            request.user = user

        patches = [
            patch("log_adapter.home.views.resolve", side_effect=wrapped_resolve),
            patch("log_adapter.home.views.ExternalAuditRecorder", RecordingRecorder),
            patch("log_adapter.home.views.AuthorizerSettings.get_authorizer", return_value=AUTHORIZER),
            patch("log_adapter.home.views.auth.authenticate", side_effect=fake_authenticate),
            patch("log_adapter.home.views.auth.login", side_effect=fake_login),
        ]
        if capability is not None:
            patches.append(patch("apps.log_commons.external_auth.pipeline.get_capability", return_value=capability))

        with ExitStack() as stack:
            for item in patches:
                stack.enter_context(item)
            return self.client.post(
                "/dispatch_external_proxy/",
                data=json.dumps({"url": self.SEARCH_URL, "space_uid": SPACE_UID, "method": "POST", "data": "{}"}),
                content_type="application/json",
                HTTP_USER=json.dumps({"username": EXTERNAL_USER}),
            )

    def test_execution_uses_the_authorizer_while_audit_records_the_external_user(self):
        captured = {}

        response = self._call_proxy(captured)
        recorder = RecordingRecorder.instances[0]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured["authenticated_username"], AUTHORIZER)
        self.assertEqual(captured["execution_user"], AUTHORIZER)
        self.assertEqual(captured["external_user_on_fake_request"], EXTERNAL_USER)
        self.assertEqual(recorder.external_user, EXTERNAL_USER)
        self.assertEqual(recorder.authorizer, AUTHORIZER)

    def test_auth_sources_receive_the_external_user_as_authorization_subject(self):
        """新侧接入后判权主体必须仍是外部用户，而不是即将登录的内部授权人。"""
        source = SubjectCapturingSource()
        captured = {}

        response = self._call_proxy(captured, capability=Capability(action_id="", sources=(source,)))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(source.identities), 1)
        identity = source.identities[0]
        self.assertEqual(identity.authorization_subject, EXTERNAL_USER)
        self.assertEqual(identity.execution_user, AUTHORIZER)
        self.assertEqual(identity.audit_user, EXTERNAL_USER)
        self.assertEqual(identity.bk_tenant_id, "system")
        # 判权发生在 login 之前，此刻请求还没有被换成授权人
        self.assertEqual(captured["execution_user"], AUTHORIZER)
