"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

import copy
from dataclasses import dataclass, replace

import ujson

from apps.api import UnifyQueryApi
from apps.log_search.export import state
from apps.log_search.export.config import policy_from_snapshot
from apps.log_unifyquery.handler.base import UnifyQueryHandler
from apps.utils.log import logger


class PlanError(Exception):
    """规划阶段的确定性失败；retryable 表示换一次尝试可能成功。"""

    def __init__(self, code, detail="", retryable=False):
        super().__init__(detail or code)
        self.code = code
        self.retryable = retryable


def encode_export_row(row):
    """与旧异步导出链路一致的 JSONL 编码方式。"""
    return (ujson.dumps(row, ensure_ascii=False) + "\n").encode("utf-8")


def build_handler(job, start=None, end=None):
    """
    用任务创建时冻结的快照重建查询 Handler。

    这里直接复用 UnifyQueryHandler：路由、字段映射、脱敏与结果投影都由它负责，
    分片只需要把时间范围收窄到自己的区间。时间范围只在下面覆盖 base_dict 一处：
    构造器自己算出的 base_dict 会被整体替换，重复覆盖 search_params 的时间不会生效。
    """
    handler = UnifyQueryHandler(copy.deepcopy(job.search_params))
    base_dict = copy.deepcopy(job.base_dict)
    if start is not None:
        base_dict["start_time"], base_dict["end_time"] = str(start), str(end)
    handler.base_dict = base_dict
    return handler


def _statistics_params(handler, start, end):
    params = copy.deepcopy(handler.base_dict)
    params.update(
        {
            "start_time": str(start),
            "end_time": str(end),
            "from": 0,
            # 一期只做应用层时间分片，明确关闭 ES slice
            "slice_max": 0,
            "highlight": {"enable": False},
        }
    )
    return params


def _series_points(result, label):
    """取出聚合结果的单序列点位；聚合只应返回一条序列，多于一条说明统计口径不成立。"""
    series = result["series"]
    if len(series) > 1:
        raise PlanError("STATISTICS_FAILED", f"unify-query {label}返回了多条序列", retryable=True)
    return [(item[0], item[1]) for item in (series[0]["values"] if series else [])]


def count_rows(handler, start, end):
    """
    区间内的总条数，用于配额校验和分片收益估算。

    不能用 query/ts/raw 的 total：它取自 ES 的 hits.total.value，而 unify-query 没有设置
    track_total_hits，超过 1 万的区间会被 ES 默认截断（多路由时还按路由数成倍截断），
    拿它做配额校验和密度估算都会失真。这里改用聚合 count，聚合结果不受 result window 限制。
    """
    params = _statistics_params(handler, start, end)
    for query in params.get("query_list", []):
        query["function"] = [{"method": "count"}]
        query["time_aggregation"] = {}
    result = UnifyQueryApi.query_ts_reference(params)
    return int(sum(value for _, value in _series_points(result, "统计")))


def sample_rows(handler, start, end, limit):
    """采样少量日志用来估算平均序列化字节数，避免单条日志很大时只按条数判断失真。"""
    params = _statistics_params(handler, start, end)
    params["limit"] = limit
    result = UnifyQueryApi.query_ts_raw(params)
    # 复用 handler 的结果投影，保证采样口径与真实导出完全一致
    return [encode_export_row(row) for row in handler._deal_query_result(result)["origin_log_list"]]


def histogram(handler, start, end, interval):
    """按 interval 统计时间密度，用于定位热点区间。返回 {桶起始毫秒: 条数}。"""
    window = f"{interval}ms"
    params = copy.deepcopy(handler.base_dict)
    for query in params.get("query_list", []):
        query["function"] = [{"method": "count"}, {"method": "date_histogram", "window": window}]
        query["time_aggregation"] = {}
    params.update({"step": window, "order_by": [], "start_time": str(start), "end_time": str(end)})
    result = UnifyQueryApi.query_ts_reference(params)
    buckets = {}
    for timestamp, value in _series_points(result, "直方图"):
        buckets[timestamp] = buckets.get(timestamp, 0) + value
    return buckets


@dataclass(frozen=True)
class PartSpec:
    """一个待落库的分片时间范围，estimated_* 是规划期的预估值。"""

    start_time: int
    end_time: int
    estimated_rows: int
    estimated_bytes: int
    oversized: bool = False


@dataclass(frozen=True)
class PlanResult:
    """规划输入与产出，随计划版本落库。分片数由调用方按实际分片计划写入，不在此重复。"""

    total_rows: int
    avg_row_bytes: int
    initial_interval_ms: int


def split_thresholds(policy):
    return int(policy.target_rows * policy.split_factor), int(policy.target_bytes * policy.split_factor)


def merge_thresholds(policy):
    return int(policy.target_rows * policy.merge_factor), int(policy.target_bytes * policy.merge_factor)


def is_hot(rows, avg_bytes, policy):
    split_rows, split_bytes = split_thresholds(policy)
    return rows >= split_rows or rows * avg_bytes >= split_bytes


def can_merge(rows, size, policy):
    merge_rows, merge_bytes = merge_thresholds(policy)
    return rows <= merge_rows and size <= merge_bytes


def _ceil_to(value, step):
    return -(-int(value) // step) * step


def _align(value, step):
    return value - value % step


def choose_interval(total, start, end, tick, policy):
    """
    选择初始统计桶宽。

    按当前区间的数据密度反推：让每个桶的期望条数接近单分片目标，这样桶数只和
    数据量有关，不会因为查询范围很长而爆炸；同时用 max_buckets 兜住桶数上限。
    """
    span = max(tick, end - start)
    if total <= 0:
        return max(tick, _ceil_to(policy.bucket_seconds * 1000, tick))
    interval = int(policy.target_rows * span / total)
    interval = max(interval, policy.bucket_seconds * 1000)
    interval = max(interval, _ceil_to(span / policy.max_buckets, tick))
    return max(tick, _ceil_to(interval, tick))


def refine(handler, start, end, rows, tick, policy, avg_bytes):
    """把超过触发值的时间范围按时间二分，直到达到软目标或时间字段最小精度。"""
    parts = []
    pending = [(start, end, rows)]
    while pending:
        left, right, count = pending.pop()
        hot = is_hot(count, avg_bytes, policy)
        if not hot or right - left <= tick:
            # 到达时间字段最小精度仍超量时标记 oversized，交由 Worker 按原样受控执行
            parts.append(PartSpec(left, right, count, count * avg_bytes, oversized=hot))
            continue
        middle = left + ((right - left) // tick // 2) * tick
        if middle <= left:
            parts.append(PartSpec(left, right, count, count * avg_bytes, oversized=True))
            continue
        pending.append((middle, right, count_rows(handler, middle, right)))
        pending.append((left, middle, count_rows(handler, left, middle)))
    return parts


def merge_adjacent(parts, policy):
    """相邻小分片合并，减少低密度区间产生的大量碎片。"""
    merged = []
    for part in parts:
        previous = merged[-1] if merged else None
        if (
            previous is not None
            and not previous.oversized
            and not part.oversized
            and previous.end_time == part.start_time
            and can_merge(
                previous.estimated_rows + part.estimated_rows,
                previous.estimated_bytes + part.estimated_bytes,
                policy,
            )
        ):
            merged[-1] = replace(
                previous,
                end_time=part.end_time,
                estimated_rows=previous.estimated_rows + part.estimated_rows,
                estimated_bytes=previous.estimated_bytes + part.estimated_bytes,
            )
            continue
        merged.append(part)
    return merged


def build_parts(job, policy):
    """生成覆盖 [start_time, end_time) 且无重叠无遗漏的完整分片计划，返回分片、总量与规划过程量。"""
    handler = build_handler(job)
    total = count_rows(handler, job.start_time, job.end_time)
    if total > policy.max_rows:
        raise PlanError("QUOTA_EXCEEDED", f"预计条数 {total} 超过单任务上限 {policy.max_rows}")
    interval = choose_interval(total, job.start_time, job.end_time, job.time_tick, policy)
    if not total:
        parts = [PartSpec(job.start_time, job.end_time, 0, 0)]
        return parts, total, _plan_result(total, policy.fallback_row_bytes, interval)

    avg_bytes = policy.fallback_row_bytes
    sample = sample_rows(handler, job.start_time, job.end_time, policy.sample_rows)
    if sample:
        avg_bytes = max(1, sum(len(row) for row in sample) // len(sample))

    buckets = histogram(handler, job.start_time, job.end_time, interval)
    if not buckets:
        # 有总量却拿不到时间分布，说明统计链路异常；交给重试而不是猜一份没有密度依据的等分计划
        raise PlanError("STATISTICS_FAILED", "unify-query 直方图未返回任何数据点", retryable=True)

    parts = []
    cursor = _align(job.start_time, interval)
    while cursor < job.end_time:
        left = max(cursor, job.start_time)
        right = min(cursor + interval, job.end_time)
        parts.extend(refine(handler, left, right, buckets.get(cursor, 0), job.time_tick, policy, avg_bytes))
        if len(parts) > policy.max_parts:
            raise PlanError("PART_LIMIT_EXCEEDED", f"分片数量超过上限 {policy.max_parts}")
        cursor += interval

    parts = merge_adjacent(parts, policy)
    if len(parts) > policy.max_parts:
        raise PlanError("PART_LIMIT_EXCEEDED", f"分片数量超过上限 {policy.max_parts}")
    return parts, total, _plan_result(total, avg_bytes, interval)


def _plan_result(total, avg_bytes, interval):
    return PlanResult(total_rows=total, avg_row_bytes=avg_bytes, initial_interval_ms=interval)


def run_planning(job_id):
    """规划一个任务的完整分片计划；重复投递由状态流转保证幂等。"""
    job = state.claim_planning(job_id)
    if job is None:
        return
    try:
        # 使用任务创建时冻结的策略，避免灰度调整影响已准入的任务
        policy = policy_from_snapshot(job.policy)
        parts, total, result = build_parts(job, policy)
        state.persist_plan(job.pk, parts=parts, estimated_total=total, plan_result=result)
    except PlanError as error:
        logger.warning("[run_planning] job=%s code=%s detail=%s", job.pk, error.code, error)
        state.fail_planning(job.pk, error.code, str(error), retryable=error.retryable)
    except Exception as error:  # pylint: disable=broad-except
        logger.exception("[run_planning] job=%s planning failed: %s", job.pk, error)
        state.fail_planning(job.pk, "PLANNING_FAILED", type(error).__name__, retryable=True)
