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

import json
from unittest.mock import MagicMock

import pytest
from django.test import override_settings


class TestIamReadWriteEnvironmentConfig:
    """default.py 只收集环境变量；语义校验不应散落在 settings 文件中。"""

    @staticmethod
    def _reload_default(monkeypatch, env: dict[str, str]):
        import importlib

        import config.default as default_mod

        keys = (
            "BK_IAM_PROVIDERS",
            "BK_IAM_READ_PROVIDERS",
            "BK_IAM_READ_POLICY",
            "BK_IAM_READ_STRATEGY",
            "BK_IAM_READ_OPTIONS",
            "BK_IAM_WRITE_PROVIDERS",
            "BK_IAM_WRITE_ON_FAILURE",
        )
        for key in keys:
            monkeypatch.delenv(key, raising=False)
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        return importlib.reload(default_mod)

    def test_default_declarations_are_grouped_by_catalog_enabled_read_and_write(self, monkeypatch):
        settings_module = self._reload_default(monkeypatch, {})

        framework = settings_module.IAM_FRAMEWORK
        assert set(framework["PROVIDER_CATALOG"]) == {"v3", "v4"}
        assert framework["ENABLED_PROVIDERS"] == "v4,v3"
        assert framework["READ"]["PROVIDERS"] == "v4,v3"
        assert framework["READ"]["POLICY"] == "dynamic"
        assert json.loads(framework["READ"]["OPTIONS"]) == {
            "selector": {
                "type": "django_setting",
                "attr": "BK_IAM_READ_STRATEGY",
                "default": "any_of",
            },
            "fallback_key": "any_of",
        }
        assert framework["WRITE"] == {"PROVIDERS": "v4,v3", "ON_FAILURE": "log"}

    def test_single_read_can_keep_dual_write_targets(self, monkeypatch):
        settings_module = self._reload_default(
            monkeypatch,
            {
                "BK_IAM_PROVIDERS": "v4,v3",
                "BK_IAM_READ_PROVIDERS": "v3",
                "BK_IAM_READ_POLICY": "single",
                "BK_IAM_WRITE_PROVIDERS": "v4,v3",
            },
        )

        framework = settings_module.IAM_FRAMEWORK
        assert framework["READ"]["PROVIDERS"] == "v3"
        assert framework["READ"]["POLICY"] == "single"
        assert framework["WRITE"]["PROVIDERS"] == "v4,v3"

    def test_dynamic_options_are_supplied_by_the_generic_options_environment_variable(self, monkeypatch):
        settings_module = self._reload_default(
            monkeypatch,
            {
                "BK_IAM_READ_STRATEGY": "primary_v3",
                "BK_IAM_READ_OPTIONS": (
                    '{"selector":{"type":"django_setting","attr":"BK_IAM_READ_STRATEGY","default":"primary_v3"},'
                    '"fallback_key":"all_of"}'
                ),
            },
        )

        options = json.loads(settings_module.IAM_FRAMEWORK["READ"]["OPTIONS"])
        assert options["selector"] == {
            "type": "django_setting",
            "attr": "BK_IAM_READ_STRATEGY",
            "default": "primary_v3",
        }
        assert options["fallback_key"] == "all_of"

    def test_v3_only_environment_needs_no_v4_connection_setting(self, monkeypatch):
        settings_module = self._reload_default(
            monkeypatch,
            {
                "BK_IAM_PROVIDERS": "v3",
                "BK_IAM_READ_PROVIDERS": "v3",
                "BK_IAM_READ_POLICY": "single",
                "BK_IAM_WRITE_PROVIDERS": "v3",
            },
        )

        assert settings_module.IAM_FRAMEWORK["ENABLED_PROVIDERS"] == "v3"

    @pytest.mark.parametrize("configured", (None, ""))
    def test_v4_callback_url_defaults_to_monitor_web_endpoint(self, monkeypatch, configured):
        if configured is None:
            monkeypatch.delenv("BK_IAM_V4_CALLBACK_URL", raising=False)
        else:
            monkeypatch.setenv("BK_IAM_V4_CALLBACK_URL", configured)
        monkeypatch.setenv("BK_MONITOR_HOST", "https://monitor.example.test/app/")

        settings_module = self._reload_default(monkeypatch, {})

        expected = "https://monitor.example.test/app/rest/v2/iam/v4/callback/"
        assert settings_module.BK_IAM_V4_CALLBACK_URL == expected
        system = settings_module.IAM_FRAMEWORK["PROVIDER_CATALOG"]["v4"]["options"]["system"]
        assert system["callback_url"] == expected

    def test_v4_callback_url_can_be_overridden(self, monkeypatch):
        monkeypatch.setenv("BK_MONITOR_HOST", "https://monitor.example.test/")
        monkeypatch.setenv("BK_IAM_V4_CALLBACK_URL", "http://bk-monitor-web/iam-callback/")

        settings_module = self._reload_default(monkeypatch, {})

        assert settings_module.BK_IAM_V4_CALLBACK_URL == "http://bk-monitor-web/iam-callback/"
        system = settings_module.IAM_FRAMEWORK["PROVIDER_CATALOG"]["v4"]["options"]["system"]
        assert system["callback_url"] == "http://bk-monitor-web/iam-callback/"


class TestIamFrameworkLoading:
    """引用、策略和失败策略都在框架加载期验证。"""

    @staticmethod
    def _raw(*, enabled=("v4", "v3"), read=("v3",), policy="single", write=("v4", "v3"), on_failure="log"):
        return {
            "PROVIDER_CATALOG": {
                "v4": {"class": "unused.v4", "options": {}},
                "v3": {"class": "unused.v3", "options": {}},
            },
            "ENABLED_PROVIDERS": list(enabled),
            "READ": {
                "PROVIDERS": list(read),
                "POLICY": policy,
                "OPTIONS": {
                    "selector": {"type": "django_setting", "attr": "BK_IAM_READ_STRATEGY", "default": "any_of"},
                    "fallback_key": "any_of",
                },
            },
            "WRITE": {"PROVIDERS": list(write), "ON_FAILURE": on_failure},
        }

    @staticmethod
    def _load(monkeypatch, raw, **extra_settings):
        from bkmonitor.iam.iam_engine.django import conf
        from bkmonitor.iam.iam_engine.django.facade import _set_framework, get_framework

        try:
            previous_framework = get_framework()
        except RuntimeError:
            previous_framework = None

        def _fake_build_provider(provider_cfg, _schema):
            provider = MagicMock()
            provider.name = provider_cfg.name
            provider.get_apply_url.return_value = f"apply://{provider_cfg.name}"
            return provider

        monkeypatch.setattr(conf, "_build_provider", _fake_build_provider)
        try:
            with override_settings(IAM_FRAMEWORK=raw, **extra_settings):
                return conf.load_framework()
        finally:
            _set_framework(previous_framework)  # type: ignore[arg-type]

    def test_load_uses_distinct_read_and_generic_write_provider_sets(self, monkeypatch):
        framework = self._load(monkeypatch, self._raw())

        assert [provider.name for provider in framework.router.read_policy.providers] == ["v3"]
        assert [provider.name for provider in framework.router.permission_writer.providers] == ["v4", "v3"]

    def test_primary_provider_is_a_primary_policy_option_not_a_read_level_field(self, monkeypatch):
        raw = self._raw(read=("v4", "v3"), policy="primary")
        raw["READ"]["OPTIONS"] = {"primary_provider": "v3"}

        framework = self._load(monkeypatch, raw)

        assert framework.router.read_policy.primary().name == "v3"

    def test_dynamic_single_candidate_uses_its_own_provider_set_and_apply_display(self, monkeypatch):
        raw = self._raw(read=("v4", "v3"), policy="dynamic")
        raw["READ"]["OPTIONS"]["selector"] = {"type": "static", "value": "single_v3"}
        framework = self._load(
            monkeypatch,
            raw,
        )

        policy = framework.router.read_policy
        assert [provider.name for provider in policy._policies["single_v3"].providers] == ["v3"]
        assert policy.primary().name == "v3"
        assert framework.get_apply_url(MagicMock()) == "apply://v3"

    def test_dynamic_candidates_can_be_supplied_as_json_with_independent_provider_sets(self, monkeypatch):
        raw = self._raw(read=("v4", "v3"), policy="dynamic")
        raw["READ"]["OPTIONS"].update(
            {
                "selector": {"type": "static", "value": "only_v3"},
                "fallback_key": "only_v3",
                "policies": {"only_v3": {"providers": ["v3"], "policy": "single"}},
            }
        )

        framework = self._load(monkeypatch, raw)

        policy = framework.router.read_policy
        assert [provider.name for provider in policy._policies["only_v3"].providers] == ["v3"]
        assert policy.primary().name == "v3"

    def test_rejects_read_or_write_provider_not_enabled(self, monkeypatch):
        with pytest.raises(RuntimeError, match="WRITE.PROVIDERS references providers not enabled"):
            self._load(monkeypatch, self._raw(enabled=("v3",), read=("v3",), write=("v4",)))

    def test_rejects_single_read_policy_with_multiple_providers_at_loading(self, monkeypatch):
        from bkmonitor.iam.iam_engine.core.exceptions import ConfigError

        with pytest.raises(ConfigError, match="exactly 1 provider"):
            self._load(monkeypatch, self._raw(read=("v4", "v3"), policy="single"))

    def test_rejects_unimplemented_write_failure_policy_at_loading(self, monkeypatch):
        with pytest.raises(ValueError, match="only on_failure='log'"):
            self._load(monkeypatch, self._raw(enabled=("v3",), read=("v3",), write=("v3",), on_failure="outbox"))


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
            "BK_IAM_PROVIDERS",
            "BK_IAM_READ_PROVIDERS",
            "BK_IAM_READ_POLICY",
            "BK_IAM_READ_OPTIONS",
            "BK_IAM_WRITE_PROVIDERS",
        ):
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("BK_IAM_PROVIDERS", "v3")
        monkeypatch.setenv("BK_IAM_READ_PROVIDERS", "v3")
        monkeypatch.setenv("BK_IAM_READ_POLICY", "single")
        monkeypatch.setenv("BK_IAM_WRITE_PROVIDERS", "v3")
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
