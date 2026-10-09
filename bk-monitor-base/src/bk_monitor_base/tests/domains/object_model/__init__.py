"""
object_model 模块单元测试
"""

from bk_monitor_base.domains.object_model.define import AttributeConfig, AttributeConfigItem

ATTRIBUTE_CONFIG_ENTITY = AttributeConfig(
    config=[
        AttributeConfigItem(bk_property_id="test_property", bk_property_name="测试属性", bk_property_type="string")
    ],
    sync_time="2024-01-01 00:00:00",
)
