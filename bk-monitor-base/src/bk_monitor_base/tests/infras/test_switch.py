"""
测试 infras.switch 模块
"""

from typing import Any
from unittest.mock import Mock

import pytest

from bk_monitor_base.config import Config, get_config, set_config
from bk_monitor_base.infras.switch import base_switch


class TestBaseSwitch:
    """测试 base_switch 函数"""

    @pytest.fixture
    def mock_legacy_func(self) -> Mock:
        """创建 legacy 函数的 mock 对象"""
        mock = Mock(return_value="legacy_result")
        mock.__name__ = "legacy_func"
        return mock

    @pytest.fixture
    def mock_current_func(self) -> Mock:
        """创建 current 函数的 mock 对象"""
        mock = Mock(return_value="current_result")
        mock.__name__ = "current_func"
        return mock

    @pytest.fixture
    def original_config(self) -> Config:
        """保存原始配置用于恢复"""
        return get_config()

    @pytest.fixture(autouse=True)
    def restore_config(self, original_config: Config):
        """测试结束后恢复原始配置"""
        yield
        set_config(original_config)

    def test_switch_disabled_calls_legacy(self, mock_legacy_func: Mock, mock_current_func: Mock):
        """测试开关关闭时调用 legacy 函数"""
        # 设置开关为关闭状态
        config = get_config()
        config.common.enable_base_compatible_switch = False
        set_config(config)

        # 调用 base_switch
        result = base_switch(legacy=mock_legacy_func, current=mock_current_func, params=("arg1", "arg2"))

        # 验证调用了 legacy 函数
        mock_legacy_func.assert_called_once_with("arg1", "arg2")
        mock_current_func.assert_not_called()
        assert result == "legacy_result"

    def test_switch_enabled_calls_current(self, mock_legacy_func: Mock, mock_current_func: Mock):
        """测试开关打开时调用 current 函数"""
        # 设置开关为打开状态
        config = get_config()
        config.common.enable_base_compatible_switch = True
        set_config(config)

        # 调用 base_switch
        result = base_switch(legacy=mock_legacy_func, current=mock_current_func, params=("arg1", "arg2"))

        # 验证调用了 current 函数
        mock_current_func.assert_called_once_with("arg1", "arg2")
        mock_legacy_func.assert_not_called()
        assert result == "current_result"

    def test_switch_with_no_params(self, mock_legacy_func: Mock, mock_current_func: Mock):
        """测试无参数调用"""
        config = get_config()
        config.common.enable_base_compatible_switch = False
        set_config(config)

        # 不传递 params 参数（使用默认空元组）
        result = base_switch(legacy=mock_legacy_func, current=mock_current_func)

        # 验证调用了 legacy 函数且无参数
        mock_legacy_func.assert_called_once_with()
        assert result == "legacy_result"

    def test_switch_with_complex_params(self, mock_legacy_func: Mock, mock_current_func: Mock):
        """测试复杂参数传递"""
        config = get_config()
        config.common.enable_base_compatible_switch = True
        set_config(config)

        # 传递复杂参数
        obj = {"key": "value"}
        params = (123, "string", obj, [1, 2, 3])
        result = base_switch(legacy=mock_legacy_func, current=mock_current_func, params=params)

        # 验证参数正确传递
        mock_current_func.assert_called_once_with(123, "string", obj, [1, 2, 3])
        assert result == "current_result"

    def test_switch_preserves_return_type(self):
        """测试返回值类型保持正确"""

        def legacy_func(x: int) -> dict[str, Any]:
            return {"legacy": x}

        def current_func(x: int) -> dict[str, Any]:
            return {"current": x}

        config = get_config()
        config.common.enable_base_compatible_switch = True
        set_config(config)

        # 调用并验证返回类型
        result = base_switch(legacy=legacy_func, current=current_func, params=(42,))

        assert isinstance(result, dict)
        assert result == {"current": 42}

        # 切换开关
        config.common.enable_base_compatible_switch = False
        set_config(config)

        result = base_switch(legacy=legacy_func, current=current_func, params=(42,))

        assert isinstance(result, dict)
        assert result == {"legacy": 42}

    def test_switch_with_exceptions(self):
        """测试函数抛出异常时的行为"""

        def legacy_func() -> str:
            raise ValueError("Legacy error")

        def current_func() -> str:
            raise RuntimeError("Current error")

        config = get_config()

        # 测试 legacy 函数抛出异常
        config.common.enable_base_compatible_switch = False
        set_config(config)

        with pytest.raises(ValueError, match="Legacy error"):
            base_switch(legacy=legacy_func, current=current_func)

        # 测试 current 函数抛出异常
        config.common.enable_base_compatible_switch = True
        set_config(config)

        with pytest.raises(RuntimeError, match="Current error"):
            base_switch(legacy=legacy_func, current=current_func)

    def test_switch_with_callable_objects(self):
        """测试使用可调用对象（如类方法）"""

        class LegacyApi:
            """模拟旧的 API 类"""

            @staticmethod
            def method(value: str) -> str:
                return f"legacy_{value}"

        class CurrentApi:
            """模拟新的 API 类"""

            @staticmethod
            def method(value: str) -> str:
                return f"current_{value}"

        config = get_config()

        # 测试调用 legacy
        config.common.enable_base_compatible_switch = False
        set_config(config)

        result = base_switch(legacy=LegacyApi.method, current=CurrentApi.method, params=("test",))
        assert result == "legacy_test"

        # 测试调用 current
        config.common.enable_base_compatible_switch = True
        set_config(config)

        result = base_switch(legacy=LegacyApi.method, current=CurrentApi.method, params=("test",))
        assert result == "current_test"

    def test_switch_toggle_behavior(self, mock_legacy_func: Mock, mock_current_func: Mock):
        """测试开关来回切换的行为"""
        config = get_config()

        # 第一次：关闭状态
        config.common.enable_base_compatible_switch = False
        set_config(config)
        result1 = base_switch(legacy=mock_legacy_func, current=mock_current_func, params=("test1",))
        assert result1 == "legacy_result"
        assert mock_legacy_func.call_count == 1

        # 第二次：打开状态
        config.common.enable_base_compatible_switch = True
        set_config(config)
        result2 = base_switch(legacy=mock_legacy_func, current=mock_current_func, params=("test2",))
        assert result2 == "current_result"
        assert mock_current_func.call_count == 1

        # 第三次：再次关闭
        config.common.enable_base_compatible_switch = False
        set_config(config)
        result3 = base_switch(legacy=mock_legacy_func, current=mock_current_func, params=("test3",))
        assert result3 == "legacy_result"
        assert mock_legacy_func.call_count == 2

        # 验证每次调用的参数
        assert mock_legacy_func.call_args_list[0][0] == ("test1",)
        assert mock_current_func.call_args_list[0][0] == ("test2",)
        assert mock_legacy_func.call_args_list[1][0] == ("test3",)
