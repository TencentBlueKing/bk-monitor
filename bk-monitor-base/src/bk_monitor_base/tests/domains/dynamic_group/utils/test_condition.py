"""
测试 ConditionConverter 条件转换工具

测试操作符映射、字段类型转换、条件结构构建等功能。
"""

from unittest.mock import patch

from bk_monitor_base.domains.dynamic_group.utils.condition import ConditionConverter


class TestBuildCmdbCondition:
    """测试 build_cmdb_condition 方法"""

    def test_build_from_list(self):
        """测试从列表构建条件"""
        condition_list = [{"field": "bk_host_innerip", "value": "10.", "operator": "contains"}]

        result = ConditionConverter.build_cmdb_condition(condition_list)

        assert result["condition"] == "AND"
        assert result["rules"] == condition_list

    def test_build_from_empty_list(self):
        """测试从空列表构建条件"""
        result = ConditionConverter.build_cmdb_condition([])

        assert result["condition"] == "AND"
        assert result["rules"] == []

    def test_build_from_dict_with_rules(self):
        """测试已经是完整结构时直接返回"""
        condition = {"condition": "OR", "rules": [{"field": "status", "value": "running", "operator": "equal"}]}

        result = ConditionConverter.build_cmdb_condition(condition)  # type: ignore

        assert result == condition

    def test_build_from_none(self):
        """测试从 None 构建条件"""
        result = ConditionConverter.build_cmdb_condition(None)  # type: ignore

        assert result["condition"] == "AND"
        assert result["rules"] == []


class TestConvertOperators:
    """测试 convert_operators 方法"""

    def test_convert_operators(self):
        """测试操作符转换"""
        condition = {
            "condition": "AND",
            "rules": [
                {"field": "status", "value": "running", "operator": "equal"},
                {"field": "name", "value": "test", "operator": "contains"},
            ],
        }

        result = ConditionConverter.convert_operators(condition)

        assert result["rules"][0]["operator"] == "equal"
        assert result["rules"][1]["operator"] == "contains"

    def test_convert_operators_empty_rules(self):
        """测试空规则"""
        condition = {"condition": "AND", "rules": []}

        result = ConditionConverter.convert_operators(condition)

        assert result["rules"] == []

    def test_convert_operators_preserves_condition(self):
        """测试保留原有条件类型"""
        condition = {"condition": "OR", "rules": [{"field": "status", "value": "running", "operator": "equal"}]}

        result = ConditionConverter.convert_operators(condition)

        assert result["condition"] == "OR"


class TestConvertFieldTypes:
    """测试 convert_field_types 方法"""

    @patch.object(ConditionConverter, "_get_field_type_map")
    def test_convert_int_field(self, mock_get_field_type_map):
        """测试整数字段转换"""
        mock_get_field_type_map.return_value = {"bk_cloud_id": "int"}

        condition = {"condition": "AND", "rules": [{"field": "bk_cloud_id", "value": "0", "operator": "equal"}]}

        result = ConditionConverter.convert_field_types("system", "cw-Host", condition)

        assert result["rules"][0]["value"] == 0

    @patch.object(ConditionConverter, "_get_field_type_map")
    def test_convert_float_field(self, mock_get_field_type_map):
        """测试浮点数字段转换"""
        mock_get_field_type_map.return_value = {"cpu_usage": "float"}

        condition = {"condition": "AND", "rules": [{"field": "cpu_usage", "value": "50.5", "operator": "greater"}]}

        result = ConditionConverter.convert_field_types("system", "cw-Host", condition)

        assert result["rules"][0]["value"] == 50.5

    @patch.object(ConditionConverter, "_get_field_type_map")
    def test_convert_bool_field(self, mock_get_field_type_map):
        """测试布尔字段转换"""
        mock_get_field_type_map.return_value = {"is_active": "bool"}

        condition = {"condition": "AND", "rules": [{"field": "is_active", "value": "true", "operator": "equal"}]}

        result = ConditionConverter.convert_field_types("system", "cw-Host", condition)

        assert result["rules"][0]["value"] is True

    @patch.object(ConditionConverter, "_get_field_type_map")
    def test_convert_list_field(self, mock_get_field_type_map):
        """测试列表字段转换"""
        mock_get_field_type_map.return_value = {"tags": "list"}

        condition = {"condition": "AND", "rules": [{"field": "tags", "value": "tag1, tag2, tag3", "operator": "in"}]}

        result = ConditionConverter.convert_field_types("system", "cw-Host", condition)

        assert result["rules"][0]["value"] == ["tag1", "tag2", "tag3"]

    @patch.object(ConditionConverter, "_get_field_type_map")
    def test_convert_preserves_already_correct_types(self, mock_get_field_type_map):
        """测试已经是正确类型时保持不变"""
        mock_get_field_type_map.return_value = {"bk_cloud_id": "int"}

        condition = {
            "condition": "AND",
            "rules": [{"field": "bk_cloud_id", "value": 0, "operator": "equal"}],  # 已经是 int
        }

        result = ConditionConverter.convert_field_types("system", "cw-Host", condition)

        assert result["rules"][0]["value"] == 0

    @patch.object(ConditionConverter, "_get_field_type_map")
    def test_convert_handles_empty_field_type_map(self, mock_get_field_type_map):
        """测试空字段类型映射"""
        mock_get_field_type_map.return_value = {}

        condition = {"condition": "AND", "rules": [{"field": "unknown", "value": "value", "operator": "equal"}]}

        result = ConditionConverter.convert_field_types("system", "cw-Host", condition)

        assert result["rules"][0]["value"] == "value"  # 保持不变


class TestConvertValueByType:
    """测试 _convert_value_by_type 方法"""

    def test_convert_string_to_int(self):
        """测试字符串转整数"""
        result = ConditionConverter._convert_value_by_type("123", "int")
        assert result == 123

    def test_convert_string_to_long(self):
        """测试字符串转长整数"""
        result = ConditionConverter._convert_value_by_type("123456789", "long")
        assert result == 123456789

    def test_convert_string_to_float(self):
        """测试字符串转浮点数"""
        result = ConditionConverter._convert_value_by_type("3.14", "float")
        assert result == 3.14

    def test_convert_string_to_bool_true(self):
        """测试字符串转布尔值（true）"""
        assert ConditionConverter._convert_value_by_type("true", "bool") is True
        assert ConditionConverter._convert_value_by_type("1", "bool") is True
        assert ConditionConverter._convert_value_by_type("yes", "bool") is True
        assert ConditionConverter._convert_value_by_type("on", "bool") is True

    def test_convert_string_to_bool_false(self):
        """测试字符串转布尔值（false）"""
        assert ConditionConverter._convert_value_by_type("false", "bool") is False
        assert ConditionConverter._convert_value_by_type("0", "bool") is False
        assert ConditionConverter._convert_value_by_type("no", "bool") is False

    def test_convert_int_to_bool(self):
        """测试整数转布尔值"""
        assert ConditionConverter._convert_value_by_type(1, "bool") is True
        assert ConditionConverter._convert_value_by_type(0, "bool") is False

    def test_convert_string_to_list(self):
        """测试字符串转列表"""
        result = ConditionConverter._convert_value_by_type("a, b, c", "list")
        assert result == ["a", "b", "c"]

    def test_convert_list_of_strings_to_int(self):
        """测试字符串列表转整数列表"""
        result = ConditionConverter._convert_value_by_type(["1", "2", "3"], "int")
        assert result == [1, 2, 3]

    def test_convert_unknown_type_returns_original(self):
        """测试未知类型返回原值"""
        result = ConditionConverter._convert_value_by_type("value", "unknown_type")
        assert result == "value"


class TestBuildSearchInstCondition:
    """测试 build_search_inst_condition 方法"""

    def test_build_search_inst_condition(self):
        """测试构建 search_inst 条件"""
        condition_list = [
            {"field": "bk_inst_name", "value": "test", "operator": "equal"},
            {"field": "ip", "value": "10.", "operator": "contains"},
        ]

        result = ConditionConverter.build_search_inst_condition("bk_switch", condition_list)

        assert "bk_switch" in result
        assert len(result["bk_switch"]) == 2
        assert result["bk_switch"][0]["operator"] == "$eq"
        assert result["bk_switch"][1]["operator"] == "$regex"

    def test_build_search_inst_condition_empty(self):
        """测试空条件"""
        result = ConditionConverter.build_search_inst_condition("bk_switch", [])

        assert result == {"bk_switch": []}

    def test_build_search_inst_condition_all_operators(self):
        """测试所有操作符映射"""
        condition_list = [
            {"field": "f1", "value": "v1", "operator": "equal"},
            {"field": "f2", "value": "v2", "operator": "not_equal"},
            {"field": "f3", "value": "v3", "operator": "contains"},
            {"field": "f4", "value": ["v4"], "operator": "in"},
            {"field": "f5", "value": ["v5"], "operator": "not_in"},
            {"field": "f6", "value": 10, "operator": "less"},
            {"field": "f7", "value": 20, "operator": "less_or_equal"},
            {"field": "f8", "value": 30, "operator": "greater"},
            {"field": "f9", "value": 40, "operator": "greater_or_equal"},
        ]

        result = ConditionConverter.build_search_inst_condition("obj", condition_list)

        operators = [r["operator"] for r in result["obj"]]
        assert operators == ["$eq", "$ne", "$regex", "$in", "$nin", "$lt", "$lte", "$gt", "$gte"]


class TestBuildForDynamicGroup:
    """测试 build_for_dynamic_group 方法"""

    @patch.object(ConditionConverter, "convert_field_types")
    def test_build_for_dynamic_group_basic(self, mock_convert_field_types):
        """测试基本条件构建"""
        mock_convert_field_types.return_value = {
            "condition": "AND",
            "rules": [{"field": "status", "value": "running", "operator": "equal"}],
        }

        condition_list = [{"field": "status", "value": "running", "operator": "equal"}]

        result = ConditionConverter.build_for_dynamic_group(
            condition_list,
            object_model_code="cw-Host",
            bk_tenant_id="system",
        )

        assert result["condition"] == "AND"
        mock_convert_field_types.assert_called_once()

    def test_build_for_dynamic_group_empty(self):
        """测试空条件"""
        result = ConditionConverter.build_for_dynamic_group([])

        assert result == {"condition": "AND", "rules": []}

    @patch.object(ConditionConverter, "convert_field_types")
    def test_build_for_dynamic_group_without_object_model(self, mock_convert_field_types):
        """测试不提供对象模型时跳过字段类型转换"""
        condition_list = [{"field": "status", "value": "running", "operator": "equal"}]

        result = ConditionConverter.build_for_dynamic_group(condition_list)

        mock_convert_field_types.assert_not_called()
        assert result["condition"] == "AND"


class TestBuildCmdbInstanceDsl:
    """测试 build_cmdb_instance_dsl 方法"""

    @patch("bk_monitor_base.domains.cmdb_instance.models.CMDBInstance.get_query_field")
    @patch.object(ConditionConverter, "build_for_dynamic_group")
    def test_build_cmdb_instance_dsl_basic(self, mock_build_for_group, mock_get_query_field):
        mock_build_for_group.return_value = {
            "condition": "AND",
            "rules": [{"field": "bk_os_type", "value": "1", "operator": "equal"}],
        }
        mock_get_query_field.side_effect = lambda field: field

        result = ConditionConverter.build_cmdb_instance_dsl(
            bk_tenant_id="system",
            bk_obj_id="host",
            condition_list=[{"field": "bk_os_type", "value": "1", "operator": "equal"}],
            bk_biz_id=2,
        )

        must_clauses = result["bool"]["must"]
        assert {"term": {"bk_tenant_id": "system"}} in must_clauses
        assert {"term": {"bk_obj_id": "host"}} in must_clauses
        assert {"term": {"bk_biz_id": "2"}} in must_clauses
        assert {"term": {"bk_os_type": "1"}} in must_clauses

    @patch("bk_monitor_base.domains.cmdb_instance.models.CMDBInstance.get_query_field")
    @patch.object(ConditionConverter, "build_for_dynamic_group")
    def test_build_cmdb_instance_dsl_contains_and_not_equal(self, mock_build_for_group, mock_get_query_field):
        mock_build_for_group.return_value = {
            "condition": "AND",
            "rules": [
                {"field": "bk_host_innerip", "value": "10.", "operator": "contains"},
                {"field": "status", "value": "offline", "operator": "not_equal"},
            ],
        }
        mock_get_query_field.side_effect = lambda field: field

        result = ConditionConverter.build_cmdb_instance_dsl(
            bk_tenant_id="system",
            bk_obj_id="host",
            condition_list=[],
        )

        must_clauses = result["bool"]["must"]
        must_not_clauses = result["bool"]["must_not"]
        assert {"wildcard": {"bk_host_innerip": "*10.*"}} in must_clauses
        assert {"term": {"status": "offline"}} in must_not_clauses


class TestClearFieldTypeCache:
    """测试 clear_field_type_cache 方法"""

    def test_clear_cache(self):
        """测试清空缓存"""
        # 先添加一些缓存
        ConditionConverter._FIELD_TYPE_CACHE["test:model"] = {"field": "type"}

        ConditionConverter.clear_field_type_cache()

        assert ConditionConverter._FIELD_TYPE_CACHE == {}


class TestGetFieldTypeMap:
    """测试 _get_field_type_map 方法"""

    def teardown_method(self):
        """每个测试后清空缓存"""
        ConditionConverter.clear_field_type_cache()

    def test_get_field_type_map_success(self):
        """测试成功获取字段类型映射"""
        # 先清空缓存确保不使用缓存
        ConditionConverter.clear_field_type_cache()

        # 使用 patch.object 直接 mock cmdb 模块中的函数
        from bk_monitor_base.infras.third_party_api import cmdb

        with patch.object(
            cmdb,
            "search_object_attribute",
            return_value=[
                {"bk_property_id": "bk_cloud_id", "bk_property_type": "int"},
                {"bk_property_id": "bk_host_name", "bk_property_type": "singlechar"},
            ],
        ):
            result = ConditionConverter._get_field_type_map("system", "host")

            assert result["bk_cloud_id"] == "int"
            assert result["bk_host_name"] == "singlechar"

    def test_get_field_type_map_from_cache(self):
        """测试从缓存获取"""
        ConditionConverter._FIELD_TYPE_CACHE["system:host"] = {"field": "cached_type"}

        result = ConditionConverter._get_field_type_map("system", "host")

        assert result["field"] == "cached_type"

    def test_get_field_type_map_api_error(self):
        """测试 API 调用失败时返回空字典"""
        # 先清空缓存确保不使用缓存
        ConditionConverter.clear_field_type_cache()

        from bk_monitor_base.infras.third_party_api import cmdb

        with patch.object(cmdb, "search_object_attribute", side_effect=Exception("API error")):
            result = ConditionConverter._get_field_type_map("system", "host")

            assert result == {}
