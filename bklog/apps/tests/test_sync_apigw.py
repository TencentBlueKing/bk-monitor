"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial portions
of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED
TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of the project
delivered to anyone in the future.
"""

from pathlib import Path
from unittest.mock import patch

from apigw_manager.apigw.helper import Definition
from django.conf import settings
from django.test import SimpleTestCase, override_settings

from apps.api.management.commands.sync_apigw import Command


class SyncApiGatewayStageTests(SimpleTestCase):
    @override_settings(SYNC_APIGATEWAY_ENABLED="on")
    def test_stage_definition_matches_release_target(self):
        definition_path = Path(settings.BASE_DIR) / "support-files" / "apigw" / "definition.yaml"

        for stage, description in (("prod", "生产环境"), ("stage", "测试环境")):
            with self.subTest(stage=stage), override_settings(APIGW_STAGE=stage):
                definition = Definition.load_from(definition_path, {"settings": settings})
                self.assertEqual(definition.get("stage")["name"], stage)
                self.assertEqual(definition.get("stage")["description"], description)

                with patch("apps.api.management.commands.sync_apigw.call_command") as mock_call:
                    Command().handle()

                release_call = next(
                    call for call in mock_call.call_args_list if call.args[0] == "create_version_and_release_apigw"
                )
                self.assertIn(f"--stage={stage}", release_call.args)
