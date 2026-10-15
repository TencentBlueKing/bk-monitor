"""
测试 dynamic_group 常量定义模块

测试 DynamicGroupOperator, CMDBOperator, OPERATOR_MAPPING, 缓存 key 函数等。
"""

from unittest.mock import MagicMock, patch

from bk_monitor_base.domains.dynamic_group.constants import (
    DYNAMIC_GROUP_CACHE_TTL,
    OPERATOR_MAPPING,
    SEARCH_INST_OPERATOR_MAP,
    SEARCH_INST_OPERATOR_REVERSE_MAP,
    USAGE_RECORD_APP_ID,
    USAGE_RECORD_APP_NAME,
    USAGE_RECORD_MODULE_ID,
    USAGE_RECORD_MODULE_NAME,
    BuiltinObjectModelCode,
    CMDBOperator,
    DynamicGroupConstants,
    DynamicGroupOperator,
    get_dynamic_group_cache_key,
    get_dynamic_inst_group_cache_key,
)


class TestDynamicGroupOperator:
    """测试动态分组查询操作符"""

    def test_basic_operators_exist(self):
        """测试基本操作符存在"""
        assert DynamicGroupOperator.EQUAL == "equal"
        assert DynamicGroupOperator.NOT_EQUAL == "not_equal"
        assert DynamicGroupOperator.CONTAINS == "contains"
        assert DynamicGroupOperator.NOT_CONTAINS == "not_contains"
        assert DynamicGroupOperator.IN == "in"
        assert DynamicGroupOperator.NOT_IN == "not_in"

    def test_comparison_operators_exist(self):
        """测试比较操作符存在"""
        assert DynamicGroupOperator.LESS == "less"
        assert DynamicGroupOperator.LESS_OR_EQUAL == "less_or_equal"
        assert DynamicGroupOperator.GREATER == "greater"
        assert DynamicGroupOperator.GREATER_OR_EQUAL == "greater_or_equal"


class TestCMDBOperator:
    """测试 CMDB API 查询操作符"""

    def test_cmdb_operators_exist(self):
        """测试 CMDB 操作符存在"""
        assert CMDBOperator.EQ == "$eq"
        assert CMDBOperator.NE == "$ne"
        assert CMDBOperator.REGEX == "$regex"
        assert CMDBOperator.IN == "$in"
        assert CMDBOperator.NIN == "$nin"
        assert CMDBOperator.LT == "$lt"
        assert CMDBOperator.LTE == "$lte"
        assert CMDBOperator.GT == "$gt"
        assert CMDBOperator.GTE == "$gte"


class TestBuiltinObjectModelCode:
    """测试内置对象模型编码"""

    def test_builtin_object_model_codes(self):
        """测试内置对象模型编码存在"""
        assert BuiltinObjectModelCode.HOST == "cw-Host"
        assert BuiltinObjectModelCode.BIZ == "cw-Biz"
        assert BuiltinObjectModelCode.MODULE == "cw-Module"
        assert BuiltinObjectModelCode.SET == "cw-Set"


class TestOperatorMapping:
    """测试动态分组操作符到 CMDB 操作符的映射"""

    def test_basic_operator_mappings(self):
        """测试基本操作符映射"""
        assert OPERATOR_MAPPING[DynamicGroupOperator.EQUAL] == CMDBOperator.EQ
        assert OPERATOR_MAPPING[DynamicGroupOperator.NOT_EQUAL] == CMDBOperator.NE
        assert OPERATOR_MAPPING[DynamicGroupOperator.CONTAINS] == CMDBOperator.REGEX
        assert OPERATOR_MAPPING[DynamicGroupOperator.NOT_CONTAINS] == CMDBOperator.REGEX
        assert OPERATOR_MAPPING[DynamicGroupOperator.IN] == CMDBOperator.IN
        assert OPERATOR_MAPPING[DynamicGroupOperator.NOT_IN] == CMDBOperator.NIN

    def test_comparison_operator_mappings(self):
        """测试比较操作符映射"""
        assert OPERATOR_MAPPING[DynamicGroupOperator.LESS] == CMDBOperator.LT
        assert OPERATOR_MAPPING[DynamicGroupOperator.LESS_OR_EQUAL] == CMDBOperator.LTE
        assert OPERATOR_MAPPING[DynamicGroupOperator.GREATER] == CMDBOperator.GT
        assert OPERATOR_MAPPING[DynamicGroupOperator.GREATER_OR_EQUAL] == CMDBOperator.GTE

    def test_all_operators_mapped(self):
        """测试所有动态分组操作符都有对应的 CMDB 操作符"""
        all_dg_operators = [
            DynamicGroupOperator.EQUAL,
            DynamicGroupOperator.NOT_EQUAL,
            DynamicGroupOperator.CONTAINS,
            DynamicGroupOperator.NOT_CONTAINS,
            DynamicGroupOperator.IN,
            DynamicGroupOperator.NOT_IN,
            DynamicGroupOperator.LESS,
            DynamicGroupOperator.LESS_OR_EQUAL,
            DynamicGroupOperator.GREATER,
            DynamicGroupOperator.GREATER_OR_EQUAL,
        ]

        for op in all_dg_operators:
            assert op in OPERATOR_MAPPING, f"Operator {op} is not mapped"


class TestSearchInstOperatorMaps:
    """测试搜索实例操作符映射"""

    def test_search_inst_operator_map(self):
        """测试搜索实例操作符映射"""
        assert SEARCH_INST_OPERATOR_MAP["equal"] == "$eq"
        assert SEARCH_INST_OPERATOR_MAP["not_equal"] == "$ne"
        assert SEARCH_INST_OPERATOR_MAP["contains"] == "$regex"
        assert SEARCH_INST_OPERATOR_MAP["in"] == "$in"
        assert SEARCH_INST_OPERATOR_MAP["not_in"] == "$nin"

    def test_search_inst_operator_reverse_map(self):
        """测试搜索实例操作符反向映射"""
        assert SEARCH_INST_OPERATOR_REVERSE_MAP["$eq"] == "equal"
        assert SEARCH_INST_OPERATOR_REVERSE_MAP["$ne"] == "not_equal"
        assert SEARCH_INST_OPERATOR_REVERSE_MAP["$regex"] == "contains"
        assert SEARCH_INST_OPERATOR_REVERSE_MAP["$in"] == "in"
        assert SEARCH_INST_OPERATOR_REVERSE_MAP["$nin"] == "not_in"

    def test_maps_are_consistent(self):
        """测试正向和反向映射一致性"""
        for key, value in SEARCH_INST_OPERATOR_MAP.items():
            assert SEARCH_INST_OPERATOR_REVERSE_MAP[value] == key


class TestDynamicGroupConstants:
    """测试动态分组常量"""

    def test_topic_constant(self):
        """测试 topic 常量"""
        assert DynamicGroupConstants.DYNAMIC_GROUP_TOPIC == "bk_monitor_dynamic_group"

    def test_change_constant(self):
        """测试变更记录常量"""
        assert DynamicGroupConstants.META_DYNAMIC_GROUP_CHANGE == "meta_dynamic_group_change"


class TestUsageRecordConstants:
    """测试使用记录常量"""

    def test_usage_record_constants(self):
        """测试使用记录常量值"""
        assert USAGE_RECORD_APP_ID == "meta_saas"
        assert USAGE_RECORD_APP_NAME == "鲸眼元数据中心"
        assert USAGE_RECORD_MODULE_ID == "meta_dynamic_group"
        assert USAGE_RECORD_MODULE_NAME == "动态分组"


class TestCacheConstants:
    """测试缓存相关常量"""

    def test_cache_ttl(self):
        """测试缓存过期时间"""
        # 7天 = 7 * 24 * 60 * 60 秒
        expected_ttl = 7 * 24 * 60 * 60
        assert DYNAMIC_GROUP_CACHE_TTL == expected_ttl


class TestCacheKeyFunctions:
    """测试缓存 key 生成函数"""

    @patch("bk_monitor_base.domains.dynamic_group.constants.get_config")
    def test_get_dynamic_group_cache_key(self, mock_get_config):
        """测试获取动态分组缓存键"""
        mock_config = MagicMock()
        mock_config.common.redis_key_prefix = "bk_monitor:"
        mock_get_config.return_value = mock_config

        cache_key = get_dynamic_group_cache_key(123)

        assert cache_key == "bk_monitor:dynamic_group:123"

    @patch("bk_monitor_base.domains.dynamic_group.constants.get_config")
    def test_get_dynamic_group_cache_key_with_different_ids(self, mock_get_config):
        """测试不同 ID 生成不同的缓存键"""
        mock_config = MagicMock()
        mock_config.common.redis_key_prefix = "test:"
        mock_get_config.return_value = mock_config

        key1 = get_dynamic_group_cache_key(1)
        key2 = get_dynamic_group_cache_key(2)

        assert key1 != key2
        assert "1" in key1
        assert "2" in key2

    @patch("bk_monitor_base.domains.dynamic_group.constants.get_config")
    def test_get_dynamic_inst_group_cache_key(self, mock_get_config):
        """测试获取实例分组关系缓存键"""
        mock_config = MagicMock()
        mock_config.common.redis_key_prefix = "bk_monitor:"
        mock_get_config.return_value = mock_config

        cache_key = get_dynamic_inst_group_cache_key("cw-Host")

        assert cache_key == "bk_monitor:dynamic_inst_group:cw-Host"

    @patch("bk_monitor_base.domains.dynamic_group.constants.get_config")
    def test_get_dynamic_inst_group_cache_key_with_different_models(self, mock_get_config):
        """测试不同对象模型生成不同的缓存键"""
        mock_config = MagicMock()
        mock_config.common.redis_key_prefix = "test:"
        mock_get_config.return_value = mock_config

        key_host = get_dynamic_inst_group_cache_key("cw-Host")
        key_biz = get_dynamic_inst_group_cache_key("cw-Biz")

        assert key_host != key_biz
        assert "cw-Host" in key_host
        assert "cw-Biz" in key_biz

    @patch("bk_monitor_base.domains.dynamic_group.constants.get_config")
    def test_cache_key_respects_prefix(self, mock_get_config):
        """测试缓存键遵循配置的前缀"""
        mock_config = MagicMock()
        mock_config.common.redis_key_prefix = "custom_prefix:"
        mock_get_config.return_value = mock_config

        group_key = get_dynamic_group_cache_key(1)
        inst_key = get_dynamic_inst_group_cache_key("cw-Host")

        assert group_key.startswith("custom_prefix:")
        assert inst_key.startswith("custom_prefix:")
