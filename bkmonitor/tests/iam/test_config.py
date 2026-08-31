"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

# ==============================================================================
# V4 Provider 配置契约的单元测试
#
# 覆盖：
#   1. V4Credentials.from_dict 正常/缺字段
#   2. V4SystemInfo.from_dict   正常/缺字段/managers/clients 类型转换
#   3. V4Options.from_dict      正常/缺 base_url / credentials / system / 非法类型
#   4. V4Options.from_dict      未知字段收纳到 extra
#   5. V4PermissionProvider     构造后 self._cfg / self.schema / self.get_system_info() 正确
# ==============================================================================

import pytest

from bkmonitor.iam.iam_engine.django.facade import get_framework
from bkmonitor.iam.iam_engine.schema.registry import SchemaRegistry
from bkmonitor.iam.iam_v4.config import V4Credentials, V4Options, V4SystemInfo
from bkmonitor.iam.iam_v4.provider import V4PermissionProvider


# ==============================================================================
# V4Credentials
# ==============================================================================


class TestV4Credentials:
    def test_from_dict_ok(self):
        c = V4Credentials.from_dict({"app_code": "abc", "app_secret": "xyz"})
        assert c.app_code == "abc"
        assert c.app_secret == "xyz"

    def test_missing_app_code(self):
        with pytest.raises(ValueError) as exc:
            V4Credentials.from_dict({"app_secret": "xyz"})
        assert "app_code" in str(exc.value)

    def test_missing_app_secret(self):
        with pytest.raises(ValueError) as exc:
            V4Credentials.from_dict({"app_code": "abc"})
        assert "app_secret" in str(exc.value)

    def test_frozen(self):
        c = V4Credentials.from_dict({"app_code": "abc", "app_secret": "xyz"})
        with pytest.raises(Exception):
            c.app_code = "changed"  # frozen dataclass


# ==============================================================================
# V4SystemInfo
# ==============================================================================


class TestV4SystemInfo:
    def test_from_dict_minimal(self):
        s = V4SystemInfo.from_dict({"id": "bk_monitor_v4", "name": "监控 V4"})
        assert s.id == "bk_monitor_v4"
        assert s.name == "监控 V4"
        assert s.description == ""
        assert s.callback_url == ""
        assert s.managers == ()
        assert s.clients == ()

    def test_from_dict_full(self):
        s = V4SystemInfo.from_dict(
            {
                "id": "bk_monitor_v4",
                "name": "监控 V4",
                "description": "V4 权限系统",
                "callback_url": "https://cb/",
                "managers": ["admin", "root"],
                "clients": ["app1", "app2"],
            }
        )
        assert s.description == "V4 权限系统"
        assert s.callback_url == "https://cb/"
        assert s.managers == ("admin", "root")  # list → tuple
        assert s.clients == ("app1", "app2")

    def test_missing_id(self):
        with pytest.raises(ValueError) as exc:
            V4SystemInfo.from_dict({"name": "监控"})
        assert "id" in str(exc.value)

    def test_missing_name(self):
        with pytest.raises(ValueError) as exc:
            V4SystemInfo.from_dict({"id": "bk_monitor_v4"})
        assert "name" in str(exc.value)


# ==============================================================================
# V4Options
# ==============================================================================


def _valid_options(**overrides) -> dict:
    """构造一份最小合法的 options，可覆盖任意字段。"""
    opts = {
        "base_url": "https://iam.example.com",
        "credentials": {"app_code": "app1", "app_secret": "secret1"},
        "system": {"id": "bk_monitor_v4", "name": "监控"},
    }
    opts.update(overrides)
    return opts


class TestV4Options:
    def test_from_dict_minimal(self):
        cfg = V4Options.from_dict(_valid_options())
        assert cfg.base_url == "https://iam.example.com"
        assert cfg.credentials.app_code == "app1"
        assert cfg.credentials.app_secret == "secret1"
        assert cfg.system.id == "bk_monitor_v4"
        assert cfg.system.name == "监控"
        # 默认值
        assert cfg.timeout == 30
        assert cfg.chunk_size == 20
        assert cfg.max_workers == 1
        assert cfg.extra == {}

    def test_from_dict_all_optional_fields(self):
        cfg = V4Options.from_dict(_valid_options(timeout=5, chunk_size=10, max_workers=4))
        assert cfg.timeout == 5
        assert cfg.chunk_size == 10
        assert cfg.max_workers == 4

    def test_missing_base_url(self):
        with pytest.raises(ValueError) as exc:
            V4Options.from_dict(
                {"credentials": {"app_code": "a", "app_secret": "b"}, "system": {"id": "i", "name": "n"}}
            )
        assert "base_url" in str(exc.value)

    def test_empty_base_url_fails_fast(self):
        """key 存在但值为空字符串 → fail-fast，避免线上"启动通过，首次请求 500"。"""
        with pytest.raises(ValueError) as exc:
            V4Options.from_dict(_valid_options(base_url=""))
        assert "base_url" in str(exc.value)
        assert "non-empty" in str(exc.value)

    def test_whitespace_only_base_url_fails_fast(self):
        """值仅由空白构成时也视作缺失。"""
        with pytest.raises(ValueError) as exc:
            V4Options.from_dict(_valid_options(base_url="   \t\n"))
        assert "base_url" in str(exc.value)
        assert "non-empty" in str(exc.value)

    def test_base_url_is_stripped_before_storage(self):
        """必要规范化：通过校验的 URL 必须以 strip 后的值传给 HTTP client。"""
        cfg = V4Options.from_dict(_valid_options(base_url=" \thttps://iam.example.com/api/  \n"))
        assert cfg.base_url == "https://iam.example.com/api/"

    def test_non_string_base_url_fails_fast(self):
        """非字符串类型（None / int）也应立即抛错，而不是被 str(None) 静默转换。"""
        with pytest.raises(ValueError):
            V4Options.from_dict(_valid_options(base_url=None))
        with pytest.raises(ValueError):
            V4Options.from_dict(_valid_options(base_url=12345))

    def test_missing_credentials(self):
        with pytest.raises(ValueError) as exc:
            V4Options.from_dict({"base_url": "u", "system": {"id": "i", "name": "n"}})
        assert "credentials" in str(exc.value)

    def test_missing_system(self):
        with pytest.raises(ValueError) as exc:
            V4Options.from_dict({"base_url": "u", "credentials": {"app_code": "a", "app_secret": "b"}})
        assert "system" in str(exc.value)

    def test_credentials_wrong_type(self):
        with pytest.raises(ValueError) as exc:
            V4Options.from_dict(_valid_options(credentials="not-a-dict"))
        assert "credentials must be a dict" in str(exc.value)

    def test_system_wrong_type(self):
        with pytest.raises(ValueError) as exc:
            V4Options.from_dict(_valid_options(system=["not", "a", "dict"]))
        assert "system must be a dict" in str(exc.value)

    def test_extra_fields_collected(self):
        """未识别字段应收纳到 extra，不报错。"""
        cfg = V4Options.from_dict(_valid_options(custom_field="hello", another=123))
        assert cfg.extra == {"custom_field": "hello", "another": 123}

    def test_fallback_apply_url_default_empty(self):
        """未配置 fallback_apply_url 时保持空字符串（维持既有降级契约）。"""
        cfg = V4Options.from_dict(_valid_options())
        assert cfg.fallback_apply_url == ""

    def test_fallback_apply_url_parsed(self):
        """显式配置的 fallback_apply_url 应被解析到 _cfg.fallback_apply_url。"""
        cfg = V4Options.from_dict(_valid_options(fallback_apply_url="https://itsm.example.com/apply"))
        assert cfg.fallback_apply_url == "https://itsm.example.com/apply"

    def test_fallback_apply_url_none_coerced_to_empty(self):
        """None 被视作未配置（兼容 os.getenv 未设置且 or "" 的写法）。"""
        cfg = V4Options.from_dict(_valid_options(fallback_apply_url=None))
        assert cfg.fallback_apply_url == ""

    def test_fallback_apply_url_not_in_extra(self):
        """新增字段必须列入 known 白名单，不能被误收纳到 extra。"""
        cfg = V4Options.from_dict(_valid_options(fallback_apply_url="https://x.example.com"))
        assert "fallback_apply_url" not in cfg.extra

    def test_frozen(self):
        cfg = V4Options.from_dict(_valid_options())
        with pytest.raises(Exception):
            cfg.base_url = "changed"


# ==============================================================================
# V4PermissionProvider 构造行为
# ==============================================================================


class TestV4ProviderConstruction:
    """验证 Provider 从 options 里读取所有配置，不依赖 ctx / Django settings。"""

    @staticmethod
    def _fresh_schema() -> SchemaRegistry:
        """返回一个 freeze 好的最小 SchemaRegistry（复用框架已构建的即可）。"""
        return get_framework().schema

    def test_construct_from_options(self):
        schema = self._fresh_schema()
        provider = V4PermissionProvider(
            schema,
            **_valid_options(timeout=15, chunk_size=8, max_workers=2),
        )
        # schema 直接挂在 self.schema 上，非 ctx.schema
        assert provider.schema is schema
        # _cfg 存放解析后的强类型配置
        assert provider._cfg.base_url == "https://iam.example.com"
        assert provider._cfg.credentials.app_code == "app1"
        assert provider._cfg.system.id == "bk_monitor_v4"
        # 分片参数字段来自 options
        assert provider.CHUNK_SIZE == 8
        assert provider.MAX_WORKERS == 2

    def test_get_system_info(self):
        schema = self._fresh_schema()
        provider = V4PermissionProvider(schema, **_valid_options())
        info = provider.get_system_info()
        assert isinstance(info, V4SystemInfo)
        assert info.id == "bk_monitor_v4"
        assert info.name == "监控"

    def test_missing_required_field_fails_fast(self):
        """缺少 credentials 应在 Provider 构造阶段就 fail，而不是等到运行时。"""
        schema = self._fresh_schema()
        with pytest.raises(ValueError):
            V4PermissionProvider(schema, base_url="u", system={"id": "i", "name": "n"})

    def test_no_ctx_attribute(self):
        """确保重构后 Provider 上不再暴露 ctx 属性。"""
        schema = self._fresh_schema()
        provider = V4PermissionProvider(schema, **_valid_options())
        assert not hasattr(provider, "ctx")


# ==============================================================================
# FrameworkConfig 层面回归：确认 credentials_provider 字段已删除
# ==============================================================================


class TestFrameworkConfigNoCredentialsProvider:
    def test_from_dict_ignores_legacy_credentials_provider_key(self):
        """settings 里即使残留 CREDENTIALS_PROVIDER，也不应影响解析（字段已删除）。"""
        from bkmonitor.iam.iam_engine.core.config import FrameworkConfig

        raw = {
            "ACTIONS": "",
            "RESOURCE_TYPES": "",
            "ROLES": "",
            "CREDENTIALS_PROVIDER": "legacy.path.that.should.be.ignored",
            "PROVIDERS": [],
            "COMPOSITION": {"policy": "single"},
        }
        cfg = FrameworkConfig.from_dict(raw)
        assert not hasattr(cfg, "credentials_provider")


class TestFrameworkConfigExtensibility:
    def test_migration_recorder_and_bypass_rule_options_are_parsed(self):
        from bkmonitor.iam.iam_engine.core.config import FrameworkConfig
        from bkmonitor.iam.iam_engine.core.types import Subject
        from bkmonitor.iam.iam_engine.django.conf import _build_bypass_rules

        cfg = FrameworkConfig.from_dict(
            {
                "MIGRATION": {
                    "database": "iam",
                    "table_name": "project_iam_migration_state",
                },
                "BYPASS_RULES": [
                    {
                        "class": "bkmonitor.iam.iam_engine.crosscutting.bypass.SubjectBypassRule",
                        "options": {"subject_ids": ["iam_admin"]},
                    }
                ],
            }
        )

        assert cfg.migration.database == "iam"
        assert cfg.migration.table_name == "project_iam_migration_state"
        rules = _build_bypass_rules(cfg.bypass_rules)
        assert rules[0].should_bypass(Subject(id="iam_admin"), (), ()) is True

    def test_legacy_bypass_rule_path_is_still_supported(self):
        from bkmonitor.iam.iam_engine.core.config import FrameworkConfig

        cfg = FrameworkConfig.from_dict(
            {"BYPASS_RULES": ["bkmonitor.iam.iam_engine.crosscutting.bypass.SettingsSkipRule"]}
        )

        assert cfg.bypass_rules[0].cls == "bkmonitor.iam.iam_engine.crosscutting.bypass.SettingsSkipRule"
        assert cfg.bypass_rules[0].options == {}
