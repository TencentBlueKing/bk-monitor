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
# 阶段 1 · 评论 1 + 评论 4 —— IAM 单开关 + 迁移安全默认
#
# 校验 Django settings 落地的语义正确性：
#   1. BK_IAM_MODE 取值必须在 {v3, v4, union} 内（不允许被静默塞脏值进来）
#   2. 装配结果与 BK_IAM_MODE 语义一致：
#        - v3 / v4  → 单 Provider + composition=single
#        - union    → V4 + V3 双 Provider（V4 在前）+ composition=any_of
#   3. MIGRATION.allow_destructive is False（评论 4）
#
# 说明：BK_IAM_MODE 的三分支分派在 config/default.py 里直接内联 if/elif/else，
# 不再单独抽纯函数；本测试通过读取 django.conf.settings 校验最终装配语义，
# 从而在任意 .env 覆盖下（包括开发者本地 export BK_IAM_MODE=union）都能守住
# "分派逻辑正确 + 安全默认不倒退"这两条底线。
# ==============================================================================

import pytest


class TestIamModeStackWiring:
    """按 BK_IAM_MODE 的实际值验证装配结果，覆盖三种模式的语义。"""

    def test_bk_iam_mode_is_valid_enum(self):
        from django.conf import settings

        mode = getattr(settings, "BK_IAM_MODE", "").lower()
        assert mode in {"v3", "v4", "union"}, f"BK_IAM_MODE={mode!r} 非法，仅允许 'v3' | 'v4' | 'union'"

    def test_providers_and_composition_match_mode(self):
        from django.conf import settings

        mode = settings.BK_IAM_MODE.lower()
        providers = settings.IAM_FRAMEWORK["PROVIDERS"]
        composition = settings.IAM_FRAMEWORK["COMPOSITION"]

        if mode == "v3":
            assert len(providers) == 1
            assert providers[0]["class"].endswith("V3PermissionProvider")
            assert composition == {"policy": "single"}
        elif mode == "v4":
            assert len(providers) == 1
            assert providers[0]["class"].endswith("V4PermissionProvider")
            assert composition == {"policy": "single"}
        else:  # union
            assert len(providers) == 2
            # V4 必须在前：primary() 取 providers[0]，get_apply_url/get_apply_data 优先出 V4 页面
            assert providers[0]["class"].endswith("V4PermissionProvider"), (
                "union 模式下 V4 必须作为 primary，即 providers[0]"
            )
            assert providers[1]["class"].endswith("V3PermissionProvider")
            # union 模式改为 DynamicCompositionPolicy：装配契约（PROVIDERS）不变，
            # union 内部读组合策略走 GlobalConfig 动态开关 BK_IAM_MODE_UNION_STRATEGY。
            assert composition["policy"] == "dynamic"
            options = composition["options"]
            # selector 是显式的规格 dict：type + kwargs，通过 selectors 注册表解析
            assert options["selector"] == {
                "type": "django_setting",
                "attr": "BK_IAM_MODE_UNION_STRATEGY",
                "default": "any_of",
            }
            assert options["fallback_key"] == "any_of"
            policies = options["policies"]
            # 候选池至少覆盖："any_of / all_of / primary_v4 / primary_v3"
            assert set(policies.keys()) >= {"any_of", "all_of", "primary_v4", "primary_v3"}
            # 兜底策略 any_of 必须已注册（与 fallback_key 对齐，避免装配期崩溃）
            assert options["fallback_key"] in policies
            # primary_v4 / primary_v3 必须携带 primary_provider 参数
            assert policies["primary_v4"] == {
                "policy": "primary",
                "options": {"primary_provider": "v4"},
            }
            assert policies["primary_v3"] == {
                "policy": "primary",
                "options": {"primary_provider": "v3"},
            }


class TestV4ModeBaseUrlRequired:
    """默认 V4 仍 fail-fast；仅 V3 模式允许不提供 V4 地址。"""

    def test_v4_mode_requires_non_empty_v4_base_url(self, monkeypatch):
        import importlib

        from django.core.exceptions import ImproperlyConfigured

        import config.default as default_mod

        with monkeypatch.context() as m:
            m.setenv("BK_IAM_MODE", "v4")
            m.setenv("BK_IAM_V4_API_BASE_URL", " \t ")
            with pytest.raises(ImproperlyConfigured, match="BK_IAM_MODE=v4/union requires BK_IAM_V4_API_BASE_URL"):
                importlib.reload(default_mod)

        # 上一个 reload 会在模块中途退出；恢复环境后立即重载，避免污染本文件
        # 后续的 settings 组装验证。
        importlib.reload(default_mod)

    def test_union_mode_requires_non_empty_v4_base_url(self, monkeypatch):
        import importlib

        from django.core.exceptions import ImproperlyConfigured

        import config.default as default_mod

        with monkeypatch.context() as m:
            m.setenv("BK_IAM_MODE", "union")
            m.setenv("BK_IAM_V4_API_BASE_URL", "")
            with pytest.raises(ImproperlyConfigured, match="BK_IAM_MODE=v4/union requires BK_IAM_V4_API_BASE_URL"):
                importlib.reload(default_mod)

        importlib.reload(default_mod)

    def test_v3_mode_does_not_require_v4_base_url(self, monkeypatch):
        import importlib

        import config.default as default_mod

        with monkeypatch.context() as m:
            m.setenv("BK_IAM_MODE", "v3")
            m.setenv("BK_IAM_V4_API_BASE_URL", "")
            reloaded = importlib.reload(default_mod)
            assert reloaded.BK_IAM_MODE == "v3"
            assert reloaded.IAM_FRAMEWORK["PROVIDERS"][0]["class"].endswith("V3PermissionProvider")

        importlib.reload(default_mod)


class TestMigrationSafeDefault:
    """评论 4：破坏性变更必须走独立命令显式确认，不允许 post_migrate 默认放开。"""

    def test_migration_allow_destructive_defaults_false(self):
        from django.conf import settings

        migration = settings.IAM_FRAMEWORK["MIGRATION"]
        assert migration["allow_destructive"] is False, (
            "破坏性变更必须走独立命令显式确认，绝不允许在 post_migrate 自动流程里默认放开"
        )


class TestMigrationEnvOverrides:
    """MIGRATION 三个字段都通过 BK_IAM_ENGINE_MIGRATION_* 环境变量覆写，未显式设置时走安全默认。

    通过 monkeypatch.setenv + importlib.reload(config.default) 让 default.py
    重新按环境变量装配 IAM_FRAMEWORK，然后直接检查 module 内的 dict；不修改
    django.conf.settings 避免污染整个 session。
    """

    @staticmethod
    def _reload_default_migration(monkeypatch, env: dict[str, str]) -> dict:
        """按 env 设置环境变量后 reload config.default，返回 IAM_FRAMEWORK['MIGRATION']。"""
        import importlib

        # 清理再赋值：避免上一个 case 残留污染
        for k in (
            "BK_IAM_ENGINE_MIGRATION_MODE",
            "BK_IAM_ENGINE_MIGRATION_DIRECTORY",
            "BK_IAM_ENGINE_MIGRATION_ALLOW_DESTRUCTIVE",
        ):
            monkeypatch.delenv(k, raising=False)
        for k, v in env.items():
            monkeypatch.setenv(k, v)

        import config.default as default_mod

        reloaded = importlib.reload(default_mod)
        return reloaded.IAM_FRAMEWORK["MIGRATION"]

    def test_defaults_without_env(self, monkeypatch):
        migration = self._reload_default_migration(monkeypatch, {})
        assert migration["mode"] == "semi_auto"
        assert migration["directory"] == "bkmonitor/iam/iam_migrations"
        assert migration["allow_destructive"] is False

    def test_mode_override(self, monkeypatch):
        migration = self._reload_default_migration(monkeypatch, {"BK_IAM_ENGINE_MIGRATION_MODE": "manual"})
        assert migration["mode"] == "manual"

    def test_directory_override(self, monkeypatch):
        migration = self._reload_default_migration(
            monkeypatch, {"BK_IAM_ENGINE_MIGRATION_DIRECTORY": "/tmp/custom_migrations"}
        )
        assert migration["directory"] == "/tmp/custom_migrations"

    def test_allow_destructive_truthy_values(self, monkeypatch):
        for value in ("1", "true", "True", "YES", "yes"):
            migration = self._reload_default_migration(
                monkeypatch, {"BK_IAM_ENGINE_MIGRATION_ALLOW_DESTRUCTIVE": value}
            )
            assert migration["allow_destructive"] is True, f"value={value!r} 应视为开启"

    def test_allow_destructive_falsy_values(self, monkeypatch):
        for value in ("0", "false", "no", "off", "", "anything_else"):
            migration = self._reload_default_migration(
                monkeypatch, {"BK_IAM_ENGINE_MIGRATION_ALLOW_DESTRUCTIVE": value}
            )
            assert migration["allow_destructive"] is False, f"value={value!r} 不应视为开启"
