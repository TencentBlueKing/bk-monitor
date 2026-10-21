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

from unittest.mock import patch

from django.test import SimpleTestCase

from apps.exceptions import ApiResultError
from apps.log_databus.handlers.collector_scenario.base import CollectorScenario


MODULE = "apps.log_databus.handlers.collector_scenario.base"


class TestCollectorScenarioDataId(SimpleTestCase):
    def test_create_v4_data_id_marks_created_from_bkdata(self):
        with (
            patch(f"{MODULE}.TransferApi.get_data_id", side_effect=ApiResultError),
            patch(f"{MODULE}.TransferApi.create_data_id", return_value={"bk_data_id": 1001}) as create_data_id,
            patch(f"{MODULE}.FeatureToggleObject.switch", return_value=True) as feature_switch,
        ):
            result = CollectorScenario.update_or_create_data_id(data_name="2_log_demo", bk_biz_id=2)

        self.assertEqual(result, 1001)
        feature_switch.assert_called_once_with("log_v4_data_link", 2)
        self.assertEqual(create_data_id.call_args.args[0]["created_from"], "bkdata")

    def test_create_non_v4_data_id_does_not_pass_created_from(self):
        with (
            patch(f"{MODULE}.TransferApi.get_data_id", side_effect=ApiResultError),
            patch(f"{MODULE}.TransferApi.create_data_id", return_value={"bk_data_id": 1001}) as create_data_id,
            patch(f"{MODULE}.FeatureToggleObject.switch", return_value=False) as feature_switch,
        ):
            result = CollectorScenario.update_or_create_data_id(data_name="2_log_demo", bk_biz_id=2)

        self.assertEqual(result, 1001)
        feature_switch.assert_called_once_with("log_v4_data_link", 2)
        self.assertNotIn("created_from", create_data_id.call_args.args[0])

    def test_existing_data_id_does_not_check_v4_source(self):
        with (
            patch(f"{MODULE}.TransferApi.get_data_id", return_value={"bk_data_id": 1001}),
            patch(f"{MODULE}.TransferApi.create_data_id") as create_data_id,
            patch(f"{MODULE}.TransferApi.modify_data_id"),
            patch(f"{MODULE}.ClusteringConfig.objects.filter") as filter_clustering,
            patch(f"{MODULE}.FeatureToggleObject.switch") as feature_switch,
        ):
            filter_clustering.return_value.first.return_value = None
            result = CollectorScenario.update_or_create_data_id(data_name="2_log_demo", bk_biz_id=2)

        self.assertEqual(result, 1001)
        create_data_id.assert_not_called()
        feature_switch.assert_not_called()
