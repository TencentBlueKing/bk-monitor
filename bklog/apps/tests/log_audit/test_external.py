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

import os
from unittest import mock

from bk_audit.log.exporters import BaseExporter
from django.core.exceptions import BadRequest, PermissionDenied, SuspiciousOperation
from django.http import Http404
from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from apps.iam import ActionEnum
from apps.log_audit.client import bk_audit_client, otlp_report_enabled
from apps.log_audit.external import ExternalAuditRecorder, resolve_exception_status_code

EXTERNAL_USER = "external_tester@example.com"
AUTHORIZER = "authorizer_tester"
SPACE_UID = "bkcc__2"
INDEX_SET_ID = 1

CLIENT_IP = "127.0.0.2"
PROXY_IP = "127.0.0.3"

OUTER_META = {
    "HTTP_X_FORWARDED_FOR": f"{CLIENT_IP}, {PROXY_IP}",
    "HTTP_USER_AGENT": "Mozilla/5.0 ExternalBrowser",
    "REMOTE_ADDR": PROXY_IP,
}


class CaptureExporter(BaseExporter):
    """捕获审计事件，避免测试真正上报"""

    is_delay = False

    def __init__(self):
        self.events = []

    def export(self, events):
        self.events.extend(event.to_json() for event in events)


class FakeOuterRequest:
    """模拟外部代理的外层真实请求"""

    def __init__(self, meta=None):
        self.META = OUTER_META.copy() if meta is None else meta
        self.request_id = "test-request-id"


class TestExternalAuditRecorder(SimpleTestCase):
    def setUp(self):
        self.exporter = CaptureExporter()
        patcher = mock.patch.object(bk_audit_client._log, "_sync_exporters", [self.exporter])
        patcher.start()
        self.addCleanup(patcher.stop)

    @staticmethod
    def build_recorder(**kwargs):
        recorder = ExternalAuditRecorder(FakeOuterRequest())
        recorder.external_user = EXTERNAL_USER
        recorder.authorizer = AUTHORIZER
        recorder.space_uid = SPACE_UID
        recorder.view_set = "SearchViewSet"
        recorder.view_action = "search"
        recorder.action_id = "log_search"
        for key, value in kwargs.items():
            setattr(recorder, key, value)
        return recorder

    def test_audit_subject_is_external_user(self):
        """审计主体必须是外部账号，而不是被替换上去的授权人"""
        recorder = self.build_recorder(resource=INDEX_SET_ID)
        recorder.push()

        self.assertEqual(len(self.exporter.events), 1)
        event = self.exporter.events[0]
        self.assertEqual(event["username"], EXTERNAL_USER)
        self.assertEqual(event["scope_type"], "space_uid")
        self.assertEqual(event["scope_id"], SPACE_UID)
        self.assertEqual(event["instance_id"], str(INDEX_SET_ID))
        self.assertEqual(event["result_code"], 0)

    def test_authorizer_goes_to_extend_data_not_identify_src(self):
        """审计中心对这两个标准字段没有约定词表，含义待定，授权人只走 extend_data"""
        recorder = self.build_recorder(resource=INDEX_SET_ID)
        recorder.push()

        event = self.exporter.events[0]
        self.assertEqual(event["user_identify_src"], "")
        self.assertEqual(event["user_identify_src_username"], "")
        self.assertEqual(event["extend_data"]["authorizer"], AUTHORIZER)

    def test_action_matches_internal_definition(self):
        """外部访问要和内部版上报同一个 action 与资源类型，审计中心才能按操作统一查询"""
        recorder = self.build_recorder(resource=INDEX_SET_ID)
        recorder.push()

        event = self.exporter.events[0]
        self.assertEqual(event["action_id"], ActionEnum.SEARCH_LOG.id)
        self.assertEqual(event["resource_type_id"], "LogSearch")
        # view_set / view_action 是外部代理独有的细粒度信息，放扩展字段保留
        self.assertEqual(event["extend_data"]["view_set"], "SearchViewSet")
        self.assertEqual(event["extend_data"]["view_action"], "search")
        self.assertEqual(event["extend_data"]["external_user"], EXTERNAL_USER)
        self.assertEqual(event["extend_data"]["authorizer"], AUTHORIZER)

    def test_client_log_maps_to_download_action(self):
        recorder = self.build_recorder(action_id="client_log", view_set="TGPATaskViewSet", view_action="download_file")
        recorder.push()

        event = self.exporter.events[0]
        self.assertEqual(event["action_id"], ActionEnum.DOWNLOAD_CLIENT_LOG.id)
        self.assertEqual(event["resource_type_id"], "ClientLog")

    def test_access_source_ip_from_outer_request(self):
        """fake_request 的 REMOTE_ADDR 恒为 127.0.0.1，IP 必须取自外层请求"""
        recorder = self.build_recorder()
        recorder.push()

        event = self.exporter.events[0]
        self.assertEqual(event["access_source_ip"], CLIENT_IP)
        self.assertEqual(event["access_user_agent"], "Mozilla/5.0 ExternalBrowser")
        self.assertEqual(event["request_id"], "test-request-id")

    def test_access_source_ip_fallback_to_remote_addr(self):
        recorder = self.build_recorder()
        recorder.request = FakeOuterRequest({"REMOTE_ADDR": PROXY_IP})
        recorder.push()

        self.assertEqual(self.exporter.events[0]["access_source_ip"], PROXY_IP)

    def test_denied_access_is_recorded(self):
        """拒绝事件的审计价值高于成功访问，必须留痕"""
        message = f"external_user:{EXTERNAL_USER} cannot access resource(ID:99)."
        recorder = self.build_recorder()
        recorder.set_result(403, message)
        recorder.push()

        event = self.exporter.events[0]
        self.assertEqual(event["result_code"], 403)
        self.assertEqual(event["result_content"], message)
        self.assertEqual(event["username"], EXTERNAL_USER)

    def test_common_action_success_is_ignored(self):
        """元数据接口调用量大且不涉及日志数据，成功访问不上报"""
        recorder = self.build_recorder(action_id="log_common", view_set="MetaViewSet")
        recorder.push()

        self.assertEqual(self.exporter.events, [])

    def test_common_action_denied_is_recorded(self):
        recorder = self.build_recorder(action_id="log_common", view_set="MetaViewSet")
        recorder.set_result(403, "denied")
        recorder.push()

        self.assertEqual(len(self.exporter.events), 1)

    def test_unresolved_action_is_skipped(self):
        """action_id 为空是 AuditEvent 的必填校验项，跳过而不是抛 AssertionError"""
        for action_id in ("", "not_an_external_action"):
            with self.subTest(action_id=action_id):
                self.exporter.events.clear()
                recorder = self.build_recorder(action_id=action_id)
                recorder.push()

                self.assertEqual(self.exporter.events, [])

    def test_empty_external_user_is_skipped(self):
        recorder = self.build_recorder(external_user="")
        recorder.push()

        self.assertEqual(self.exporter.events, [])

    def test_push_never_raises(self):
        """审计上报失败不能影响外部用户的正常请求"""
        recorder = self.build_recorder()
        recorder.request = object()

        recorder.push()

        self.assertEqual(self.exporter.events, [])


class TestOtlpReportEnabled(SimpleTestCase):
    """这个开关决定审计事件能否到达审计中心，收紧条件会静默关掉现网上报"""

    ENV = {"BKAPP_OTEL_LOG_ENDPOINT": "http://collector:4317", "BKAPP_OTEL_LOG_BK_DATA_TOKEN": "token"}

    def test_endpoint_and_token_is_enough(self):
        """现网只配 endpoint 与 token，bk-collector 按 token 路由，不能额外要求 data_id"""
        with mock.patch.dict(os.environ, self.ENV, clear=True):
            self.assertTrue(otlp_report_enabled())

    def test_missing_endpoint_or_token_disables_report(self):
        for missing in self.ENV:
            with self.subTest(missing=missing), mock.patch.dict(os.environ, self.ENV, clear=True):
                del os.environ[missing]
                self.assertFalse(otlp_report_enabled())


class TestResolveExceptionStatusCode(SimpleTestCase):
    """异常统一记 500 会把越权和资源不存在都算成服务端故障"""

    def test_django_builtin_exceptions(self):
        self.assertEqual(resolve_exception_status_code(Http404()), 404)
        self.assertEqual(resolve_exception_status_code(PermissionDenied()), 403)
        self.assertEqual(resolve_exception_status_code(BadRequest()), 400)
        self.assertEqual(resolve_exception_status_code(SuspiciousOperation()), 400)

    def test_drf_exception_uses_own_status_code(self):
        self.assertEqual(resolve_exception_status_code(ValidationError("invalid")), 400)

    def test_unknown_exception_falls_back_to_500(self):
        self.assertEqual(resolve_exception_status_code(ValueError("boom")), 500)

    def test_non_int_status_code_falls_back_to_500(self):
        class WeirdError(Exception):
            status_code = "403"

        self.assertEqual(resolve_exception_status_code(WeirdError()), 500)
