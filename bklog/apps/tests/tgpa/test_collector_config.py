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

from django.test import TestCase

from apps.log_databus.models import CollectorConfig
from apps.tgpa.constants import TGPA_TASK_COLLECTOR_CONFIG_NAME_EN
from apps.tgpa.handlers.base import TGPACollectorConfigHandler

BK_BIZ_ID = 2
COLLECTOR_CONFIG_ID = 9001
BK_DATA_ID = 1600900


class TestTGPACollectorConfigVisibility(TestCase):
    """客户端日志采集项由 TGPA 定时任务自动维护，不应出现在通用采集接入列表中。"""

    def test_created_collector_config_is_not_displayed(self):
        # 英文名与 TGPA 约定值不同，get_or_create 的存在性检查不会命中，从而走到创建分支；
        # 同时保证 custom_create 之后按 collector_config_id 的回查能取到记录。
        CollectorConfig.objects.create(
            collector_config_id=COLLECTOR_CONFIG_ID,
            collector_config_name="客户端日志",
            collector_config_name_en="placeholder_not_tgpa_name",
            collector_scenario_id="client",
            bk_biz_id=BK_BIZ_ID,
            category_id="application_check",
            target_object_type="HOST",
            target_node_type="TOPO",
            target_nodes=[],
            target_subscription_diff={},
            description="客户端日志",
            is_active=True,
            bk_data_id=BK_DATA_ID,
            is_display=False,
        )

        feature_toggle = MagicMock()
        feature_toggle.feature_config = {"storage_cluster_id": 1}

        with (
            patch("apps.tgpa.handlers.base.FeatureToggleObject.toggle", return_value=feature_toggle),
            patch(
                "apps.tgpa.handlers.base.CollectorHandler.custom_create",
                return_value={"bk_data_id": BK_DATA_ID, "collector_config_id": COLLECTOR_CONFIG_ID},
            ) as mock_custom_create,
            patch.object(TGPACollectorConfigHandler, "release_collector_config"),
        ):
            TGPACollectorConfigHandler.get_or_create_collector_config(BK_BIZ_ID)

        create_kwargs = mock_custom_create.call_args.kwargs
        self.assertEqual(create_kwargs["collector_config_name_en"], TGPA_TASK_COLLECTOR_CONFIG_NAME_EN)
        self.assertFalse(create_kwargs["is_display"])
