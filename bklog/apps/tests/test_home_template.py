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

# Render the production homepage placeholders through the real Mako backend.

import copy
import os
import re
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.test import RequestFactory, SimpleTestCase, override_settings

from config import default
from home_application.views import home


class HomeTemplateTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        bklog_root = Path(__file__).resolve().parents[2]
        webpack_config = (bklog_root / "web/webpack.config.js").read_text(encoding="utf-8")
        variates = re.search(r"pcBuildVariates:\s*`(.*?)`", webpack_config, flags=re.DOTALL)
        if variates is None:
            raise AssertionError("Production homepage variable injection was not found")

        # Reproduce LogWebpackPlugin's replacement without requiring Node in backend CI.
        # Read the live sources: a new placeholder must be supplied by the backend too.
        index = (bklog_root / "web/index.ejs").read_text(encoding="utf-8")
        index, replacements = re.subn(
            r"<script template>\s*</script>",
            lambda match: variates[1].replace(r"\${", "${"),
            index,
        )
        if replacements != 1:
            raise AssertionError("Expected exactly one production homepage injection point")

        template_dir = tempfile.TemporaryDirectory()
        cls.addClassCleanup(template_dir.cleanup)
        (Path(template_dir.name) / settings.VUE_INDEX).write_text(index, encoding="utf-8")
        mako_config = copy.deepcopy(
            next(config for config in settings.TEMPLATES if config["BACKEND"].endswith(".MakoTemplates"))
        )
        mako_config["DIRS"] = [template_dir.name]
        cls.template_settings = override_settings(TEMPLATES=[mako_config])
        cls.template_settings.enable()
        cls.addClassCleanup(cls.template_settings.disable)

    def render_home(self, is_external="false"):
        request = RequestFactory().get("/", HTTP_IS_EXTERNAL=is_external)
        request.user = SimpleNamespace(username="homepage-test", is_superuser=False)
        # Only replace database reads; run home(), get_toggle_data(), the configured
        # context processors and the actual Mako render instead of mocking render().
        with (
            patch("apps.utils.db.FeatureToggleObject.toggle_list", return_value=[]),
            patch(
                "apps.utils.db.FeatureToggle.objects.get_or_create",
                return_value=(SimpleNamespace(feature_config={}), False),
            ),
        ):
            response = home(request)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('<div id="app"></div>', content)
        self.assertNotIn("${", content)
        return content

    def test_guide_settings_have_environment_backed_empty_defaults(self):
        self.assertEqual(default.BK_LOG_ACCESS_GUIDE_URL, os.getenv("BKAPP_LOG_ACCESS_GUIDE_URL", ""))
        self.assertEqual(default.BK_LOG_PERMISSION_GUIDE_URL, os.getenv("BKAPP_LOG_PERMISSION_GUIDE_URL", ""))

    @override_settings(BK_LOG_ACCESS_GUIDE_URL="", BK_LOG_PERMISSION_GUIDE_URL="")
    def test_home_renders_without_configured_guide_urls(self):
        for is_external in ("false", "true"):
            with self.subTest(is_external=is_external):
                content = self.render_home(is_external)
                self.assertIn("window.BK_LOG_ACCESS_GUIDE_URL = ''", content)
                self.assertIn("window.BK_LOG_PERMISSION_GUIDE_URL = ''", content)

    def test_home_injects_configured_guide_urls(self):
        for access_url, permission_url in (
            ("https://docs.example.com/access?source=log&lang=zh", "https://docs.example.com/permission"),
            ("https://docs.example.com/access", ""),
            ("", "https://docs.example.com/permission"),
        ):
            with (
                self.subTest(access_url=access_url, permission_url=permission_url),
                override_settings(BK_LOG_ACCESS_GUIDE_URL=access_url, BK_LOG_PERMISSION_GUIDE_URL=permission_url),
            ):
                content = self.render_home()
                self.assertIn(f"window.BK_LOG_ACCESS_GUIDE_URL = '{access_url}'", content)
                self.assertIn(f"window.BK_LOG_PERMISSION_GUIDE_URL = '{permission_url}'", content)
