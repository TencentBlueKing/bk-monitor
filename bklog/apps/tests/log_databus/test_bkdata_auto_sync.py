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

from unittest.mock import Mock, call, patch

from django.test import SimpleTestCase

from apps.feature_toggle.handlers.toggle import FeatureToggleObject, Toggle
from apps.log_clustering.components.collections.data_access_component import CreateBkdataDataIdService
from apps.log_databus.models import CollectorConfig
from apps.log_databus.tasks import bkdata


class TestBkdataAutoSync(SimpleTestCase):
    def collector(self, biz_id=1, data_biz_id=None):
        collector = CollectorConfig(
            collector_config_id=1,
            bk_biz_id=biz_id,
            bkdata_biz_id=data_biz_id,
            bk_data_id=100,
            bkdata_data_id=None,
            bkdata_data_id_sync_times=2,
        )
        collector.save = Mock()
        return collector

    def toggle(self, name):
        if name == "log_v4_data_link":
            return Toggle(name=name, status="debug", biz_id_white_list=[1, -1])
        return Toggle(name=name, status="on")

    @patch.object(FeatureToggleObject, "toggle")
    @patch.object(bkdata, "create_bkdata_data_id")
    @patch.object(CollectorConfig, "objects")
    def test_async_sync_respects_business_rollout(self, get_collector, create_data_id, get_toggle):
        get_toggle.side_effect = self.toggle
        # 同时覆盖普通业务、非 CC 空间和数据归属业务优先级。
        cases = [(1, None, True), (2, None, False), (-1, None, True), (2, 1, True), (1, 2, False)]
        for biz_id, data_biz_id, skipped in cases:
            with self.subTest(biz_id=biz_id, data_biz_id=data_biz_id):
                collector = self.collector(biz_id, data_biz_id)
                get_collector.get.return_value = collector
                create_data_id.reset_mock()
                bkdata.async_create_bkdata_data_id(collector.collector_config_id, "test_operator")
                if skipped:
                    create_data_id.assert_not_called()
                else:
                    create_data_id.assert_called_once_with(collector, "test_operator")
                collector.save.assert_not_called()
                self.assertIsNone(collector.bkdata_data_id)
                self.assertEqual(collector.bkdata_data_id_sync_times, 2)

    @patch.object(FeatureToggleObject, "toggle")
    @patch.object(bkdata, "create_bkdata_data_id")
    @patch.object(CollectorConfig, "objects")
    def test_review_skips_v4_without_changing_retry_state(self, filter_collectors, create_data_id, get_toggle):
        get_toggle.side_effect = self.toggle
        v4 = self.collector(1)
        legacy = self.collector(2)
        failed = self.collector(3)
        exhausted = self.collector(4)
        exhausted.bkdata_data_id_sync_times = 3
        filter_collectors.filter.return_value = [v4, legacy, failed, exhausted]
        create_data_id.side_effect = [None, RuntimeError("test sync failure")]

        bkdata.review_bkdata_data_id()

        filter_collectors.filter.assert_called_once_with(bkdata_data_id__isnull=True)
        self.assertEqual(
            create_data_id.call_args_list, [call(legacy, raise_exception=True), call(failed, raise_exception=True)]
        )
        v4.save.assert_not_called()
        self.assertIsNone(v4.bkdata_data_id)
        self.assertEqual(v4.bkdata_data_id_sync_times, 2)
        self.assertEqual(legacy.bkdata_data_id_sync_times, 0)
        self.assertEqual(failed.bkdata_data_id_sync_times, 3)
        legacy.save.assert_called_once()
        failed.save.assert_called_once()
        exhausted.save.assert_not_called()

    @patch.object(FeatureToggleObject, "toggle")
    @patch.object(bkdata.Space, "get_tenant_id", return_value="test_tenant")
    @patch.object(bkdata.BkDataAccessApi, "get_deploy_summary", return_value={})
    @patch("apps.log_clustering.components.collections.data_access_component.ClusteringConfig.objects")
    @patch.object(CollectorConfig, "objects")
    def test_clustering_still_syncs_on_demand_for_v4(
        self, filter_collectors, get_clustering, get_summary, get_tenant, get_toggle
    ):
        get_toggle.side_effect = self.toggle
        collector = self.collector(1)
        filter_collectors.filter.return_value.first.return_value = collector
        clustering = Mock(bkdata_data_id=None)
        get_clustering.get.return_value = clustering
        data = Mock()
        data.get_one_of_inputs.return_value = collector.collector_config_id

        self.assertTrue(CreateBkdataDataIdService()._execute(data, None))

        get_summary.assert_called_once_with({"raw_data_id": 100, "bk_biz_id": 1}, bk_tenant_id="test_tenant")
        self.assertEqual(collector.bkdata_data_id, 100)
        self.assertEqual(clustering.bkdata_data_id, 100)
        collector.save.assert_called_once_with(update_fields=["bkdata_data_id"])
        clustering.save.assert_called_once()
