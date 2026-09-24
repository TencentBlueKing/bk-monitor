"""
测试 infras.compare 模块
"""

from bk_monitor_base.infras.compare import nested_equal


class TestNestedEqual:
    """测试 nested_equal 函数"""

    def test_nested_equal_lists(self):
        """测试嵌套列表相等比较"""
        # 相同列表
        assert nested_equal([1, 2, 3], [1, 2, 3]) is True
        assert nested_equal([], []) is True

        # 不同列表
        assert nested_equal([1, 2, 3], [1, 2, 4]) is False
        assert nested_equal([1, 2, 3], [1, 2]) is False

        # 嵌套列表
        assert nested_equal([[1, 2], [3, 4]], [[1, 2], [3, 4]]) is True
        assert nested_equal([[1, 2], [3, 4]], [[1, 2], [3, 5]]) is False

    def test_nested_equal_dicts(self):
        """测试嵌套字典相等比较"""
        # 相同字典
        assert nested_equal({"a": 1, "b": 2}, {"a": 1, "b": 2}) is True
        assert nested_equal({}, {}) is True

        # 不同字典
        assert nested_equal({"a": 1, "b": 2}, {"a": 1, "b": 3}) is False
        assert nested_equal({"a": 1, "b": 2}, {"a": 1}) is False

        # 嵌套字典
        assert nested_equal({"a": {"b": 1}, "c": 2}, {"a": {"b": 1}, "c": 2}) is True
        assert nested_equal({"a": {"b": 1}, "c": 2}, {"a": {"b": 2}, "c": 2}) is False

    def test_nested_equal_mixed_types(self):
        """测试混合类型相等比较"""
        # 列表和字典混合
        data1 = {"a": [1, 2, {"b": 3}], "c": [4, 5]}
        data2 = {"a": [1, 2, {"b": 3}], "c": [4, 5]}
        assert nested_equal(data1, data2) is True

        data3 = {"a": [1, 2, {"b": 4}], "c": [4, 5]}
        assert nested_equal(data1, data3) is False

    def test_nested_equal_primitives(self):
        """测试基本类型相等比较"""
        assert nested_equal(1, 1) is True
        assert nested_equal("test", "test") is True
        assert nested_equal(True, True) is True
        assert nested_equal(None, None) is True

        assert nested_equal(1, 2) is False
        assert nested_equal("test", "other") is False
        assert nested_equal(True, False) is False

    def test_nested_equal_type_mismatch(self):
        """测试类型不匹配"""
        assert nested_equal([1, 2, 3], {"a": 1}) is False
        assert nested_equal({"a": 1}, [1, 2, 3]) is False
        assert nested_equal(1, "1") is False

    def test_nested_equal_complex_nested_structures(self):
        """测试复杂的嵌套结构"""
        # 深度嵌套的混合结构
        complex_data1 = {
            "level1": {
                "level2": [
                    {"id": 1, "data": [10, 20, {"nested": True}]},
                    {"id": 2, "data": [30, 40, {"nested": False}]},
                ],
                "metadata": {"version": "1.0", "enabled": True},
            }
        }

        complex_data2 = {
            "level1": {
                "level2": [
                    {"id": 1, "data": [10, 20, {"nested": True}]},
                    {"id": 2, "data": [30, 40, {"nested": False}]},
                ],
                "metadata": {"version": "1.0", "enabled": True},
            }
        }

        assert nested_equal(complex_data1, complex_data2) is True

        # 稍微修改的数据
        complex_data3 = {
            "level1": {
                "level2": [
                    {"id": 1, "data": [10, 20, {"nested": True}]},
                    {"id": 2, "data": [30, 40, {"nested": True}]},  # 这里改为 True
                ],
                "metadata": {"version": "1.0", "enabled": True},
            }
        }

        assert nested_equal(complex_data1, complex_data3) is False

    def test_nested_equal_edge_cases(self):
        """测试边界情况"""
        # 空结构
        assert nested_equal([], []) is True
        assert nested_equal({}, {}) is True

        # 单元素结构
        assert nested_equal([1], [1]) is True
        assert nested_equal([1], [2]) is False
        assert nested_equal({"a": 1}, {"a": 1}) is True
        assert nested_equal({"a": 1}, {"a": 2}) is False

        # 包含 None 值
        assert nested_equal([None, 1], [None, 1]) is True
        assert nested_equal([None, 1], [None, 2]) is False
        assert nested_equal({"a": None}, {"a": None}) is True
        assert nested_equal({"a": None}, {"b": None}) is False
