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

from apps.log_databus.tasks.collector import update_collector_storage_config
from apps.utils.local import del_local_param, get_local_param, get_request_tenant_id, set_local_param


class HotWarmStorageRefreshTest(SimpleTestCase):
    def _collector(self, collector_config_id):
        collector = MagicMock()
        collector.collector_config_id = collector_config_id
        collector.bk_biz_id = -4759
        collector.collector_config_name_en = "mho_public_tokyo_svr_log"
        return collector

    def _collect_config(self):
        return {
            "retention": 60,
            "allocation_min_days": 10,
            "storage_replies": 0,
            "storage_shards_nums": 38,
            "etl_params": {"separator": "|"},
            "etl_config": "bk_log_text",
            "fields": [{"field_name": "log", "is_built_in": False}, {"field_name": "ip", "is_built_in": True}],
        }

    @patch("apps.log_databus.tasks.collector.EtlHandler")
    @patch("apps.log_databus.tasks.collector.CollectorHandler")
    @patch("apps.log_databus.tasks.collector._space_tenant_id", return_value="tencent")
    @patch("apps.log_databus.tasks.collector.CollectorConfig")
    @patch("apps.log_databus.tasks.collector.LogIndexSet")
    def test_refresh_keeps_hot_days_and_sets_tenant(self, index_set, collector_model, tenant, handler_cls, etl_cls):
        index_set.objects.filter.return_value.values_list.return_value = [2902]
        collector_model.objects.filter.return_value = [self._collector(2482)]
        handler = handler_cls.get_instance.return_value
        handler.retrieve.return_value = self._collect_config()
        handler.get_clean_stash.return_value = None
        seen = {}

        def update_or_create(**kwargs):
            seen["tenant"] = get_local_param("bk_tenant_id")
            seen["params"] = kwargs

        etl_cls.get_instance.return_value.update_or_create.side_effect = update_or_create

        update_collector_storage_config(10175)

        self.assertEqual(seen["tenant"], "tencent")
        self.assertEqual(seen["params"]["allocation_min_days"], 10)
        self.assertEqual(seen["params"]["retention"], 60)
        self.assertEqual(seen["params"]["fields"], [{"field_name": "log", "is_built_in": False}])
        self.assertIsNone(get_local_param("bk_tenant_id"))
        tenant.assert_called_once_with(-4759)

    @patch("apps.log_databus.tasks.collector.EtlHandler")
    @patch("apps.log_databus.tasks.collector.CollectorHandler")
    @patch("apps.log_databus.tasks.collector._space_tenant_id", side_effect=["", "tencent"])
    @patch("apps.log_databus.tasks.collector.CollectorConfig")
    @patch("apps.log_databus.tasks.collector.LogIndexSet")
    def test_one_collector_failure_does_not_stop_the_batch(
        self, index_set, collector_model, tenant, handler_cls, etl_cls
    ):
        index_set.objects.filter.return_value.values_list.return_value = [1, 2]
        collector_model.objects.filter.return_value = [self._collector(1), self._collector(2)]
        handler = handler_cls.get_instance.return_value
        handler.retrieve.return_value = self._collect_config()
        handler.get_clean_stash.return_value = None

        update_collector_storage_config(10175)

        etl_cls.get_instance.return_value.update_or_create.assert_called_once()
        self.assertIsNone(get_local_param("bk_tenant_id"))
        self.assertEqual(tenant.call_count, 2)

    @override_settings(ENABLE_MULTI_TENANT_MODE=False, BK_APP_TENANT_ID="system")
    def test_background_tenant_overrides_app_default(self):
        set_local_param("bk_tenant_id", "tencent")
        try:
            self.assertEqual(get_request_tenant_id(), "tencent")
        finally:
            del_local_param("bk_tenant_id")
        self.assertEqual(get_request_tenant_id(), "system")

    @patch("apps.log_databus.handlers.storage.TransferApi.get_cluster_info", return_value=[{"cluster_id": 10175}])
    def test_cluster_lookup_passes_explicit_tenant(self, get_cluster_info):
        from apps.log_databus.handlers.storage import StorageHandler

        set_local_param("bk_tenant_id", "tencent")
        try:
            StorageHandler(10175).get_cluster_info_by_id()
        finally:
            del_local_param("bk_tenant_id")
        get_cluster_info.assert_called_once_with({"cluster_id": 10175}, bk_tenant_id="tencent")
