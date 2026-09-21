"""
动态分组领域模块入口

提供动态分组的完整功能，包括：
- 动态分组的增删改查
- 成员管理
- 缓存操作
- 权限控制

使用示例:
    # 方式1: 导入具体函数
    from bk_monitor_base.dynamic_group import create_dynamic_group, list_dynamic_groups

    # 创建动态分组
    group = create_dynamic_group(
        dynamic_group_name="测试分组",
        condition_list=[{"field": "bk_host_innerip", "value": "10.", "operator": "contains"}],
        object_model_code="cw-Host",
        space_code="bkcc__2",
        created_by="admin"
    )

    # 查询动态分组列表
    groups = list_dynamic_groups(space_codes=["bkcc__2"])

    # 方式2: 导入 operations 模块
    from bk_monitor_base.dynamic_group import operations

    result = operations.preview_dynamic_group_members(dynamic_group_id=1)

    # 方式3: 通过模块导入
    from bk_monitor_base import dynamic_group

    group = dynamic_group.get_dynamic_group(dynamic_group_id=1)
"""

# 导入 operations 模块本身（用于 operations.xxx 调用方式）
from bk_monitor_base.domains.dynamic_group import operations

# 常量
from bk_monitor_base.domains.dynamic_group.constants import (
    OPERATOR_MAPPING,
    DynamicGroupOperator,
)

# 数据定义
from bk_monitor_base.domains.dynamic_group.define import (
    DynamicGroup,
    DynamicGroupMember,
    DynamicGroupPermission,
    DynamicGroupQueryFilter,
)

# 异常（从 errors 模块导入，避免 __init__ 中的国际化问题）
from bk_monitor_base.domains.dynamic_group.errors import (
    DynamicGroupBaseError,
    DynamicGroupMemberNotFound,
    DynamicGroupMemberOperateError,
    DynamicGroupNotFound,
    DynamicGroupOperateError,
    DynamicGroupValidError,
    ErrorCodes,
)

# ORM 模型
from bk_monitor_base.domains.dynamic_group.models import (
    DynamicGroupMemberORM,
    DynamicGroupORM,
)

# 能力层方法
from bk_monitor_base.domains.dynamic_group.operations import (
    batch_delete_dynamic_groups,
    cache_dynamic_group_member,
    count_dynamic_groups,
    create_dynamic_group,
    delete_dynamic_group,
    delete_dynamic_group_cache,
    exists_dynamic_group,
    fetch_dynamic_group_inst_map,
    get_dynamic_group,
    get_dynamic_group_members,
    get_member_fetcher,
    list_dynamic_group_members,
    list_dynamic_groups,
    preview_dynamic_group_members,
    update_dynamic_group,
)

__all__ = [
    # 操作层模块
    "operations",
    # 能力层方法
    "create_dynamic_group",
    "update_dynamic_group",
    "delete_dynamic_group",
    "batch_delete_dynamic_groups",
    "get_dynamic_group",
    "list_dynamic_groups",
    "count_dynamic_groups",
    "exists_dynamic_group",
    "get_dynamic_group_members",
    "list_dynamic_group_members",
    "fetch_dynamic_group_inst_map",
    "preview_dynamic_group_members",
    "cache_dynamic_group_member",
    "delete_dynamic_group_cache",
    "get_member_fetcher",
    # 数据定义
    "DynamicGroup",
    "DynamicGroupMember",
    "DynamicGroupPermission",
    "DynamicGroupQueryFilter",
    # ORM 模型
    "DynamicGroupORM",
    "DynamicGroupMemberORM",
    # 常量
    "DynamicGroupOperator",
    "OPERATOR_MAPPING",
    # 异常
    "ErrorCodes",
    "DynamicGroupBaseError",
    "DynamicGroupNotFound",
    "DynamicGroupValidError",
    "DynamicGroupOperateError",
    "DynamicGroupMemberNotFound",
    "DynamicGroupMemberOperateError",
]
