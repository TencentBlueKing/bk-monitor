"""
测试 dynamic_group 操作模块

测试 list_dynamic_groups, get_dynamic_group, create_dynamic_group,
update_dynamic_group, delete_dynamic_group 等 CRUD 操作。
"""

from unittest.mock import MagicMock, patch

import pytest

from bk_monitor_base.domains.dynamic_group.define import DynamicGroup
from bk_monitor_base.domains.dynamic_group.errors import DynamicGroupNotFound, DynamicGroupValidError
from bk_monitor_base.domains.dynamic_group.models import DynamicGroupMemberORM, DynamicGroupORM
from bk_monitor_base.domains.dynamic_group.operations.dynamic_group import (
    batch_delete_dynamic_groups,
    count_dynamic_groups,
    create_dynamic_group,
    delete_dynamic_group,
    exists_dynamic_group,
    fetch_dynamic_group_inst_map,
    get_dynamic_group,
    get_dynamic_group_members,
    list_dynamic_group_members,
    list_dynamic_groups,
    preview_dynamic_group_members,
    update_dynamic_group,
)


@pytest.mark.django_db(databases=["default"])
class TestListDynamicGroups:
    """测试 list_dynamic_groups 函数"""

    def test_list_all_groups(self, db_dynamic_group):
        """测试查询所有动态分组"""
        total, result = list_dynamic_groups()

        assert total >= 1
        assert len(result) >= 1
        group_ids = [g.dynamic_group_id for g in result]
        assert db_dynamic_group.dynamic_group_id in group_ids

    def test_list_by_ids(self, db_dynamic_group):
        """测试按 ID 列表过滤"""
        total, result = list_dynamic_groups(dynamic_group_ids=[db_dynamic_group.dynamic_group_id])

        assert total == 1
        assert len(result) == 1
        assert result[0].dynamic_group_id == db_dynamic_group.dynamic_group_id

    def test_list_by_object_model_codes(self, db_dynamic_group):
        """测试按对象模型代码过滤"""
        total, result = list_dynamic_groups(object_model_codes=["cw-Host"])

        assert total >= 1
        assert len(result) >= 1
        for group in result:
            assert group.object_model_code == "cw-Host"

    def test_list_by_space_codes(self, db_dynamic_group):
        """测试按空间代码过滤"""
        total, result = list_dynamic_groups(space_codes=["bkcc__2"])

        assert total >= 1
        assert len(result) >= 1
        for group in result:
            assert group.space_code == "bkcc__2"

    def test_list_by_bk_tenant_ids(self, db_dynamic_group):
        """测试按租户 ID 过滤"""
        total, result = list_dynamic_groups(bk_tenant_ids=["system"])

        assert total >= 1
        assert len(result) >= 1
        for group in result:
            assert group.bk_tenant_id == "system"

    def test_list_by_name_contains(self, db_dynamic_group):
        """测试按名称模糊查询"""
        total, result = list_dynamic_groups(name_contains="测试")

        assert total >= 1
        assert len(result) >= 1
        for group in result:
            assert "测试" in group.dynamic_group_name

    def test_list_with_pagination(self, db_dynamic_group):
        """测试分页"""
        total, result = list_dynamic_groups(limit=1, offset=0)

        assert total >= 1
        assert len(result) <= 1

    def test_list_with_member_count(self, db_dynamic_group_with_members):
        """测试统计成员数量"""
        total, result = list_dynamic_groups(
            dynamic_group_ids=[db_dynamic_group_with_members.dynamic_group_id],
            with_member_count=True,
        )

        assert total == 1
        assert len(result) == 1
        assert result[0].member_count == 3

    def test_list_empty_raises_when_flag_set(self):
        """测试空结果时抛出异常（当 raise_not_found=True）"""
        with pytest.raises(DynamicGroupNotFound):
            list_dynamic_groups(dynamic_group_ids=[99999], raise_not_found=True)

    def test_list_with_order_by(self, db_dynamic_group):
        """测试排序"""
        total, result = list_dynamic_groups(order_by=["dynamic_group_name"])

        assert total >= 1
        assert len(result) >= 1


@pytest.mark.django_db(databases=["default"])
class TestGetDynamicGroup:
    """测试 get_dynamic_group 函数"""

    def test_get_group_success(self, db_dynamic_group):
        """测试成功获取动态分组"""
        result = get_dynamic_group(db_dynamic_group.dynamic_group_id)

        assert result is not None
        assert result.dynamic_group_id == db_dynamic_group.dynamic_group_id
        assert result.dynamic_group_name == "测试动态分组"

    def test_get_group_not_found_raises(self):
        """测试获取不存在的分组抛出异常"""
        with pytest.raises(DynamicGroupNotFound):
            get_dynamic_group(99999, raise_not_found=True)

    def test_get_group_not_found_returns_none(self):
        """测试获取不存在的分组返回 None（当 raise_not_found=False）"""
        result = get_dynamic_group(99999, raise_not_found=False)

        assert result is None

    def test_get_group_with_member_count(self, db_dynamic_group_with_members):
        """测试获取分组并统计成员数量"""
        result = get_dynamic_group(
            db_dynamic_group_with_members.dynamic_group_id,
            with_member_count=True,
        )

        assert result is not None
        assert result.member_count == 3


@pytest.mark.django_db(databases=["default"])
class TestCreateDynamicGroup:
    """测试 create_dynamic_group 函数"""

    @patch("bk_monitor_base.domains.dynamic_group.operations.dynamic_group.get_member_fetcher")
    @patch("bk_monitor_base.domains.dynamic_group.operations.dynamic_group.cache_dynamic_group_member")
    @patch("bk_monitor_base.domains.dynamic_group.operations.dynamic_group.UsageRecordOperator")
    def test_create_group_success(
        self,
        mock_usage_record,
        mock_cache,
        mock_get_fetcher,
        db_object_model,
    ):
        """测试成功创建动态分组"""
        # 模拟 fetcher 返回成员
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_all.return_value = [
            {"bk_inst_id": 1, "ip_list": [{"ip": "10.0.0.1", "error": False}]},
            {"bk_inst_id": 2, "ip_list": [{"ip": "10.0.0.2", "error": True}]},
        ]
        mock_get_fetcher.return_value = mock_fetcher

        entity = DynamicGroup(
            dynamic_group_name="新建分组",
            condition_list=[{"field": "bk_host_innerip", "value": "10.", "operator": "contains"}],
            object_model_code="cw-Host",
            space_code="bkcc__3",
            bk_tenant_id="system",
            created_by="test_user",
        )

        created_group, member_inst_ids = create_dynamic_group(entity)

        assert created_group.dynamic_group_id is not None
        assert created_group.dynamic_group_name == "新建分组"
        assert member_inst_ids == [1, 2]
        saved_members = list(
            DynamicGroupMemberORM.objects.filter(dynamic_group_id=created_group.dynamic_group_id).values_list(
                "member",
                flat=True,
            )
        )
        assert saved_members[0]["ip_list"][0]["error"] is False
        assert saved_members[1]["ip_list"][0]["error"] is True

        # 验证缓存被调用
        mock_cache.assert_called_once()

        # 验证使用记录被创建
        mock_usage_record.create.assert_called_once()

        # 清理
        DynamicGroupMemberORM.objects.filter(dynamic_group_id=created_group.dynamic_group_id).delete()
        DynamicGroupORM.objects.filter(dynamic_group_id=created_group.dynamic_group_id).delete()

    def test_create_group_duplicate_name_raises(self, db_dynamic_group):
        """测试创建重复名称的分组抛出异常"""
        entity = DynamicGroup(
            dynamic_group_name="测试动态分组",  # 与 db_dynamic_group 同名
            condition_list=[],
            object_model_code="cw-Host",
            space_code="bkcc__2",
            bk_tenant_id="system",
        )

        with pytest.raises(DynamicGroupValidError):
            create_dynamic_group(entity)


@pytest.mark.django_db(databases=["default"])
class TestUpdateDynamicGroup:
    """测试 update_dynamic_group 函数"""

    @patch("bk_monitor_base.domains.dynamic_group.operations.dynamic_group.get_member_fetcher")
    @patch("bk_monitor_base.domains.dynamic_group.operations.dynamic_group.cache_dynamic_group_member")
    def test_update_group_name(self, mock_cache, mock_get_fetcher, db_dynamic_group):
        """测试更新动态分组名称"""
        # 模拟 fetcher 返回空成员
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_all.return_value = []
        mock_get_fetcher.return_value = mock_fetcher

        entity = DynamicGroup(
            dynamic_group_id=db_dynamic_group.dynamic_group_id,
            dynamic_group_name="更新后的名称",
            object_model_code=db_dynamic_group.object_model_code,
            updated_by="test_user",
        )

        updated_group, add_list, delete_list, has_changed = update_dynamic_group(entity)

        assert updated_group.dynamic_group_name == "更新后的名称"

    @patch("bk_monitor_base.domains.dynamic_group.operations.dynamic_group.get_member_fetcher")
    @patch("bk_monitor_base.domains.dynamic_group.operations.dynamic_group.cache_dynamic_group_member")
    def test_update_group_with_member_changes(
        self,
        mock_cache,
        mock_get_fetcher,
        db_dynamic_group_with_members,
    ):
        """测试更新动态分组时成员变化"""
        # 模拟新成员列表（新增一个，删除一个）
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_all.return_value = [
            {"bk_inst_id": 101, "ip_list": [{"ip": "10.0.0.1", "bk_cloud_id": 0, "error": False}]},
            {"bk_inst_id": 102, "ip_list": [{"ip": "10.0.0.2", "bk_cloud_id": 0, "error": False}]},
            {"bk_inst_id": 104, "ip_list": [{"ip": "10.0.0.4", "bk_cloud_id": 0, "error": True}]},  # 新成员
            # 103 被移除
        ]
        mock_get_fetcher.return_value = mock_fetcher

        entity = DynamicGroup(
            dynamic_group_id=db_dynamic_group_with_members.dynamic_group_id,
            dynamic_group_name=db_dynamic_group_with_members.dynamic_group_name,
            object_model_code=db_dynamic_group_with_members.object_model_code,
            updated_by="test_user",
        )

        updated_group, add_list, delete_list, has_changed = update_dynamic_group(entity, only_member=True)

        assert has_changed is True
        assert 104 in add_list
        assert 103 in delete_list

    def test_update_nonexistent_group_raises(self):
        """测试更新不存在的分组抛出异常"""
        entity = DynamicGroup(
            dynamic_group_id=99999,
            dynamic_group_name="不存在",
            object_model_code="cw-Host",
        )

        with pytest.raises(DynamicGroupNotFound):
            update_dynamic_group(entity)

    def test_update_without_id_raises(self):
        """测试更新时缺少 ID 抛出异常"""
        entity = DynamicGroup(
            dynamic_group_name="缺少ID",
            object_model_code="cw-Host",
        )

        with pytest.raises(DynamicGroupValidError):
            update_dynamic_group(entity)


@pytest.mark.django_db(databases=["default"])
class TestDeleteDynamicGroup:
    """测试 delete_dynamic_group 函数"""

    @patch("bk_monitor_base.domains.dynamic_group.operations.dynamic_group.delete_dynamic_group_cache")
    @patch("bk_monitor_base.domains.dynamic_group.operations.dynamic_group.UsageRecordOperator")
    def test_delete_group_success(self, mock_usage_record, mock_delete_cache, db_dynamic_group_with_members):
        """测试成功删除动态分组"""
        group_id = db_dynamic_group_with_members.dynamic_group_id

        object_model_code, member_inst_ids = delete_dynamic_group(group_id)

        assert object_model_code == "cw-Host"
        assert set(member_inst_ids) == {101, 102, 103}

        # 验证分组已删除
        assert not DynamicGroupORM.objects.filter(dynamic_group_id=group_id).exists()

        # 验证成员已删除
        assert not DynamicGroupMemberORM.objects.filter(dynamic_group_id=group_id).exists()

        # 验证缓存删除被调用
        mock_delete_cache.assert_called_once()

        # 验证使用记录被删除
        mock_usage_record.delete.assert_called_once()

    def test_delete_nonexistent_group_raises(self):
        """测试删除不存在的分组抛出异常"""
        with pytest.raises(DynamicGroupNotFound):
            delete_dynamic_group(99999)


@pytest.mark.django_db(databases=["default"])
class TestBatchDeleteDynamicGroups:
    """测试 batch_delete_dynamic_groups 函数"""

    @patch("bk_monitor_base.domains.dynamic_group.operations.dynamic_group.delete_dynamic_group_cache")
    @patch("bk_monitor_base.domains.dynamic_group.operations.dynamic_group.UsageRecordOperator")
    def test_batch_delete_success(self, mock_usage_record, mock_delete_cache, db_object_model):
        """测试批量删除动态分组"""
        # 创建多个分组
        group1 = DynamicGroupORM.objects.create(
            dynamic_group_name="批量删除分组1",
            condition_list=[],
            object_model_code="cw-Host",
            space_code="bkcc__2",
            bk_tenant_id="system",
        )
        group2 = DynamicGroupORM.objects.create(
            dynamic_group_name="批量删除分组2",
            condition_list=[],
            object_model_code="cw-Host",
            space_code="bkcc__2",
            bk_tenant_id="system",
        )

        # 添加成员
        DynamicGroupMemberORM.objects.create(
            dynamic_group=group1,
            member={"bk_inst_id": 201},
        )

        result = batch_delete_dynamic_groups([group1.dynamic_group_id, group2.dynamic_group_id])

        assert group1.dynamic_group_id in result
        assert group2.dynamic_group_id in result
        assert result[group1.dynamic_group_id]["object_model_code"] == "cw-Host"
        assert result[group1.dynamic_group_id]["member_inst_ids"] == [201]

        # 验证分组已删除
        assert not DynamicGroupORM.objects.filter(
            dynamic_group_id__in=[group1.dynamic_group_id, group2.dynamic_group_id]
        ).exists()

    def test_batch_delete_empty_list(self):
        """测试批量删除空列表"""
        result = batch_delete_dynamic_groups([])

        assert result == {}


@pytest.mark.django_db(databases=["default"])
class TestCountDynamicGroups:
    """测试 count_dynamic_groups 函数"""

    def test_count_all(self, db_dynamic_group):
        """测试统计所有分组"""
        count = count_dynamic_groups()

        assert count >= 1

    def test_count_by_object_model_codes(self, db_dynamic_group):
        """测试按对象模型代码统计"""
        count = count_dynamic_groups(object_model_codes=["cw-Host"])

        assert count >= 1

    def test_count_by_space_codes(self, db_dynamic_group):
        """测试按空间代码统计"""
        count = count_dynamic_groups(space_codes=["bkcc__2"])

        assert count >= 1

    def test_count_by_bk_tenant_ids(self, db_dynamic_group):
        """测试按租户 ID 统计"""
        count = count_dynamic_groups(bk_tenant_ids=["system"])

        assert count >= 1

    def test_count_empty_result(self):
        """测试统计空结果"""
        count = count_dynamic_groups(object_model_codes=["nonexistent"])

        assert count == 0


@pytest.mark.django_db(databases=["default"])
class TestExistsDynamicGroup:
    """测试 exists_dynamic_group 函数"""

    def test_exists_returns_true(self, db_dynamic_group):
        """测试分组存在时返回 True"""
        result = exists_dynamic_group(
            dynamic_group_name="测试动态分组",
            space_code="bkcc__2",
            bk_tenant_id="system",
        )

        assert result is True

    def test_exists_returns_false(self):
        """测试分组不存在时返回 False"""
        result = exists_dynamic_group(
            dynamic_group_name="不存在的分组",
            space_code="bkcc__2",
            bk_tenant_id="system",
        )

        assert result is False

    def test_exists_with_exclude_id(self, db_dynamic_group):
        """测试排除指定 ID 后不存在"""
        result = exists_dynamic_group(
            dynamic_group_name="测试动态分组",
            space_code="bkcc__2",
            bk_tenant_id="system",
            exclude_id=db_dynamic_group.dynamic_group_id,
        )

        assert result is False


@pytest.mark.django_db(databases=["default"])
class TestPreviewDynamicGroupMembers:
    """测试 preview_dynamic_group_members 函数"""

    @patch("bk_monitor_base.domains.dynamic_group.operations.dynamic_group.get_member_fetcher")
    @patch("bk_monitor_base.domains.dynamic_group.operations.dynamic_group.list_object_models")
    @patch("bk_monitor_base.domains.dynamic_group.operations.dynamic_group.MemberFormatter")
    def test_preview_by_group_id(
        self,
        mock_formatter,
        mock_list_models,
        mock_get_fetcher,
        db_dynamic_group,
    ):
        """测试通过分组 ID 预览成员"""
        # 模拟对象模型
        mock_model = MagicMock()
        mock_model.display_fields = [{"bk_property_id": "bk_host_innerip"}]
        mock_list_models.return_value = [mock_model]

        # 模拟 fetcher
        mock_fetcher = MagicMock()
        mock_fetcher.fetch.return_value = (
            2,
            [{"bk_inst_id": 1, "bk_os_type": "1"}, {"bk_inst_id": 2, "bk_os_type": "1"}],
        )
        mock_get_fetcher.return_value = mock_fetcher

        # 模拟 formatter
        mock_formatter.format_members.return_value = [
            {"bk_inst_id": 1, "bk_os_type": "Linux"},
            {"bk_inst_id": 2, "bk_os_type": "Linux"},
        ]

        result = preview_dynamic_group_members(
            dynamic_group_id=db_dynamic_group.dynamic_group_id,
            page=1,
            page_size=20,
        )

        assert result["count"] == 2
        assert len(result["items"]) == 2
        assert result["items"][0]["bk_os_type"] == "Linux"
        assert result["page"] == 1
        assert result["page_size"] == 20

    @patch("bk_monitor_base.domains.dynamic_group.operations.dynamic_group.get_member_fetcher")
    @patch("bk_monitor_base.domains.dynamic_group.operations.dynamic_group.list_object_models")
    @patch("bk_monitor_base.domains.dynamic_group.operations.dynamic_group.MemberFormatter")
    def test_preview_by_conditions(
        self,
        mock_formatter,
        mock_list_models,
        mock_get_fetcher,
        db_object_model,
    ):
        """测试通过条件预览成员"""
        # 模拟对象模型
        mock_model = MagicMock()
        mock_model.display_fields = [{"bk_property_id": "bk_host_innerip"}]
        mock_list_models.return_value = [mock_model]

        # 模拟 fetcher
        mock_fetcher = MagicMock()
        mock_fetcher.fetch.return_value = (1, [{"bk_inst_id": 100}])
        mock_get_fetcher.return_value = mock_fetcher

        # 模拟 formatter
        mock_formatter.format_members.return_value = [{"bk_inst_id": 100}]

        result = preview_dynamic_group_members(
            object_model_code="cw-Host",
            condition_list=[{"field": "bk_host_innerip", "value": "10.", "operator": "contains"}],
            space_code="bkcc__2",
            bk_tenant_id="system",
        )

        assert result["count"] == 1
        assert result["object_model_code"] == "cw-Host"

    def test_preview_nonexistent_group_raises(self):
        """测试预览不存在的分组抛出异常"""
        with pytest.raises(DynamicGroupNotFound):
            preview_dynamic_group_members(dynamic_group_id=99999)

    def test_preview_missing_object_model_code_raises(self):
        """测试缺少 object_model_code 抛出异常"""
        with pytest.raises(DynamicGroupValidError):
            preview_dynamic_group_members(
                condition_list=[],
                space_code="bkcc__2",
            )


@pytest.mark.django_db(databases=["default"])
class TestListDynamicGroupMembers:
    """测试 list_dynamic_group_members 函数"""

    @patch("bk_monitor_base.domains.dynamic_group.operations.dynamic_group.get_member_fetcher")
    def test_list_members_success(self, mock_get_fetcher, mock_dynamic_group):
        """测试成功查询成员列表"""
        mock_fetcher = MagicMock()
        mock_fetcher.fetch.return_value = (
            3,
            [
                {"bk_inst_id": 1},
                {"bk_inst_id": 2},
                {"bk_inst_id": 3},
            ],
        )
        mock_get_fetcher.return_value = mock_fetcher

        count, members = list_dynamic_group_members(mock_dynamic_group, page=1, page_size=20)

        assert count == 3
        assert len(members) == 3

    @patch("bk_monitor_base.domains.dynamic_group.operations.dynamic_group.get_member_fetcher")
    def test_list_members_handles_exception(self, mock_get_fetcher, mock_dynamic_group):
        """测试查询成员失败时返回空列表"""
        mock_get_fetcher.side_effect = Exception("CMDB error")

        count, members = list_dynamic_group_members(mock_dynamic_group)

        assert count == 0
        assert members == []


@pytest.mark.django_db(databases=["default"])
class TestGetDynamicGroupMembers:
    """测试 get_dynamic_group_members 函数"""

    def test_get_members_success(self, db_dynamic_group_with_members):
        """测试成功获取成员列表"""
        members = get_dynamic_group_members(db_dynamic_group_with_members.dynamic_group_id)

        assert len(members) == 3
        inst_ids = [m.get("bk_inst_id") for m in members]
        assert set(inst_ids) == {101, 102, 103}

    def test_get_members_nonexistent_group_raises(self):
        """测试获取不存在分组的成员抛出异常"""
        with pytest.raises(DynamicGroupNotFound):
            get_dynamic_group_members(99999, raise_not_found=True)

    def test_get_members_nonexistent_group_returns_empty(self):
        """测试获取不存在分组的成员返回空列表"""
        members = get_dynamic_group_members(99999, raise_not_found=False)

        assert members == []


@pytest.mark.django_db(databases=["default"])
class TestFetchDynamicGroupInstMap:
    """测试 fetch_dynamic_group_inst_map 函数"""

    def test_fetch_inst_map_success(self, db_dynamic_group_with_members):
        """测试成功获取实例映射"""
        result = fetch_dynamic_group_inst_map([db_dynamic_group_with_members.dynamic_group_id])

        assert "cw-Host" in result
        assert set(result["cw-Host"]) == {101, 102, 103}

    def test_fetch_inst_map_all(self, db_dynamic_group_with_members):
        """测试获取所有分组的实例映射"""
        result = fetch_dynamic_group_inst_map()

        assert "cw-Host" in result

    def test_fetch_inst_map_empty_ids(self):
        """测试空 ID 列表返回空结果"""
        result = fetch_dynamic_group_inst_map([])

        assert result == {}

    def test_fetch_inst_map_nonexistent_ids(self):
        """测试不存在的 ID 返回空结果"""
        result = fetch_dynamic_group_inst_map([99999])

        assert result == {}
