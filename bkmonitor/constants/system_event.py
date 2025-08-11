"""
系统事件维度常量定义
"""

from django.utils.translation import gettext_lazy as _

# 基础维度字段
BASE_DIMENSION_FIELDS = ["bk_target_cloud_id", "bk_target_ip"]

# 各种系统事件的维度字段定义【兜底字段】
PING_EVENT_DIMENSION_FIELDS = BASE_DIMENSION_FIELDS + []

DISK_FULL_EVENT_DIMENSION_FIELDS = BASE_DIMENSION_FIELDS + []

DISK_READONLY_EVENT_DIMENSION_FIELDS = BASE_DIMENSION_FIELDS + ["position", "fs", "type"]

COREFILE_EVENT_DIMENSION_FIELDS = BASE_DIMENSION_FIELDS + ["executable", "executable_path", "signal"]

OOM_EVENT_DIMENSION_FIELDS = BASE_DIMENSION_FIELDS + []

AGENT_EVENT_DIMENSION_FIELDS = BASE_DIMENSION_FIELDS + []

GSE_CUSTOM_STR_EVENT_DIMENSION_FIELDS = BASE_DIMENSION_FIELDS + []

GSE_PROCESS_EVENT_DIMENSION_FIELDS = BASE_DIMENSION_FIELDS + ["process_name", "process_group_id"]

PROC_PORT_EVENT_DIMENSION_FIELDS = BASE_DIMENSION_FIELDS + []

OS_RESTART_EVENT_DIMENSION_FIELDS = BASE_DIMENSION_FIELDS

# 完整的维度定义[待商议]
BASE_DIMENSIONS = [
    {"id": "bk_target_cloud_id", "name": _("云区域ID")},
    {"id": "bk_target_ip", "name": _("目标IP")},
]

PING_EVENT_DIMENSIONS = BASE_DIMENSIONS + [
    {"id": "count", "name": _("失败次数")},
    {"id": "ping_server", "name": _("Ping服务器")},
]

DISK_FULL_EVENT_DIMENSIONS = BASE_DIMENSIONS + [
    {"id": "disk", "name": _("磁盘路径")},
    {"id": "file_system", "name": _("文件系统")},
    {"id": "fstype", "name": _("文件系统类型")},
]

DISK_READONLY_EVENT_DIMENSIONS = BASE_DIMENSIONS + [
    {"id": "position", "name": _("位置")},
    {"id": "fs", "name": _("文件系统")},
    {"id": "type", "name": _("类型")},
]

COREFILE_EVENT_DIMENSIONS = BASE_DIMENSIONS + [
    {"id": "executable", "name": _("可执行文件")},
    {"id": "executable_path", "name": _("可执行文件路径")},
    {"id": "signal", "name": _("信号")},
]

OOM_EVENT_DIMENSIONS = BASE_DIMENSIONS + [
    {"id": "process", "name": _("进程名")},
    {"id": "task", "name": _("任务名")},
    {"id": "message", "name": _("消息")},
    {"id": "oom_memcg", "name": _("OOM内存控制组")},
    {"id": "task_memcg", "name": _("任务内存控制组")},
    {"id": "constraint", "name": _("约束")},
]

AGENT_EVENT_DIMENSIONS = BASE_DIMENSIONS

GSE_CUSTOM_STR_EVENT_DIMENSIONS = BASE_DIMENSIONS + [
    {"id": "agent_version", "name": _("Agent版本")},
]

GSE_PROCESS_EVENT_DIMENSIONS = [
    {"id": "event_name", "name": _("事件名称")},
    {"id": "process_name", "name": _("进程名称")},
    {"id": "process_group_id", "name": _("进程组ID")},
    {"id": "process_index", "name": _("进程索引")},
]

PROC_PORT_EVENT_DIMENSIONS = BASE_DIMENSIONS + [
    {"id": "display_name", "name": _("显示名称")},
    {"id": "protocol", "name": _("协议")},
    {"id": "bind_ip", "name": _("绑定IP")},
]

OS_RESTART_EVENT_DIMENSIONS = BASE_DIMENSIONS

# 系统事件维度映射表（用于指标缓存）
SYSTEM_EVENT_DIMENSIONS_MAP = {
    "ping-gse": PING_EVENT_DIMENSIONS,
    "disk-full-gse": DISK_FULL_EVENT_DIMENSIONS,
    "disk-readonly-gse": DISK_READONLY_EVENT_DIMENSIONS,
    "corefile-gse": COREFILE_EVENT_DIMENSIONS,
    "oom-gse": OOM_EVENT_DIMENSIONS,
    "agent-gse": AGENT_EVENT_DIMENSIONS,
    "gse_custom_event": GSE_CUSTOM_STR_EVENT_DIMENSIONS,
    "gse_process_event": GSE_PROCESS_EVENT_DIMENSIONS,
    "proc_port": PROC_PORT_EVENT_DIMENSIONS,
    "os_restart": OS_RESTART_EVENT_DIMENSIONS,
}
