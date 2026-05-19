# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

自定义指标查询链路健康巡检。

覆盖路径：transfer redis 上报 → metadata DB → BMW broker 调度 → 路由 redis hash →
unify-query → InfluxDB。每条链路异常都对应一个 ``Issue``；若开启 autoremediate 则按
安全阀闸放行后调用现成 API 修复。
"""

import json
import logging
import time
import traceback
from typing import Dict, List, Optional, Tuple

import requests
from django.conf import settings

from alarm_backends.core.lock.service_lock import share_lock
from metadata import models
from metadata.config import PERIODIC_TASK_DEFAULT_TTL
from metadata.models.space.constants import (
    RESULT_TABLE_DETAIL_CHANNEL,
    RESULT_TABLE_DETAIL_KEY,
    SPACE_TO_RESULT_TABLE_KEY,
)
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis
from metadata.utils.redis_tools import RedisTools

logger = logging.getLogger("metadata")

REPORT_REDIS_KEY = "bkmonitorv3:metadata:link_health:last"
FIX_HISTORY_REDIS_KEY = "bkmonitorv3:metadata:link_health:fix_history"
STREAK_REDIS_KEY_PREFIX = "bkmonitorv3:metadata:link_health:streak"
COOLDOWN_REDIS_KEY_PREFIX = "bkmonitorv3:metadata:link_health:fix_cooldown"
UQ_SNAPSHOT_REDIS_KEY = "bkmonitorv3:metadata:link_health:uq_counters_snapshot"
REPORT_TTL_SECONDS = 3600
FIX_HISTORY_MAX_LEN = 1000
UQ_SNAPSHOT_TTL_SECONDS = 3600

BMW_PERIODIC_TASK_NAMES = (
    "periodic:metadata:refresh_ts_metric",
    "periodic:metadata:refresh_datasource",
    "periodic:metadata:refresh_kafka_topic_info",
    "periodic:cluster_metrics:push_and_publish_space_router_info",
)
BMW_BROKER_QUEUE = "default"
ALLOWED_STORAGE_TYPES = {"influxdb", "victoria_metrics", "elasticsearch"}


class Issue:
    """单条异常及其修复动作。"""

    __slots__ = ("stage", "code", "scope", "detail", "fix_callable")

    def __init__(self, stage: str, code: str, scope: str, detail: Dict, fix_callable=None):
        self.stage = stage
        self.code = code
        self.scope = scope
        self.detail = detail
        self.fix_callable = fix_callable

    @property
    def actionable(self) -> bool:
        return self.fix_callable is not None

    @property
    def gate_key(self) -> str:
        """streak / cooldown 在 redis 的 key suffix；按 (scope, code) 唯一。"""
        return f"{self.scope}:{self.code}"

    def to_dict(self) -> Dict:
        return {"stage": self.stage, "code": self.code, "scope": self.scope, "detail": self.detail}


class Report:
    """巡检报告聚合。"""

    def __init__(self):
        self.started_at = time.time()
        self.issues: List[Issue] = []
        self.fix_attempts: List[Dict] = []
        self.skipped: List[Dict] = []
        self.stage_stats: Dict[str, Dict[str, int]] = {}

    def add(self, issue: Issue):
        self.issues.append(issue)
        stat = self.stage_stats.setdefault(issue.stage, {"issue_total": 0})
        stat["issue_total"] += 1

    def mark_fix(self, issue: Issue, ok: bool, err: Optional[str] = None, dry_run: bool = False):
        record = {
            "ts": int(time.time()),
            "stage": issue.stage,
            "code": issue.code,
            "scope": issue.scope,
            "dry_run": dry_run,
            "ok": ok,
            "err": err,
        }
        self.fix_attempts.append(record)

    def mark_skip(self, issue: Issue, reason: str):
        record = {
            "ts": int(time.time()),
            "stage": issue.stage,
            "code": issue.code,
            "scope": issue.scope,
            "reason": reason,
        }
        self.skipped.append(record)

    def summary(self) -> Dict:
        return {
            "ts": int(self.started_at),
            "elapsed_seconds": round(time.time() - self.started_at, 3),
            "issue_total": len(self.issues),
            "fix_total": sum(1 for r in self.fix_attempts if r.get("ok") and not r.get("dry_run")),
            "fix_failed": sum(1 for r in self.fix_attempts if not r.get("ok")),
            "dry_run_total": sum(1 for r in self.fix_attempts if r.get("dry_run")),
            "skipped_total": len(self.skipped),
            "stage_stats": self.stage_stats,
            "issues": [i.to_dict() for i in self.issues[:50]],
            "fix_attempts": self.fix_attempts[:50],
            "skipped": self.skipped[:50],
        }


def _bmw_broker_client():
    from utils.redis_client import RedisClient

    prefix = settings.BMW_BROKER_REDIS_PREFIX
    db = settings.BMW_BROKER_REDIS_DB
    return RedisClient.from_envs(prefix=prefix, db=db)


def _streak_inc(key_suffix: str) -> int:
    """连续命中计数；超过 LINK_HEALTH_FIX_AFTER_STREAK 才放行修复。"""
    client = RedisTools().client
    key = f"{STREAK_REDIS_KEY_PREFIX}:{key_suffix}"
    n = client.incr(key)
    client.expire(key, 3600)
    return int(n)


def _streak_clear(key_suffix: str):
    client = RedisTools().client
    client.delete(f"{STREAK_REDIS_KEY_PREFIX}:{key_suffix}")


def _cooldown_acquire(key_suffix: str) -> bool:
    """同 key 在 LINK_HEALTH_FIX_COOLDOWN_SECONDS 内只允许修一次。"""
    client = RedisTools().client
    key = f"{COOLDOWN_REDIS_KEY_PREFIX}:{key_suffix}"
    return bool(client.set(key, "1", ex=settings.LINK_HEALTH_FIX_COOLDOWN_SECONDS, nx=True))


def _should_skip_table_id(table_id: str) -> bool:
    return table_id in set(settings.LINK_HEALTH_EXCLUDE_TABLE_IDS)


def _ensure_storage_type(table_id: str) -> bool:
    """补齐 result_table_detail 中缺失的 storage_type，不改写已合法的值。

    仅在以下情况写入：
    - 字段缺失或为空；
    - 当前值不在 ALLOWED_STORAGE_TYPES 范围内（即非法字面量）；
    - 当前值是 influxdb / victoria_metrics 但与 vm_rt 实际指向矛盾（漂移）。
    若当前值 ∈ ALLOWED_STORAGE_TYPES（含 elasticsearch）且与 vm_rt 不冲突，直接返回 False。
    """
    raw = RedisTools.hget(RESULT_TABLE_DETAIL_KEY, table_id)
    if raw is None:
        return False
    try:
        detail = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
    except (ValueError, TypeError):
        return False

    vm_rt = detail.get("vm_rt", "") or ""
    current = detail.get("storage_type", "") or ""

    if current in ALLOWED_STORAGE_TYPES:
        # 已是合法值，仅在与 vm_rt 显著冲突时纠正：vm_rt 非空但 storage_type 是 influxdb，
        # 或反之 storage_type=victoria_metrics 但无 vm_rt。其它情况（如 elasticsearch）保留。
        if vm_rt and current == "influxdb":
            new_value = "victoria_metrics"
        elif not vm_rt and current == "victoria_metrics":
            new_value = "influxdb"
        else:
            return False
    else:
        # 缺失或非法值，按 vm_rt 推断
        new_value = "victoria_metrics" if vm_rt else "influxdb"

    detail["storage_type"] = new_value
    RedisTools.hset_to_redis(RESULT_TABLE_DETAIL_KEY, table_id, json.dumps(detail))
    RedisTools.publish(RESULT_TABLE_DETAIL_CHANNEL, [table_id])
    return True


# ============= Stage C: BMW broker =============


def check_bmw_broker(report: Report):
    """探测 BMW broker 是否存在孤儿 active task（lease 已过期但 hash 未清）。"""
    try:
        client = _bmw_broker_client()
    except Exception as exc:
        logger.error("link_health.bmw_broker connect failed: %s", exc)
        report.add(Issue("bmw_broker", "broker_unreachable", "default", {"error": str(exc)}))
        return

    lease_key = f"{{bmw}}:{{{BMW_BROKER_QUEUE}}}:lease"
    now_ts = int(time.time())
    grace = settings.LINK_HEALTH_BMW_LEASE_GRACE_SECONDS

    for task_name in BMW_PERIODIC_TASK_NAMES:
        t_key = f"{{bmw}}:{{{BMW_BROKER_QUEUE}}}:t:{task_name}"
        gate_key = f"bmw_orphan:{task_name}:orphan_active_task"
        try:
            state = client.hget(t_key, "state")
            if state is None:
                _streak_clear(gate_key)
                continue
            state_str = state.decode("utf-8") if isinstance(state, bytes) else state
            if state_str != "active":
                _streak_clear(gate_key)
                continue
            lease_score = client.zscore(lease_key, task_name)
            if lease_score is not None and lease_score >= now_ts - grace:
                _streak_clear(gate_key)
                continue
        except Exception as exc:
            logger.exception("link_health.bmw_broker probe %s failed", task_name)
            report.add(Issue("bmw_broker", "probe_error", task_name, {"error": str(exc)}))
            continue

        detail = {
            "task": task_name,
            "queue": BMW_BROKER_QUEUE,
            "state": state_str,
            "lease_score": lease_score,
            "now": now_ts,
        }

        def _fix(_t_key=t_key, _task_name=task_name, _lease_key=lease_key):
            client.delete(_t_key)
            client.zrem(_lease_key, _task_name)
            unique_key = f"{{bmw}}:{{{BMW_BROKER_QUEUE}}}:unique:{_task_name}:"
            client.delete(unique_key)

        report.add(Issue("bmw_broker", "orphan_active_task", f"bmw_orphan:{task_name}", detail, _fix))


# ============= Stage D: Redis 路由完整性 =============


def _parse_detail(raw) -> Optional[Dict]:
    if raw is None:
        return None
    try:
        return json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
    except (ValueError, TypeError):
        return None


def _list_sample_table_ids(limit: int) -> List[str]:
    """从 space_to_result_table 中抽样 table_id。"""
    client = RedisTools().client
    seen: List[str] = []
    cursor = 0
    while len(seen) < limit:
        cursor, fields = client.hscan(SPACE_TO_RESULT_TABLE_KEY, cursor=cursor, count=20)
        for _, raw in fields.items():
            try:
                payload = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
            except (ValueError, TypeError):
                continue
            for tid in payload:
                if tid not in seen:
                    seen.append(tid)
                    if len(seen) >= limit:
                        return seen
        if cursor == 0:
            break
    return seen


def check_routing(report: Report):
    """巡检 result_table_detail 中字段完整性，重点是 storage_type 缺失。"""
    sample_size = settings.LINK_HEALTH_SAMPLE_SIZE
    try:
        table_ids = _list_sample_table_ids(sample_size)
    except Exception as exc:
        logger.exception("link_health.routing sample failed")
        report.add(Issue("routing", "sample_error", "sample", {"error": str(exc)}))
        return

    if not table_ids:
        return

    raws = RedisTools.hmget(RESULT_TABLE_DETAIL_KEY, table_ids)

    space_redis = SpaceTableIDRedis()

    for tid, raw in zip(table_ids, raws):
        if _should_skip_table_id(tid):
            continue

        scope = f"routing:{tid}"

        if raw is None:
            # detail_missing 用 push_table_id_detail 重建（首次或被清），随后再 ensure storage_type
            def _fix_missing(_tid=tid):
                space_redis.push_table_id_detail(table_id_list=[_tid], is_publish=True)
                _ensure_storage_type(_tid)

            report.add(
                Issue(
                    "routing",
                    "detail_missing",
                    scope,
                    {"table_id": tid},
                    fix_callable=_fix_missing,
                )
            )
            continue

        detail = _parse_detail(raw)
        if detail is None:
            report.add(Issue("routing", "detail_invalid_json", scope, {"table_id": tid}))
            continue

        storage_type = detail.get("storage_type", "") or ""
        vm_rt = detail.get("vm_rt", "") or ""
        code: Optional[str] = None
        detail_payload: Optional[Dict] = None
        actionable = True

        if not storage_type:
            code = "detail_no_storage_type"
            detail_payload = {"table_id": tid, "detail_keys": list(detail.keys()), "vm_rt": vm_rt}
        elif storage_type not in ALLOWED_STORAGE_TYPES:
            code = "detail_unknown_storage_type"
            detail_payload = {"table_id": tid, "storage_type": storage_type}
        elif storage_type == "influxdb" and vm_rt:
            # 两个 ts 类型间的漂移，可自动按 vm_rt 纠正
            code = "storage_type_mismatch"
            detail_payload = {"table_id": tid, "storage_type": storage_type, "vm_rt": vm_rt}
        elif storage_type == "victoria_metrics" and not vm_rt:
            code = "storage_type_mismatch"
            detail_payload = {"table_id": tid, "storage_type": storage_type, "vm_rt": vm_rt}
        elif storage_type == "elasticsearch" and vm_rt:
            # ES 与 vm_rt 同时出现是异常组合，但语义不明，仅告警不自愈
            code = "detail_inconsistent_es_with_vm"
            detail_payload = {"table_id": tid, "storage_type": storage_type, "vm_rt": vm_rt}
            actionable = False

        if not code:
            _streak_clear(f"{scope}:detail_no_storage_type")
            _streak_clear(f"{scope}:detail_unknown_storage_type")
            _streak_clear(f"{scope}:storage_type_mismatch")
            _streak_clear(f"{scope}:detail_inconsistent_es_with_vm")
            continue

        # fix：局部 HSET 补 storage_type，不调 push_table_id_detail 以免擦掉 BMW 已写好的字段。
        # _ensure_storage_type 自身对 storage_type ∈ ALLOWED 且与 vm_rt 一致时直接 noop。
        fix_callable = (lambda _tid=tid: _ensure_storage_type(_tid)) if actionable else None
        report.add(Issue("routing", code, scope, detail_payload, fix_callable))


# ============= Stage A/B: 输入侧 + DB 一致性（与 F3 漂移） =============


def _transfer_redis_client():
    from utils.redis_client import RedisClient

    return RedisClient.from_envs(prefix="BK_MONITOR_TRANSFER")


def check_transfer_and_db(report: Report):
    """对比 transfer redis 中已上报的指标 vs metadata DB；落后则触发重新拉取。"""
    sample_size = settings.LINK_HEALTH_SAMPLE_SIZE
    try:
        client = _transfer_redis_client()
    except Exception as exc:
        logger.error("link_health.transfer redis connect failed: %s", exc)
        report.add(Issue("transfer", "redis_unreachable", "all", {"error": str(exc)}))
        return

    metrics_prefix = getattr(settings, "METRICS_KEY_PREFIX", "bkmonitor:metrics_")
    fetch_window = getattr(settings, "FETCH_TIME_SERIES_METRIC_INTERVAL_SECONDS", 7200)
    now_ts = int(time.time())

    group_qs = (
        models.TimeSeriesGroup.objects.filter(is_enable=True, is_delete=False)
        .order_by("-last_modify_time")
        .values("time_series_group_id", "bk_data_id", "table_id", "last_modify_time")[:sample_size]
    )
    space_redis = SpaceTableIDRedis()

    for group in group_qs:
        data_id = group["bk_data_id"]
        table_id = group["table_id"]
        group_id = group["time_series_group_id"]

        if _should_skip_table_id(table_id):
            continue

        scope = f"metric_drift:{data_id}"
        gate_key = f"{scope}:metric_drift"

        try:
            # 仅观察 fetch_window 内的活跃指标，与下游 instance 方法 update_time_series_metrics 口径一致
            redis_count = client.zcount(f"{metrics_prefix}{data_id}", now_ts - fetch_window, now_ts)
        except Exception as exc:
            logger.exception("link_health.transfer zcount failed bk_data_id=%s", data_id)
            report.add(Issue("transfer", "zcount_error", f"data_id:{data_id}", {"error": str(exc)}))
            continue

        if redis_count == 0:
            _streak_clear(gate_key)
            continue

        db_count = models.TimeSeriesMetric.objects.filter(group_id=group_id).count()
        if db_count >= redis_count:
            _streak_clear(gate_key)
            continue

        detail = {
            "bk_data_id": data_id,
            "table_id": table_id,
            "redis_metric_count": int(redis_count),
            "db_metric_count": db_count,
        }

        def _fix_drift(_group_id=group_id, _table_id=table_id):
            ts_group = models.TimeSeriesGroup.objects.get(time_series_group_id=_group_id)
            is_updated = ts_group.update_time_series_metrics()
            if is_updated:
                space_redis.push_table_id_detail(table_id_list=[_table_id], is_publish=True)
                # push_table_id_detail 不写 storage_type，需要补回，避免擦掉 BMW 写好的字段
                _ensure_storage_type(_table_id)

        report.add(Issue("transfer", "metric_drift", scope, detail, _fix_drift))


# ============= Stage E: unify-query metrics =============


def check_unify_query(report: Report):
    """观测 unify-query SPACE_* counter 与上一轮快照的增量。

    Prometheus counter 是累加器，健康态也非零；仅当与上一轮快照差值 ≥ 阈值才认为异常。
    """
    url = settings.LINK_HEALTH_UNIFY_QUERY_METRICS_URL
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
    except Exception as exc:
        report.add(Issue("unify_query", "metrics_unreachable", "endpoint", {"url": url, "error": str(exc)}))
        return

    counters: Dict[str, float] = {}
    for line in resp.text.splitlines():
        if not line or line.startswith("#"):
            continue
        if not line.startswith("unify_query_space_router_total{"):
            continue
        try:
            metric, value = line.rsplit(" ", 1)
            counters[metric] = float(value)
        except ValueError:
            continue

    if not counters:
        return

    threshold = settings.LINK_HEALTH_UQ_COUNTER_DELTA_THRESHOLD
    client = RedisTools().client
    last_snapshot_raw = client.hgetall(UQ_SNAPSHOT_REDIS_KEY) or {}
    last_snapshot: Dict[str, float] = {}
    for k, v in last_snapshot_raw.items():
        k_str = k.decode("utf-8") if isinstance(k, bytes) else k
        v_str = v.decode("utf-8") if isinstance(v, bytes) else v
        try:
            last_snapshot[k_str] = float(v_str)
        except (ValueError, TypeError):
            continue

    deltas: Dict[str, float] = {}
    for metric, value in counters.items():
        prev = last_snapshot.get(metric, value)  # 首次未见过则视为 0 增长
        delta = value - prev
        if delta >= threshold:
            deltas[metric] = delta

    # 刷新本轮快照供下一轮对比；三步用 pipeline 原子提交，避免中间步骤失败
    # 导致 baseline 无 TTL 永久驻留或与新一轮数据不一致。
    try:
        snapshot_payload = {k: str(v) for k, v in counters.items()}
        if snapshot_payload:
            pipe = client.pipeline()
            pipe.delete(UQ_SNAPSHOT_REDIS_KEY)
            pipe.hmset(UQ_SNAPSHOT_REDIS_KEY, snapshot_payload)
            pipe.expire(UQ_SNAPSHOT_REDIS_KEY, UQ_SNAPSHOT_TTL_SECONDS)
            pipe.execute()
    except Exception:
        logger.exception("link_health.unify_query snapshot persist failed")

    if not deltas:
        return

    report.add(
        Issue(
            "unify_query",
            "space_router_anomaly_delta",
            "metrics_snapshot",
            {
                "threshold": threshold,
                "delta_count": len(deltas),
                "sample": dict(list(deltas.items())[:10]),
            },
        )
    )


# ============= Stage F: InfluxDB 可达性 =============


def check_influxdb(report: Report):
    url = settings.LINK_HEALTH_INFLUXDB_PING_URL
    try:
        resp = requests.get(url, timeout=5)
    except Exception as exc:
        report.add(Issue("influxdb", "ping_failed", "endpoint", {"url": url, "error": str(exc)}))
        return
    if resp.status_code not in (200, 204):
        report.add(Issue("influxdb", "ping_bad_status", "endpoint", {"url": url, "status_code": resp.status_code}))


# ============= 安全阀 + 调度入口 =============


def _passes_safety_gates(issue: Issue) -> Tuple[bool, str]:
    streak_threshold = settings.LINK_HEALTH_FIX_AFTER_STREAK
    streak = _streak_inc(issue.gate_key)
    if streak < streak_threshold:
        return False, f"streak {streak}/{streak_threshold}"
    if not _cooldown_acquire(issue.gate_key):
        return False, "cooldown"
    return True, "ok"


def _publish_report(report: Report):
    summary = report.summary()
    body = json.dumps(summary, default=str, ensure_ascii=False)
    try:
        client = RedisTools().client
        client.set(REPORT_REDIS_KEY, body, ex=REPORT_TTL_SECONDS)
        records = list(report.fix_attempts) + list(report.skipped)
        if records:
            for record in records:
                client.lpush(FIX_HISTORY_REDIS_KEY, json.dumps(record, ensure_ascii=False))
            client.ltrim(FIX_HISTORY_REDIS_KEY, 0, FIX_HISTORY_MAX_LEN - 1)
    except Exception:
        logger.exception("link_health publish report failed")

    if summary["issue_total"] == 0:
        logger.info("link_health: clean, elapsed=%.3fs", summary["elapsed_seconds"])
        return
    level = logger.warning if summary["fix_failed"] == 0 else logger.error
    level(
        "link_health: %s issues, fixed=%s failed=%s skipped=%s dry_run=%s elapsed=%.3fs detail=%s",
        summary["issue_total"],
        summary["fix_total"],
        summary["fix_failed"],
        summary["skipped_total"],
        summary["dry_run_total"],
        summary["elapsed_seconds"],
        body[:2000],
    )


def run_health_check(dry_run: Optional[bool] = None) -> Dict:
    """执行一轮巡检。``dry_run=True`` 时仅检测不修复。"""
    if dry_run is None:
        dry_run = not settings.LINK_HEALTH_AUTOREMEDIATE

    report = Report()

    for check in (
        check_bmw_broker,
        check_routing,
        check_transfer_and_db,
        check_unify_query,
        check_influxdb,
    ):
        try:
            check(report)
        except Exception:
            logger.exception("link_health check %s panicked", check.__name__)
            report.add(Issue(check.__name__, "panic", check.__name__, {"traceback": traceback.format_exc()[:2000]}))

    fix_budget = settings.LINK_HEALTH_MAX_FIX_PER_ROUND
    fix_count = 0
    for issue in report.issues:
        if not issue.actionable:
            report.mark_skip(issue, "not_actionable")
            continue
        if fix_count >= fix_budget:
            logger.error("link_health: fix budget %s exhausted, remaining issues skipped", fix_budget)
            report.mark_skip(issue, "budget_exhausted")
            continue

        passed, reason = _passes_safety_gates(issue)
        if not passed:
            logger.info(
                "link_health: skip fix stage=%s code=%s scope=%s reason=%s",
                issue.stage,
                issue.code,
                issue.scope,
                reason,
            )
            report.mark_skip(issue, reason)
            continue

        if dry_run:
            report.mark_fix(issue, ok=True, dry_run=True)
            fix_count += 1
            continue

        try:
            issue.fix_callable()
            report.mark_fix(issue, ok=True)
            logger.warning(
                "link_health: fixed stage=%s code=%s scope=%s detail=%s",
                issue.stage,
                issue.code,
                issue.scope,
                json.dumps(issue.detail, default=str, ensure_ascii=False)[:1000],
            )
        except Exception as exc:
            report.mark_fix(issue, ok=False, err=str(exc))
            logger.exception(
                "link_health: fix failed stage=%s code=%s scope=%s",
                issue.stage,
                issue.code,
                issue.scope,
            )
        fix_count += 1

    _publish_report(report)
    return report.summary()


@share_lock(ttl=PERIODIC_TASK_DEFAULT_TTL, identify="metadata_linkHealthCheck")
def link_health_check():
    """周期入口：每 10 min 一次。"""
    run_health_check()
