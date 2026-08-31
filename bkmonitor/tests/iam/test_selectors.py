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
# selectors 模块单测
#
# 覆盖：
#   1. build_selector 参数校验（spec 非 dict / 缺 type / type 非 str 都要 raise）
#   2. 内置 "static" selector：返回值固定
#   3. 内置 "django_setting" selector：从 django.conf.settings 读，支持 default
#   4. dotted path 走 import_class：可指向业务自定义 factory
#   5. 未注册的短名 → ValueError（并给出可用列表）
#   6. factory 返回非 callable → ValueError（fail fast）
#   7. register_selector 注册后可被 build_selector 命中
# ==============================================================================

from collections.abc import Callable

import pytest

from bkmonitor.iam.iam_engine.provider.composition.selectors import (
    _SELECTOR_REGISTRY,
    build_selector,
    register_selector,
)


class TestBuildSelectorContract:
    def test_spec_must_be_dict(self):
        with pytest.raises(ValueError, match="must be a dict"):
            build_selector("not-a-dict")  # type: ignore[arg-type]

    def test_spec_missing_type(self):
        with pytest.raises(ValueError, match="missing 'type'"):
            build_selector({"value": "x"})

    def test_spec_type_must_be_non_empty_string(self):
        with pytest.raises(ValueError, match="non-empty string"):
            build_selector({"type": ""})
        with pytest.raises(ValueError, match="non-empty string"):
            build_selector({"type": 123})  # type: ignore[dict-item]

    def test_unknown_short_name_raises_with_available(self):
        with pytest.raises(ValueError, match="unknown selector type"):
            build_selector({"type": "not_registered"})


class TestStaticSelector:
    def test_returns_fixed_value(self):
        selector = build_selector({"type": "static", "value": "any_of"})
        assert callable(selector)
        assert selector() == "any_of"
        # 幂等：多次调用返回同一个值
        assert selector() == "any_of"

    def test_value_must_be_string(self):
        with pytest.raises(ValueError, match="'value' to be str"):
            build_selector({"type": "static", "value": 42})


class TestDjangoSettingSelector:
    def test_reads_from_django_settings(self, settings):
        # 使用 pytest-django 的 settings fixture 隔离修改
        settings.MY_TEST_MODE_ATTR = "primary_v4"
        selector = build_selector({"type": "django_setting", "attr": "MY_TEST_MODE_ATTR"})
        assert selector() == "primary_v4"

    def test_default_when_attr_missing(self, settings):
        # 确保属性不存在
        assert not hasattr(settings, "DOES_NOT_EXIST_ATTR_XYZ")
        selector = build_selector({"type": "django_setting", "attr": "DOES_NOT_EXIST_ATTR_XYZ", "default": "fallback"})
        assert selector() == "fallback"

    def test_selector_reflects_runtime_setting_change(self, settings):
        """selector 每次调用都重新读 settings，能反映运行期的动态变更。"""
        settings.MY_TEST_MODE_ATTR = "any_of"
        selector = build_selector({"type": "django_setting", "attr": "MY_TEST_MODE_ATTR"})
        assert selector() == "any_of"

        # 模拟运维在 Admin 里改配置 → DynamicSettings 触发 settings 变化
        settings.MY_TEST_MODE_ATTR = "all_of"
        assert selector() == "all_of"

    def test_attr_required(self):
        with pytest.raises(ValueError, match="non-empty 'attr'"):
            build_selector({"type": "django_setting"})
        with pytest.raises(ValueError, match="non-empty 'attr'"):
            build_selector({"type": "django_setting", "attr": ""})


# ------------------------------------------------------------------
# dotted path & 注册表扩展
# ------------------------------------------------------------------


# 模块级 factory：给 dotted path 用例作为目标。返回始终一个固定字符串。
def _test_dotted_factory(value: str = "dotted-hit") -> Callable[[], str]:
    return lambda: value


class TestDottedPathSelector:
    def test_dotted_factory_loaded(self):
        selector = build_selector(
            {
                "type": "tests.iam.test_selectors._test_dotted_factory",
                "value": "custom-xyz",
            }
        )
        assert selector() == "custom-xyz"

    def test_dotted_factory_default_kwargs(self):
        selector = build_selector({"type": "tests.iam.test_selectors._test_dotted_factory"})
        assert selector() == "dotted-hit"


class TestFactoryContract:
    def test_non_callable_return_raises(self):
        # 临时注册一个坏 factory：返回非 callable
        try:
            register_selector("_broken_factory_for_test")(lambda: "not-callable")  # type: ignore[arg-type]
            with pytest.raises(ValueError, match="returned non-callable"):
                build_selector({"type": "_broken_factory_for_test"})
        finally:
            _SELECTOR_REGISTRY.pop("_broken_factory_for_test", None)

    def test_register_and_build(self):
        # 走注册表的用户扩展路径
        def _factory(prefix: str = "p") -> Callable[[], str]:
            return lambda: f"{prefix}-value"

        register_selector("_ok_factory_for_test")(_factory)
        try:
            selector = build_selector({"type": "_ok_factory_for_test", "prefix": "hello"})
            assert selector() == "hello-value"
        finally:
            _SELECTOR_REGISTRY.pop("_ok_factory_for_test", None)
