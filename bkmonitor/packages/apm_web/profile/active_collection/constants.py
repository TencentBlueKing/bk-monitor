"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from constants.apm import BUILTIN_PROFILING_APP_NAME as BUILTIN_PROFILING_APP_NAME

BUILTIN_PROFILE_SERVICE_NAME = "active_allocation"

COLLECTION_METHOD_CHOICES = (
    ("perf", "perf"),
    ("golang", "golang"),
    ("java", "java"),
)

COLLECTION_TYPE_CHOICES = (
    ("native_cpu", "native_cpu"),
    ("go_cpu", "go_cpu"),
    ("go_heap", "go_heap"),
    ("java_cpu", "java_cpu"),
    ("java_allocation", "java_allocation"),
)

COLLECTION_TYPES_BY_METHOD = {
    "perf": ("native_cpu",),
    "golang": ("go_cpu", "go_heap"),
    "java": ("java_cpu", "java_allocation"),
}

SCHEDULE_TYPE_CHOICES = (
    ("immediate", "immediate"),
    ("once_at", "once_at"),
    ("cron", "cron"),
)

# 查询默认读后台 MySQL 执行表，es 保留一期按 Event 聚合的查询能力，前端不传
QUERY_SOURCE_CHOICES = (
    ("mysql", "mysql"),
    ("es", "es"),
)

PLANNED_SCHEDULE_TYPE_CHOICES = (
    ("once_at", "once_at"),
    ("cron", "cron"),
)

PROCESS_SELECTOR_TYPE_CHOICES = (
    ("command", "command"),
    ("pid_file", "pid_file"),
    ("pid", "pid"),
)

STACK_UNWIND_CHOICES = (
    ("fp", "fp"),
    ("dwarf", "dwarf"),
)

EXECUTION_STATUS_CHOICES = (
    ("running", "running"),
    ("succeed", "succeed"),
    ("partial_succeed", "partial_succeed"),
    ("failed", "failed"),
    ("timeout", "timeout"),
    ("cancelled", "cancelled"),
    ("unknown", "unknown"),
    ("outdate", "outdate"),
)

# 预览是交互操作，只为确认匹配是否正确，不需要扫完所有机器
PROCESS_PREVIEW_MAX_HOSTS = 50

# 选择器会进入每条 Event 的配置快照，采集端 event.content 有 32 KB 上限；
# 限制选择器大小保证快照总能完整上报，采集端加载配置时按同样的上限校验
PROCESS_SELECTOR_MAX_PIDS = 1000
PROCESS_SELECTOR_MAX_HOST_PIDS = 500
PROCESS_SELECTOR_MAX_PID_PATHS = 20
PROCESS_SELECTOR_MAX_TEXT_LENGTH = 1024
PROCESS_SELECTOR_MAX_PID_PATH_LENGTH = 4096
# pid_path 的多个文件路径与 pids 的多个 PID 都用分号分隔，原样下发给采集端
PROCESS_SELECTOR_SEPARATOR = ";"

BKMONITORBEAT_RELATIVE_PATH = "plugins/bin/bkmonitorbeat"

# 脚本体是常量，选择器经 base64 从脚本参数进 stdin，用户输入不落到 shell 可解释的位置
PROCESS_MATCH_SCRIPT = 'echo "$1" | base64 -d | {beat_path} -active-profile-match\n'

# 失败原因的 error_type 大多由采集端上报，前端按类型给出展示文案；以下两类由 SaaS 归类：
# 作业平台没有执行成功，以及旧版采集端只输出错误文本
ERROR_TYPE_DISPATCH_FAILED = "dispatch_failed"
ERROR_TYPE_CONFIG_INVALID = "config_invalid"

# SaaS 侧先按 5 分钟封顶，采集器另有自身上限
COLLECTOR_MAX_DURATION_SEC = 300

# 只有 started 的主机执行超过“采集时长 + 300 秒”仍没有 finished，视为 unknown
EXECUTION_UNKNOWN_GRACE_SEC = 300

# 开始后超过采集时长上限 + 300 秒仍无 finished 即为 unknown，running 行和 finished 事件都落在这个窗口内
RUNNING_EXECUTION_WINDOW_MS = (COLLECTOR_MAX_DURATION_SEC + EXECUTION_UNKNOWN_GRACE_SEC) * 1000

DEPLOYMENT_STATUS_DEPLOYING = "deploying"
DEPLOYMENT_STATUS_SUCCESS = "success"
DEPLOYMENT_STATUS_FAILED = "failed"
DEPLOYMENT_STATUS_EXPIRED = "outdate"

DEPLOYMENT_STATUS_CHOICES = (
    (DEPLOYMENT_STATUS_DEPLOYING, DEPLOYMENT_STATUS_DEPLOYING),
    (DEPLOYMENT_STATUS_SUCCESS, DEPLOYMENT_STATUS_SUCCESS),
    (DEPLOYMENT_STATUS_FAILED, DEPLOYMENT_STATUS_FAILED),
    (DEPLOYMENT_STATUS_EXPIRED, DEPLOYMENT_STATUS_EXPIRED),
)

TASK_STATUS_BY_ENABLED = {True: "enabled", False: "disabled"}

PROCESS_PREVIEW_COLUMNS = [
    {"field": "ip", "name": "目标 IP", "type": "text"},
    {"field": "pid", "name": "PID", "type": "number"},
    {"field": "process_name", "name": "进程名", "type": "text"},
    {"field": "command", "name": "命令行", "type": "text"},
    {"field": "started_at", "name": "启动时间", "type": "datetime"},
]
TASK_LIST_COLUMNS = [
    {"field": "name", "name": "任务名称", "type": "text"},
    {"field": "schedule", "name": "执行方式", "type": "schedule"},
    {"field": "schedule", "name": "执行时间", "type": "schedule_time"},
    {"field": "task_status", "name": "状态", "type": "status"},
    {"field": "deployment_status", "name": "部署状态", "type": "status"},
    {"field": "collection_method", "name": "采集方式", "type": "text"},
    {"field": "collection_type", "name": "采集类型", "type": "text"},
    {"field": "creator", "name": "创建人", "type": "text"},
    {"field": "updated_at", "name": "更新时间", "type": "datetime"},
]

HOST_QUERY_COLUMNS = [
    {"field": "ip", "name": "目标 IP", "type": "text"},
    {"field": "processes", "name": "采集进程", "type": "process_list"},
    {"field": "task", "name": "采集历史", "type": "task"},
    {"field": "collection_method", "name": "采集方式", "type": "text"},
    {"field": "collection_type", "name": "采集类型", "type": "text"},
    {"field": "creator", "name": "创建人", "type": "text"},
    {"field": "scheduled_at", "name": "执行时间", "type": "datetime"},
    {"field": "started_at", "name": "开始时间", "type": "datetime"},
    {"field": "finished_at", "name": "结束时间", "type": "datetime"},
    {"field": "duration_ms", "name": "采集时长", "type": "duration"},
    {"field": "status", "name": "状态", "type": "status"},
]

EXECUTION_LIST_TASK_COLUMNS = [
    {"field": "task_name", "name": "任务名称", "type": "text"},
    {"field": "schedule_type", "name": "执行方式", "type": "text"},
    {"field": "collection_method", "name": "采集方式", "type": "text"},
    {"field": "collection_type", "name": "采集类型", "type": "text"},
    {"field": "creator", "name": "创建人", "type": "text"},
    {"field": "scheduled_at", "name": "执行时间", "type": "datetime"},
    {"field": "started_at", "name": "开始时间", "type": "datetime"},
    {"field": "finished_at", "name": "结束时间", "type": "datetime"},
    {"field": "duration_ms", "name": "采集时长", "type": "duration"},
    {"field": "target_count", "name": "主机数", "type": "number"},
    {"field": "execution_status", "name": "状态", "type": "status"},
]

# 与 Event 维度同名；进程维度是逗号拼接的多个进程，process_names 候选按进程名去重，process_pids 候选显示为 进程名:PID
TOPK_FIELDS = (
    "target",
    "task_name",
    "collection_method",
    "collection_type",
    "schedule_type",
    "process_names",
    "process_pids",
)

EXECUTION_DETAIL_HOST_COLUMNS = [
    {"field": "ip", "name": "目标 IP", "type": "text"},
    {"field": "processes", "name": "采集进程", "type": "process_list"},
    {"field": "status", "name": "状态", "type": "status"},
    {"field": "message", "name": "执行信息", "type": "text"},
    {"field": "started_at", "name": "开始时间", "type": "datetime"},
    {"field": "finished_at", "name": "结束时间", "type": "datetime"},
    {"field": "duration_ms", "name": "采集时长", "type": "duration"},
]

# 取值是现有 Profiling diagrammer 的注册名，结果接口开放火焰图、表格与调用图
DIAGRAM_TYPE_CHOICES = (
    ("flamegraph", "flamegraph"),
    ("table", "table"),
    ("callgraph", "callgraph"),
)


def _choice_values(choices):
    return [value for value, __ in choices]


# 表单默认值与请求/展示枚举。展示状态比筛选状态多出主机行的 parsing
META_CONFIG = {
    "collector_config": {
        "native_cpu": {
            "duration_sec": 30,
            "frequency_hz": 99,
            "stack_unwind": "fp",
        },
        "go_cpu": {
            "ip_address": "127.0.0.1",
            "port": 6060,
            "duration_sec": 30,
        },
        "go_heap": {
            "ip_address": "127.0.0.1",
            "port": 6060,
        },
        "java_cpu": {
            "duration_sec": 30,
        },
        "java_allocation": {
            "duration_sec": 30,
        },
    },
    "resource_guard_config": {
        "auto_stop_on_resource_pressure": True,
        "max_disk_usage": 1024,
        "min_mem_level": 100,
    },
    # 周期任务表单默认每小时整点执行
    "schedule": {
        "cron": {
            "cron_expression": "0 * * * *",
        },
    },
    "collection_methods": _choice_values(COLLECTION_METHOD_CHOICES),
    "collection_types_by_method": {method: list(types) for method, types in COLLECTION_TYPES_BY_METHOD.items()},
    "schedule_types": _choice_values(SCHEDULE_TYPE_CHOICES),
    "process_selector_types": _choice_values(PROCESS_SELECTOR_TYPE_CHOICES),
    "stack_unwinds": _choice_values(STACK_UNWIND_CHOICES),
    "task_statuses": [TASK_STATUS_BY_ENABLED[True], TASK_STATUS_BY_ENABLED[False]],
    "deployment_statuses": _choice_values(DEPLOYMENT_STATUS_CHOICES),
    "execution_statuses": [*_choice_values(EXECUTION_STATUS_CHOICES), "parsing"],
    "execution_status_filters": _choice_values(EXECUTION_STATUS_CHOICES),
    "diagram_types": _choice_values(DIAGRAM_TYPE_CHOICES),
}
