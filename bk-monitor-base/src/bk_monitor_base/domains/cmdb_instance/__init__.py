"""
CMDB 实例领域模块

提供 CMDB 实例的 ES 模型定义和查询操作。

快速使用:
    # 导入模型
    from bk_monitor_base.domains.cmdb_instance import CMDBInstance, CMDBObjRelate, CMDBInstRelate

    # 导入操作函数
    from bk_monitor_base.domains.cmdb_instance import search_instances, get_instance
"""

# 导出模型类
from .agent_status import enrich_host_instances_with_agent_status, get_host_agent_status_map
from .models import BaseInstance, CMDBDocument, CMDBInstance, CMDBInstRelate, CMDBObjRelate, CWDocument

# 导出操作函数
from .operations import (
    get_instance,
    get_instance_with_relations,
    iter_inst_relations,
    iter_instances,
    iter_instances_by_dsl,
    query_option_values,
    refresh_host_agent_status,
    search_all_inst_relations,
    search_all_instances,
    search_all_instances_by_dsl,
    search_inst_relations,
    search_instances,
    search_instances_by_dsl,
    search_obj_relations,
)

__all__ = [
    # 基础文档类
    "CWDocument",
    "BaseInstance",
    "CMDBDocument",
    # CMDB 模型类
    "CMDBInstance",
    "CMDBObjRelate",
    "CMDBInstRelate",
    # 查询操作函数
    "search_instances",
    "search_all_instances",
    "get_host_agent_status_map",
    "enrich_host_instances_with_agent_status",
    "refresh_host_agent_status",
    "iter_instances",
    "get_instance",
    "query_option_values",
    "search_obj_relations",
    "search_inst_relations",
    "search_all_inst_relations",
    "iter_inst_relations",
    "get_instance_with_relations",
    "search_instances_by_dsl",
    "search_all_instances_by_dsl",
    "iter_instances_by_dsl",
]
