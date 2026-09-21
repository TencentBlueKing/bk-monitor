"""主机卡片统计：在一次 instant 查询中聚合，返回计数和身份完整性标志。"""

import math
import time
from collections import defaultdict

from bkmonitor.data_source import UnifyQuery, load_data_source
from constants.data_source import DataSourceLabel, DataTypeLabel

HOST_STATS_METRICS = {
    "cpu": ("system.cpu_summary", "usage"),
    "mem": ("system.mem", "pct_used"),
    "disk": ("system.disk", "in_use"),
}


def build_host_stats_query(bk_biz_id, category, hosts):
    """白名单只随身份数增长；表达式不为每台主机展开一个查询分支。"""
    table, field = HOST_STATS_METRICS[category]
    ips_by_cloud = defaultdict(set)
    for host in hosts:
        ips_by_cloud[str(int(host.get("bk_cloud_id") or 0))].add(host.get("bk_host_innerip") or "")
    targets = [
        {"bk_target_ip": sorted(ips), "bk_target_cloud_id": [cloud, ""] if cloud == "0" else [cloud]}
        for cloud, ips in sorted(ips_by_cloud.items())
    ]
    data_source_class = load_data_source(DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES)
    sources = [
        data_source_class(
            bk_biz_id=bk_biz_id,
            interval=180,
            table=table,
            metrics=[{"field": field, "method": "MAX", "alias": alias}],
            group_by=["bk_host_id", "bk_target_ip", "bk_target_cloud_id"],
            filter_dict=filters,
            where=where,
        )
        for alias, filters, where in (
            ("a", {"bk_host_id": sorted({str(host["bk_host_id"]) for host in hosts})}, []),
            ("b", {"targets": targets}, [{"key": "bk_host_id", "method": "eq", "value": [""]}]),
        )
    ]
    # 列表按三元身份聚合后再映射至 CMDB；阈值比较本身会排除 NaN。
    raw_by_ip = (
        'label_replace(label_replace(b, "raw_cloud", "$1", "bk_target_cloud_id", "(.*)"), '
        '"bk_target_cloud_id", "0", "bk_target_cloud_id", "^$")'
    )
    # ratio=1 的百分比：79.995 是使 Python round(value, 2) >= 80 的最小 float64。
    # 前一个相邻浮点数 round 后是 79.99，避免 PromQL round 的中点规则差异。
    counts = f"(count(a >= 79.995) or vector(0)) + (count({raw_by_ip} >= 79.995) or vector(0))"
    duplicates = (
        "(count(count by (bk_host_id) (a) > 1) or vector(0)) + "
        f"(count(count by (bk_target_ip, bk_target_cloud_id) ({raw_by_ip}) > 1) or vector(0))"
    )
    expressions = {
        "value": counts,
        "id_count": "count(a) or vector(0)",
        "ip_count": "count(b) or vector(0)",
        "duplicates": duplicates,
    }
    expression = " or ".join(
        f'label_replace(({value}), "stat", "{name}", "", "")' for name, value in expressions.items()
    )
    return UnifyQuery(data_sources=sources, bk_biz_id=bk_biz_id, expression=expression)


def query_host_metric_stats(bk_biz_id, category, hosts, start_time=None, end_time=None):
    if not hosts:
        return {"category": category, "value": 0, "complete": True}
    query = build_host_stats_query(bk_biz_id, category, hosts)
    # 与列表复用 instant 时间对齐、设备过滤和 180 秒窗口。
    # 多数据源表达式必走 UQ；标准查询路径会将异常上抛。
    query_end = int(end_time if end_time is not None and start_time is not None else time.time()) * 1000
    records = query.query_data(start_time=query_end - 180000, end_time=query_end, instant=True)
    unknown = {"category": category, "value": None, "complete": False}
    if query.is_partial:
        return {**unknown, "reason": "partial"}
    values = {}
    for record in records:
        name, value = record.get("stat"), record.get("_result_")
        if name in values or not isinstance(value, int | float) or not math.isfinite(value):
            return {**unknown, "reason": "invalid_result"}
        values[name] = value
    if set(values) != {"value", "id_count", "ip_count", "duplicates"}:
        return {**unknown, "reason": "invalid_result"}
    # 不同身份记录映射到同一主机时，旧列表按返回顺序覆盖。
    # 缺少当前 CMDB 映射 JOIN 时混合身份的交集无法可靠判断，保留未知。
    if (
        values["duplicates"]
        or (values["id_count"] and values["ip_count"])
        or (values["ip_count"] and any(host.get("has_duplicate_ip") for host in hosts))
    ):
        return {**unknown, "reason": "ambiguous_identity"}
    return {"category": category, "value": int(values["value"]), "complete": True}
