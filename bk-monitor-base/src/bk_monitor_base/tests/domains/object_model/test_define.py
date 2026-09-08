"""
测试 object_model.define 模块
"""

import pytest
from pydantic import ValidationError

from bk_monitor_base.domains.object_model.define import (
    AttributeConfig,
    AttributeConfigItem,
    AttributeConfigItemOption,
    DatasourceType,
    ObjectModel,
    ObjectModelGroup,
    ObjectModelRelateType,
    ObjectModelUsageRecord,
)
from bk_monitor_base.tests.domains.object_model import ATTRIBUTE_CONFIG_ENTITY


class TestDatasourceType:
    """测试 DatasourceType 枚举"""

    def test_enum_values(self):
        """测试枚举值"""
        assert DatasourceType.CMDB == "cmdb"
        assert DatasourceType.CUSTOM == "custom"
        assert DatasourceType.LEGACY == "legacy"

    def test_enum_membership(self):
        """测试枚举成员"""
        # 检查枚举值
        assert DatasourceType.CMDB.value == "cmdb"
        assert DatasourceType.CUSTOM.value == "custom"
        assert DatasourceType.LEGACY.value == "legacy"

        # 检查枚举成员
        assert DatasourceType.CMDB in DatasourceType
        assert DatasourceType.CUSTOM in DatasourceType
        assert DatasourceType.LEGACY in DatasourceType


class TestObjectModelRelateType:
    """测试 ObjectModelRelateType 枚举"""

    def test_enum_values(self):
        """测试枚举值"""
        assert ObjectModelRelateType.LEGACY == "LEGACY"
        assert ObjectModelRelateType.APM == "APM"
        assert ObjectModelRelateType.EMPTY == ""

    def test_enum_membership(self):
        """测试枚举成员"""
        # 检查枚举值
        assert ObjectModelRelateType.LEGACY.value == "LEGACY"
        assert ObjectModelRelateType.APM.value == "APM"
        assert ObjectModelRelateType.EMPTY.value == ""

        # 检查枚举成员
        assert ObjectModelRelateType.LEGACY in ObjectModelRelateType
        assert ObjectModelRelateType.APM in ObjectModelRelateType
        assert ObjectModelRelateType.EMPTY in ObjectModelRelateType


class TestObjectModel:
    """测试 ObjectModel 模型"""

    def test_valid_model(self):
        """测试有效的对象模型"""
        model = ObjectModel(
            object_model_id=1,
            object_model_code="test_model",
            object_model_name="测试模型",
            object_model_group_id=1,
            datasource=DatasourceType.CMDB,
            is_default=False,
            bk_cmdb_obj_id="test_cmdb_obj",
            display_fields=[{"field": "name"}],
            inst_display_name="test_display",
            attribute_config=ATTRIBUTE_CONFIG_ENTITY,
        )
        assert model.object_model_id == 1
        assert model.object_model_code == "test_model"
        assert model.object_model_name == "测试模型"
        assert model.object_model_group_id == 1
        assert model.datasource == DatasourceType.CMDB
        assert model.is_default is False
        assert model.bk_cmdb_obj_id == "test_cmdb_obj"
        assert model.display_fields == [{"field": "name"}]
        assert model.inst_display_name == "test_display"
        assert model.attribute_config == ATTRIBUTE_CONFIG_ENTITY

    @pytest.mark.parametrize(
        "is_default, code, should_raise",
        [
            (False, "abc_123", False),
            (False, "abc-123", True),
            (False, "1abc", True),
            (True, "abc-123", False),
            (True, "abc_123", False),
            (True, "1abc-123", True),
            (True, "abc$123", True),
        ],
    )
    def test_code_regex(self, is_default, code, should_raise):
        params = dict(
            object_model_id=1,
            object_model_code=code,
            object_model_name="测试模型",
            object_model_group_id=1,
            datasource=DatasourceType.CMDB,
            is_default=is_default,
            bk_cmdb_obj_id="test_cmdb_obj",
            display_fields=[{"field": "name"}],
            inst_display_name="test_display",
        )
        if should_raise:
            with pytest.raises(Exception):
                ObjectModel(**params)
        else:
            ObjectModel(**params)

    @pytest.mark.parametrize(
        "field,value,should_raise",
        [
            ("host_related_field", "a" * 256, True),
            ("topo_related_field", "a" * 256, True),
            ("port_field", "a" * 256, True),
            ("inst_display_name", "a" * 256, True),
            ("related_model_code", "a" * 256, True),
            ("host_related_field", "a" * 255, False),
            ("topo_related_field", "a" * 255, False),
            ("port_field", "a" * 255, False),
            ("inst_display_name", "a" * 255, False),
            ("related_model_code", "a" * 255, False),
        ],
    )
    def test_field_length(self, field, value, should_raise):
        params = dict(
            object_model_id=1,
            object_model_code="test_model",
            object_model_name="测试模型",
            object_model_group_id=1,
            datasource=DatasourceType.CMDB,
            is_default=False,
            bk_cmdb_obj_id="test_cmdb_obj",
            display_fields=[{"field": "name"}],
            inst_display_name="test_display",
        )
        params[field] = value
        if should_raise:
            with pytest.raises(Exception):
                ObjectModel(**params)
        else:
            ObjectModel(**params)

    def test_default_values(self):
        model = ObjectModel(
            object_model_id=1,
            object_model_code="test_model",
            object_model_name="测试模型",
            object_model_group_id=1,
            datasource=DatasourceType.CMDB,
            is_default=False,
            bk_cmdb_obj_id="test_cmdb_obj",
            display_fields=[{"field": "name"}],
            inst_display_name="test_display",
        )
        assert model.host_related_field == ""
        assert model.operator_fields == []
        assert model.topo_related_field == ""
        assert model.port_field == ""
        assert model.related_model_type == ObjectModelRelateType.EMPTY
        assert model.related_model_code == ObjectModelRelateType.EMPTY
        assert model.can_update is False
        assert model.can_delete is False
        assert model.plugin_manage is False
        assert model.attribute_config == AttributeConfig()


class TestObjectModelGroup:
    """测试 ObjectModelGroup 模型"""

    def test_valid_group(self):
        """测试有效的对象模型分组"""
        group = ObjectModelGroup(
            object_model_group_id=1,
            object_model_group_code="test_group",
            object_model_group_name="测试分组",
            is_default=False,
        )
        assert group.object_model_group_id == 1
        assert group.object_model_group_code == "test_group"
        assert group.object_model_group_name == "测试分组"
        assert group.is_default is False

    def test_default_values(self):
        group = ObjectModelGroup(
            object_model_group_id=1,
            object_model_group_code="test_group",
            object_model_group_name="测试分组",
        )
        assert group.is_default is False
        assert group.related_obj is False
        assert group.can_delete is False
        assert group.can_update is False
        assert group.can_create is False

    @pytest.mark.parametrize(
        "object_model_group_code,object_model_group_name,expected_exception",
        [
            ("", "测试分组", ValidationError),  # 代码为空
            ("a" * 129, "测试分组", ValidationError),  # 代码超长
            ("test_group", "a" * 256, ValidationError),  # 名称超长
        ],
    )
    def test_invalid_code_and_name(self, object_model_group_code, object_model_group_name, expected_exception):
        """参数化测试对象模型分组代码和名称校验"""
        with pytest.raises(expected_exception):
            ObjectModelGroup(
                object_model_group_id=1,
                object_model_group_code=object_model_group_code,
                object_model_group_name=object_model_group_name,
                is_default=False,
            )

    @pytest.mark.parametrize(
        "is_default, code, should_raise",
        [
            (False, "abc_123", False),
            (False, "abc-123", True),  # 非内置不能有'-'
            (False, "1abc", True),  # 必须字母开头
            (True, "abc-123", False),  # 内置可有'-'
            (True, "abc_123", False),
            (True, "1abc-123", True),  # 必须字母开头
            (True, "abc$123", True),  # 非法字符
        ],
    )
    def test_code_regex(self, is_default, code, should_raise):
        """测试对象模型分组code正则校验"""
        params = dict(
            object_model_group_id=1,
            object_model_group_code=code,
            object_model_group_name="测试分组",
            is_default=is_default,
        )
        if should_raise:
            with pytest.raises(Exception):
                ObjectModelGroup(**params)
        else:
            ObjectModelGroup(**params)


class TestObjectModelUsageRecord:
    """测试 ObjectModelUsageRecord 模型"""

    def test_valid_record(self):
        """测试有效的对象模型使用记录"""
        record = ObjectModelUsageRecord(
            object_model_id=1,
            app_id="test_model",
            app_name="kmc_saas",
            module_id="10",
            module_name="监控策略",
            inst_id="123",
            inst_name="ping不可达检测",
        )
        assert record.object_model_id == 1
        assert record.app_id == "test_model"
        assert record.app_name == "kmc_saas"
        assert record.module_id == "10"
        assert record.module_name == "监控策略"
        assert record.inst_id == "123"
        assert record.inst_name == "ping不可达检测"

    @pytest.mark.parametrize(
        "field, value, expected_exception",
        [
            ("app_id", "", ValidationError),
            ("app_id", "a" * 65, ValidationError),  # 超过64字符
            ("app_name", "a" * 65, ValidationError),  # 超过64字符
            ("module_id", "", ValidationError),
            ("module_id", "a" * 256, ValidationError),  # 超过255字符
            ("module_name", "a" * 256, ValidationError),  # 超过255字符
            ("inst_id", "", ValidationError),
            ("inst_id", "a" * 256, ValidationError),  # 超过255字符
            ("inst_name", "a" * 256, ValidationError),  # 超过255字符
        ],
    )
    def test_invalid_fields(self, field, value, expected_exception):
        """参数化测试ObjectModelUsageRecord字段校验"""
        valid_data = dict(
            object_model_id=1,
            app_id="test_model",
            app_name="kmc_saas",
            module_id="10",
            module_name="监控策略",
            inst_id="123",
            inst_name="ping不可达检测",
        )
        valid_data[field] = value
        with pytest.raises(expected_exception):
            ObjectModelUsageRecord(**valid_data)


class TestAttributeConfig:
    """测试 AttributeConfig 模型"""

    def test_attribute_config_model_dump(self):
        """测试模型序列化"""
        config = ATTRIBUTE_CONFIG_ENTITY
        config_dict = config.model_dump()
        assert isinstance(config_dict, dict)
        assert config_dict["config"][0]["bk_property_id"] == "test_property"
        assert config_dict["sync_time"] == "2024-01-01 00:00:00"

    def test_init_from_dict(self):
        """测试从字典初始化"""
        params = {
            "config": [
                {
                    "bk_property_id": "test_prop",
                    "bk_property_name": "测试属性",
                }
            ],
            "sync_time": "2024-01-01 12:00:00",
        }
        config = AttributeConfig(**params)
        assert len(config.config) == 1
        assert config.config[0].bk_property_id == "test_prop"
        assert config.sync_time == "2024-01-01 12:00:00"

    def test_nested_structure(self):
        """测试嵌套结构构建"""
        config = AttributeConfig(
            config=[
                AttributeConfigItem(
                    bk_property_id="test_prop",
                    bk_property_name="测试属性",
                    bk_property_type="enum",
                    option=[
                        AttributeConfigItemOption(id="1", name="选项1", type="text", is_default=True),
                        AttributeConfigItemOption(id="2", name="选项2", type="text", is_default=False),
                    ],
                )
            ],
            sync_time="2024-01-01 12:00:00",
        )
        item = config.config[0]
        assert item.bk_property_id == "test_prop"
        assert item.option[0].id == "1"
        assert item.option[1].is_default is False

    def test_default_values(self):
        """测试默认值"""
        # AttributeConfig 默认值
        config = AttributeConfig()
        assert config.config == []
        assert config.sync_time == ""

        # AttributeConfigItem 默认值
        item = AttributeConfigItem(bk_property_id="test", bk_property_name="test")
        assert item.bk_property_type == ""
        assert item.option is None

        # AttributeConfigItemOption 默认值
        option = AttributeConfigItemOption(id="1", name="opt", type="text")
        assert option.is_default is True

    @pytest.mark.parametrize(
        "field,value",
        [
            ("bk_property_id", 123),
            ("bk_property_name", 123),
            ("bk_property_type", 123),
            ("option", "invalid"),
            ("option", [{"id": 1}]),
        ],
    )
    def test_invalid_types(self, field, value):
        """测试非法类型校验"""
        base_params = {field: value}
        with pytest.raises(ValidationError):
            AttributeConfigItem(**base_params)
