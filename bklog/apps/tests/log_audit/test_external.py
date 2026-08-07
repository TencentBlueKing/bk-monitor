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

from unittest import mock

from bk_audit.log.exporters import BaseExporter
from django.test import SimpleTestCase

from apps.log_audit.client import bk_audit_client
from apps.log_audit.external import ExternalAuditRecorder

EXTERNAL_USER = "external_user@tai"
AUTHORIZER = "authorizer_user"
SPACE_UID = "bkcc__615"
INDEX_SET_ID = 12902

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
        self.assertEqual(event["user_identify_src_username"], AUTHORIZER)
        self.assertEqual(event["user_identify_src"], "po_external")
        self.assertEqual(event["scope_type"], "space_uid")
        self.assertEqual(event["scope_id"], SPACE_UID)
        self.assertEqual(event["action_id"], "log_search")
        self.assertEqual(event["resource_type_id"], "SearchViewSet")
        self.assertEqual(event["instance_id"], str(INDEX_SET_ID))
        self.assertEqual(event["result_code"], 0)

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
        recorder = self.build_recorder(action_id="")
        recorder.push()

        self.assertEqual(self.exporter.events, [])

    def test_push_never_raises(self):
        """审计上报失败不能影响外部用户的正常请求"""
        recorder = self.build_recorder()
        recorder.request = object()

        recorder.push()

        self.assertEqual(self.exporter.events, [])
