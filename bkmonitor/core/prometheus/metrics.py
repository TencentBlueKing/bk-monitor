# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
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

from core.prometheus.base import REGISTRY, BkCollectorRegistry, Counter, Histogram
from core.prometheus.tools import get_metric_agg_gateway_url, udp_handler

logger = logging.getLogger(__name__)


def report_all(job: str = settings.DEFAULT_METRIC_PUSH_JOB, registry: BkCollectorRegistry = REGISTRY):
    """
    批量上报指标
    """
    if not get_metric_agg_gateway_url():
        return
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

ALERT_PROCESS_COUNT = Counter(
    name="bkmonitor_alert_process_count",
    documentation="alert(builder) 模块处理次数",
    labelnames=("status", "exception"),
)

ALERT_POLLER_TIME = Histogram(
    name="bkmonitor_alert_poller_time",
    documentation="alert(builder) 模块拉取处理时间",
    labelnames=("bk_data_id",),
)

ALERT_POLLER_COUNT = Counter(
    name="bkmonitor_alert_poller_count",
    documentation="alert(builder) 模块拉取次数",
    labelnames=("bk_data_id", "status", "exception"),
)

ALERT_MANAGE_TIME = Histogram(
    name="bkmonitor_alert_manage_time",
    documentation="alert(manager) 模块处理耗时",
    labelnames=("status", "exception"),
)

ALERT_MANAGE_COUNT = Counter(
    name="bkmonitor_alert_manage_count",
    documentation="alert(manager) 模块处理次数",
    labelnames=("status", "exception"),
)

ALERT_PROCESS_PULL_EVENT_COUNT = Counter(
    name="bkmonitor_alert_process_pull_event_count",
    documentation="alert(builder) 模块事件拉取条数",
    labelnames=("bk_data_id", "topic"),
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

DETECT_PROCESS_LATENCY = Histogram(
    name="bkmonitor_detect_process_latency",
    documentation="告警从 access 到 detect 模块的整体处理延迟",
    labelnames=("strategy_id",),
    buckets=(1, 2, 3, 5, 10, 15, 20, 30, 60, 180, 300, INF),
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

Alert_QOS_COUNT = Counter(
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
    name="bkmonitor_alarm_context_get_field_time", documentation="处理套餐上下文字段获取耗时", labelnames=("field", "exception")
)

TOTAL_TAG = "__total__"
