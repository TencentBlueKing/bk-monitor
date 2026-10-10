"""
测试 dynamic_group 实体定义模块

测试 DynamicGroup, DynamicGroupQueryFilter, DynamicGroupMember, DynamicGroupPermission 实体类。
"""

import pytest
from pydantic import ValidationError

from bk_monitor_base.domains.dynamic_group.define import (
    DynamicGroup,
    DynamicGroupMember,
    DynamicGroupPermission,
    DynamicGroupQueryFilter,
)


@pytest.mark.django_db(databases=["default"])
class TestDynamicGroup:
    """测试 DynamicGroup 实体类"""

    def test_create_dynamic_group_entity(self):
        """测试创建 DynamicGroup 实体"""
        group = DynamicGroup(
            dynamic_group_id=1,
            dynamic_group_name="测试分组",
            condition_list=[{"field": "bk_host_innerip", "value": "10.", "operator": "contains"}],
            object_model_code="cw-Host",
            space_code="bkcc__2",
            bk_tenant_id="system",
            member_count=10,
        )

        assert group.dynamic_group_id == 1
        assert group.dynamic_group_name == "测试分组"
        assert len(group.condition_list) == 1
        assert group.object_model_code == "cw-Host"
        assert group.space_code == "bkcc__2"
        assert group.bk_tenant_id == "system"
        assert group.member_count == 10

    def test_dynamic_group_default_values(self):
        """测试 DynamicGroup 默认值"""
        group = DynamicGroup(
            dynamic_group_name="测试分组",
            object_model_code="cw-Host",
        )

        assert group.dynamic_group_id is None
        assert group.condition_list == []
        assert group.space_code == ""
        assert group.bk_tenant_id == "system"
        assert group.member_count == 0

    def test_get_bk_biz_id_success(self, mock_dynamic_group):
        """测试从 space_code 成功提取业务 ID"""
        bk_biz_id = mock_dynamic_group.get_bk_biz_id()
        assert bk_biz_id == 2

    def test_get_bk_biz_id_empty_space_code(self):
        """测试 space_code 为空时抛出异常"""
        group = DynamicGroup(
            dynamic_group_name="测试分组",
            object_model_code="cw-Host",
            space_code="",
        )

        with pytest.raises(ValueError, match="space_code is null"):
            group.get_bk_biz_id()

    def test_get_bk_biz_id_invalid_format(self):
        """测试 space_code 格式错误时抛出异常"""
        group = DynamicGroup(
            dynamic_group_name="测试分组",
            object_model_code="cw-Host",
            space_code="invalid_format",
        )

        with pytest.raises(ValueError, match="invalid space_code format"):
            group.get_bk_biz_id()

    def test_get_bk_biz_id_non_numeric(self):
        """测试 space_code 中业务 ID 非数字时抛出异常"""
        group = DynamicGroup(
            dynamic_group_name="测试分组",
            object_model_code="cw-Host",
            space_code="bkcc__abc",
        )

        with pytest.raises(ValueError):
            group.get_bk_biz_id()

    def test_dynamic_group_name_min_length(self):
        """测试名称最小长度校验"""
        with pytest.raises(ValidationError):
            DynamicGroup(
                dynamic_group_name="",
                object_model_code="cw-Host",
            )

    def test_dynamic_group_name_max_length(self):
        """测试名称最大长度校验"""
        with pytest.raises(ValidationError):
            DynamicGroup(
                dynamic_group_name="a" * 256,
                object_model_code="cw-Host",
            )

    def test_object_model_code_min_length(self):
        """测试对象模型代码最小长度校验"""
        with pytest.raises(ValidationError):
            DynamicGroup(
                dynamic_group_name="测试分组",
                object_model_code="",
            )


@pytest.mark.django_db(databases=["default"])
class TestDynamicGroupQueryFilter:
    """测试 DynamicGroupQueryFilter 实体类"""

    def test_create_query_filter(self, mock_dynamic_group_query_filter):
        """测试创建查询过滤条件"""
        filter_obj = mock_dynamic_group_query_filter

        assert filter_obj.dynamic_group_ids == [1, 2, 3]
        assert filter_obj.space_codes == ["bkcc__2"]
        assert filter_obj.name_keywords == ["测试"]
        assert filter_obj.object_model_code == "cw-Host"
        assert filter_obj.page == 1
        assert filter_obj.page_size == 20

    def test_query_filter_default_values(self):
        """测试查询过滤条件默认值"""
        filter_obj = DynamicGroupQueryFilter()

        assert filter_obj.dynamic_group_ids == []
        assert filter_obj.space_codes == []
        assert filter_obj.name_keywords == []
        assert filter_obj.dynamic_group_names == []
        assert filter_obj.object_model_code is None
        assert filter_obj.is_return_member_list is False
        assert filter_obj.page == 1
        assert filter_obj.page_size == 20

    def test_query_filter_page_validation(self):
        """测试页码校验（必须 >= 1）"""
        with pytest.raises(ValidationError):
            DynamicGroupQueryFilter(page=0)

    def test_query_filter_page_size_validation(self):
        """测试每页数量校验（必须 >= 1）"""
        with pytest.raises(ValidationError):
            DynamicGroupQueryFilter(page_size=0)

    def test_query_filter_page_size_max_validation(self):
        """测试每页数量最大值校验（必须 <= 1000）"""
        with pytest.raises(ValidationError):
            DynamicGroupQueryFilter(page_size=1001)

    def test_query_filter_with_all_params(self):
        """测试带所有参数的查询过滤条件"""
        filter_obj = DynamicGroupQueryFilter(
            dynamic_group_ids=[1, 2],
            space_codes=["bkcc__2", "bkcc__3"],
            name_keywords=["关键词1", "关键词2"],
            dynamic_group_names=["分组1", "分组2"],
            object_model_code="cw-Host",
            is_return_member_list=True,
            page=2,
            page_size=50,
        )

        assert len(filter_obj.dynamic_group_ids) == 2
        assert len(filter_obj.space_codes) == 2
        assert len(filter_obj.name_keywords) == 2
        assert len(filter_obj.dynamic_group_names) == 2
        assert filter_obj.is_return_member_list is True
        assert filter_obj.page == 2
        assert filter_obj.page_size == 50


@pytest.mark.django_db(databases=["default"])
class TestDynamicGroupMember:
    """测试 DynamicGroupMember 实体类"""

    def test_create_member(self, mock_dynamic_group_member):
        """测试创建成员实体"""
        member = mock_dynamic_group_member

        assert member.id == 1
        assert member.dynamic_group_id == 1
        assert member.member["bk_inst_id"] == 101
        assert member.member["bk_host_innerip"] == "10.0.0.1"

    def test_member_default_values(self):
        """测试成员实体默认值"""
        member = DynamicGroupMember(dynamic_group_id=1)

        assert member.id is None
        assert member.member == {}

    def test_member_with_complex_data(self):
        """测试成员实体包含复杂数据"""
        member = DynamicGroupMember(
            id=1,
            dynamic_group_id=1,
            member={
                "bk_inst_id": 101,
                "bk_host_innerip": "10.0.0.1",
                "ip_list": [
                    {"ip": "10.0.0.1", "bk_cloud_id": 0},
                    {"ip": "10.0.0.2", "bk_cloud_id": 0},
                ],
                "extra_info": {"key": "value"},
            },
        )

        assert len(member.member["ip_list"]) == 2
        assert member.member["extra_info"]["key"] == "value"


@pytest.mark.django_db(databases=["default"])
class TestDynamicGroupPermission:
    """测试 DynamicGroupPermission 实体类"""

    def test_create_permission(self, mock_dynamic_group_permission):
        """测试创建权限实体"""
        permission = mock_dynamic_group_permission

        assert permission.edit_allowed is True
        assert permission.edit_message == ""
        assert permission.delete_allowed is False
        assert permission.delete_message == "该分组被其他模块引用，无法删除"

    def test_permission_default_values(self):
        """测试权限实体默认值"""
        permission = DynamicGroupPermission()

        assert permission.edit_allowed is True
        assert permission.edit_message == ""
        assert permission.delete_allowed is True
        assert permission.delete_message == ""

    def test_permission_all_denied(self):
        """测试所有操作都被拒绝的权限"""
        permission = DynamicGroupPermission(
            edit_allowed=False,
            edit_message="无编辑权限",
            delete_allowed=False,
            delete_message="无删除权限",
        )

        assert permission.edit_allowed is False
        assert permission.edit_message == "无编辑权限"
        assert permission.delete_allowed is False
        assert permission.delete_message == "无删除权限"

    def test_permission_all_allowed(self):
        """测试所有操作都被允许的权限"""
        permission = DynamicGroupPermission(
            edit_allowed=True,
            edit_message="",
            delete_allowed=True,
            delete_message="",
        )

        assert permission.edit_allowed is True
        assert permission.delete_allowed is True
