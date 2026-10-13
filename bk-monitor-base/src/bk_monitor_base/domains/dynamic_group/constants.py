"""
动态分组常量定义
"""

from typing import final

from bk_monitor_base.config import get_config

# 对象模型使用记录常量 - 从配置中获取
_config = get_config()
USAGE_RECORD_APP_ID = _config.common.usage_record_meta_app_id
USAGE_RECORD_APP_NAME = _config.common.usage_record_meta_app_name
USAGE_RECORD_MODULE_ID = _config.common.usage_record_dynamic_group_module_id
USAGE_RECORD_MODULE_NAME = _config.common.usage_record_dynamic_group_module_name


@final
class DynamicGroupOperator:
    """动态分组查询操作符"""

    # 基本操作符
    EQUAL = "equal"
    NOT_EQUAL = "not_equal"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    IN = "in"
    NOT_IN = "not_in"

    # 比较操作符
    LESS = "less"
    LESS_OR_EQUAL = "less_or_equal"
    GREATER = "greater"
    GREATER_OR_EQUAL = "greater_or_equal"


@final
class CMDBOperator:
    """CMDB API 查询操作符"""

    EQ = "$eq"
    NE = "$ne"
    REGEX = "$regex"
    IN = "$in"
    NIN = "$nin"
    LT = "$lt"
    LTE = "$lte"
    GT = "$gt"
    GTE = "$gte"


@final
class BuiltinObjectModelCode:
    """内置对象模型编码"""

    HOST = "cw-Host"
    BIZ = "cw-Biz"
    MODULE = "cw-Module"
    SET = "cw-Set"


# 动态分组操作符到 CMDB 操作符的映射
OPERATOR_MAPPING = {
    DynamicGroupOperator.EQUAL: CMDBOperator.EQ,
    DynamicGroupOperator.NOT_EQUAL: CMDBOperator.NE,
    DynamicGroupOperator.CONTAINS: CMDBOperator.REGEX,
    DynamicGroupOperator.NOT_CONTAINS: CMDBOperator.REGEX,  # 需要配合 $not 使用
    DynamicGroupOperator.IN: CMDBOperator.IN,
    DynamicGroupOperator.NOT_IN: CMDBOperator.NIN,
    DynamicGroupOperator.LESS: CMDBOperator.LT,
    DynamicGroupOperator.LESS_OR_EQUAL: CMDBOperator.LTE,
    DynamicGroupOperator.GREATER: CMDBOperator.GT,
    DynamicGroupOperator.GREATER_OR_EQUAL: CMDBOperator.GTE,
}


@final
class DynamicGroupConstants:
    """
    动态分组常量
    """

    # 动态分组topic
    DYNAMIC_GROUP_TOPIC = "bk_monitor_dynamic_group"

    # 动态分组变更记录
    META_DYNAMIC_GROUP_CHANGE = "meta_dynamic_group_change"


# agent状态的属性id
CW_AGENT_STATUS_ID = "cw-agent_status"

SEARCH_INST_OPERATOR_MAP = {
    "equal": "$eq",
    "not_equal": "$ne",
    "contains": "$regex",
    "in": "$in",
    "not_in": "$nin",
}

SEARCH_INST_OPERATOR_REVERSE_MAP = {
    "$eq": "equal",
    "$ne": "not_equal",
    "$regex": "contains",
    "$in": "in",
    "$nin": "not_in",
}


def get_dynamic_group_cache_key(dynamic_group_id: int) -> str:
    """
    获取动态分组缓存键

    Args:
        dynamic_group_id: 动态分组ID

    Returns:
        完整的Redis缓存键
    """
    config = get_config()
    return f"{config.common.redis_key_prefix}dynamic_group:{dynamic_group_id}"


def get_dynamic_inst_group_cache_key(cw_object_model_code: str) -> str:
    """
    获取实例分组关系缓存键

    Args:
        cw_object_model_code: 对象模型代码

    Returns:
        完整的Redis缓存键
    """
    config = get_config()
    return f"{config.common.redis_key_prefix}dynamic_inst_group:{cw_object_model_code}"


# Redis缓存键模板（已废弃，使用上面的函数替代）
# 为保持向后兼容，这些常量现在也使用 common config 中的 redis_key_prefix
_config = get_config()
DYNAMIC_GROUP_CACHE_KEY = f"{_config.common.redis_key_prefix}dynamic_group:{{dynamic_group_id}}"
DYNAMIC_INST_GROUP_CACHE_KEY = f"{_config.common.redis_key_prefix}dynamic_inst_group:{{cw_object_model_code}}"

# Redis缓存过期时间（秒）
DYNAMIC_GROUP_CACHE_TTL = 7 * 24 * 60 * 60  # 7天

# 动态分组成员刷新任务分布式锁
DYNAMIC_GROUP_REFRESH_LOCK_KEY = f"{_config.common.redis_key_prefix}dynamic_group:refresh_lock:{{dynamic_group_id}}"
DYNAMIC_GROUP_REFRESH_LOCK_TTL = 5 * 60  # 5分钟
