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
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from apps.api.modules.cmsi import _CmsiApi
from apps.log_clustering.tasks import subscription
from apps.log_databus.models import RestoreConfig
from apps.log_search.tasks import async_export, unify_query_async_export
from apps.log_unifyquery.handler import scene_async_export
from apps.utils.notify import EmailNotify


class CmsiContractTest(SimpleTestCase):
    def setUp(self):
        self.session = Mock()
        self.session.headers = {}
        self.response = Mock(status_code=200)
        self.response.json.side_effect = lambda: {
            "data": {"summary": {"total": 1, "succeeded": 1, "failed": 0}, "message": "", "details": {}}
        }
        self.session.request.return_value = self.response
        for patcher in (
            patch("apps.api.base.requests.session", return_value=self.session),
            patch(
                "apps.api.modules.cmsi.add_esb_info_before_request",
                side_effect=lambda params: dict(params, bk_username="worker"),
            ),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def request_body(self):
        return json.loads(self.session.request.call_args.kwargs["data"])

    @override_settings(USE_APIGW=True, PAAS_API_HOST="https://gateway.example", ENVIRONMENT="prod")
    def test_gateway_channels_preserve_caller_fields(self):
        self.response.json.side_effect = lambda: {
            "data": [
                {"type": "mail", "name": "Email", "enabled": True},
                {"type": "weixin", "name": "Weixin", "enabled": False},
            ]
        }
        result = _CmsiApi().get_msg_type({}, bk_tenant_id="tenant-a", request_cookies=False)
        self.assertEqual(
            self.session.request.call_args.kwargs["url"], "https://gateway.example/api/bk-cmsi/prod/v1/channels"
        )
        self.assertEqual([(row["label"], row["is_active"]) for row in result], [("Email", True), ("Weixin", False)])
        self.assertEqual(self.session.headers["X-Bk-Tenant-Id"], "tenant-a")

    @override_settings(USE_APIGW=False)
    def test_esb_channels_unchanged(self):
        rows = [{"type": "mail", "label": "Email", "is_active": True}]
        self.response.json.side_effect = lambda: {"result": True, "data": deepcopy(rows)}
        self.assertEqual(_CmsiApi().get_msg_type({}, bk_tenant_id="tenant-a", request_cookies=False), rows)
        self.assertTrue(self.session.request.call_args.kwargs["url"].endswith("/cmsi/get_msg_type/"))

    @override_settings(USE_APIGW=True)
    def test_gateway_mail_recipient_forms(self):
        for receivers in ("alice,bob", ["alice", "bob"]):
            with self.subTest(receivers=receivers):
                result = _CmsiApi().send_mail(
                    {"receivers": receivers, "title": "title", "content": "content"},
                    bk_tenant_id="tenant-a",
                    request_cookies=False,
                )
                self.assertEqual(self.request_body()["receiver__username"], ["alice", "bob"])
                self.assertEqual(result["summary"]["succeeded"], 1)
                self.assertEqual(self.session.headers["X-Bk-Tenant-Id"], "tenant-a")

    @override_settings(USE_APIGW=True)
    def test_gateway_mail_addresses_and_cc(self):
        _CmsiApi().send_mail(
            {
                "receiver": "alice@example.com,bob@example.com",
                "receiver__username": ["alice"],
                "cc": ["carol@example.com"],
                "cc__username": "carol,dave",
                "title": "title",
                "content": "content",
            },
            bk_tenant_id="tenant-a",
            request_cookies=False,
        )
        body = self.request_body()
        self.assertEqual(body["receiver"], ["alice@example.com", "bob@example.com"])
        self.assertEqual(body["receiver__username"], ["alice"])
        self.assertEqual(body["cc"], ["carol@example.com"])
        self.assertEqual(body["cc__username"], ["carol", "dave"])

    @override_settings(USE_APIGW=True)
    def test_gateway_weixin_body_and_tenant(self):
        for receivers in ("alice,bob", ["alice", "bob"]):
            with self.subTest(receivers=receivers):
                _CmsiApi().send_weixin(
                    {"receivers": receivers, "title": "title", "content": "content"},
                    bk_tenant_id="tenant-a",
                    request_cookies=False,
                )
                body = self.request_body()
                self.assertEqual(body["receiver__username"], ["alice", "bob"])
                self.assertEqual(body["message_data"], {"heading": "title", "message": "content"})
                self.assertNotIn("data", body)
                self.assertTrue(self.session.request.call_args.kwargs["url"].endswith("/v1/send_weixin/"))
                self.assertEqual(self.session.headers["X-Bk-Tenant-Id"], "tenant-a")

    @override_settings(USE_APIGW=False)
    def test_esb_send_payloads_unchanged(self):
        self.response.json.side_effect = lambda: {"result": True, "data": True}
        api = _CmsiApi()
        for name in ("send_mail", "send_weixin"):
            with self.subTest(api=name):
                self.assertTrue(
                    getattr(api, name)(
                        {"receivers": ["alice", "bob"], "title": "title", "content": "content"},
                        bk_tenant_id="tenant-a",
                        request_cookies=False,
                    )
                )
                body = self.request_body()
                self.assertEqual(body["receiver__username"], "alice,bob")
                self.assertNotIn("message_data", body)
                self.assertIn("/compapi/v2/cmsi/", self.session.request.call_args.kwargs["url"])
                if name == "send_weixin":
                    self.assertEqual(body["data"], {"heading": "title", "message": "content"})
                else:
                    self.assertEqual(body["content"], "content")

    @override_settings(USE_APIGW=True)
    def test_email_notify_internal_and_external_tenant(self):
        for external, receivers, field in (
            (False, "alice", "receiver__username"),
            (True, "alice@example.com", "receiver"),
        ):
            with self.subTest(external=external), patch("apps.utils.notify.CmsiApi", _CmsiApi()):
                EmailNotify().send(receivers, "title", "content", is_external=external, bk_tenant_id="task-tenant")
                self.assertEqual(self.request_body()[field], [receivers])
                if external:
                    self.assertEqual(self.request_body()["receiver__username"], [])
                self.assertEqual(self.session.headers["X-Bk-Tenant-Id"], "task-tenant")


class NotificationTenantTest(SimpleTestCase):
    def test_all_export_notification_paths_use_task_business(self):
        cases = (
            (async_export.AsyncExportUtils, {"index_set_id": 1}),
            (async_export.UnionAsyncExportUtils, {"index_set_ids": [1]}),
            (unify_query_async_export.AsyncExportUtils, {"index_set_id": 1}),
            (unify_query_async_export.UnionAsyncExportUtils, {"index_set_ids": [1]}),
            (scene_async_export.SceneExportUtils, {}),
        )
        index_set = SimpleNamespace(index_set_name="test", indexes=[{"result_table_id": "a.b"}])
        task = SimpleNamespace(bk_biz_id=-12, created_by="alice", file_size=1, request_param={}, download_url="test")
        for cls, params in cases:
            with (
                self.subTest(cls=cls),
                patch("apps.log_search.models.LogIndexSet.objects.get", return_value=index_set),
                patch("apps.log_search.models.LogIndexSet.objects.filter", return_value=[index_set]),
                patch("apps.log_search.models.Space.get_tenant_id", return_value="task-tenant") as tenant,
            ):
                utils = cls.__new__(cls)
                utils.notify = Mock()
                utils.is_external = False
                utils.send_msg(async_task=task, search_url_path="test", language="zh", **params)
                tenant.assert_called_once_with(bk_biz_id=-12)
                self.assertEqual(utils.notify.send.call_args.kwargs["bk_tenant_id"], "task-tenant")

    def test_restore_notifies_both_channels_in_index_space(self):
        restore = RestoreConfig(index_set_id=1, notice_user="alice")
        with (
            patch.object(restore, "save"),
            patch("apps.log_databus.models.LogIndexSet.delete_tag_by_name"),
            patch("apps.log_databus.models.LogIndexSet.set_tag"),
            patch("apps.log_databus.models.LogIndexSet.objects.get", return_value=SimpleNamespace(space_uid="bkcc__1")),
            patch("apps.log_databus.models.Space.get_tenant_id", return_value="restore-tenant") as tenant,
            patch("apps.log_databus.models.CmsiApi") as cmsi,
        ):
            restore.done(10)
            tenant.assert_called_once_with(space_uid="bkcc__1")
            self.assertEqual(cmsi.send_mail.call_args.kwargs["bk_tenant_id"], "restore-tenant")
            self.assertEqual(cmsi.send_weixin.call_args.kwargs["bk_tenant_id"], "restore-tenant")

    def test_subscription_mail_forwards_tenant(self):
        with (
            patch.object(subscription, "render_title", return_value="title"),
            patch.object(subscription, "render_template", return_value="content"),
            patch.object(subscription, "CmsiApi") as cmsi,
        ):
            subscription.send_mail(
                {"language": "zh", "title": "title"}, [{"id": "alice"}], "test", "subscription-tenant"
            )
            self.assertEqual(cmsi.send_mail.call_args.kwargs["bk_tenant_id"], "subscription-tenant")

    def test_subscription_task_resolves_index_space(self):
        config = SimpleNamespace(
            index_set_id=1,
            log_col_show_type="pattern",
            title="title",
            year_on_year_hour=0,
            group_by=[],
            subscription_type=subscription.SubscriptionTypeEnum.EMAIL.value,
            receivers=[{"id": "alice"}],
        )
        with (
            patch.object(subscription, "query_patterns", return_value=[{"percentage": 1}]),
            patch.object(
                subscription.ClusteringConfig, "get_by_index_set_id", return_value=SimpleNamespace(clustering_fields=[])
            ),
            patch.object(
                subscription, "clean_pattern", return_value={"patterns": {"data": [1]}, "new_patterns": {"data": []}}
            ),
            patch.object(subscription.LogIndexSet.objects, "filter") as indexes,
            patch.object(subscription, "generate_log_search_url", return_value="test"),
            patch.object(subscription.Space, "get_tenant_id", return_value="subscription-tenant") as tenant,
            patch.object(subscription, "send_mail") as send_mail,
            patch.object(subscription.timezone, "activate"),
            patch.object(subscription, "set_local_param"),
        ):
            indexes.return_value.first.return_value = SimpleNamespace(index_set_name="test", space_uid="bkcc__1")
            subscription.send(config, {}, "test", "zh", "test", "UTC")
            tenant.assert_called_once_with(space_uid="bkcc__1")
            self.assertEqual(send_mail.call_args.kwargs["bk_tenant_id"], "subscription-tenant")
