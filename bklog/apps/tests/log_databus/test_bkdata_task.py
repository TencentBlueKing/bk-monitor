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

from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from apps.exceptions import ApiResultError
from apps.log_databus.models import CollectorConfig
from apps.log_databus.tasks.bkdata import create_bkdata_data_id, get_collector_maintainers_and_platform_username


class TestBkdataTask(SimpleTestCase):
    def _collector_config(self):
        collector_config = CollectorConfig(
            collector_config_id=1,
            bk_biz_id=19076,
            bk_data_id=1596434,
            bkdata_data_id=None,
            collector_config_name="BCS-K8S-40836_nrc_test_sv_log_std",
            collector_config_name_en="bcs_k8s_40836_nrc_test_sv_log_std",
            table_id="19076_bklog.bcs_k8s_40836_nrc_test_sv_log_std",
            index_set_id=3629,
            description="BCS-K8S-40836_nrc_test_sv_log_std",
            created_by="v_wzwenwei",
            updated_by="admin",
        )
        collector_config.save = Mock()
        return collector_config

    @patch("apps.log_databus.tasks.bkdata.CCApi.get_app_list")
    def test_get_collector_maintainers_passes_tenant_to_cmdb(self, mock_get_app_list):
        collector_config = self._collector_config()
        mock_get_app_list.return_value = {
            "count": 1,
            "info": [{"bk_biz_maintainer": "qingweisum,mlcheong,jamzzhu,v_fqxinwang"}],
        }

        result = get_collector_maintainers_and_platform_username(
            collector_config=collector_config,
            bk_biz_id=19076,
            bk_tenant_id="tencent",
            platform_username=None,
        )

        self.assertEqual(result["platform_username"], "jamzzhu")
        self.assertEqual(
            result["maintainers"],
            {"qingweisum", "mlcheong", "jamzzhu", "v_fqxinwang", "v_wzwenwei", "admin"},
        )
        mock_get_app_list.assert_called_once()
        self.assertEqual(mock_get_app_list.call_args.kwargs["bk_tenant_id"], "tencent")

    @patch("apps.log_databus.tasks.bkdata.FeatureToggleObject.switch", return_value=True)
    @patch("apps.log_databus.tasks.bkdata.Space.get_tenant_id", return_value="tencent")
    @patch("apps.log_databus.tasks.bkdata.CCApi.get_app_list")
    @patch("apps.log_databus.tasks.bkdata.BkDataAccessApi.deploy_plan_post")
    @patch("apps.log_databus.tasks.bkdata.BkDataAccessApi.get_deploy_summary")
    def test_create_bkdata_data_id_passes_tenant_to_bkdata_and_cmdb(
        self,
        mock_get_deploy_summary,
        mock_deploy_plan_post,
        mock_get_app_list,
        mock_get_tenant_id,
        mock_feature_switch,
    ):
        collector_config = self._collector_config()
        mock_get_deploy_summary.side_effect = ApiResultError("permission denied", code="1511001")
        mock_get_app_list.return_value = {
            "count": 1,
            "info": [{"bk_biz_maintainer": "qingweisum,mlcheong,jamzzhu,v_fqxinwang"}],
        }
        mock_deploy_plan_post.return_value = {"raw_data_id": collector_config.bk_data_id}

        create_bkdata_data_id(collector_config)

        mock_get_tenant_id.assert_called_once_with(bk_biz_id=19076)
        self.assertEqual(mock_get_deploy_summary.call_args.kwargs["bk_tenant_id"], "tencent")
        self.assertEqual(mock_get_app_list.call_args.kwargs["bk_tenant_id"], "tencent")
        self.assertEqual(mock_deploy_plan_post.call_args.kwargs["bk_tenant_id"], "tencent")
        self.assertEqual(mock_deploy_plan_post.call_args.kwargs["params"]["bk_username"], "jamzzhu")
        self.assertEqual(collector_config.bkdata_data_id, collector_config.bk_data_id)
        collector_config.save.assert_called_once_with(update_fields=["bkdata_data_id"])

    @patch("apps.log_databus.tasks.bkdata.FeatureToggleObject.switch", return_value=True)
    @patch("apps.log_databus.tasks.bkdata.Space.get_tenant_id", return_value="tencent")
    @patch("apps.log_databus.tasks.bkdata.CCApi.get_app_list")
    @patch("apps.log_databus.tasks.bkdata.BkDataAccessApi.deploy_plan_post")
    @patch("apps.log_databus.tasks.bkdata.BkDataAccessApi.get_deploy_summary")
    def test_create_bkdata_data_id_skips_when_cmdb_maintainers_empty(
        self,
        mock_get_deploy_summary,
        mock_deploy_plan_post,
        mock_get_app_list,
        mock_get_tenant_id,
        mock_feature_switch,
    ):
        collector_config = self._collector_config()
        mock_get_deploy_summary.side_effect = ApiResultError("permission denied", code="1511001")
        mock_get_app_list.return_value = {"count": 0, "info": []}

        create_bkdata_data_id(collector_config)

        mock_get_tenant_id.assert_called_once_with(bk_biz_id=19076)
        self.assertEqual(mock_get_deploy_summary.call_args.kwargs["bk_tenant_id"], "tencent")
        self.assertEqual(mock_get_app_list.call_args.kwargs["bk_tenant_id"], "tencent")
        mock_deploy_plan_post.assert_not_called()
        collector_config.save.assert_not_called()
