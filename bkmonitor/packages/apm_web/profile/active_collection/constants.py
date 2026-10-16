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
BUILTIN_EVENT_GROUP_NAME = "active_profiling_builtin_events"
BUILTIN_EVENT_GROUP_LABEL = "application_check"

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
BKMONITORBEAT_MAIN_CONF_RELATIVE_PATH = "plugins/etc/bkmonitorbeat.conf"

# 子配置模板随 bkmonitorbeat 插件包发布，context 结构由模板约定
ACTIVE_PROFILE_SUBSCRIPTION_STEP_ID = "bkmonitorbeat_active_profile"
ACTIVE_PROFILE_CONFIG_TEMPLATE_NAME = "bkmonitorbeat_active_profile.conf"

# 脚本体是常量，选择器经 base64 从脚本参数进 stdin，用户输入不落到 shell 可解释的位置
PROCESS_MATCH_SCRIPT = 'echo "$1" | base64 -d | {beat_path} -active-profile-match\n'

# 运行目录由主配置的 path.data 推导，取消命令靠它定位采集进程，因此必须显式传 -c
IMMEDIATE_COLLECT_SCRIPT = 'echo "$1" | base64 -d | {beat_path} -c {main_conf} -active-profile-run\n'
CANCEL_EXECUTION_SCRIPT = 'echo "$1" | base64 -d | {beat_path} -c {main_conf} -active-profile-cancel\n'

ACTIVE_PROFILING_STARTED_EVENT = "active_profiling_started"
ACTIVE_PROFILING_FINISHED_EVENT = "active_profiling_finished"
EVENT_CONTENT_SCHEMA_VERSION = 1
EVENT_ERROR_MESSAGE_MAX_LENGTH = 2048

# SaaS 侧先按 5 分钟封顶，采集器另有自身上限
COLLECTOR_MAX_DURATION_SEC = 300

# 只有 started 的主机执行超过“采集时长 + 300 秒”仍没有 finished，视为 unknown
EXECUTION_UNKNOWN_GRACE_SEC = 300

# 开始后超过采集时长上限 + 300 秒仍无 finished 即为 unknown，running 行和 finished 事件都落在这个窗口内
RUNNING_EXECUTION_WINDOW_MS = (COLLECTOR_MAX_DURATION_SEC + EXECUTION_UNKNOWN_GRACE_SEC) * 1000

# 成功类终态的结果超过 Profiling 保留期后显示为 outdate，与采集器上报的过期状态用同一个值
SUCCEED_STATUSES = ("succeed", "partial_succeed")

# unify-query 单次最多返回 1 万条，ES 的 from + size 默认也不能超过 1 万
EVENT_QUERY_BATCH_SIZE = 200
EVENT_QUERY_MAX_SIZE = 10000

# 一次执行可能覆盖很多主机，任务历史每批多读一些，减少续读请求
EXECUTION_QUERY_BATCH_SIZE = 500

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

# 计划最后一次执行过去 1 天后才停用并移除主机上的子配置，执行时离线的主机上线后仍能收到配置、上报配置晚到的失败
EXPIRED_TASK_STOP_DELAY_MS = 24 * 3600 * 1000

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
    {"field": "duration_ms", "name": "耗时", "type": "duration"},
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
    {"field": "duration_ms", "name": "耗时", "type": "duration"},
    {"field": "target_count", "name": "主机数", "type": "number"},
    {"field": "execution_status", "name": "状态", "type": "status"},
]

# 与 Event 维度同名；process_names/process_pids 是逗号拼接的多个进程，拆开后再计数
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
    {"field": "duration_ms", "name": "耗时", "type": "duration"},
]

# 取值是现有 Profiling diagrammer 的注册名，结果接口只开放火焰图与表格
DIAGRAM_TYPE_CHOICES = (
    ("flamegraph", "flamegraph"),
    ("table", "table"),
)

# unknown 由 started 超时派生，ES 筛不出来，列表筛选不提供这一项
EXECUTION_STATUS_FILTER_CHOICES = tuple(item for item in EXECUTION_STATUS_CHOICES if item[0] != "unknown")


def _choice_values(choices):
    return [value for value, __ in choices]


# 表单默认值与请求/展示枚举。筛选状态不含 unknown，展示状态含 unknown
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
    "execution_statuses": _choice_values(EXECUTION_STATUS_CHOICES),
    "execution_status_filters": _choice_values(EXECUTION_STATUS_FILTER_CHOICES),
    "diagram_types": _choice_values(DIAGRAM_TYPE_CHOICES),
}
