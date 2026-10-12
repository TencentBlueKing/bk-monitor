"""主机卡片统计：在一次 instant 查询中聚合，返回计数和身份完整性标志。"""

import math
import time
from collections import defaultdict

from bkmonitor.data_source import UnifyQuery, load_data_source
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import api

HOST_STATS_METRICS = {
    "cpu": ("system.cpu_summary", "usage"),
    "mem": ("system.mem", "pct_used"),
    "disk": ("system.disk", "in_use"),
}


def build_host_stats_query(bk_biz_id, category, hosts=None):
    """局部范围使用白名单；业务根返回异常 ID 和全量身份完整性标志。"""
    table, field = HOST_STATS_METRICS[category]
    ips_by_cloud = defaultdict(set)
    for host in hosts or []:
        ips_by_cloud[str(int(host.get("bk_cloud_id") or 0))].add(host.get("bk_host_innerip") or "")
    targets = [
        {"bk_target_ip": sorted(ips), "bk_target_cloud_id": [cloud, ""] if cloud == "0" else [cloud]}
        for cloud, ips in sorted(ips_by_cloud.items())
    ]
    scopes = (
        ("a", {}, [{"key": "bk_host_id", "method": "neq", "value": [""]}]),
        ("b", {}, [{"key": "bk_host_id", "method": "eq", "value": [""]}]),
    )
    if hosts is not None:
        scopes = (
            ("a", {"bk_host_id": sorted({str(host["bk_host_id"]) for host in hosts})}, []),
            ("b", {"targets": targets}, [{"key": "bk_host_id", "method": "eq", "value": [""]}]),
        )
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
        for alias, filters, where in scopes
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
    if hosts is None:
        # group 将 +Inf 等异常值转换为 1；value scalar 同时校验异常向量是否完整。
        expressions["abnormal"] = "group by (bk_host_id) (a >= 79.995)"
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


def query_business_host_metric_stats(bk_biz_id, category, start_time=None, end_time=None):
    """先查询业务异常 ID，仅对候选查询 CMDB；复杂身份复用原白名单语义。"""
    query = build_host_stats_query(bk_biz_id, category)
    query_end = int(end_time if end_time is not None and start_time is not None else time.time())
    records = query.query_data(start_time=(query_end - 180) * 1000, end_time=query_end * 1000, instant=True)
    unknown = {"category": category, "value": None, "complete": False}
    if query.is_partial:
        return {**unknown, "reason": "partial"}
    values = {}
    abnormal_ids = set()
    for record in records:
        name, value = record.get("stat"), record.get("_result_")
        if not isinstance(value, int | float) or not math.isfinite(value) or value < 0 or int(value) != value:
            return {**unknown, "reason": "invalid_result"}
        if name == "abnormal":
            host_id = str(record.get("bk_host_id") or "")
            if not host_id or host_id in abnormal_ids or value != 1:
                return {**unknown, "reason": "invalid_result"}
            abnormal_ids.add(host_id)
        else:
            if name in values:
                return {**unknown, "reason": "invalid_result"}
            values[name] = value
    if set(values) != {"value", "id_count", "ip_count", "duplicates"}:
        return {**unknown, "reason": "invalid_result"}
    if values["ip_count"] or values["duplicates"]:
        # 范围外的 IP/重复身份也可能触发标志。仅白名单过滤后才能决定
        # 当前 CMDB 集合是否有歧义，不能直接返回未知或仅对异常身份去重。
        hosts = api.cmdb.get_host_identities(bk_biz_id=bk_biz_id)
        return query_host_metric_stats(bk_biz_id, category, hosts, query_end - 180, query_end)
    if len(abnormal_ids) != values["value"] or values["id_count"] < values["value"]:
        return {**unknown, "reason": "invalid_result"}
    candidate_ids = []
    for host_id in abnormal_ids:
        # 保留旧 str(CMDB ID) 白名单的精确匹配，不能让 "001" 匹配主机 1。
        try:
            candidate_id = int(host_id)
        except ValueError:
            continue
        if str(candidate_id) == host_id:
            candidate_ids.append(candidate_id)
    hosts = (
        api.cmdb.get_host_identities(bk_biz_id=bk_biz_id, bk_host_ids=sorted(candidate_ids)) if candidate_ids else []
    )
    value = len(abnormal_ids & {str(host["bk_host_id"]) for host in hosts})
    return {"category": category, "value": value, "complete": True}
