"""
拨测(Uptime Check)模块入口

提供服务可用性、访问性能、链路连通性的全维度检测能力
"""

# 核心模型
# 常量定义
from bk_monitor_base.domains.uptime_check.constants import (
    BEAT_STATUS,
    DEFAULT_MAX_TIMEOUT,
    TASK_MIN_PERIOD,
    UPTIME_CHECK_ALLOWED_HEADERS,
    UPTIME_CHECK_AVAILABLE_DEFAULT_VALUE,
    UPTIME_CHECK_DB,
    UPTIME_CHECK_MONIT_RESPONSE,
    UPTIME_CHECK_MONIT_RESPONSE_CODE,
    UPTIME_CHECK_SUMMARY_TIME_RANGE,
    UPTIME_CHECK_TASK_DETAIL_GROUP_BY_MINUTE1_TIME_RANGE,
    UPTIME_CHECK_TASK_DETAIL_TIME_RANGE,
    UPTIME_DATA_SOURCE_LABEL,
    UPTIME_DATA_TYPE_LABEL,
    UptimeCheckProtocol,
)
from bk_monitor_base.domains.uptime_check.define import (
    UptimeCheckGroup,
    UptimeCheckNode,
    UptimeCheckNodeIPType,
    UptimeCheckTask,
    UptimeCheckTaskProtocol,
    UptimeCheckTaskStatus,
)
from bk_monitor_base.domains.uptime_check.models import (
    UPTIME_CHECK_TASK_STATUS_NAME_MAP,
    UptimeCheckGroupModel,
    UptimeCheckNodeModel,
    UptimeCheckTaskModel,
    UptimeCheckTaskSubscription,
)

# Operation 层（暴露所有公共操作）
from bk_monitor_base.domains.uptime_check.operation import (
    control_task,
    count_groups,
    count_tasks,
    delete_group,
    delete_node,
    delete_task,
    generate_task_sub_config,
    # Group 统一操作
    get_group,
    # Node 统一操作
    get_node,
    get_node_with_host_id,
    # ==================== 统一 CRUD 操作 ====================
    # Task 统一操作
    get_task,
    # CollectorLog 统一操作
    list_collector_logs,
    list_groups,
    list_nodes,
    list_tasks,
    manage_group_tasks,
    refresh_task_status,
    save_group,
    save_node,
    save_task,
    # ==================== 旧版操作函数（保留兼容）====================
    # 任务操作
    test_uptime_check_task,
)
from bk_monitor_base.domains.uptime_check.services import TestTaskError

__all__ = [
    # Define 定义
    "UptimeCheckTask",
    "UptimeCheckNode",
    "UptimeCheckGroup",
    "UptimeCheckTaskProtocol",
    "UptimeCheckTaskStatus",
    "UptimeCheckNodeIPType",
    # 模型
    "UptimeCheckTaskModel",
    "UptimeCheckNodeModel",
    "UptimeCheckGroupModel",
    "UptimeCheckTaskSubscription",
    # 常量
    "UptimeCheckProtocol",
    "TASK_MIN_PERIOD",
    "DEFAULT_MAX_TIMEOUT",
    "BEAT_STATUS",
    "UPTIME_CHECK_ALLOWED_HEADERS",
    "UPTIME_CHECK_AVAILABLE_DEFAULT_VALUE",
    "UPTIME_CHECK_DB",
    "UPTIME_CHECK_MONIT_RESPONSE",
    "UPTIME_CHECK_MONIT_RESPONSE_CODE",
    "UPTIME_CHECK_SUMMARY_TIME_RANGE",
    "UPTIME_CHECK_TASK_DETAIL_GROUP_BY_MINUTE1_TIME_RANGE",
    "UPTIME_CHECK_TASK_DETAIL_TIME_RANGE",
    "UPTIME_DATA_SOURCE_LABEL",
    "UPTIME_DATA_TYPE_LABEL",
    "UPTIME_CHECK_TASK_STATUS_NAME_MAP",
    # 服务
    "TestTaskError",
    # ==================== 统一 CRUD 操作（推荐使用）====================
    # Task 统一操作
    "get_task",
    "list_tasks",
    "count_tasks",
    "save_task",
    "delete_task",
    "control_task",
    "refresh_task_status",
    # Node 统一操作
    "get_node",
    "list_nodes",
    "save_node",
    "delete_node",
    "get_node_with_host_id",
    # Group 统一操作
    "get_group",
    "list_groups",
    "count_groups",
    "save_group",
    "delete_group",
    "manage_group_tasks",
    # CollectorLog 统一操作
    "list_collector_logs",
    # ==================== 旧版操作函数（保留兼容）====================
    # 任务操作
    "test_uptime_check_task",
    "generate_task_sub_config",
]
