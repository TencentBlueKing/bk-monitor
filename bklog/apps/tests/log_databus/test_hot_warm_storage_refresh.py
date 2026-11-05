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

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from apps.api import TransferApi
from apps.log_databus.tasks.collector import update_collector_storage_config
from apps.utils.local import del_local_param, get_local_param, get_request_tenant_id, set_local_param

CLUSTER_ID = 7
BIZ_ID = 1001
TENANT_ID = "tenant-a"


class HotWarmStorageRefreshTest(SimpleTestCase):
    def _collector(self, collector_config_id, bk_biz_id=BIZ_ID):
        collector = MagicMock()
        collector.collector_config_id = collector_config_id
        collector.bk_biz_id = bk_biz_id
        collector.collector_config_name_en = "demo_app_log"
        return collector

    def _collect_config(self):
        return {
            "retention": 30,
            "allocation_min_days": 7,
            "storage_replies": 1,
            "storage_shards_nums": 3,
            "etl_params": {"separator": "|"},
            "etl_config": "bk_log_text",
            "fields": [{"field_name": "log", "is_built_in": False}, {"field_name": "ip", "is_built_in": True}],
        }

    def _bind_handler(self, handler_cls):
        handler = handler_cls.get_instance.return_value
        handler.retrieve.return_value = self._collect_config()
        handler.get_clean_stash.return_value = None
        return handler

    @patch("apps.log_databus.tasks.collector.EtlHandler")
    @patch("apps.log_databus.tasks.collector.CollectorHandler")
    @patch("apps.log_databus.tasks.collector.Space.get_tenant_id", return_value=TENANT_ID)
    @patch("apps.log_databus.tasks.collector.CollectorConfig")
    @patch("apps.log_databus.tasks.collector.LogIndexSet")
    def test_refresh_keeps_hot_days_and_sets_tenant(self, index_set, collector_model, tenant, handler_cls, etl_cls):
        index_set.objects.filter.return_value.values_list.return_value = [21]
        collector_model.objects.filter.return_value = [self._collector(11)]
        self._bind_handler(handler_cls)
        seen = {}

        def update_or_create(**kwargs):
            seen["tenant"] = get_local_param("bk_tenant_id")
            seen["params"] = kwargs

        etl_cls.get_instance.return_value.update_or_create.side_effect = update_or_create

        update_collector_storage_config(CLUSTER_ID)

        self.assertEqual(seen["tenant"], TENANT_ID)
        self.assertEqual(seen["params"]["allocation_min_days"], 7)
        self.assertEqual(seen["params"]["retention"], 30)
        self.assertEqual(seen["params"]["fields"], [{"field_name": "log", "is_built_in": False}])
        self.assertIsNone(get_local_param("bk_tenant_id"))
        tenant.assert_called_once_with(bk_biz_id=BIZ_ID, is_need_default=False)

    @patch("apps.log_databus.tasks.collector.EtlHandler")
    @patch("apps.log_databus.tasks.collector.CollectorHandler")
    @patch("apps.log_databus.tasks.collector.Space.get_tenant_id", side_effect=[None, TENANT_ID])
    @patch("apps.log_databus.tasks.collector.CollectorConfig")
    @patch("apps.log_databus.tasks.collector.LogIndexSet")
    def test_one_collector_failure_does_not_stop_the_batch(
        self, index_set, collector_model, tenant, handler_cls, etl_cls
    ):
        index_set.objects.filter.return_value.values_list.return_value = [21, 22]
        collector_model.objects.filter.return_value = [self._collector(11), self._collector(12)]
        self._bind_handler(handler_cls)

        update_collector_storage_config(CLUSTER_ID)

        etl_cls.get_instance.return_value.update_or_create.assert_called_once()
        self.assertIsNone(get_local_param("bk_tenant_id"))
        self.assertEqual(tenant.call_count, 2)

    @patch("apps.log_databus.tasks.collector.EtlHandler")
    @patch("apps.log_databus.tasks.collector.CollectorHandler")
    @patch("apps.log_databus.tasks.collector.Space.get_tenant_id", side_effect=[RuntimeError("db down"), TENANT_ID])
    @patch("apps.log_databus.tasks.collector.CollectorConfig")
    @patch("apps.log_databus.tasks.collector.LogIndexSet")
    def test_tenant_query_exception_does_not_stop_the_batch(
        self, index_set, collector_model, tenant, handler_cls, etl_cls
    ):
        index_set.objects.filter.return_value.values_list.return_value = [21, 22]
        collector_model.objects.filter.return_value = [self._collector(11), self._collector(12)]
        self._bind_handler(handler_cls)
        seen = {}

        def update_or_create(**kwargs):
            seen["tenant"] = get_local_param("bk_tenant_id")
            seen["collector_id"] = kwargs

        etl_cls.get_instance.return_value.update_or_create.side_effect = update_or_create

        update_collector_storage_config(CLUSTER_ID)

        etl_cls.get_instance.return_value.update_or_create.assert_called_once()
        self.assertEqual(seen["tenant"], TENANT_ID)
        self.assertEqual(etl_cls.get_instance.call_args.args[0], 12)
        self.assertIsNone(get_local_param("bk_tenant_id"))
        self.assertEqual(tenant.call_count, 2)

    @patch("apps.log_databus.tasks.collector.EtlHandler")
    @patch("apps.log_databus.tasks.collector.CollectorHandler")
    @patch("apps.log_databus.tasks.collector.Space.get_tenant_id")
    @patch("apps.log_databus.tasks.collector.CollectorConfig")
    @patch("apps.log_databus.tasks.collector.LogIndexSet")
    def test_empty_biz_id_skips_without_default_tenant(self, index_set, collector_model, tenant, handler_cls, etl_cls):
        index_set.objects.filter.return_value.values_list.return_value = [21]
        collector_model.objects.filter.return_value = [self._collector(11, bk_biz_id=0)]

        update_collector_storage_config(CLUSTER_ID)

        tenant.assert_not_called()
        handler_cls.get_instance.assert_not_called()
        etl_cls.get_instance.assert_not_called()
        self.assertIsNone(get_local_param("bk_tenant_id"))

    @override_settings(ENABLE_MULTI_TENANT_MODE=False, BK_APP_TENANT_ID="system")
    def test_background_tenant_overrides_app_default(self):
        set_local_param("bk_tenant_id", TENANT_ID)
        try:
            self.assertEqual(get_request_tenant_id(), TENANT_ID)
        finally:
            del_local_param("bk_tenant_id")
        self.assertEqual(get_request_tenant_id(), "system")

    @override_settings(ENABLE_MULTI_TENANT_MODE=False, BK_APP_TENANT_ID="system")
    @patch("apps.api.base.requests.session")
    def test_cluster_lookup_sends_background_tenant_header(self, session_factory):
        session = MagicMock()
        session.headers = {}
        response = MagicMock(status_code=200)
        response.json.return_value = {"result": True, "data": [{"cluster_id": CLUSTER_ID}]}
        session.request.return_value = response
        session_factory.return_value = session
        api = TransferApi.get_cluster_info
        set_local_param("bk_tenant_id", TENANT_ID)
        try:
            with patch.object(api, "before_request", lambda params: params):
                from apps.log_databus.handlers.storage import StorageHandler

                info = StorageHandler(CLUSTER_ID).get_cluster_info_by_id()
        finally:
            del_local_param("bk_tenant_id")

        self.assertEqual(info["cluster_id"], CLUSTER_ID)
        self.assertEqual(session.headers["X-Bk-Tenant-Id"], TENANT_ID)
        self.assertNotIn("bk_tenant_id", session.request.call_args.kwargs["params"])
