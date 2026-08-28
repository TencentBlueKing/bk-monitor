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
            assert composition == {"policy": "any_of"}


class TestMigrationSafeDefault:
    """评论 4：破坏性变更必须走独立命令显式确认，不允许 post_migrate 默认放开。"""

    def test_migration_allow_destructive_defaults_false(self):
        from django.conf import settings

        migration = settings.IAM_FRAMEWORK["MIGRATION"]
        assert migration["allow_destructive"] is False, (
            "破坏性变更必须走独立命令显式确认，绝不允许在 post_migrate 自动流程里默认放开"
        )
