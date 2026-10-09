"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

运营指标取数 handlers + 注册。

handler 统一签名：``handler(bk_biz_id: int, end_time: int | None = None) -> Any``。
- PromQL 类用 ``make_promql_handler`` 工厂；
- ORM / collector / API 类各写独立函数；
- 模型 / 可选 app 一律在函数内惰性 import，避免某些环境未安装对应 app 时模块加载失败。

口径全部来自《观测平台对外运营数据》表「统计方法」列。
"""

import time
from collections import defaultdict

from django.conf import settings

from core.drf_resource import api, resource
from core.drf_resource.base import logger

from .registry import (
    OPERATION_METRIC_REGISTRY,
    HandlerType,
    MetricCategory,
    OperationMetric,
    register_metric,
)

# ======================================================================================
# PromQL 执行
# ======================================================================================


def _resolve_query_biz_id(stat_source: str, fallback_biz_id: int) -> int:
    """解析查询某类平台统计指标应使用的业务 ID。

    平台统计指标（bkm_statistics / vm / bkunifylogbeat 等）上报在特定业务下，需用该业务 ID 查询；
    各业务 ID 因环境而异，从 settings 读（均未配置时回退到调用方 bk_biz_id）：
      OPERATION_MCP_STAT_BIZ_IDS   = {"default": <主统计业务>, "vm": <VM业务>, "logbeat": <日志采集业务>, ...}
      OPERATION_MCP_PLATFORM_BIZ_ID = <主统计业务>（stat_map 未命中时兜底）
    """
    stat_map = getattr(settings, "OPERATION_MCP_STAT_BIZ_IDS", None) or {}
    biz_id = stat_map.get(stat_source) or getattr(settings, "OPERATION_MCP_PLATFORM_BIZ_ID", 0)
    return int(biz_id or fallback_biz_id)


def _run_promql(
    bk_biz_id: int,
    promql: str,
    stat_source: str = "default",
    end_time: int | None = None,
    lookback: int = 300,
    step: str = "1m",
):
    """执行一段 PromQL 并归约为"最新标量值"。

    平台统计指标上报在特定业务下，统一用 ``graph_promql_query(bk_biz_id=<统计业务>)`` 查询，
    统计业务 ID 由 stat_source 经 settings 解析（见 _resolve_query_biz_id）；
    返回 series[*].datapoints = [[value, ts], ...]，取最后一个点的 value。
    """
    end_time = int(end_time or time.time())
    start_time = end_time - lookback
    query_biz_id = _resolve_query_biz_id(stat_source, bk_biz_id)
    data = resource.grafana.graph_promql_query(
        bk_biz_id=query_biz_id,
        promql=promql,
        start_time=start_time,
        end_time=end_time,
        step=step,
        type="instant",
        time_alignment=False,
    )
    for series in data.get("series") or []:
        datapoints = series.get("datapoints") or []
        if datapoints:
            return datapoints[-1][0]
    return None


def make_promql_handler(promql: str, stat_source: str = "default"):
    def handler(bk_biz_id: int, end_time: int | None = None):
        return _run_promql(bk_biz_id, promql, stat_source=stat_source, end_time=end_time)

    return handler


# ======================================================================================
# ORM / collector 类
# ======================================================================================


def ascode_biz_count(bk_biz_id: int, end_time: int | None = None):
    """As Code 业务数：配置了 as-code（hash 非空）策略的业务个数。"""
    from django.db.models import Count

    from bkmonitor.models import StrategyModel

    return (
        StrategyModel.objects.exclude(hash="")
        .filter(bk_biz_id__gt=0)
        .values("bk_biz_id")
        .annotate(count=Count("bk_biz_id"))
        .count()
    )


def custom_metric_biz_count(bk_biz_id: int, end_time: int | None = None):
    """自定义指标上报业务数。"""
    from django.db.models import Count

    from monitor_web.models import CustomTSTable

    return CustomTSTable.objects.filter(bk_biz_id__gt=0).values("bk_biz_id").annotate(count=Count("bk_biz_id")).count()


# 注意：以下日志相关指标依赖日志平台(bk-log) 的模型（apps.log_search / apps.log_clustering），
# 这些模型不在 bk-monitor 进程内，无法在本 MCP 直接 ORM 取数，已登记为 MANUAL（见 register_all_metrics）：
#   - log_space_count          有日志的空间数
#   - doris_access_biz_count   doris 接入业务量
#   - log_clustering_index_count 日志聚类接入索引数
# 如需程序化，应在日志平台侧提供 operation MCP / API，或经 api.log_search 聚合。


# -------- APM --------


def _apm_enabled_apps():
    """有数据的 APM 应用（trace/log/metric/profiling 任一 normal）。"""
    from django.db.models import Q

    from apm_web.models import Application

    return list(
        Application.objects.filter(
            Q(is_enabled=True)
            & (
                Q(trace_data_status="normal")
                | Q(log_data_status="normal")
                | Q(metric_data_status="normal")
                | Q(profiling_data_status="normal")
            )
        )
    )


def apm_biz_application_count(bk_biz_id: int, end_time: int | None = None):
    """APM 应用数（业务空间，bk_biz_id > 0）。"""
    return len([app for app in _apm_enabled_apps() if app.bk_biz_id > 0])


def apm_not_biz_application_count(bk_biz_id: int, end_time: int | None = None):
    """APM 应用数（非业务空间，bk_biz_id < 0）。"""
    return len([app for app in _apm_enabled_apps() if app.bk_biz_id < 0])


def apm_service_count(bk_biz_id: int, end_time: int | None = None):
    """APM 服务数（拓扑节点数）。"""
    from apm.models import TopoNode

    return TopoNode.objects.count()


def apm_profiling_application_count(bk_biz_id: int, end_time: int | None = None):
    """Profiling 开启的应用数。"""
    from apm_web.models import Application

    return Application.objects.filter(profiling_data_status="normal").count()


def ebpf_biz_count(bk_biz_id: int, end_time: int | None = None):
    """eBPF 业务数：已安装 eBPF 采集组件的业务数。"""
    from apm_ebpf.models import DeepflowWorkload

    return len({i.bk_biz_id for i in DeepflowWorkload.objects.all() if i.bk_biz_id > 0})


def ebpf_k8s_cluster_count(bk_biz_id: int, end_time: int | None = None):
    """eBPF K8S 集群数：已安装 eBPF 采集组件的集群数。"""
    from apm_ebpf.models import DeepflowWorkload

    return len({i.cluster_id for i in DeepflowWorkload.objects.all()})


# 注意：监控核数(monitor_core_count) = 统计 system.cpu_detail 全平台 idle 序列数，
# 该查询命中序列数 >50w，会触发 VictoriaMetrics 的 maxUniqueTimeseries(500000) 限制而失败，
# 无法经本 MCP 在线取数，已登记为 MANUAL；运维侧用 vmui 的 cardinality 工具查看。


# ======================================================================================
# API 类（bkdata / metadata / aiops / resource）
# ======================================================================================


def _bkdata_distinct_over_days(sql_tmp: str, field: str, days: int = 30) -> set:
    """按天循环执行 bkdata SQL，汇总某字段的去重集合（口径同 Excel：近 30 天滑窗）。"""
    import datetime

    now = datetime.datetime.now()
    until = now.strftime("%Y%m%d")
    values: set = set()
    for i in range(days):
        _from = (now - datetime.timedelta(days=i + 1)).strftime("%Y%m%d")
        sql = sql_tmp.format(_from=_from, until=until)
        ret = api.bkdata.query_data(sql=sql)
        for item in ret.get("list") or []:
            value = item.get(field)
            if value is not None:
                values.add(value)
        until = _from
    return values


def _frontend_event_config() -> tuple[str, str]:
    """前端埋点事件表与 target（部署相关，从 settings 读，避免在开源代码中硬编码内部标识）。

    部署方在 settings 配置：
      OPERATION_MCP_FRONTEND_EVENT_TABLE  = "<bkdata 前端埋点结果表>"
      OPERATION_MCP_FRONTEND_EVENT_TARGET = "<埋点 target 取值>"
    未配置则月活 / 活跃业务 / 活跃部门返回 None。
    """
    table = getattr(settings, "OPERATION_MCP_FRONTEND_EVENT_TABLE", "") or ""
    target = getattr(settings, "OPERATION_MCP_FRONTEND_EVENT_TARGET", "") or ""
    return table, target


def monthly_active_users(bk_biz_id: int, end_time: int | None = None):
    """月活跃用户数（近 30 天去重 user_name）。"""
    table, target = _frontend_event_config()
    if not table or not target:
        return None
    sql = (
        "SELECT distinct(user_name) FROM " + table + ".tspider "
        "WHERE thedate>='{_from}' AND thedate<='{until}' AND target='" + target + "' "
        "ORDER BY dtEventTime DESC LIMIT 1000"
    )
    return len(_bkdata_distinct_over_days(sql, "user_name"))


def active_biz_count(bk_biz_id: int, end_time: int | None = None):
    """活跃业务数（近 30 天去重 space_id 数）。"""
    table, target = _frontend_event_config()
    if not table or not target:
        return None
    sql = (
        "SELECT distinct(space_id) FROM " + table + ".tspider "
        "WHERE thedate>='{_from}' AND thedate<='{until}' AND target='" + target + "' "
        "ORDER BY dtEventTime DESC LIMIT 1000"
    )
    return len(_bkdata_distinct_over_days(sql, "space_id"))


def active_dept_count(bk_biz_id: int, end_time: int | None = None):
    """活跃用户部门数量（近 30 天去重的部门层级组合数）。"""
    import datetime

    table, target = _frontend_event_config()
    if not table or not target:
        return None
    sql_tmpl = (
        "SELECT distinct(`department_1`, `department_2`, `department_3`) as `new` "
        "FROM " + table + ".hdfs WHERE thedate='{_from}' AND target='" + target + "' LIMIT 1000"
    )
    now = datetime.datetime.now()
    depts: set = set()
    for i in range(30):
        _from = (now - datetime.timedelta(days=i + 1)).strftime("%Y%m%d")
        ret = api.bkdata.query_data(sql=sql_tmpl.format(_from=_from))
        for item in ret.get("list") or []:
            if item.get("new") is not None:
                depts.add(item["new"])
    return len(depts)


def _event_group_name_dict() -> dict:
    """聚合自定义上报事件分组（过滤 bcs/Log 内部分组、负业务）。"""
    event_group_list = api.metadata.query_event_group()
    event_name_dict: dict[str, int] = defaultdict(int)
    for event_group in event_group_list:
        if event_group["bk_biz_id"] < 0:
            continue
        name = event_group["event_group_name"]
        if name.startswith("bcs_BCS-K8S-") or name.startswith("Log_log_"):
            continue
        key = "{bk_biz_id}|{bk_data_id}".format(**event_group)
        event_name_dict[key] += len(event_group.get("event_info_list") or [])
    return event_name_dict


def custom_event_name_count(bk_biz_id: int, end_time: int | None = None):
    """自定义上报事件名称数。"""
    return sum(_event_group_name_dict().values())


def custom_event_biz_count(bk_biz_id: int, end_time: int | None = None):
    """自定义上报事件业务数。"""
    return len({key.split("|")[0] for key in _event_group_name_dict()})


def noise_reduction_ratio_1d(bk_biz_id: int, end_time: int | None = None):
    """降噪比(1d)：1 - 告警数 / 事件数。"""
    from bkmonitor.utils.user import set_local_username

    set_local_username(settings.COMMON_USERNAME)
    details = resource.home.statistics(page=0, days=1)["details"]
    event_total = sum(a["event"].get("count", 0) for a in details)
    if not event_total:
        return None
    alert_total = sum(a["alert"].get("count", 0) for a in details)
    return 1 - alert_total / event_total


def incident_count(bk_biz_id: int, end_time: int | None = None, days: int = 30):
    """故障数：近 N 天（默认 30 天）的故障数。

    复用 bk-monitor 自有的故障 ES 文档 IncidentDocument（索引 bkmonitor_aiops_incident_info），
    与 IncidentQueryHandler 同一数据源，无需外部 aiops 服务。
    """
    from bkmonitor.documents.incident import IncidentDocument

    end = int(end_time or time.time())
    start = end - days * 86400
    return IncidentDocument.search(start_time=start, end_time=end).count()


# ======================================================================================
# doris 存储量（按环境选择不同 PromQL）
# ======================================================================================


def doris_storage_used(bk_biz_id: int, end_time: int | None = None):
    """doris 存储量（字节）。集群域名因环境而异，PromQL 从 settings 读，避免在开源代码硬编码内部集群标识。

    部署方在 settings 配置（按环境给 PromQL，或直接给单条字符串）：
      OPERATION_MCP_DORIS_STORAGE_PROMQL = {"bkte": "<promql>", "sg": "<promql>"}
    未配置则返回 None；bkop 与上云共用存储集群，通常不单独统计。
    """
    promql_conf = getattr(settings, "OPERATION_MCP_DORIS_STORAGE_PROMQL", None) or {}
    if isinstance(promql_conf, str):
        promql = promql_conf
    else:
        env = getattr(settings, "OPERATION_MCP_ENV", None) or "bkte"
        promql = promql_conf.get(env)
    if not promql:
        return None
    return _run_promql(bk_biz_id, promql, stat_source="default", end_time=end_time)


# ======================================================================================
# 注册全部指标
# ======================================================================================


def log_query_api_count_1d(bk_biz_id: int, end_time: int | None = None):
    """日志查询量(API)。口径为 django_monitor 上报指标求和，指标名内含业务 ID（环境相关），
    PromQL 从 settings 读，避免在开源代码硬编码内部业务 ID。

    部署方在 settings 配置：OPERATION_MCP_LOG_QUERY_API_PROMQL = "<promql>"
    未配置则返回 None。
    """
    promql = getattr(settings, "OPERATION_MCP_LOG_QUERY_API_PROMQL", "") or ""
    if not promql:
        return None
    return _run_promql(bk_biz_id, promql, stat_source="default", end_time=end_time)


def register_all_metrics() -> None:
    """把全部运营指标注册到全局注册表（幂等）。"""
    if OPERATION_METRIC_REGISTRY:
        return

    metrics: list[OperationMetric] = [
        # ---------------- 基础监控（PromQL 平台总量） ----------------
        OperationMetric(
            key="host_count",
            category=MetricCategory.BASE,
            name="主机数",
            unit="台",
            description="Number of reporting hosts (NORMAL). 正常上报的主机数。",
            handler_type=HandlerType.PROMQL,
            handler=make_promql_handler('sum(bkmonitor:bkm_statistics:base:host_report_count{data_status="NORMAL"})'),
        ),
        OperationMetric(
            key="k8s_cluster_count",
            category=MetricCategory.BASE,
            name="k8s Cluster 数",
            unit="个",
            description="Number of k8s clusters. k8s 集群数。",
            handler_type=HandlerType.PROMQL,
            handler=make_promql_handler("sum(custom:bkm_statistics:base:k8s_cluster_count)"),
        ),
        OperationMetric(
            key="k8s_pod_count",
            category=MetricCategory.BASE,
            name="k8s Pod 数",
            unit="个",
            description="Number of k8s pods. k8s Pod 数。",
            handler_type=HandlerType.PROMQL,
            handler=make_promql_handler("sum(custom:bkm_statistics:base:k8s_pod_count)"),
        ),
        OperationMetric(
            key="grafana_dashboard_count",
            category=MetricCategory.BASE,
            name="仪表盘数",
            unit="个",
            description="Number of grafana dashboards. 仪表盘数。",
            handler_type=HandlerType.PROMQL,
            handler=make_promql_handler("sum(custom:bkm_statistics:base:grafana_dashboard_count)"),
        ),
        OperationMetric(
            key="grafana_dashboard_panel_count",
            category=MetricCategory.BASE,
            name="仪表盘视图数",
            unit="个",
            description="Number of grafana dashboard panels. 仪表盘视图（panel）数。",
            handler_type=HandlerType.PROMQL,
            handler=make_promql_handler("sum(custom:bkm_statistics:base:grafana_dashboard_panel_count)"),
        ),
        OperationMetric(
            key="strategy_enabled_count",
            category=MetricCategory.BASE,
            name="启用策略数",
            unit="个",
            description="Number of enabled alarm strategies. 启用状态的告警策略数。",
            handler_type=HandlerType.PROMQL,
            handler=make_promql_handler('sum(custom:bkm_statistics:base:strategy_count{status="enabled"})'),
        ),
        OperationMetric(
            key="action_config_enabled_count",
            category=MetricCategory.BASE,
            name="自愈套餐数",
            unit="个",
            description="Number of enabled action configs (fix-it packages). 启用的自愈套餐数。",
            handler_type=HandlerType.PROMQL,
            handler=make_promql_handler('sum(custom:bkm_statistics:base:action_config_count{status="enabled"})'),
        ),
        OperationMetric(
            key="action_count_1d",
            category=MetricCategory.BASE,
            name="日均自愈套餐执行次数",
            unit="次",
            description="Daily fix-it action executions (excluding notice). 日均自愈套餐执行次数（不含通知）。",
            handler_type=HandlerType.PROMQL,
            handler=make_promql_handler(
                'sum(custom:bkm_statistics:base:action_count{plugin_type!="notice",time_range="1d"})'
            ),
        ),
        OperationMetric(
            key="notice_count_1d",
            category=MetricCategory.BASE,
            name="告警通知数(所有渠道)",
            unit="次/天",
            description="Daily alarm notifications across all channels. 日均告警通知次数（所有渠道）。",
            handler_type=HandlerType.PROMQL,
            handler=make_promql_handler(
                'sum(custom:bkm_statistics:base:action_count{plugin_type="notice",time_range="1d"})'
            ),
        ),
        OperationMetric(
            key="alert_count_1d",
            category=MetricCategory.BASE,
            name="告警事件数",
            unit="次/天",
            description="Daily alert events. 日均告警事件数。",
            handler_type=HandlerType.PROMQL,
            handler=make_promql_handler('sum(custom:bkm_statistics:base:alert_count{time_range="1d"})'),
        ),
        OperationMetric(
            key="collect_plugin_count",
            category=MetricCategory.BASE,
            name="插件数",
            unit="个",
            description="Number of collect plugins. 采集插件数。",
            handler_type=HandlerType.PROMQL,
            handler=make_promql_handler("sum(custom:bkm_statistics:base:collect_plugin_count)"),
        ),
        OperationMetric(
            key="collect_config_instance_count",
            category=MetricCategory.BASE,
            name="插件采集实例数",
            unit="个",
            description="Number of collect config instances (CMDB instances). 插件采集实例数。",
            handler_type=HandlerType.PROMQL,
            handler=make_promql_handler("sum(custom:bkm_statistics:base:collect_config_instance_count)"),
        ),
        # ---------------- 基础监控（ORM / API） ----------------
        OperationMetric(
            key="ascode_biz_count",
            category=MetricCategory.BASE,
            name="As Code 业务数",
            unit="个业务",
            description="Number of biz using strategy as-code. 使用 As Code 策略的业务数。",
            handler_type=HandlerType.ORM,
            handler=ascode_biz_count,
        ),
        OperationMetric(
            key="custom_metric_biz_count",
            category=MetricCategory.BASE,
            name="自定义指标上报业务数",
            unit="业务",
            description="Number of biz reporting custom time-series metrics. 自定义指标上报业务数。",
            handler_type=HandlerType.ORM,
            handler=custom_metric_biz_count,
        ),
        OperationMetric(
            key="custom_event_name_count",
            category=MetricCategory.BASE,
            name="自定义上报事件名称数",
            unit="个",
            description="Number of custom reported event names. 自定义上报事件名称数。",
            handler_type=HandlerType.API,
            handler=custom_event_name_count,
        ),
        OperationMetric(
            key="custom_event_biz_count",
            category=MetricCategory.BASE,
            name="自定义上报事件业务数",
            unit="业务",
            description="Number of biz reporting custom events. 自定义上报事件业务数。",
            handler_type=HandlerType.API,
            handler=custom_event_biz_count,
        ),
        OperationMetric(
            key="noise_reduction_ratio_1d",
            category=MetricCategory.BASE,
            name="降噪比(1d)",
            unit="",
            description="Noise reduction ratio over 1d = 1 - alerts/events. 降噪比(1天)=1-告警数/事件数。",
            handler_type=HandlerType.API,
            handler=noise_reduction_ratio_1d,
        ),
        OperationMetric(
            key="monitor_core_count",
            category=MetricCategory.BASE,
            name="监控核数",
            unit="核",
            description="Monitored CPU cores via system.cpu_detail idle series count. 受监控 CPU 核数。",
            handler_type=HandlerType.MANUAL,
            note="全平台 cpu_detail idle 序列数 >50w，触发 VM maxUniqueTimeseries 限制无法在线查询；"
            '用 vmui cardinality 工具查看（match={__name__="idle_value", result_table_id="<env>_system_cpu_detail_raw"}）。',
        ),
        OperationMetric(
            key="monthly_active_users",
            category=MetricCategory.BASE,
            name="月活跃用户数",
            unit="人",
            description="Monthly active users (distinct user_name over 30d via bkdata). 月活跃用户数。",
            handler_type=HandlerType.API,
            handler=monthly_active_users,
            slow=True,
            cache_ttl=3600,
            note="bkdata 按天 30 次循环 SQL，较慢，已缓存 1h。需配置 "
            "OPERATION_MCP_FRONTEND_EVENT_TABLE / OPERATION_MCP_FRONTEND_EVENT_TARGET，未配置返回 null。",
        ),
        OperationMetric(
            key="active_biz_count",
            category=MetricCategory.BASE,
            name="活跃业务数",
            unit="个",
            description="Active businesses (distinct space_id over 30d via bkdata). 近 30 天活跃业务数。",
            handler_type=HandlerType.API,
            handler=active_biz_count,
            slow=True,
            cache_ttl=3600,
            note="bkdata 按天 30 次循环 SQL，较慢，已缓存 1h。需配置 "
            "OPERATION_MCP_FRONTEND_EVENT_TABLE / OPERATION_MCP_FRONTEND_EVENT_TARGET，未配置返回 null。",
        ),
        OperationMetric(
            key="active_dept_count",
            category=MetricCategory.BASE,
            name="活跃用户部门数量",
            unit="个",
            description="Distinct active org departments over 30d via bkdata. 近 30 天活跃用户部门数。",
            handler_type=HandlerType.API,
            handler=active_dept_count,
            slow=True,
            cache_ttl=3600,
            note="bkdata 按天 30 次循环 SQL，较慢，已缓存 1h。需配置 "
            "OPERATION_MCP_FRONTEND_EVENT_TABLE / OPERATION_MCP_FRONTEND_EVENT_TARGET，未配置返回 null。",
        ),
        # ---------------- 指标存储 ----------------
        # 说明：以下 vm_* 为 VictoriaMetrics 内部运维指标，不经普通业务空间路由暴露，
        # 本 MCP 的 PromQL 取数路径(graph_promql_query)查不到（实测各业务 series=0），登记为 MANUAL；
        # 请用 unify-query / vmstorage 运维仪表盘查看，note 中保留原 PromQL 供参考。
        OperationMetric(
            key="metric_daily_report_count",
            category=MetricCategory.STORAGE,
            name="日均指标上报数",
            unit="个",
            description="Estimated daily metric rows inserted. 日均指标上报数（按每分钟插入速率推算）。",
            handler_type=HandlerType.MANUAL,
            note="VM 内部指标，不经业务空间路由、本 MCP 查不到；运维仪表盘 PromQL："
            'sum(rate(vm_rows_inserted_total{job!="monitor-op-vminsert", type="influx"}[1m])) * 60 * 60 * 24',
        ),
        OperationMetric(
            key="metric_stored_count",
            category=MetricCategory.STORAGE,
            name="已有存储指标数",
            unit="个",
            description="Total stored metric rows (excluding indexdb). 已存储指标数。",
            handler_type=HandlerType.MANUAL,
            note='VM 内部指标，本 MCP 查不到；运维仪表盘 PromQL：sum(vm_rows{job!="monitor-op-vmstorage", type!~"indexdb.*"})',
        ),
        OperationMetric(
            key="series_daily_growth",
            category=MetricCategory.STORAGE,
            name="日均 Series 增长量",
            unit="个",
            description="Daily new time-series created. 日均新增时间序列数。",
            handler_type=HandlerType.MANUAL,
            note="VM 内部指标，本 MCP 查不到；运维仪表盘 PromQL："
            'sum(increase(vm_new_timeseries_created_total{job!="monitor-op-vmstorage"}[1d]))',
        ),
        OperationMetric(
            key="metric_storage_daily_growth_tb",
            category=MetricCategory.STORAGE,
            name="指标存储增长",
            unit="TB/天",
            description="Daily metric storage growth in TB. 日均指标存储增长量(TB)。",
            handler_type=HandlerType.MANUAL,
            note="VM 内部指标，本 MCP 查不到；运维仪表盘 PromQL："
            '(sum(vm_data_size_bytes{job!="monitor-op-vmstorage"}) - '
            'sum(vm_data_size_bytes{job!="monitor-op-vmstorage"} offset 24h)) / 1099511627776',
        ),
        OperationMetric(
            key="doris_storage_used",
            category=MetricCategory.STORAGE,
            name="doris 存储量",
            unit="byte",
            description="Doris BE local used capacity (bytes). doris 存储量（字节）。",
            handler_type=HandlerType.PROMQL,
            handler=doris_storage_used,
            supported_envs=["bkte", "sg"],
            note="集群域名因环境而异，需配置 OPERATION_MCP_DORIS_STORAGE_PROMQL（按环境给 PromQL），"
            "未配置返回 null；bkop 与上云共用存储集群通常不单独统计。",
        ),
        # ---------------- 观测能力 - APM ----------------
        OperationMetric(
            key="apm_biz_application_count",
            category=MetricCategory.APM,
            name="APM 应用数(业务)",
            unit="个",
            description="APM applications in business spaces (bk_biz_id>0) with data. 业务空间下有数据的 APM 应用数。",
            handler_type=HandlerType.ORM,
            handler=apm_biz_application_count,
        ),
        OperationMetric(
            key="apm_not_biz_application_count",
            category=MetricCategory.APM,
            name="APM 应用数(非业务空间)",
            unit="个",
            description="APM applications in non-business spaces (bk_biz_id<0) with data. 非业务空间下有数据的 APM 应用数。",
            handler_type=HandlerType.ORM,
            handler=apm_not_biz_application_count,
        ),
        OperationMetric(
            key="apm_service_count",
            category=MetricCategory.APM,
            name="APM 服务数",
            unit="个服务",
            description="APM service count (topology nodes). APM 服务数（拓扑节点）。",
            handler_type=HandlerType.ORM,
            handler=apm_service_count,
        ),
        OperationMetric(
            key="apm_profiling_application_count",
            category=MetricCategory.APM,
            name="Profiling 开启的应用数",
            unit="个",
            description="Applications with profiling enabled and data normal. 开启 Profiling 且有数据的应用数。",
            handler_type=HandlerType.ORM,
            handler=apm_profiling_application_count,
        ),
        OperationMetric(
            key="ebpf_biz_count",
            category=MetricCategory.APM,
            name="eBPF 业务数",
            unit="个",
            description="Businesses with eBPF collector installed. 已安装 eBPF 采集组件的业务数。",
            handler_type=HandlerType.ORM,
            handler=ebpf_biz_count,
            supported_envs=["bkte", "bkop"],
        ),
        OperationMetric(
            key="ebpf_k8s_cluster_count",
            category=MetricCategory.APM,
            name="eBPF K8S 集群数",
            unit="个",
            description="Clusters with eBPF collector installed. 已安装 eBPF 采集组件的集群数。",
            handler_type=HandlerType.ORM,
            handler=ebpf_k8s_cluster_count,
            supported_envs=["bkte", "bkop"],
        ),
        # ---------------- 观测能力 - 日志 ----------------
        OperationMetric(
            key="log_space_count",
            category=MetricCategory.LOG,
            name="有日志的空间数",
            unit="业务",
            description="Spaces with index set and data. 有索引集且有数据的空间数。",
            handler_type=HandlerType.MANUAL,
            note="依赖日志平台(bk-log) 模型 apps.log_search.LogIndexSet，不在 bk-monitor 进程内，"
            "需在日志平台侧取数：len(set(LogIndexSet.objects.exclude("
            'tag_ids__contains=f",{IndexSetTag.get_tag_id(\'no_data\')},").values_list("space_uid", flat=True)))',
        ),
        OperationMetric(
            key="doris_access_biz_count",
            category=MetricCategory.LOG,
            name="doris 接入业务量",
            unit="个",
            description="Spaces with doris-backed index set. 已接入 doris 的空间数。",
            handler_type=HandlerType.MANUAL,
            note="依赖日志平台(bk-log) 模型 apps.log_search.LogIndexSet，需在日志平台侧取数："
            'len(set(LogIndexSet.objects.exclude(doris_table_id__isnull=True).values_list("space_uid", flat=True)))',
        ),
        OperationMetric(
            key="log_collector_lines_per_min",
            category=MetricCategory.LOG,
            name="日志采集器行数",
            unit="条/分钟",
            description="Log collector received lines per minute (host + k8s). 日志采集器每分钟接收行数。",
            handler_type=HandlerType.PROMQL,
            handler=make_promql_handler(
                "sum(sum_over_time(custom:bkunifylogbeat_task:base:crawler_received[1m])) + "
                "sum(sum_over_time(custom:bkunifylogbeat_k8s_task:base:crawler_received[1m]))",
                stat_source="logbeat",
            ),
        ),
        OperationMetric(
            key="log_collect_host_count",
            category=MetricCategory.LOG,
            name="日志采集的主机数",
            unit="台",
            description="Hosts running log collector. 运行日志采集器的主机数。",
            handler_type=HandlerType.PROMQL,
            handler=make_promql_handler(
                "sum(count_over_time(custom:bkunifylogbeat_common:base:beat_memstats_rss[1m])) / 2",
                stat_source="logbeat",
            ),
        ),
        OperationMetric(
            key="container_log_node_count",
            category=MetricCategory.LOG,
            name="容器日志采集的节点数",
            unit="个",
            description="Nodes running container log collector. 运行容器日志采集的节点数。",
            handler_type=HandlerType.PROMQL,
            handler=make_promql_handler(
                "sum(count_over_time(custom:bkunifylogbeat_k8s_common:base:beat_memstats_rss[1m]))",
                stat_source="logbeat",
            ),
        ),
        OperationMetric(
            key="container_log_cluster_count",
            category=MetricCategory.LOG,
            name="容器日志采集的集群数",
            unit="个",
            description="Clusters running container log collector. 运行容器日志采集的集群数。",
            handler_type=HandlerType.PROMQL,
            handler=make_promql_handler(
                "count(sum by (k8s_cluster_id) "
                "(sum_over_time(custom:bkunifylogbeat_k8s_common:base:beat_memstats_rss[1m])))",
                stat_source="logbeat",
            ),
        ),
        OperationMetric(
            key="log_query_api_count_1d",
            category=MetricCategory.LOG,
            name="日志查询量(API)",
            unit="次/天",
            description="Daily log query count via API. 日均日志查询次数(API)。",
            handler_type=HandlerType.PROMQL,
            handler=log_query_api_count_1d,
            note="PromQL 因环境而异（指标名内含业务 ID），需配置 OPERATION_MCP_LOG_QUERY_API_PROMQL，未配置返回 null。",
        ),
        # ---------------- AIOps 能力 ----------------
        OperationMetric(
            key="aiops_biz_count",
            category=MetricCategory.AIOPS,
            name="智能监控业务数",
            unit="个",
            description="Businesses using aiops strategies. 使用智能监控策略的业务数。",
            handler_type=HandlerType.PROMQL,
            handler=make_promql_handler(
                'sum(bkmonitor:bkm_statistics:base:biz_usage_count{function="has_aiops_strategy"})'
            ),
        ),
        OperationMetric(
            key="aiops_strategy_count",
            category=MetricCategory.AIOPS,
            name="智能监控策略数",
            unit="个",
            description="Enabled aiops detection strategies. 启用的智能监控策略数。",
            handler_type=HandlerType.PROMQL,
            handler=make_promql_handler(
                "sum(custom:bkm_statistics:base:strategy_detect_algorithm_count"
                '{algorithm_type=~"^(AbnormalCluster|TimeSeriesForecasting|IntelligentDetect)$",'
                'status="enabled",valid_status="valid"})'
            ),
        ),
        OperationMetric(
            key="log_clustering_index_count",
            category=MetricCategory.AIOPS,
            name="日志聚类接入索引数",
            unit="个",
            description="Index sets with log clustering enabled and access finished. 日志聚类接入索引数。",
            handler_type=HandlerType.MANUAL,
            note="依赖日志平台(bk-log) 模型 apps.log_clustering.ClusteringConfig，不在 bk-monitor 进程内，"
            "需在日志平台侧取数：ClusteringConfig.objects.filter(signature_enable=True, access_finished=True).count()",
        ),
        OperationMetric(
            key="incident_count",
            category=MetricCategory.AIOPS,
            name="故障数",
            unit="个",
            description="Incident count in the last 30 days (bk-monitor IncidentDocument). 近 30 天故障数。",
            handler_type=HandlerType.API,
            handler=incident_count,
            note="复用 bk-monitor 自有故障 ES 文档 IncidentDocument(索引 bkmonitor_aiops_incident_info)，"
            "统计口径为近 30 天故障数；如需仅统计已定位根因，可在 ES 查询追加 snapshot 存在过滤。",
        ),
        OperationMetric(
            key="xiaojing_mau",
            category=MetricCategory.AIOPS,
            name="小鲸(监控入口)MAU",
            unit="人",
            description="Monthly active users of Xiaojing AI entry. 小鲸 AI 入口月活用户数。",
            handler_type=HandlerType.PROMQL,
            handler=make_promql_handler(
                "count(sum by (username) (count_over_time("
                'custom:custom_report_aggate:ai_agents_requests_total{resource_name="CreateChatCompletionResource"}[30d])))'
            ),
        ),
        # ---------------- 暂无法程序化（MANUAL，仅登记目录与口径） ----------------
        OperationMetric(
            key="biz_outside_space_active",
            category=MetricCategory.BASE,
            name="业务外空间(活跃)",
            unit="个",
            description="Active non-business spaces. 活跃的业务外空间数。",
            handler_type=HandlerType.MANUAL,
            note="由活跃 space_id 按前缀拆分得出，无独立程序化口径，需结合 active_biz_count 人工拆分。",
        ),
        OperationMetric(
            key="metric_query_count_page",
            category=MetricCategory.STORAGE,
            name="日均指标查询次数(页面)",
            unit="次/天",
            description="Daily metric queries from page. 日均指标查询次数(页面)。",
            handler_type=HandlerType.MANUAL,
            note="取自 unify-query Grafana 仪表盘，暂无程序化口径。",
        ),
        OperationMetric(
            key="metric_query_count_api",
            category=MetricCategory.STORAGE,
            name="日均指标查询次数(API)",
            unit="次/天",
            description="Daily metric queries from API. 日均指标查询次数(API)。",
            handler_type=HandlerType.MANUAL,
            note="取自 unify-query Grafana 仪表盘，暂无程序化口径。",
        ),
        OperationMetric(
            key="relation_instance_count",
            category=MetricCategory.STORAGE,
            name="关联关系实例数",
            unit="个",
            description="Relation instance count. 关联关系实例数。",
            handler_type=HandlerType.MANUAL,
            note="unify-query 代码本地执行脚本，暂未程序化。",
        ),
        OperationMetric(
            key="relation_edge_count",
            category=MetricCategory.STORAGE,
            name="关联关系边数",
            unit="条",
            description="Relation edge count. 关联关系边数。",
            handler_type=HandlerType.MANUAL,
            note="unify-query 代码本地执行脚本，暂未程序化。",
        ),
        OperationMetric(
            key="trace_span_daily",
            category=MetricCategory.APM,
            name="Trace 上报量(span数)",
            unit="亿/天",
            description="Daily trace span volume. 日均 Trace 上报 span 数。",
            handler_type=HandlerType.MANUAL,
            note="中心化集群总量 + 部分业务集群总量人工汇总，暂未程序化。",
        ),
        OperationMetric(
            key="log_query_page_count_1d",
            category=MetricCategory.LOG,
            name="日志查询量(页面)",
            unit="次/天",
            description="Daily log query count from page. 日均日志查询次数(页面)。",
            handler_type=HandlerType.MANUAL,
            note="仅统计点击搜索与翻页动作，取自 Grafana 仪表盘，暂无程序化口径。",
        ),
        OperationMetric(
            key="chart_grep_analysis_mau",
            category=MetricCategory.LOG,
            name="图表分析及grep分析 MAU",
            unit="人",
            description="MAU of chart/grep analysis (currently DAU proxy). 图表/grep 分析月活(暂用 DAU 代替)。",
            handler_type=HandlerType.MANUAL,
            note="缺少长期存储，暂用 DAU 代替，取自 Trace 仪表盘。",
        ),
    ]

    for metric in metrics:
        register_metric(metric)

    logger.info("operation mcp: registered %s metrics", len(OPERATION_METRIC_REGISTRY))
