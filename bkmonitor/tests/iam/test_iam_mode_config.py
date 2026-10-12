"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

"""IAM 读写分离配置与加载期校验。"""


import pytest


class TestMigrationSafeDefault:
    def test_migration_allow_destructive_defaults_false(self):
        from django.conf import settings

        assert settings.IAM_FRAMEWORK["MIGRATION"]["allow_destructive"] is False


class TestMigrationEnvOverrides:
    @staticmethod
    def _reload_default_migration(monkeypatch, env: dict[str, str]) -> dict:
        import importlib

        for key in (
            "BK_IAM_ENGINE_MIGRATION_MODE",
            "BK_IAM_ENGINE_MIGRATION_DIRECTORY",
            "BK_IAM_ENGINE_MIGRATION_ALLOW_DESTRUCTIVE",
        ):
            monkeypatch.delenv(key, raising=False)
        for key, value in env.items():
            monkeypatch.setenv(key, value)

        import config.default as default_mod

        return importlib.reload(default_mod).IAM_FRAMEWORK["MIGRATION"]

    def test_defaults_without_env(self, monkeypatch):
        migration = self._reload_default_migration(monkeypatch, {})
        assert migration["mode"] == "semi_auto"
        assert migration["directory"] == "bkmonitor/iam/iam_migrations"
        assert migration["allow_destructive"] is False

    @pytest.mark.parametrize("value", ("1", "true", "True", "YES", "yes"))
    def test_allow_destructive_truthy_values(self, monkeypatch, value):
        migration = self._reload_default_migration(monkeypatch, {"BK_IAM_ENGINE_MIGRATION_ALLOW_DESTRUCTIVE": value})
        assert migration["allow_destructive"] is True

    @pytest.mark.parametrize("value", ("0", "false", "no", "off", "", "anything_else"))
    def test_allow_destructive_falsy_values(self, monkeypatch, value):
        migration = self._reload_default_migration(monkeypatch, {"BK_IAM_ENGINE_MIGRATION_ALLOW_DESTRUCTIVE": value})
        assert migration["allow_destructive"] is False
