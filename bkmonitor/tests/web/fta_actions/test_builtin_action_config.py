"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest.mock import call, patch

from django.test import TestCase

from bkmonitor.models import ActionConfig, ActionPlugin
from constants.action import ActionPluginType
from fta_web.constants import QuickSolutionsConfig
from fta_web.tasks import run_init_builtin_action_config


class TestRunInitBuiltinActionConfig(TestCase):
    databases = {"default", "monitor_api"}
    sops_plugin_id = "44"

    def setUp(self):
        ActionConfig.objects.filter(bk_biz_id=100474).delete()
        ActionPlugin.objects.filter(plugin_key=ActionPluginType.SOPS).exclude(id=self.sops_plugin_id).delete()
        ActionPlugin.objects.update_or_create(
            id=self.sops_plugin_id,
            defaults={
                "plugin_type": ActionPluginType.SOPS,
                "plugin_key": ActionPluginType.SOPS,
                "name": "标准运维",
                "category": "execute",
                "config_schema": {},
                "backend_config": {},
            },
        )

    def tearDown(self):
        ActionConfig.objects.filter(bk_biz_id=100474).delete()
        ActionPlugin.objects.filter(id=self.sops_plugin_id).delete()

    @staticmethod
    def create_quick_solution_actions(bk_biz_id, plugin_id, is_builtin=False, limit=None):
        configs = list(QuickSolutionsConfig.QUICK_SOLUTIONS_CONFIG.values())
        if limit is not None:
            configs = configs[:limit]
        for config in configs:
            ActionConfig.objects.create(
                bk_biz_id=bk_biz_id,
                name=str(config["name"]),
                plugin_id=plugin_id,
                is_builtin=is_builtin,
                is_enabled=False,
                execute_config={
                    "template_detail": config["template_detail"],
                    "timeout": 600,
                },
                app="default",
                path=f"{config['name']}.yaml",
            )

    @staticmethod
    def get_templates():
        return [
            {"id": index, "name": str(name)}
            for index, name in enumerate(QuickSolutionsConfig.QUICK_SOLUTIONS_TEMPLATE_NAMES.values(), start=1)
        ]

    def assert_quick_solution_actions(self, templates):
        template_ids = {template["name"]: template["id"] for template in templates}
        actions = ActionConfig.objects.filter(bk_biz_id=100474)
        self.assertEqual(actions.count(), len(QuickSolutionsConfig.QUICK_SOLUTIONS_CONFIG))
        for config in QuickSolutionsConfig.QUICK_SOLUTIONS_CONFIG.values():
            action = actions.get(name=str(config["name"]))
            self.assertTrue(action.is_builtin)
            self.assertEqual(action.plugin_id, self.sops_plugin_id)
            self.assertEqual(action.execute_config["template_id"], template_ids[str(config["template_name"])])

    @patch("fta_web.tasks.api.sops.get_template_list", return_value=[])
    @patch("fta_web.tasks.api.sops.import_project_template")
    def test_skip_sops_import_when_all_quick_solution_actions_already_exist(
        self, mock_import_project_template, mock_get_template_list
    ):
        self.create_quick_solution_actions(bk_biz_id=100474, plugin_id=self.sops_plugin_id, is_builtin=False)

        run_init_builtin_action_config(100474)

        mock_import_project_template.assert_not_called()
        mock_get_template_list.assert_not_called()

    @patch("fta_web.tasks.api.sops.get_template_list", return_value=[])
    @patch("fta_web.tasks.api.sops.import_project_template")
    def test_keep_sops_import_when_quick_solution_actions_are_incomplete(
        self, mock_import_project_template, mock_get_template_list
    ):
        self.create_quick_solution_actions(bk_biz_id=100474, plugin_id=self.sops_plugin_id, is_builtin=False, limit=1)

        run_init_builtin_action_config(100474)

        self.assertEqual(mock_import_project_template.call_count, 2)
        self.assertEqual(mock_get_template_list.call_count, 2)

    @patch("fta_web.tasks.api.sops.get_template_list", side_effect=RuntimeError("SOPS list unavailable"))
    @patch("fta_web.tasks.api.sops.import_project_template")
    def test_list_failure_does_not_import_or_create_actions(self, mock_import_project_template, mock_get_template_list):
        with self.assertRaisesRegex(RuntimeError, "SOPS list unavailable"):
            run_init_builtin_action_config(100474)

        mock_import_project_template.assert_not_called()
        self.assertFalse(ActionConfig.objects.filter(bk_biz_id=100474).exists())

    @patch("fta_web.tasks.api.sops.get_template_list")
    @patch("fta_web.tasks.api.sops.import_project_template")
    def test_reuse_existing_templates(self, mock_import_project_template, mock_get_template_list):
        templates = self.get_templates()
        mock_get_template_list.return_value = templates

        run_init_builtin_action_config(100474)

        mock_import_project_template.assert_not_called()
        mock_get_template_list.assert_called_once_with(bk_biz_id=100474)
        self.assert_quick_solution_actions(templates)

    @patch("fta_web.tasks.api.sops.get_template_list")
    @patch("fta_web.tasks.api.sops.import_project_template")
    def test_import_when_list_succeeds_without_builtin_templates(
        self, mock_import_project_template, mock_get_template_list
    ):
        templates = self.get_templates()
        mock_get_template_list.side_effect = [[{"id": 99, "name": "业务自建流程"}], templates]

        def import_template(**kwargs):
            mock_get_template_list.assert_called_once_with(bk_biz_id=100474)

        mock_import_project_template.side_effect = import_template
        run_init_builtin_action_config(100474)

        self.assertEqual(mock_import_project_template.call_count, 2)
        self.assert_quick_solution_actions(templates)

    @patch("fta_web.tasks.api.sops.get_template_list")
    @patch("fta_web.tasks.api.sops.import_project_template")
    def test_retry_after_list_failure_reuses_imported_templates(
        self, mock_import_project_template, mock_get_template_list
    ):
        templates = self.get_templates()
        mock_get_template_list.side_effect = [[], RuntimeError("SOPS list unavailable"), templates]

        with self.assertRaisesRegex(RuntimeError, "SOPS list unavailable"):
            run_init_builtin_action_config(100474)
        self.assertFalse(ActionConfig.objects.filter(bk_biz_id=100474).exists())

        run_init_builtin_action_config(100474)

        self.assertEqual(mock_import_project_template.call_count, 2)
        self.assert_quick_solution_actions(templates)

    @patch("fta_web.tasks.api.sops.get_template_list")
    @patch("fta_web.tasks.api.sops.import_project_template")
    def test_retry_only_imports_missing_package(self, mock_import_project_template, mock_get_template_list):
        templates = self.get_templates()
        idle_name = str(QuickSolutionsConfig.QUICK_SOLUTIONS_TEMPLATE_NAMES[QuickSolutionsConfig.UPDATE_MODULE_TO_IDLE])
        quick_templates = [template for template in templates if template["name"] != idle_name]
        mock_get_template_list.side_effect = [[], quick_templates, templates]
        mock_import_project_template.side_effect = [None, RuntimeError("SOPS import unavailable"), None]

        run_init_builtin_action_config(100474)
        run_init_builtin_action_config(100474)

        self.assertEqual(
            mock_import_project_template.call_args_list,
            [
                call(bk_biz_id=100474, project_id=100474, template_data=template_data)
                for template_data in [
                    QuickSolutionsConfig.QUICK_SOLUTIONS_TEMPLATE,
                    QuickSolutionsConfig.IDLE_TEMPLATE,
                    QuickSolutionsConfig.IDLE_TEMPLATE,
                ]
            ],
        )
        self.assert_quick_solution_actions(templates)

    @patch("fta_web.tasks.api.sops.get_template_list")
    @patch("fta_web.tasks.api.sops.import_project_template")
    def test_reuse_partially_existing_package(self, mock_import_project_template, mock_get_template_list):
        templates = self.get_templates()
        idle_name = str(QuickSolutionsConfig.QUICK_SOLUTIONS_TEMPLATE_NAMES[QuickSolutionsConfig.UPDATE_MODULE_TO_IDLE])
        mock_get_template_list.return_value = [templates[0]] + [
            template for template in templates if template["name"] == idle_name
        ]

        run_init_builtin_action_config(100474)

        mock_import_project_template.assert_not_called()
        self.assertEqual(ActionConfig.objects.filter(bk_biz_id=100474).count(), 2)
