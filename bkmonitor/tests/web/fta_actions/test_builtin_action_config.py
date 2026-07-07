"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest.mock import patch

from django.test import TestCase

from bkmonitor.models import ActionConfig
from fta_web.constants import QuickSolutionsConfig
from fta_web.tasks import run_init_builtin_action_config


class TestRunInitBuiltinActionConfig(TestCase):
    databases = {"default", "monitor_api"}

    def setUp(self):
        ActionConfig.objects.filter(bk_biz_id=100474).delete()

    def tearDown(self):
        ActionConfig.objects.filter(bk_biz_id=100474).delete()

    @staticmethod
    def create_quick_solution_actions(bk_biz_id, is_builtin=False, limit=None):
        configs = list(QuickSolutionsConfig.QUICK_SOLUTIONS_CONFIG.values())
        if limit is not None:
            configs = configs[:limit]
        for config in configs:
            ActionConfig.objects.create(
                bk_biz_id=bk_biz_id,
                name=str(config["name"]),
                plugin_id="4",
                is_builtin=is_builtin,
                is_enabled=False,
                execute_config={
                    "template_detail": config["template_detail"],
                    "timeout": 600,
                },
                app="default",
                path=f"{config['name']}.yaml",
            )

    @patch("fta_web.tasks.api.sops.get_template_list", return_value=[])
    @patch("fta_web.tasks.api.sops.import_project_template")
    def test_skip_sops_import_when_all_quick_solution_actions_already_exist(
        self, mock_import_project_template, mock_get_template_list
    ):
        self.create_quick_solution_actions(bk_biz_id=100474, is_builtin=False)

        run_init_builtin_action_config(100474)

        mock_import_project_template.assert_not_called()
        mock_get_template_list.assert_not_called()

    @patch("fta_web.tasks.api.sops.get_template_list", return_value=[])
    @patch("fta_web.tasks.api.sops.import_project_template")
    def test_keep_sops_import_when_quick_solution_actions_are_incomplete(
        self, mock_import_project_template, mock_get_template_list
    ):
        self.create_quick_solution_actions(bk_biz_id=100474, is_builtin=False, limit=1)

        run_init_builtin_action_config(100474)

        self.assertEqual(mock_import_project_template.call_count, 2)
        mock_get_template_list.assert_called_once_with(bk_biz_id=100474)
