import uuid
from ipaddress import IPv4Address
from typing import Optional

from bk_monitor_base.infras.declaratives.base.resource import ResourceModelController


class TestResolveType:
    """测试 _resolve_type 方法"""

    def test_int_or_none(self):
        """测试 int | None"""
        result = ResourceModelController._resolve_type(int | None)
        assert result is int

    def test_str_or_none(self):
        """测试 str | None"""
        result = ResourceModelController._resolve_type(str | None)
        assert result is str

    def test_optional_int(self):
        """测试 Optional[int] (向后兼容)"""
        result = ResourceModelController._resolve_type(Optional[int])  # noqa: UP007
        assert result is int

    def test_list_str(self):
        """测试 list[str] - 应保持原样"""
        annotation = list[str]
        result = ResourceModelController._resolve_type(annotation)
        assert result == annotation

    def test_list_dict_or_dict(self):
        """测试 list[dict] | dict - 复杂联合类型"""
        annotation = list[dict] | dict
        result = ResourceModelController._resolve_type(annotation)
        assert result == annotation

    def test_ipv4_or_none(self):
        """测试 IPv4Address | None"""
        result = ResourceModelController._resolve_type(IPv4Address | None)
        assert result is IPv4Address

    def test_uuid(self):
        """测试 uuid.UUID"""
        result = ResourceModelController._resolve_type(uuid.UUID)
        assert result is uuid.UUID

    def test_plain_int(self):
        """测试普通 int"""
        result = ResourceModelController._resolve_type(int)
        assert result is int


class TestIsComplexUnionType:
    """测试 _is_complex_union_type 方法"""

    def test_list_dict_or_dict(self):
        assert ResourceModelController._is_complex_union_type(list[dict] | dict) is True

    def test_str_or_int(self):
        assert ResourceModelController._is_complex_union_type(str | int) is True

    def test_int_or_none(self):
        assert ResourceModelController._is_complex_union_type(int | None) is False

    def test_plain_int(self):
        assert ResourceModelController._is_complex_union_type(int) is False


class TestIsGenericContainerType:
    """测试 _is_generic_container_type 方法"""

    def test_list_str(self):
        assert ResourceModelController._is_generic_container_type(list[str]) is True

    def test_dict_str_int(self):
        assert ResourceModelController._is_generic_container_type(dict[str, int]) is True

    def test_plain_list(self):
        assert ResourceModelController._is_generic_container_type(list) is False

    def test_plain_int(self):
        assert ResourceModelController._is_generic_container_type(int) is False
