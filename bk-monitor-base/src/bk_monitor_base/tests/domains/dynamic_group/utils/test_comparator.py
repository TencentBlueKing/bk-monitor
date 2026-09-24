"""
测试 MemberComparator 成员比对工具

测试成员列表比对、ip_list 变更检测、条件过滤等功能。
"""

from unittest.mock import patch

from bk_monitor_base.domains.dynamic_group.utils.comparator import MemberComparator


class TestMemberComparatorCompare:
    """测试 MemberComparator.compare 方法"""

    @patch("bk_monitor_base.domains.object_model.constants.BuiltinObjectModelCode")
    def test_compare_host_add_members(self, mock_builtin):
        """测试主机类型：新增成员"""
        mock_builtin.HOST = "cw-Host"

        old_members = [{"bk_inst_id": 1}, {"bk_inst_id": 2}]
        new_members = [{"bk_inst_id": 1}, {"bk_inst_id": 2}, {"bk_inst_id": 3}]

        add_list, delete_list, first_related = MemberComparator.compare("cw-Host", new_members, old_members)

        assert add_list == [3]
        assert delete_list == []
        assert first_related is False

    @patch("bk_monitor_base.domains.object_model.constants.BuiltinObjectModelCode")
    def test_compare_host_delete_members(self, mock_builtin):
        """测试主机类型：删除成员"""
        mock_builtin.HOST = "cw-Host"

        old_members = [{"bk_inst_id": 1}, {"bk_inst_id": 2}, {"bk_inst_id": 3}]
        new_members = [{"bk_inst_id": 1}, {"bk_inst_id": 2}]

        add_list, delete_list, first_related = MemberComparator.compare("cw-Host", new_members, old_members)

        assert add_list == []
        assert delete_list == [3]
        assert first_related is False

    @patch("bk_monitor_base.domains.object_model.constants.BuiltinObjectModelCode")
    def test_compare_host_mixed_changes(self, mock_builtin):
        """测试主机类型：混合变更（新增和删除）"""
        mock_builtin.HOST = "cw-Host"

        old_members = [{"bk_inst_id": 1}, {"bk_inst_id": 2}]
        new_members = [{"bk_inst_id": 2}, {"bk_inst_id": 3}]

        add_list, delete_list, first_related = MemberComparator.compare("cw-Host", new_members, old_members)

        assert 3 in add_list
        assert 1 in delete_list
        assert first_related is False

    @patch("bk_monitor_base.domains.object_model.constants.BuiltinObjectModelCode")
    def test_compare_host_no_changes(self, mock_builtin):
        """测试主机类型：无变更"""
        mock_builtin.HOST = "cw-Host"

        old_members = [{"bk_inst_id": 1}, {"bk_inst_id": 2}]
        new_members = [{"bk_inst_id": 1}, {"bk_inst_id": 2}]

        add_list, delete_list, first_related = MemberComparator.compare("cw-Host", new_members, old_members)

        assert add_list == []
        assert delete_list == []
        assert first_related is False

    @patch("bk_monitor_base.domains.object_model.constants.BuiltinObjectModelCode")
    def test_compare_non_host_ip_list_change(self, mock_builtin):
        """测试非主机类型：ip_list 变化"""
        mock_builtin.HOST = "cw-Host"

        old_members = [
            {"bk_inst_id": 1, "ip_list": [{"ip": "10.0.0.1"}]},
        ]
        new_members = [
            {"bk_inst_id": 1, "ip_list": [{"ip": "10.0.0.2"}]},  # ip_list 变化
        ]

        add_list, delete_list, first_related = MemberComparator.compare("cw-Switch", new_members, old_members)

        assert add_list == []
        assert delete_list == []
        assert first_related is True

    @patch("bk_monitor_base.domains.object_model.constants.BuiltinObjectModelCode")
    def test_compare_non_host_first_related(self, mock_builtin):
        """测试非主机类型：首次关联（ip_list 从空变非空）"""
        mock_builtin.HOST = "cw-Host"

        old_members = [
            {"bk_inst_id": 1, "ip_list": []},
            {"bk_inst_id": 2, "ip_list": [{"ip": "10.0.0.2"}]},
        ]
        new_members = [
            {"bk_inst_id": 1, "ip_list": [{"ip": "10.0.0.1"}]},  # 从空变非空
            {"bk_inst_id": 3, "ip_list": []},  # 新增
        ]

        add_list, delete_list, first_related = MemberComparator.compare("cw-Switch", new_members, old_members)

        assert 3 in add_list
        assert 2 in delete_list
        assert first_related is True

    @patch("bk_monitor_base.domains.object_model.constants.BuiltinObjectModelCode")
    def test_compare_empty_lists(self, mock_builtin):
        """测试空列表比较"""
        mock_builtin.HOST = "cw-Host"

        add_list, delete_list, first_related = MemberComparator.compare("cw-Host", [], [])

        assert add_list == []
        assert delete_list == []
        assert first_related is False


class TestMemberComparatorGetUpdatedMembers:
    """测试 MemberComparator.get_updated_members 方法"""

    def test_no_changes(self):
        """测试无变更"""
        old_members = [
            {"bk_inst_id": 1, "ip_list": [{"ip": "10.0.0.1"}]},
        ]
        new_members = [
            {"bk_inst_id": 1, "ip_list": [{"ip": "10.0.0.1"}]},
        ]

        update_members, need_push_kafka = MemberComparator.get_updated_members(old_members, new_members)

        assert update_members == []
        assert need_push_kafka is False

    def test_ip_list_change(self):
        """测试 ip_list 变化"""
        old_members = [
            {"bk_inst_id": 1, "ip_list": [{"ip": "10.0.0.1"}]},
        ]
        new_members = [
            {"bk_inst_id": 1, "ip_list": [{"ip": "10.0.0.2"}]},
        ]

        update_members, need_push_kafka = MemberComparator.get_updated_members(old_members, new_members)

        assert len(update_members) == 1
        assert update_members[0]["bk_inst_id"] == 1
        assert need_push_kafka is True

    def test_only_error_field_change(self):
        """测试仅 error 字段变化（不需要推送 Kafka）"""
        old_members = [
            {"bk_inst_id": 1, "ip_list": [{"ip": "10.0.0.1", "error": "old_error"}]},
        ]
        new_members = [
            {"bk_inst_id": 1, "ip_list": [{"ip": "10.0.0.1", "error": "new_error"}]},
        ]

        update_members, need_push_kafka = MemberComparator.get_updated_members(old_members, new_members)

        assert len(update_members) == 1
        assert need_push_kafka is False  # 仅 error 变化不需要推送

    def test_mixed_changes(self):
        """测试混合变更（error 和 ip 都变化）"""
        old_members = [
            {"bk_inst_id": 1, "ip_list": [{"ip": "10.0.0.1", "error": "old_error"}]},
        ]
        new_members = [
            {"bk_inst_id": 1, "ip_list": [{"ip": "10.0.0.2", "error": "new_error"}]},
        ]

        update_members, need_push_kafka = MemberComparator.get_updated_members(old_members, new_members)

        assert len(update_members) == 1
        assert need_push_kafka is True  # ip 变化需要推送

    def test_new_member_not_in_old(self):
        """测试新成员不在旧列表中"""
        old_members = [{"bk_inst_id": 1, "ip_list": []}]
        new_members = [
            {"bk_inst_id": 1, "ip_list": []},
            {"bk_inst_id": 2, "ip_list": []},
        ]

        update_members, need_push_kafka = MemberComparator.get_updated_members(old_members, new_members)

        # 新成员不在更新列表中（它是新增，不是更新）
        assert update_members == []


class TestMemberComparatorStripError:
    """测试 MemberComparator._strip_error_from_member 方法"""

    def test_strip_error_field(self):
        """测试移除 error 字段"""
        member = {
            "bk_inst_id": 1,
            "ip_list": [
                {"ip": "10.0.0.1", "error": "some_error"},
                {"ip": "10.0.0.2", "error": "another_error"},
            ],
        }

        result = MemberComparator._strip_error_from_member(member)

        for ip_info in result["ip_list"]:
            assert "error" not in ip_info

        # 原始数据不受影响
        assert "error" in member["ip_list"][0]

    def test_strip_error_empty_ip_list(self):
        """测试空 ip_list"""
        member = {"bk_inst_id": 1, "ip_list": []}

        result = MemberComparator._strip_error_from_member(member)

        assert result["ip_list"] == []

    def test_strip_error_no_ip_list(self):
        """测试没有 ip_list 字段"""
        member = {"bk_inst_id": 1}

        result = MemberComparator._strip_error_from_member(member)

        assert "ip_list" not in result or result.get("ip_list") == []


class TestMemberComparatorFilterByCondition:
    """测试 MemberComparator.filter_by_condition 方法"""

    def test_filter_equal(self):
        """测试 equal 操作符"""
        data = [
            {"name": "host1", "status": "running"},
            {"name": "host2", "status": "stopped"},
        ]
        condition = [{"field": "status", "value": "running", "operator": "equal"}]

        result = MemberComparator.filter_by_condition(data, condition)

        assert len(result) == 1
        assert result[0]["name"] == "host1"

    def test_filter_not_equal(self):
        """测试 not_equal 操作符"""
        data = [
            {"name": "host1", "status": "running"},
            {"name": "host2", "status": "stopped"},
        ]
        condition = [{"field": "status", "value": "running", "operator": "not_equal"}]

        result = MemberComparator.filter_by_condition(data, condition)

        assert len(result) == 1
        assert result[0]["name"] == "host2"

    def test_filter_contains(self):
        """测试 contains 操作符"""
        data = [
            {"name": "test-host-1", "ip": "10.0.0.1"},
            {"name": "prod-host-1", "ip": "10.0.0.2"},
        ]
        condition = [{"field": "name", "value": "test", "operator": "contains"}]

        result = MemberComparator.filter_by_condition(data, condition)

        assert len(result) == 1
        assert result[0]["name"] == "test-host-1"

    def test_filter_not_contains(self):
        """测试 not_contains 操作符"""
        data = [
            {"name": "test-host-1", "ip": "10.0.0.1"},
            {"name": "prod-host-1", "ip": "10.0.0.2"},
        ]
        condition = [{"field": "name", "value": "test", "operator": "not_contains"}]

        result = MemberComparator.filter_by_condition(data, condition)

        assert len(result) == 1
        assert result[0]["name"] == "prod-host-1"

    def test_filter_in(self):
        """测试 in 操作符"""
        data = [
            {"name": "host1", "zone": "zone1"},
            {"name": "host2", "zone": "zone2"},
            {"name": "host3", "zone": "zone3"},
        ]
        condition = [{"field": "zone", "value": ["zone1", "zone2"], "operator": "in"}]

        result = MemberComparator.filter_by_condition(data, condition)

        assert len(result) == 2
        assert all(r["zone"] in ["zone1", "zone2"] for r in result)

    def test_filter_not_in(self):
        """测试 not_in 操作符"""
        data = [
            {"name": "host1", "zone": "zone1"},
            {"name": "host2", "zone": "zone2"},
            {"name": "host3", "zone": "zone3"},
        ]
        condition = [{"field": "zone", "value": ["zone1", "zone2"], "operator": "not_in"}]

        result = MemberComparator.filter_by_condition(data, condition)

        assert len(result) == 1
        assert result[0]["zone"] == "zone3"

    def test_filter_multiple_conditions(self):
        """测试多条件过滤"""
        data = [
            {"name": "host1", "status": "running", "zone": "zone1"},
            {"name": "host2", "status": "running", "zone": "zone2"},
            {"name": "host3", "status": "stopped", "zone": "zone1"},
        ]
        condition = [
            {"field": "status", "value": "running", "operator": "equal"},
            {"field": "zone", "value": "zone1", "operator": "equal"},
        ]

        result = MemberComparator.filter_by_condition(data, condition)

        assert len(result) == 1
        assert result[0]["name"] == "host1"

    def test_filter_empty_condition(self):
        """测试空条件（返回全部数据）"""
        data = [{"name": "host1"}, {"name": "host2"}]

        result = MemberComparator.filter_by_condition(data, [])

        assert len(result) == 2

    def test_filter_default_operator(self):
        """测试默认操作符（equal）"""
        data = [
            {"name": "host1", "status": "running"},
            {"name": "host2", "status": "stopped"},
        ]
        condition = [{"field": "status", "value": "running"}]  # 没有指定 operator

        result = MemberComparator.filter_by_condition(data, condition)

        assert len(result) == 1
        assert result[0]["name"] == "host1"
