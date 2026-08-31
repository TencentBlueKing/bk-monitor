"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
"""

import json
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.http import JsonResponse
from django.test import TestCase
from django.urls import resolve as real_resolve
from django.utils import timezone

from apps.constants import ExternalPermissionActionEnum
from apps.log_audit.external import ExternalAuditRecorder
from apps.log_commons.models import ExternalPermission
from log_adapter.home.views import RequestProcessor


class _CapturingRecorder(ExternalAuditRecorder):
    """复用生产审计收集器，只拦截上报，把中间值留给自测断言。"""

    instances = []

    def __init__(self, request):
        super().__init__(request)
        type(self).instances.append(self)

    def push(self):
        return


class _ProxySelftestMixin:
    """把请求打进真实 dispatch_external_proxy，只桩掉下游 ViewSet 与授权人 login。"""

    SPACE_UID = "bkcc__100605"
    EXTERNAL_USER = "colecai"
    AUTHORIZER = "authorizer_zhang"

    def setUp(self):
        _CapturingRecorder.instances = []

    def _create_ticket(self, action_id, resources):
        ExternalPermission.objects.create(
            authorized_user=self.EXTERNAL_USER,
            space_uid=self.SPACE_UID,
            action_id=action_id,
            resources=resources,
            expire_time=timezone.now() + timedelta(days=30),
        )

    def _install_resolve_stub(self, captured, method="post"):
        def wrapped_resolve(path, urlconf=None):
            match = real_resolve(path, urlconf=urlconf)
            captured["view_set"] = RequestProcessor.get_view_set(match.func)
            captured["view_action"] = RequestProcessor.get_view_action(match.func, method)

            def stub_view(request, **kwargs):
                user = getattr(request, "user", None)
                captured["execution_user"] = getattr(user, "username", "")
                captured["external_user_on_fake_request"] = getattr(request, "external_user", "")
                captured["view_called"] = True
                return JsonResponse({"result": True, "message": "proxy-selftest-stub", "data": []})

            # 代理用 view_func.cls / actions 识别 ViewSet，必须保留真实 resolve 结果
            if hasattr(match.func, "cls"):
                stub_view.cls = match.func.cls
            if hasattr(match.func, "actions"):
                stub_view.actions = match.func.actions
            return SimpleNamespace(func=stub_view, kwargs=match.kwargs)

        return patch("log_adapter.home.views.resolve", side_effect=wrapped_resolve)

    def _call_proxy(self, *, url, method, captured):
        def fake_authenticate(username=None, **kwargs):
            return SimpleNamespace(username=username, is_authenticated=True, pk=1, id=1)

        def fake_login(request, user):
            request.user = user
            captured["login_username"] = getattr(user, "username", "")

        with (
            self._install_resolve_stub(captured, method=method.lower()),
            patch("log_adapter.home.views.ExternalAuditRecorder", _CapturingRecorder),
            patch(
                "log_adapter.home.views.AuthorizerSettings.get_authorizer",
                return_value=self.AUTHORIZER,
            ),
            patch("log_adapter.home.views.auth.authenticate", side_effect=fake_authenticate),
            patch("log_adapter.home.views.auth.login", side_effect=fake_login),
        ):
            return self.client.post(
                "/dispatch_external_proxy/",
                data=json.dumps(
                    {
                        "url": url,
                        "space_uid": self.SPACE_UID,
                        "method": method,
                        "data": "{}",
                    }
                ),
                content_type="application/json",
                HTTP_USER=json.dumps({"username": self.EXTERNAL_USER}),
            )

    def _recorder(self):
        self.assertEqual(len(_CapturingRecorder.instances), 1)
        return _CapturingRecorder.instances[0]


class TestDispatchExternalProxySearchSelftest(_ProxySelftestMixin, TestCase):
    """【01】自测：检索请求穿过 dispatch_external_proxy 时的身份与门禁。"""

    ALLOWED_INDEX_SET_ID = 628108
    DENIED_INDEX_SET_ID = 999999
    SEARCH_URL_TMPL = "/api/v1/search/index_set/{index_set_id}/search/"

    def _post_proxy(self, index_set_id, captured):
        return self._call_proxy(
            url=self.SEARCH_URL_TMPL.format(index_set_id=index_set_id),
            method="POST",
            captured=captured,
        )

    def test_search_allowed_when_ticket_covers_index_set(self):
        """有旧票且资源命中：代理放行，判定用外部用户，执行 login 成授权人。"""
        self._create_ticket(ExternalPermissionActionEnum.LOG_SEARCH.value, [self.ALLOWED_INDEX_SET_ID])
        captured = {}

        response = self._post_proxy(self.ALLOWED_INDEX_SET_ID, captured)
        recorder = self._recorder()
        body = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(body.get("result"))
        self.assertTrue(captured.get("view_called"))
        self.assertEqual(captured["view_set"], "SearchViewSet")
        self.assertEqual(captured["view_action"], "search")
        self.assertEqual(captured["external_user_on_fake_request"], self.EXTERNAL_USER)
        self.assertEqual(captured["execution_user"], self.AUTHORIZER)
        self.assertEqual(captured["login_username"], self.AUTHORIZER)
        self.assertEqual(recorder.external_user, self.EXTERNAL_USER)
        self.assertEqual(recorder.authorizer, self.AUTHORIZER)
        self.assertEqual(recorder.space_uid, self.SPACE_UID)
        self.assertEqual(recorder.action_id, ExternalPermissionActionEnum.LOG_SEARCH.value)
        self.assertEqual(recorder.view_set, "SearchViewSet")
        self.assertEqual(recorder.view_action, "search")
        self.assertEqual(recorder.resource, self.ALLOWED_INDEX_SET_ID)

    def test_search_denied_when_no_ticket(self):
        """无旧票：代理在进 ViewSet 前 403，且不会 login 成授权人。"""
        captured = {}

        response = self._post_proxy(self.ALLOWED_INDEX_SET_ID, captured)
        recorder = self._recorder()
        body = json.loads(response.content)

        self.assertEqual(response.status_code, 403)
        self.assertFalse(body.get("result"))
        self.assertIn("has no permission", body.get("message", ""))
        self.assertFalse(captured.get("view_called"))
        self.assertEqual(captured["view_set"], "SearchViewSet")
        self.assertEqual(captured["view_action"], "search")
        self.assertNotIn("login_username", captured)
        self.assertEqual(recorder.external_user, self.EXTERNAL_USER)
        self.assertEqual(recorder.authorizer, self.AUTHORIZER)
        self.assertEqual(recorder.result_code, 403)

    def test_search_denied_when_index_set_not_in_ticket(self):
        """有检索票但索引集不在实例列表：代理按资源拒绝，不进 ViewSet。"""
        self._create_ticket(ExternalPermissionActionEnum.LOG_SEARCH.value, [self.ALLOWED_INDEX_SET_ID])
        captured = {}

        response = self._post_proxy(self.DENIED_INDEX_SET_ID, captured)
        recorder = self._recorder()
        body = json.loads(response.content)

        self.assertEqual(response.status_code, 403)
        self.assertFalse(body.get("result"))
        self.assertIn(f"cannot access resource(ID:{self.DENIED_INDEX_SET_ID})", body.get("message", ""))
        self.assertFalse(captured.get("view_called"))
        self.assertEqual(captured["view_set"], "SearchViewSet")
        self.assertEqual(captured["view_action"], "search")
        self.assertNotIn("login_username", captured)
        self.assertEqual(recorder.external_user, self.EXTERNAL_USER)
        self.assertEqual(recorder.action_id, ExternalPermissionActionEnum.LOG_SEARCH.value)
        self.assertEqual(recorder.resource, self.DENIED_INDEX_SET_ID)
        self.assertEqual(recorder.result_code, 403)


class TestDispatchExternalProxyExtractSelftest(_ProxySelftestMixin, TestCase):
    """【01】自测：提取 list_file 穿过代理时的身份与门禁。代理对提取不做索引集级资源校验。"""

    EXTRACT_URL = "/api/v1/log_extract/explorer/list_file/"

    def _post_proxy(self, captured):
        return self._call_proxy(url=self.EXTRACT_URL, method="POST", captured=captured)

    def test_extract_allowed_when_ticket_exists(self):
        self._create_ticket(ExternalPermissionActionEnum.LOG_EXTRACT.value, [])
        captured = {}

        response = self._post_proxy(captured)
        recorder = self._recorder()
        body = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(body.get("result"))
        self.assertTrue(captured.get("view_called"))
        self.assertEqual(captured["view_set"], "ExplorerViewSet")
        self.assertEqual(captured["view_action"], "list_file")
        self.assertEqual(captured["external_user_on_fake_request"], self.EXTERNAL_USER)
        self.assertEqual(captured["execution_user"], self.AUTHORIZER)
        self.assertEqual(captured["login_username"], self.AUTHORIZER)
        self.assertEqual(recorder.external_user, self.EXTERNAL_USER)
        self.assertEqual(recorder.authorizer, self.AUTHORIZER)
        self.assertEqual(recorder.action_id, ExternalPermissionActionEnum.LOG_EXTRACT.value)
        self.assertEqual(recorder.view_set, "ExplorerViewSet")
        self.assertEqual(recorder.view_action, "list_file")
        self.assertIsNone(recorder.resource)

    def test_extract_denied_when_no_ticket(self):
        captured = {}

        response = self._post_proxy(captured)
        recorder = self._recorder()
        body = json.loads(response.content)

        self.assertEqual(response.status_code, 403)
        self.assertFalse(body.get("result"))
        self.assertIn("has no permission", body.get("message", ""))
        self.assertFalse(captured.get("view_called"))
        self.assertEqual(captured["view_set"], "ExplorerViewSet")
        self.assertEqual(captured["view_action"], "list_file")
        self.assertNotIn("login_username", captured)
        self.assertEqual(recorder.external_user, self.EXTERNAL_USER)
        self.assertEqual(recorder.result_code, 403)


class TestDispatchExternalProxyClientLogSelftest(_ProxySelftestMixin, TestCase):
    """【01】自测：客户端日志 get_client_info 穿过代理时的身份与门禁。"""

    CLIENT_LOG_URL = "/api/v1/tgpa/client_info/?bk_biz_id=100605"

    def _get_proxy(self, captured):
        return self._call_proxy(url=self.CLIENT_LOG_URL, method="GET", captured=captured)

    def test_client_log_allowed_when_ticket_exists(self):
        self._create_ticket(ExternalPermissionActionEnum.CLIENT_LOG.value, [])
        captured = {}

        response = self._get_proxy(captured)
        recorder = self._recorder()
        body = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(body.get("result"))
        self.assertTrue(captured.get("view_called"))
        self.assertEqual(captured["view_set"], "TGPAViewSet")
        self.assertEqual(captured["view_action"], "get_client_info")
        self.assertEqual(captured["external_user_on_fake_request"], self.EXTERNAL_USER)
        self.assertEqual(captured["execution_user"], self.AUTHORIZER)
        self.assertEqual(captured["login_username"], self.AUTHORIZER)
        self.assertEqual(recorder.external_user, self.EXTERNAL_USER)
        self.assertEqual(recorder.authorizer, self.AUTHORIZER)
        self.assertEqual(recorder.action_id, ExternalPermissionActionEnum.CLIENT_LOG.value)
        self.assertEqual(recorder.view_set, "TGPAViewSet")
        self.assertEqual(recorder.view_action, "get_client_info")
        self.assertIsNone(recorder.resource)

    def test_client_log_denied_when_no_ticket(self):
        captured = {}

        response = self._get_proxy(captured)
        recorder = self._recorder()
        body = json.loads(response.content)

        self.assertEqual(response.status_code, 403)
        self.assertFalse(body.get("result"))
        self.assertIn("has no permission", body.get("message", ""))
        self.assertFalse(captured.get("view_called"))
        self.assertEqual(captured["view_set"], "TGPAViewSet")
        self.assertEqual(captured["view_action"], "get_client_info")
        self.assertNotIn("login_username", captured)
        self.assertEqual(recorder.external_user, self.EXTERNAL_USER)
        self.assertEqual(recorder.result_code, 403)
