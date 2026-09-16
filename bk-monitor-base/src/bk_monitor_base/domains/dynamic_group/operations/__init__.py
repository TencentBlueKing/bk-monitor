"""
动态分组操作层

提供动态分组的增删改查等核心操作功能
"""

from bk_monitor_base.domains.dynamic_group.operations.cache import (
    cache_dynamic_group_member,
    delete_dynamic_group_cache,
)
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
from bk_monitor_base.domains.dynamic_group.utils.enricher import HostRelationEnricher
from bk_monitor_base.domains.dynamic_group.utils.fetcher import get_member_fetcher

__all__ = [
    # 动态分组基础操作
    "create_dynamic_group",
    "update_dynamic_group",
    "delete_dynamic_group",
    "batch_delete_dynamic_groups",
    "get_dynamic_group",
    "list_dynamic_groups",
    "count_dynamic_groups",
    "exists_dynamic_group",
    # 成员查询
    "get_dynamic_group_members",
    "list_dynamic_group_members",  # ✅ 新增：增强版成员查询
    "fetch_dynamic_group_inst_map",
    # 成员预览
    "preview_dynamic_group_members",
    # 缓存操作
    "cache_dynamic_group_member",
    "delete_dynamic_group_cache",
    # 成员获取器
    "get_member_fetcher",
    # 主机关联增强器
    "HostRelationEnricher",
]
