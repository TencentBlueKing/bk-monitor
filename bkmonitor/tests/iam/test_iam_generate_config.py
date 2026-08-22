"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
from io import StringIO

from django.core.management import call_command


class TestIamGenerateConfigCommand:
    """iam_generate_config：--provider 指定时按 provider 可见性过滤 schema。"""

    def test_with_provider_v4_filters_hidden_actions(self):
        out = StringIO()
        call_command("iam_generate_config", provider="v4", stdout=out)
        config = json.loads(out.getvalue())
        ids = {a["id"] for a in config["actions"]}
        assert "view_dashboard" not in ids
        assert "manage_dashboard" not in ids
        assert "view_single_dashboard" in ids
        assert "view_business" in ids

    def test_with_provider_v3_keeps_all_actions(self):
        # 可见性过滤是 schema 级判定，与 v3 provider 是否装配无关
        out = StringIO()
        call_command("iam_generate_config", provider="v3", stdout=out)
        config = json.loads(out.getvalue())
        ids = {a["id"] for a in config["actions"]}
        assert "view_dashboard" in ids
        assert "manage_dashboard" in ids

    def test_without_provider_exports_full_schema(self):
        out = StringIO()
        call_command("iam_generate_config", stdout=out)
        config = json.loads(out.getvalue())
        ids = {a["id"] for a in config["actions"]}
        assert "view_dashboard" in ids
        # 未指定 provider 时不输出单数 system（多 provider 总览走 systems）
        assert "system" not in config
