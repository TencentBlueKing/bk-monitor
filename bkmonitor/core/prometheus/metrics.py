"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

# 数据源
import logging

from django.conf import settings
from prometheus_client.exposition import push_to_gateway
from prometheus_client.utils import INF

from core.prometheus.base import (
    REGISTRY,
    BkCollectorRegistry,
    Counter,
    Gauge,
    Histogram,
)
from core.prometheus.tools import get_metric_agg_gateway_url, udp_handler

logger = logging.getLogger(__name__)


class Empty:
    pass


DeploymentNotSet = Empty()
DEPLOYMENT = DeploymentNotSet


def refresh_deployment():
    try:
        with open("/etc/hostname") as f:
            hostname = f.read().strip()
        if hostname.count("-") < 2:
            return ""
        return hostname.rsplit("-", 2)[0]
    except FileNotFoundError:
        return ""


def report_all(job: str = settings.DEFAULT_METRIC_PUSH_JOB, registry: BkCollectorRegistry = REGISTRY):
    """
    批量上报指标
    """
    global DEPLOYMENT
    if registry.is_empty():
        return
    if DEPLOYMENT is DeploymentNotSet:
        DEPLOYMENT = refresh_deployment()
    if not get_metric_agg_gateway_url():
        return
    METRIC_PUSH_COUNT.labels(deployment=DEPLOYMENT).inc()
    try:
        # 发送消息
        push_to_gateway(gateway="", job=job, registry=registry, handler=udp_handler)
    except Exception:
        # 失败不处理，handler已经打了日志了，这里只是为了防止上报过程出现任何异常导致正常逻辑无法走下去
        return

    registry.clear_data()


def safe_push_to_gateway(job: str = settings.DEFAULT_METRIC_PUSH_JOB, registry: BkCollectorRegistry = REGISTRY):
    """安全批量上报指标"""
    # Q: 为什么该函数会在请求中被直接调用，而不是定期后台上报？
    # A: 当前我们的 prometheus client 是以单进程维度启动，数据存储放在进程内存中
    #    而如果我们改用多进程模式，push gateway 反而不合适了
    #    https://github.com/prometheus/client_python#multiprocess-mode-eg-gunicorn
    #    可以理解为 pushgateway 充当一个远端的分布式共享内存，所以这里可以直推
    try:
        report_all(job, registry)
    except Exception:
        logger.exception("failed to report data to gateway")


class StatusEnum:
    """
    任务状态枚举
    """

    SUCCESS = "success"
    FAILED = "failed"

    @classmethod
    def from_exc(cls, expr):
        return cls.FAILED if expr else cls.SUCCESS


METRIC_PUSH_COUNT = Counter(
    name="bkmonitor_metric_push_count",
    documentation="metric 推送次数",
    labelnames=("deployment",),
)

SPACE_QUERY_COUNT = Counter(
    name="bkmonitor_space_query_count",
    documentation="空间查询次数",
    labelnames=("using_cache", "role"),
)

CRON_TASK_EXECUTE_TIME = Histogram(
    name="bkmonitor_cron_task_execute_time",
    documentation="周期任务执行时间",
    labelnames=("task_name", "queue"),
    buckets=(1, 5, 10, 30, 60, 120, 180, 240, 300, 450, 600, 900, 1800, 3000, 10000, INF),
)

CRON_TASK_EXECUTE_COUNT = Counter(
    name="bkmonitor_cron_task_execute_count",
    documentation="周期任务执行次数",
    labelnames=("task_name", "status", "exception", "queue"),
)

CRON_BCS_SUB_TASK_EXECUTE_TIME = Histogram(
    name="bkmonitor_cron_bcs_sub_task_execute_time",
    documentation="BCS子任务执行时间",
    labelnames=("task_name", "sync_bcs_cluster_id", "queue"),
    buckets=(1, 5, 10, 30, 60, 120, 180, 240, 300, 450, 600, 900, 1800, 3000, 10000, INF),
)

CRON_BCS_SUB_TASK_EXECUTE_COUNT = Counter(
    name="bkmonitor_cron_bcs_sub_task_execute_count",
    documentation="BCS子任务执行次数",
    labelnames=("task_name", "sync_bcs_cluster_id", "status", "exception", "queue"),
)

DATASOURCE_QUERY_TIME = Histogram(
    name="bkmonitor_datasource_query_time",
    documentation="各数据源查询请求耗时",
    labelnames=("data_source_label", "data_type_label", "role", "result_table", "api"),
)

DATASOURCE_QUERY_COUNT = Counter(
    name="bkmonitor_datasource_query_count",
    documentation="各数据源查询请求次数",
    labelnames=("data_source_label", "data_type_label", "role", "result_table", "api", "status", "exception"),
)

# access
ACCESS_DATA_PROCESS_TIME = Histogram(
    name="bkmonitor_access_data_process_time",
    documentation="access(data) 模块处理耗时",
    labelnames=("strategy_group_key",),
)

ACCESS_DATA_PROCESS_COUNT = Counter(
    name="bkmonitor_access_data_process_count",
    documentation="access(data) 模块处理次数",
    labelnames=("strategy_group_key", "status", "exception"),
)

ACCESS_DATA_PROCESS_PULL_DATA_COUNT = Counter(
    name="bkmonitor_access_data_process_pull_data_count",
    documentation="access(data) 模块数据拉取条数",
    labelnames=("strategy_group_key",),
)

ACCESS_EVENT_PROCESS_TIME = Histogram(
    name="bkmonitor_access_event_process_time",
    documentation="access(event) 模块处理耗时",
    labelnames=("data_id",),
)

ACCESS_EVENT_PROCESS_COUNT = Counter(
    name="bkmonitor_access_event_process_count",
    documentation="access(event) 模块处理次数",
    labelnames=("data_id", "status", "exception"),
)

ACCESS_EVENT_PROCESS_PULL_DATA_COUNT = Counter(
    name="bkmonitor_access_event_process_pull_data_count",
    documentation="access(event) 模块数据拉取条数",
    labelnames=("data_id",),
)

ACCESS_PROCESS_PUSH_DATA_COUNT = Counter(
    name="bkmonitor_access_process_push_data_count",
    documentation="access 模块数据推送条数",
    labelnames=("strategy_id", "type"),
)

ACCESS_TOKEN_FORBIDDEN_COUNT = Counter(
    name="bkmonitor_access_token_forbidden_count",
    documentation="access 流控限制次数",
)

ACCESS_INCIDENT_PROCESS_COUNT = Counter(
    name="bkmonitor_access_incident_process_count",
    documentation="access(incident) 模块处理次数",
    labelnames=("status", "exception"),
)

# detect
DETECT_PROCESS_TIME = Histogram(
    name="bkmonitor_detect_process_time",
    documentation="detect 模块处理耗时",
    labelnames=("strategy_id",),
)

DETECT_PROCESS_COUNT = Counter(
    name="bkmonitor_detect_process_count",
    documentation="detect 模块处理次数",
    labelnames=("strategy_id", "status", "exception"),
)

DETECT_PROCESS_DATA_COUNT = Counter(
    name="bkmonitor_detect_process_data_count",
    documentation="detect 模块数据处理条数",
    labelnames=("strategy_id", "type"),
)

# trigger
TRIGGER_PROCESS_TIME = Histogram(
    name="bkmonitor_trigger_process_time",
    documentation="trigger 模块处理耗时",
    labelnames=("strategy_id",),
)

TRIGGER_PROCESS_COUNT = Counter(
    name="bkmonitor_trigger_process_count",
    documentation="trigger 模块处理次数",
    labelnames=("strategy_id", "status", "exception"),
)

TRIGGER_PROCESS_PULL_DATA_COUNT = Counter(
    name="bkmonitor_trigger_process_pull_data_count",
    documentation="trigger 模块数据拉取条数",
    labelnames=("strategy_id",),
)

TRIGGER_PROCESS_PUSH_DATA_COUNT = Counter(
    name="bkmonitor_trigger_process_push_data_count",
    documentation="trigger 模块数据推送条数",
    labelnames=("strategy_id",),
)

# nodata
NODATA_PROCESS_TIME = Histogram(
    name="bkmonitor_nodata_process_time",
    documentation="nodata 模块处理耗时",
    labelnames=("strategy_id",),
)

NODATA_PROCESS_COUNT = Counter(
    name="bkmonitor_nodata_process_count",
    documentation="nodata 模块处理次数",
    labelnames=("strategy_id", "status", "exception"),
)

NODATA_PROCESS_PULL_DATA_COUNT = Counter(
    name="bkmonitor_nodata_process_pull_data_count",
    documentation="nodata 模块数据拉取条数",
    labelnames=("strategy_id",),
)

NODATA_PROCESS_PUSH_DATA_COUNT = Counter(
    name="bkmonitor_nodata_process_push_data_count",
    documentation="nodata 模块数据推送条数",
    labelnames=("strategy_id",),
)

# alert
ALERT_PROCESS_TIME = Histogram(
    name="bkmonitor_alert_process_time",
    documentation="alert(builder) 模块处理耗时",
    labelnames=(),
)

ALERT_MANAGE_TIME = Histogram(
    name="bkmonitor_alert_manage_time",
    documentation="alert(manager) 模块处理耗时",
    labelnames=("status", "exception"),
)

ALERT_MANAGE_COUNT = Counter(
    name="bkmonitor_alert_manage_count",
    documentation="alert(manager) 模块处理告警量",
    labelnames=("status", "exception"),
)

ALERT_PROCESS_PULL_EVENT_COUNT = Counter(
    name="bkmonitor_alert_process_pull_event_count",
    documentation="alert(builder) 模块事件拉取条数",
    labelnames=("status", "exception"),
)

ALERT_PROCESS_DROP_EVENT_COUNT = Counter(
    name="bkmonitor_alert_process_drop_event_count",
    documentation="alert(builder) 模块事件丢弃条数",
    labelnames=("bk_data_id", "topic", "strategy_id"),
)

ALERT_PROCESS_PUSH_DATA_COUNT = Counter(
    name="bkmonitor_alert_process_push_data_count",
    documentation="alert(builder) 模块数据推送条数",
    labelnames=("bk_data_id", "topic", "strategy_id", "is_saved"),
)

PROCESS_BIG_LATENCY = Histogram(
    name="bkmonitor_big_process_latency",
    documentation="处理延迟过大",
    labelnames=(
        "strategy_id",
        "module",
        "bk_biz_id",
        "strategy_name",
    ),
    buckets=(60, 90, 120, 180, 300, 450, 600, 900, 1200, 1800, INF),
)

PROCESS_OVER_FLOW = Counter(
    name="bkmonitor_process_overflow",
    documentation="模块处理量级过大",
    labelnames=("module", "strategy_id", "bk_biz_id", "strategy_name"),
)

DETECT_PROCESS_LATENCY = Histogram(
    name="bkmonitor_detect_process_latency",
    documentation="告警从 access 到 detect 模块的整体处理延迟",
    labelnames=("strategy_id",),
    buckets=(1, 2, 3, 5, 10, 15, 20, 30, 60, 180, 300, INF),
)

AIOPS_DETECT_ERROR_COUNT = Gauge(
    name="bkmonitor_aiops_detect_error_count",
    documentation="AIOPS SDK检测异常类型统计",
    labelnames=("strategy_id", "strategy_name", "bk_biz_id", "error_code"),
)

AIOPS_DETECT_DIMENSION_COUNT = Gauge(
    name="bkmonitor_aiops_detect_dimension_count",
    documentation="AIOPS SDK策略覆盖维度数量",
    labelnames=("strategy_id", "strategy_name", "bk_biz_id"),
)

AIOPS_DETECT_INVALID_DIMENSION_RATE = Gauge(
    name="bkmonitor_aiops_detect_invalid_dimension_rate",
    documentation="AIOPS SDK策略无效维度比例",
    labelnames=("strategy_id", "strategy_name", "bk_biz_id"),
)

AIOPS_PRE_DETECT_LATENCY = Gauge(
    name="bkmonitor_aiops_pre_detect_latency",
    documentation="AIOPS SDK策略预检测耗时",
    labelnames=("strategy_id", "strategy_name", "bk_biz_id"),
)

TRIGGER_PROCESS_LATENCY = Histogram(
    name="bkmonitor_trigger_process_latency",
    documentation="告警从 detect 到 trigger 模块的整体处理延迟",
    labelnames=("strategy_id",),
    buckets=(1, 2, 3, 5, 10, 15, 20, 30, 60, 180, 300, INF),
)

ALERT_PROCESS_LATENCY = Histogram(
    name="bkmonitor_alert_process_latency",
    documentation="告警从 trigger 到 builder 模块的整体处理延迟",
    labelnames=("bk_data_id", "topic", "strategy_id"),
    buckets=(1, 2, 3, 5, 10, 15, 20, 30, 60, 180, 300, INF),
)

ACCESS_TO_ALERT_PROCESS_LATENCY = Histogram(
    name="bkmonitor_access_to_alert_process_latency",
    documentation="告警从 access 到 builder 模块的整体处理延迟",
    labelnames=("bk_data_id", "topic", "strategy_id"),
    buckets=(1, 2, 3, 5, 10, 15, 20, 30, 60, 180, 300, INF),
)

ALERT_MANAGE_PUSH_DATA_COUNT = Counter(
    name="bkmonitor_alert_manage_push_data_count",
    documentation="alert(manager) 模块数据推送条数",
    labelnames=("strategy_id", "signal"),
)

ALERT_QOS_COUNT = Counter(
    name="bkmonitor_alert_qos_count",
    documentation="composite 模块动作推送条数",
    labelnames=("strategy_id", "is_blocked"),
)

# composite
COMPOSITE_PROCESS_TIME = Histogram(
    name="bkmonitor_composite_process_time",
    documentation="composite 模块处理耗时",
    labelnames=("strategy_id",),
)

COMPOSITE_PROCESS_COUNT = Counter(
    name="bkmonitor_composite_process_count",
    documentation="composite 模块处理次数",
    labelnames=("strategy_id", "status", "exception"),
)

COMPOSITE_PUSH_ACTION_COUNT = Counter(
    name="bkmonitor_composite_push_action_count",
    documentation="composite 模块动作推送条数",
    labelnames=("strategy_id", "signal", "is_qos", "status"),
)

COMPOSITE_PUSH_EVENT_COUNT = Counter(
    name="bkmonitor_composite_push_event_count",
    documentation="composite 模块事件推送条数",
    labelnames=("strategy_id", "signal"),
)

# converge
CONVERGE_PROCESS_TIME = Histogram(
    name="bkmonitor_converge_process_time",
    documentation="converge 模块处理耗时",
    labelnames=(
        "bk_biz_id",
        "strategy_id",
        "instance_type",
    ),
)

CONVERGE_PROCESS_COUNT = Counter(
    name="bkmonitor_converge_process_count",
    documentation="converge 模块处理次数",
    labelnames=("bk_biz_id", "strategy_id", "instance_type", "status", "exception"),
)

CONVERGE_PUSH_CONVERGE_COUNT = Counter(
    name="bkmonitor_converge_push_converge_count",
    documentation="converge 模块收敛记录推送条数",
    labelnames=("bk_biz_id", "instance_type"),
)

CONVERGE_PUSH_ACTION_COUNT = Counter(
    name="bkmonitor_converge_push_action_count",
    documentation="converge 模块动作记录推送条数",
    labelnames=("bk_biz_id", "plugin_type", "strategy_id", "signal"),
)

# assign
ALERT_ASSIGN_PROCESS_TIME = Histogram(
    name="bkmonitor_alert_assign_process_time",
    documentation="分派处理耗时",
    labelnames=("bk_biz_id", "assign_type", "alert_source", "notice_type"),
)

ALERT_ASSIGN_PROCESS_COUNT = Counter(
    name="bkmonitor_alert_assign_process_count",
    documentation="分派处理数量",
    labelnames=("bk_biz_id", "rule_group_id", "assign_type", "alert_source", "notice_type", "status"),
)

# action
ACTION_CREATE_PROCESS_TIME = Histogram(
    name="bkmonitor_action_create_process_time",
    documentation="action 模块动作创建耗时",
    labelnames=("strategy_id", "signal", "run_type", "notice_type"),
)

ACTION_CREATE_PROCESS_COUNT = Counter(
    name="bkmonitor_action_create_process_count",
    documentation="action 模块动作创建次数",
    labelnames=("strategy_id", "signal", "run_type", "status", "exception", "notice_type"),
)

ACTION_CREATE_PUSH_COUNT = Counter(
    name="bkmonitor_action_create_push_count",
    documentation="action 模块数据推送条数",
    labelnames=("strategy_id", "signal", "run_type", "notice_type"),
)

ACTION_EXECUTE_TIME = Histogram(
    name="bkmonitor_action_execute_time",
    documentation="action 模块动作执行耗时",
    labelnames=("bk_biz_id", "plugin_type", "strategy_id", "signal"),
)

ACTION_EXECUTE_COUNT = Counter(
    name="bkmonitor_action_execute_count",
    documentation="action 模块动作执行次数",
    labelnames=("bk_biz_id", "plugin_type", "strategy_id", "signal", "status", "exception"),
)

ACTION_EXECUTE_STATUS_COUNT = Counter(
    name="bkmonitor_action_execute_status_count",
    documentation="action 执行结果",
    labelnames=("bk_biz_id", "plugin_type", "strategy_id", "signal", "status", "failure_type"),
)

ACTION_EXECUTE_LATENCY = Histogram(
    name="bkmonitor_action_execute_latency",
    documentation="动作从 alert 到 action 模块的整体执行延迟",
    labelnames=("bk_biz_id", "plugin_type", "strategy_id", "signal"),
    buckets=(1, 2, 3, 5, 10, 15, 20, 30, 60, 180, 300, INF),
)

ACTION_NOTICE_API_CALL_COUNT = Counter(
    name="bkmonitor_action_notice_api_call_count",
    documentation="通知类 API 调用次数",
    labelnames=("notice_way", "status"),
)

# cache
ALARM_CACHE_TASK_TIME = Histogram(
    name="bkmonitor_alarm_cache_task_time",
    documentation="数据缓存任务执行耗时",
    labelnames=("bk_biz_id", "type", "exception"),
    buckets=(1, 3, 5, 10, 30, 60, 300, INF),
)

# mail report
MAIL_REPORT_SEND_LATENCY = Histogram(
    name="bkmonitor_mail_report_send_latency",
    documentation="邮件订阅报表发送延迟",
    labelnames=("item_id",),
    buckets=(10, 30, 60, 120, 180, 240, 300, 450, 600, 900, 1800, INF),
)

MAIL_REPORT_SEND_COUNT = Counter(
    name="bkmonitor_mail_report_send_count",
    documentation="邮件订阅报表发送数量",
    labelnames=("item_id", "status", "exception"),
)

CELERY_TASK_EXECUTE_TIME = Histogram(
    name="bkmonitor_celery_task_execute_time",
    documentation="celery 任务执行耗时",
    labelnames=("task_name", "queue", "exception"),
    buckets=(0.1, 0.5, 1, 3, 5, 10, 30, 60, 300, 1800, INF),
)


ALARM_CONTEXT_GET_FIELD_TIME = Histogram(
    name="bkmonitor_alarm_context_get_field_time",
    documentation="处理套餐上下文字段获取耗时",
    labelnames=("field", "exception"),
)

# redis 指标
ACTIVE_DEFRAG_RUNNING = Gauge(
    name="redis_active_defrag_running",
    documentation="Automatic memory defragmentation current aggressiveness (% cpu)",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

AOF_CURRENT_REWRITE_DURATION_SEC = Gauge(
    name="redis_aof_current_rewrite_duration_sec",
    documentation="Duration of the on-going AOF rewrite operation if any",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

AOF_ENABLED = Gauge(
    name="redis_aof_enabled",
    documentation="是否开启aof，默认没开启",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

AOF_LAST_BGREWRITE_STATUS = Gauge(
    name="redis_aof_last_bgrewrite_status",
    documentation="Status of the last AOF rewrite operation",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

AOF_LAST_COW_SIZE_BYTES = Gauge(
    name="redis_aof_last_cow_size_bytes",
    documentation="The size in bytes of copy-on-write memory during the last AOF rewrite operation",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

AOF_LAST_REWRITE_DURATION_SEC = Gauge(
    name="redis_aof_last_rewrite_duration_sec",
    documentation="Duration of the last AOF rewrite operation in seconds",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

AOF_LAST_WRITE_STATUS = Gauge(
    name="redis_aof_last_write_status",
    documentation="Status of the last write operation to the AOF",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

AOF_REWRITE_IN_PROGRESS = Gauge(
    name="redis_aof_rewrite_in_progress",
    documentation="Flag indicating a AOF rewrite operation is on-going",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

AOF_REWRITE_SCHEDULED = Gauge(
    name="redis_aof_rewrite_scheduled",
    documentation="Flag indicating an AOF rewrite operation will be scheduled once the on-going RDB save is complete",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

CLUSTER_ENABLED = Gauge(
    name="redis_cluster_enabled",
    documentation="Indicate Redis cluster is enabled",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

COMMANDS_DURATION_SECONDS_TOTAL = Gauge(
    name="redis_commands_duration_seconds_total",
    documentation="How many seconds spend on processing Redis commands",
    labelnames=("node", "role", "cmd", "host", "port", "cluster_name"),
)

COMMANDS_PROCESSED_TOTAL = Gauge(
    name="redis_commands_processed_total",
    documentation="How many commands processed by Redis",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

COMMANDS_TOTAL = Gauge(
    name="redis_commands_total",
    documentation="Total number of calls per command",
    labelnames=("node", "role", "cmd", "host", "port", "cluster_name"),
)

CONFIG_MAXCLIENTS = Gauge(
    name="redis_config_maxclients",
    documentation="Maximum client number for Redis",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

CONFIG_MAXMEMORY = Gauge(
    name="redis_config_maxmemory",
    documentation="The value of the maxmemory configuration directive",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

CONNECTIONS_RECEIVED_TOTAL = Gauge(
    name="redis_connections_received_total",
    documentation="Total number of connections accepted by the server",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

CPU_SYS_CHILDREN_SECONDS_TOTAL = Gauge(
    name="redis_cpu_sys_children_seconds_total",
    documentation="System CPU consumed by the background processes",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

CPU_SYS_SECONDS_TOTAL = Gauge(
    name="redis_cpu_sys_seconds_total",
    documentation="System CPU consumed by the Redis server, which is the sum of system CPU consumed "
    "by all threads of the server process (main thread and background threads)",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

CPU_USER_CHILDREN_SECONDS_TOTAL = Gauge(
    name="redis_cpu_user_children_seconds_total",
    documentation="User CPU consumed by the background processes",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

CPU_USER_SECONDS_TOTAL = Gauge(
    name="redis_cpu_user_seconds_total",
    documentation="User CPU consumed by the Redis server, which is the sum of user CPU consumed "
    "by all threads of the server process (main thread and background threads)",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

DB_AVG_TTL_SECONDS = Gauge(
    name="redis_db_avg_ttl_seconds",
    documentation="Avg TTL in seconds",
    labelnames=("node", "role", "db", "host", "port", "cluster_name"),
)

DEFRAG_HITS = Gauge(
    name="redis_defrag_hits",
    documentation="Number of value reallocations performed by active the defragmentation process",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

DEFRAG_KEY_HITS = Gauge(
    name="redis_defrag_key_hits",
    documentation="Number of keys that were actively defragmented",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

DEFRAG_KEY_MISSES = Gauge(
    name="redis_defrag_key_misses",
    documentation="Number of keys that were skipped by the active defragmentation process",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

DEFRAG_MISSES = Gauge(
    name="redis_defrag_misses",
    documentation="Number of aborted value reallocations started by the active defragmentation process",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

EVICTED_KEYS_TOTAL = Gauge(
    name="redis_evicted_keys_total",
    documentation="Number of evicted keys due to maxmemory limit in Redis",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

EXPIRED_KEYS_TOTAL = Gauge(
    name="redis_expired_keys_total",
    documentation="number of keys that has expired",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

EXPIRED_STALE_PERCENTAGE = Gauge(
    name="redis_expired_stale_percentage",
    documentation="The percentage of keys probably expired",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

EXPIRED_TIME_CAP_REACHED_TOTAL = Gauge(
    name="redis_expired_time_cap_reached_total",
    documentation="The count of times that active expiry cycles have stopped early",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

EXPORTER_BUILD_INFO = Gauge(
    name="redis_exporter_build_info",
    documentation="redis exporter build_info",
    labelnames=("node", "role", "commit_sha", "version", "build_date", "host", "port", "cluster_name"),
)

EXPORTER_LAST_SCRAPE_CONNECT_TIME_SECONDS = Gauge(
    name="redis_exporter_last_scrape_connect_time_seconds",
    documentation="The duration(in seconds) to connect when scrape",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

EXPORTER_LAST_SCRAPE_DURATION_SECONDS = Gauge(
    name="redis_exporter_last_scrape_duration_seconds",
    documentation="The last scrape duration",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

EXPORTER_LAST_SCRAPE_ERROR = Gauge(
    name="redis_exporter_last_scrape_error",
    documentation="The last scrape error status",
    labelnames=("node", "err", "host", "port", "cluster_name"),
)

EXPORTER_SCRAPE_DURATION_SECONDS_SUM = Gauge(
    name="redis_exporter_scrape_duration_seconds_sum",
    documentation="Durations of scrapes by the exporter",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

EXPORTER_SCRAPE_DURATION_SECONDS_COUNT = Gauge(
    name="redis_exporter_scrape_duration_seconds_count",
    documentation="Durations of scrapes by the exporter",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

EXPORTER_SCRAPES_TOTAL = Gauge(
    name="redis_exporter_scrapes_total",
    documentation="Current total redis scrapes",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

INSTANCE_INFO = Gauge(
    name="redis_instance_info",
    documentation="Information about the Redis instance",
    labelnames=(
        "node_type",
        "mastername",
        "role",
        "os",
        "redis_version",
        "redis_build_id",
        "maxmemory_policy",
        "run_id",
        "tcp_port",
        "redis_mode",
        "process_id",
        "host",
        "port",
        "cluster_name",
    ),
)

KEYSPACE_HITS_TOTAL = Gauge(
    name="redis_keyspace_hits_total",
    documentation="Number of successful lookup of keys in Redis",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

KEYSPACE_MISSES_TOTAL = Gauge(
    name="redis_keyspace_misses_total",
    documentation="Number of failed lookup of keys in Redis",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

LAST_KEY_GROUPS_SCRAPE_DURATION_MILLISECONDS = Gauge(
    name="redis_last_key_groups_scrape_duration_milliseconds",
    documentation="Duration of the last key group metrics scrape in milliseconds",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

LAST_SLOW_EXECUTION_DURATION_SECONDS = Gauge(
    name="redis_last_slow_execution_duration_seconds",
    documentation="The amount of time needed for last slow execution, in seconds",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

LATEST_FORK_SECONDS = Gauge(
    name="redis_latest_fork_seconds",
    documentation="The amount of time needed for last fork, in seconds",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

LAZYFREE_PENDING_OBJECTS = Gauge(
    name="redis_lazyfree_pending_objects",
    documentation="The number of objects waiting to be freed (as a result of calling UNLINK, "
    "or FLUSHDB and FLUSHALL with the ASYNC option)",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

LOADING_DUMP_FILE = Gauge(
    name="redis_loading_dump_file",
    documentation="loading dump file",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

MEMORY_MAX_BYTES = Gauge(
    name="redis_memory_max_bytes",
    documentation="The value of the Redis maxmemory configuration directive",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

MEMORY_USED_BYTES = Gauge(
    name="redis_memory_used_bytes",
    documentation="Total number of bytes allocated by Redis using its allocator",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

MEMORY_USED_DATASET_BYTES = Gauge(
    name="redis_memory_used_dataset_bytes",
    documentation="The size in bytes of the dataset (used_memory_overhead subtracted from used_memory)",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

MEMORY_USED_LUA_BYTES = Gauge(
    name="redis_memory_used_lua_bytes",
    documentation="Number of bytes used by the Lua engine",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

MEMORY_USED_OVERHEAD_BYTES = Gauge(
    name="redis_memory_used_overhead_bytes",
    documentation="The sum in bytes of all overheads that the server allocated "
    "for managing its internal data structures",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

MEMORY_USED_PEAK_BYTES = Gauge(
    name="redis_memory_used_peak_bytes",
    documentation="Peak memory consumed by Redis (in bytes)",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

MEMORY_USED_RSS_BYTES = Gauge(
    name="redis_memory_used_rss_bytes",
    documentation="Number of bytes that Redis allocated as seen by the operating system (a.k.a resident set size). "
    "This is the number reported by tools such as top(1) and ps(1)",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

MEMORY_USED_STARTUP_BYTES = Gauge(
    name="redis_memory_used_startup_bytes",
    documentation="Initial amount of memory consumed by Redis at startup in bytes",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

MIGRATE_CACHED_SOCKETS_TOTAL = Counter(
    name="redis_migrate_cached_sockets_total",
    documentation="The number of sockets open for MIGRATE purposes",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

NET_INPUT_BYTES_TOTAL = Gauge(
    name="redis_net_input_bytes_total",
    documentation="Total input bytes",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

NET_OUTPUT_BYTES_TOTAL = Gauge(
    name="redis_net_output_bytes_total",
    documentation="Total output bytes",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

PROCESS_ID = Gauge(
    name="redis_process_id",
    documentation="Process ID",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

RDB_BGSAVE_IN_PROGRESS = Gauge(
    name="redis_rdb_bgsave_in_progress",
    documentation="Flag indicating a RDB save is on-going",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

RDB_CURRENT_BGSAVE_DURATION_SEC = Gauge(
    name="redis_rdb_current_bgsave_duration_sec",
    documentation="Duration of the on-going RDB save operation if any",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

RDB_LAST_BGSAVE_DURATION_SEC = Gauge(
    name="redis_rdb_last_bgsave_duration_sec",
    documentation="Duration of the last RDB save operation in seconds",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

RDB_LAST_BGSAVE_STATUS = Gauge(
    name="redis_rdb_last_bgsave_status",
    documentation="Status of the last RDB save operation",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

RDB_LAST_COW_SIZE_BYTES = Gauge(
    name="redis_rdb_last_cow_size_bytes",
    documentation="The size in bytes of copy-on-write memory during the last RDB save operation",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

RDB_LAST_SAVE_TIMESTAMP_SECONDS = Gauge(
    name="redis_rdb_last_save_timestamp_seconds",
    documentation="Epoch-based timestamp of last successful RDB save",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

REJECTED_CONNECTIONS_TOTAL = Gauge(
    name="redis_rejected_connections_total",
    documentation="Number of connections rejected by Redis",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

REPL_BACKLOG_FIRST_BYTE_OFFSET = Gauge(
    name="redis_repl_backlog_first_byte_offset",
    documentation="The master offset of the replication backlog buffer",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

REPL_BACKLOG_HISTORY_BYTES = Gauge(
    name="redis_repl_backlog_history_bytes",
    documentation="Size in bytes of the data in the replication backlog buffer",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

REPL_BACKLOG_IS_ACTIVE = Gauge(
    name="redis_repl_backlog_is_active",
    documentation="Flag indicating replication backlog is active",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

REPLICA_PARTIAL_RESYNC_ACCEPTED = Gauge(
    name="redis_replica_partial_resync_accepted",
    documentation="The number of accepted partial resync requests",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

REPLICA_PARTIAL_RESYNC_DENIED = Gauge(
    name="redis_replica_partial_resync_denied",
    documentation="The number of denied partial resync requests",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

REPLICA_RESYNCS_FULL = Gauge(
    name="redis_replica_resyncs_full",
    documentation="The number of full resyncs with replicas",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

REPLICATION_BACKLOG_BYTES = Gauge(
    name="redis_replication_backlog_bytes",
    documentation="Memory used by replication backlog",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

SECOND_REPL_OFFSET = Gauge(
    name="redis_second_repl_offset",
    documentation="The offset up to which replication IDs are accepted",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

SLAVE_EXPIRES_TRACKED_KEYS = Gauge(
    name="redis_slave_expires_tracked_keys",
    documentation="The number of keys tracked for expiry purposes (applicable only to writable replicas)",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

SLOWLOG_LAST_ID = Gauge(
    name="redis_slowlog_last_id",
    documentation="Last id of slowlog",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

SLOWLOG_LENGTH = Gauge(
    name="redis_slowlog_length",
    documentation="Number of of entries in the Redis slow log",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

START_TIME_SECONDS = Gauge(
    name="redis_start_time_seconds",
    documentation="Start time of the Redis instance since unix epoch in seconds",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

TARGET_SCRAPE_REQUEST_ERRORS_TOTAL = Gauge(
    name="redis_target_scrape_request_errors_total",
    documentation="Errors in requests to the exporter",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

UP = Gauge(
    name="redis_up",
    documentation="Information about the Redis instance",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

CONNECTED_CLIENTS = Gauge(
    name="Redis_connected_clients",
    documentation="Number of client connections (excluding connections from slaves)",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

CLIENT_LONGEST_OUTPUT_LIST = Gauge(
    name="redis_client_longest_output_list",
    documentation="当前客户端连接最大输出列表",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

CLIENT_BIGGEST_INPUT_BUF = Gauge(
    name="redis_client_biggest_input_buf",
    documentation="客户端最大输入缓存",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

BLOCKED_CLIENTS = Gauge(
    name="redis_blocked_clients",
    documentation="被阻塞的客户端数",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

MEM_FRAGMENTATION_RATIO = Gauge(
    name="redis_mem_fragmentation_ratio",
    documentation="内存碎片率",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

AOF_BUFFER_LENGTH = Gauge(
    name="redis_aof_buffer_length",
    documentation="aof缓冲区的大小",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

AOF_REWRITE_BUFFER_LENGTH = Gauge(
    name="redis_aof_rewrite_buffer_length",
    documentation="rewrite缓冲区大小",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

AOF_CURRENT_SIZE = Gauge(
    name="redis_aof_current_size",
    documentation="aof当前文件大小",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

RDB_CHANGES_SINCE_LAST_SAVE = Gauge(
    name="redis_rdb_changes_since_last_save",
    documentation="最近生成rdb文件后写入命令的个数",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

PUBSUB_CHANNELS = Gauge(
    name="redis_pubsub_channels",
    documentation="当前发布/订阅频道量",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

PUBSUB_PATTERNS = Gauge(
    name="redis_pubsub_patterns",
    documentation="当前发布/订阅模式数",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

CONNECTED_SLAVES = Gauge(
    name="redis_connected_slaves",
    documentation="已连接slave实例数",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

CONNECTED_SLAVE_OFFSET_BYTES = Gauge(
    name="redis_connected_slave_offset_bytes",
    documentation="slave的偏移量",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

CONNECTED_SLAVE_LAG_SECONDS = Gauge(
    name="redis_connected_slave_lag_seconds",
    documentation="从机的延迟时长",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

MASTER_REPL_OFFSET = Gauge(
    name="redis_master_repl_offset",
    documentation="master的偏移量",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

MASTER_LAST_IO_SECONDS_AGO = Gauge(
    name="redis_master_last_io_seconds_ago",
    documentation="master延迟复制时长差值",
    labelnames=("node", "role", "host", "port", "cluster_name"),
)

DB_KEYS = Gauge(
    name="redis_db_keys",
    documentation="key总数",
    labelnames=("node", "role", "db", "host", "port", "cluster_name"),
)

DB_KEYS_EXPIRING = Gauge(
    name="redis_db_keys_expiring",
    documentation="设置了ttl的 key 数量",
    labelnames=("node", "role", "db", "host", "port", "cluster_name"),
)

API_FAILED_REQUESTS_TOTAL = Counter(
    name="bkmonitor_api_failed_requests_total",
    documentation="API调用失败计数",
    labelnames=("action", "module", "code", "role", "exception", "user_name"),
)

AIOPS_ACCESS_TASK_COUNT = Gauge(
    name="bkmonitor_aiops_access_task_count",
    documentation="智能监控接入任务执行",
    labelnames=(
        "bk_biz_id",
        "strategy_id",
        "algorithm",
        "data_source_label",
        "data_type_label",
        "metric_id",
        "task_id",
        "result",
        "retries",
        "exception",
        "exc_type",
    ),
)

AIOPS_STRATEGY_CHECK = Gauge(
    name="bkmonitor_aiops_strategy_check",
    documentation="智能监控策略巡检",
    labelnames=(
        "bk_biz_id",
        "strategy_id",
        "algorithm",
        "data_source_label",
        "data_type_label",
        "metric_id",
        "flow_id",
        "status",
        "exception",
        "exc_type",
    ),
)

AIOPS_STRATEGY_ERROR_COUNT = Counter(
    name="bkmonitor_aiops_strategy_error_count",
    documentation="智能监控策略错误统计数",
    labelnames=("exc_type",),
)

METADATA_DATA_LINK_STATUS_INFO = Gauge(
    name="bkmonitor_metadata_data_link_info",
    documentation="监控元数据数据链路状态统计",
    labelnames=("data_link_name", "biz_id", "kind"),
)

METADATA_CRON_TASK_COST_SECONDS = Histogram(
    name="bkmonitor_metadata_cron_task_cost_seconds",
    documentation="监控元数据定时任务耗时统计",
    labelnames=("task_name", "process_target"),
    buckets=(0, 1, 5, 10, 30, 60, 120, 180, 240, 300, 600, 900, 1800, 3000, 6000, INF),
)

METADATA_CRON_TASK_STATUS_TOTAL = Counter(
    name="bkmonitor_metadata_cron_task_status_total",
    documentation="监控元数据定时任务状态统计",
    labelnames=("task_name", "status", "process_target"),
)

METADATA_DATA_LINK_ACCESS_TOTAL = Counter(
    name="bkmonitor_metadata_data_link_access_total",
    documentation="监控元数据数据链路接入统计",
    labelnames=("version", "biz_id", "strategy", "status"),
)

API_REQUESTS_TOTAL = Counter(
    name="bkmonitor_api_requests_total",
    documentation="三方APi调用统计",
    labelnames=("action", "module", "code", "role"),
)

AI_AGENTS_REQUESTS_TOTAL = Counter(
    name="ai_agents_requests_total",
    documentation="AI小鲸服务调用统计",
    labelnames=("agent_code", "resource_name", "status", "username", "command"),
)

MCP_REQUESTS_TOTAL = Counter(
    name="bkmonitor_mcp_requests_total",
    documentation="MCP工具调用统计",
    labelnames=("tool_name", "bk_biz_id", "username", "status", "permission_action"),
)

MCP_RESOURCE_REQUESTS_TOTAL = Counter(
    name="bkmonitor_mcp_resource_requests_total",
    documentation="MCP Resource调用统计",
    labelnames=("resource_name", "tool_name", "bk_biz_id", "username", "status", "exception_type", "has_data"),
)

MCP_RESOURCE_REQUESTS_COST_SECONDS = Histogram(
    name="bkmonitor_mcp_resource_requests_cost_seconds",
    documentation="MCP Resource调用耗时统计",
    labelnames=("resource_name", "tool_name", "bk_biz_id", "username", "status"),
    buckets=(0.1, 0.5, 1, 3, 5, 10, 30, 60, 300, INF),
)

AI_AGENTS_REQUESTS_COST_SECONDS = Gauge(
    name="ai_agents_requests_cost_seconds",
    documentation="AI小鲸服务调用耗时统计",
    labelnames=("agent_code", "resource_name", "status", "username", "command"),
)

LOG_INDEX_ROTATE_TOTAL = Counter(
    name="bkmonitor_log_index_rotate_total",
    documentation="日志索引轮转状态",
    labelnames=("table_id", "storage_cluster_id", "status"),
)

LOG_INDEX_ROTATE_REASON_TOTAL = Counter(
    name="bkmonitor_log_index_rotate_reason_total",
    documentation="日志索引轮转原因",
    labelnames=("table_id", "storage_cluster_id", "reason"),
)

TOTAL_TAG = "__total__"
