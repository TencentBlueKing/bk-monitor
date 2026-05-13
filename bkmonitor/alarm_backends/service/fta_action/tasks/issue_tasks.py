"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
import re
import time
from collections import defaultdict
from typing import Any

from alarm_backends.core.cache.cmdb import BusinessManager, SetManager
from alarm_backends.service.scheduler.app import app
from bkmonitor.documents.alert import AlertDocument
from bkmonitor.documents.base import BulkActionType
from bkmonitor.documents.issue import IssueDocument
from bkmonitor.utils.common_utils import safe_int
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from constants.issue import IssueStatus

logger = logging.getLogger("fta_action.issue")

ORPHAN_ISSUE_THRESHOLD_SECONDS = 300
ISSUE_SCAN_PAGE_SIZE = 500
ALERT_SCAN_PAGE_SIZE = 500


PROGRESS_LOG_INTERVAL = 100


@app.task(ignore_result=True, queue="celery_action_cron")
def sync_issue_alert_stats():
    """
    定期对活跃 Issue 执行：
      1) 漏关联补偿（回填 AlertDocument.issue_id）
      2) 统计 alert_count / last_alert_time
      3) 重算 impact_scope
      4) 检测 orphan issue 并触发监控告警
      5) 续命 legacy 迁移哨兵（避免 30 天 TTL 失效后 processor 退化到 fallback ES 查询）
    """
    start_ts = time.time()
    processed = 0
    failed = 0
    total = 0
    # 同一周期内同 strategy 仅做一次批量 backfill（O(N×M) → O(N+M) 性能优化）；
    # 详见 _backfill_unlinked_alerts_for_strategy。set 用 str 化的 strategy_id 做 key 防止 int/str 混淆。
    backfilled_strategies: set[str] = set()

    # 续命 legacy 迁移哨兵：30 天 TTL 内若无 deploy 触发 migrate，哨兵会过期 → processor 退化到
    # 走 fallback ES 查询。本周期任务定期检查，若哨兵不存在 + 当前确实无 fingerprint=null 活跃 Issue,
    # 主动续命避免性能退化。失败 fail-safe（不阻塞周期任务主流程）。
    _renew_legacy_migration_done_sentinel_if_needed()

    for hit, total in _iter_issue_hits_with_total():
        issue = IssueDocument(**hit.to_dict())
        processed += 1

        if processed == 1:
            logger.info("[issue] sync_issue_alert_stats: start, active_issues=%d", total)

        logger.debug(
            "[issue] sync_issue_alert_stats: processing [%d/%d] strategy(%s) issue(%s)",
            processed,
            total,
            issue.strategy_id,
            issue.id,
        )
        if processed % PROGRESS_LOG_INTERVAL == 0:
            logger.info(
                "[issue] sync_issue_alert_stats: progress [%d/%d], failed=%d, elapsed=%.1fs",
                processed,
                total,
                failed,
                time.time() - start_ts,
            )

        try:
            _process_single_issue(issue, backfilled_strategies)
        except Exception:
            failed += 1
            logger.exception(
                "[issue] sync_issue_alert_stats: failed, strategy(%s) issue(%s)",
                issue.strategy_id,
                issue.id,
            )

    elapsed = time.time() - start_ts
    logger.info(
        "[issue] sync_issue_alert_stats: done, processed=%d/%d, failed=%d, strategies_backfilled=%d, elapsed=%.1fs",
        processed,
        total,
        failed,
        len(backfilled_strategies),
        elapsed,
    )


def _renew_legacy_migration_done_sentinel_if_needed():
    """续命 legacy 迁移哨兵：cache 过期 + 当前确实无 legacy → 主动 set。

    避免 30 天 TTL 失效后 processor 永久走 fallback ES 查询（性能退化）。
    任一环节失败仅 warning，不阻塞周期任务主流程。
    """
    from alarm_backends.core.cache.key import ISSUE_LEGACY_MIGRATION_DONE_KEY
    from bkmonitor.documents.issue import _mark_legacy_migration_done

    try:
        cache_key = ISSUE_LEGACY_MIGRATION_DONE_KEY.get_key()
        if ISSUE_LEGACY_MIGRATION_DONE_KEY.client.exists(cache_key):
            return  # 哨兵在，无需续命
    except Exception:
        # Redis 故障不阻塞，下个周期再试
        return

    # 哨兵不存在：探查当前是否真无 legacy
    try:
        legacy_count = (
            IssueDocument.search(all_indices=True)
            .filter("terms", status=IssueStatus.ACTIVE_STATUSES)
            .exclude("exists", field="fingerprint")
            .params(size=0, track_total_hits=True)
            .execute()
            .hits.total.value
        )
    except Exception:
        logger.warning("[issue] sentinel renew: probe legacy count failed, skip", exc_info=True)
        return

    if legacy_count == 0:
        _mark_legacy_migration_done()
        logger.info("[issue] sentinel renew: legacy=0 confirmed, sentinel re-set")
    else:
        # 仍有 legacy（极罕见：deploy 后又有人手工导入旧数据），交给下次 deploy 的 migrate 处理
        logger.warning(
            "[issue] sentinel renew: still %d legacy active issues, "
            "skip renew (will be picked up by next deploy migrate)",
            legacy_count,
        )


def _process_single_issue(issue: IssueDocument, backfilled_strategies: set[str]):
    # legacy Issue（部署窗口期短期存在，由 post_migrate 切割为 RESOLVED）周期任务直接跳过：
    # 避免在 read-only 兜底分支承接多 fingerprint 告警时持续污染 alert_count / impact_scope / update_time
    if not issue.fingerprint:
        logger.debug(
            "[issue] sync_issue_alert_stats: skip legacy issue (no fingerprint), strategy(%s) issue(%s)",
            issue.strategy_id,
            issue.id,
        )
        return

    # 漏关联补偿：每个 strategy 在一个周期内只跑一次（去重 set 由调用方维护），
    # 避免高基数策略下"每个 fingerprint Issue 都重复扫同策略 unlinked alerts"的 O(N×M) 放大
    strategy_key = str(issue.strategy_id) if issue.strategy_id else ""
    if strategy_key and strategy_key not in backfilled_strategies:
        try:
            _backfill_unlinked_alerts_for_strategy(strategy_key)
        finally:
            # 即使本次失败也加入 set，避免本周期内重复尝试（下一周期会重试）
            backfilled_strategies.add(strategy_key)

    alert_search = AlertDocument.search(all_indices=True).filter("term", issue_id=issue.id).params(size=0)
    alert_search.aggs.metric("alert_count", "value_count", field="id")
    alert_search.aggs.metric("max_begin_time", "max", field="begin_time")

    result = alert_search.execute()
    alert_count = int(result.aggregations.alert_count.value or 0)
    # ES date aggregations always return milliseconds; IssueDocument uses epoch_second → divide by 1000
    raw_max = result.aggregations.max_begin_time.value
    last_alert_time = int(raw_max / 1000) if raw_max else issue.last_alert_time

    agg_config = issue.aggregate_config
    if hasattr(agg_config, "to_dict"):
        agg_config = agg_config.to_dict()
    # None 与 [] 等价处理（与 processor / _backfill_unlinked_alerts 保持一致），
    # 避免快照中 aggregate_dimensions=None 时下游收窄逻辑收到非预期类型
    agg_dims: list[str] = (agg_config or {}).get("aggregate_dimensions") or []
    impact_scope = _build_impact_scope(issue.id, aggregate_dimensions=agg_dims)

    now = int(time.time())
    if alert_count == 0:
        issue_create_time = issue.create_time if issue.create_time else 0
        try:
            issue_create_time = int(issue_create_time)
        except (TypeError, ValueError):
            issue_create_time = 0
        age = now - issue_create_time
        if age > ORPHAN_ISSUE_THRESHOLD_SECONDS:
            logger.error(
                "[issue] orphan issue detected (no alerts associated), strategy(%s) issue(%s) age_seconds=%.0f",
                issue.strategy_id,
                issue.id,
                age,
            )

    update_doc = IssueDocument(
        id=issue.id,
        alert_count=alert_count,
        last_alert_time=last_alert_time,
        impact_scope=impact_scope,
        update_time=now,
    )
    try:
        IssueDocument.bulk_create([update_doc], action=BulkActionType.UPDATE)
    except Exception as e:
        logger.error(
            "[issue] sync_issue_alert_stats: UPDATE failed, strategy(%s) issue(%s): %s",
            issue.strategy_id,
            issue.id,
            e,
        )
        raise


_BACKFILL_ALERT_SCAN_MAX_LOOKBACK_SEC = 7 * 86400  # 7 天，避免高基数+长生命周期策略下 alert scan 范围爆炸


def _backfill_unlinked_alerts_for_strategy(strategy_id: str):
    """按 strategy 批处理 unlinked alerts 回填（O(N×M) → O(N+M) 性能优化）。

    旧实现：对每个活跃 Issue 单独调 `_backfill_unlinked_alerts(issue)`，每次都扫一遍同策略
    unlinked alerts、对每条 alert 反算 fingerprint。高基数策略（N 个 fingerprint Issue）下
    ES alert scan 被放大 N 倍，且同一条 alert 被反算 fingerprint N 次。

    新实现：按 strategy 批处理一次：
      1. 一次 scan 该策略所有活跃 Issue，按 (agg_dims_tuple → {fingerprint: (issue_id, create_time)})
         分组建 map（配置变更窗口期不同 Issue 的 aggregate_config snapshot 可能不同）
      2. 一次 scan 该策略 unlinked alerts（since 最早 Issue create_time，但不超过 7 天）
      3. 匹配优先级：先尝试 **live config** 对应的 group → 没命中再按 len 降序回退（具体优先 catch-all）；
         避免 catch-all 必中特性把本应归具体 fingerprint 的 alert 错绑到旧 [] 维度 Issue
      4. 命中后判断 `alert.begin_time >= issue.create_time`，否则跳过（保留旧实现"alert 必须晚于
         Issue 出生才能归属"语义，避免 first_alert_time 与 alert 列表时间线断裂）

    复杂度：O(N issues + M alerts × G groups)，G 通常为 1（同策略 Issue 共享 agg_dims）。
    """
    from alarm_backends.core.cache.strategy import StrategyCacheManager
    from alarm_backends.service.fta_action.issue_processor import gen_issue_fingerprint

    try:
        strategy_id_int = int(strategy_id)
    except (TypeError, ValueError):
        return
    if not strategy_id_int:
        return

    # Step 0: 取 live issue_config 作为优先匹配 group（避免 catch-all 误绑、维度替换错位）
    # 三种 None 退化场景，全部按 len 降序匹配：
    #   (a) 策略缓存 miss / Redis 异常
    #   (b) issue_config 缺失（策略已禁用 Issue 聚合，但仍有历史活跃 Issue）—— 此处 None 而非 ()，
    #       否则空 tuple 会被当作"live=catch-all"让 catch-all group 永远优先（v1.6 review 发现的 bug）
    #   (c) 任何其他异常
    live_agg_dims_tuple: tuple | None = None
    try:
        strategy_cache = StrategyCacheManager.get_strategy_by_id(strategy_id_int) or {}
        live_issue_config = strategy_cache.get("issue_config")
        if live_issue_config is not None:
            # 仅当 issue_config 显式存在时才生成 live_agg_dims_tuple；缺失时保持 None 走 fallback
            live_agg_dims = live_issue_config.get("aggregate_dimensions") or []
            live_agg_dims_tuple = tuple(sorted(live_agg_dims))
    except Exception:
        # 策略缓存不可用 fail-open：退化为不优先 live 路径，按 len 降序匹配
        logger.warning("[issue] strategy(%s) backfill: load live config failed, fallback to len-desc", strategy_id)
        live_agg_dims_tuple = None

    # Step 1: 加载该策略所有活跃 Issue → {fingerprint: (issue_id, create_time)} 分组 map
    grouped_fp_map: dict[tuple, dict[str, tuple[str, int]]] = defaultdict(dict)
    earliest_create_time: int | None = None
    issues_search = (
        IssueDocument.search(all_indices=True)
        .filter("term", strategy_id=strategy_id)
        .filter("terms", status=IssueStatus.ACTIVE_STATUSES)
        .params(size=500)
    )
    for issue_hit in issues_search.scan():
        fp = getattr(issue_hit, "fingerprint", "") or ""
        if not fp:
            # legacy Issue 已由 _process_single_issue 入口跳过；此处再防御一次
            continue
        agg_config = getattr(issue_hit, "aggregate_config", None)
        if hasattr(agg_config, "to_dict"):
            agg_config = agg_config.to_dict()
        agg_dims_tuple = tuple(sorted((agg_config or {}).get("aggregate_dimensions") or []))
        try:
            ct = int(issue_hit.create_time) if issue_hit.create_time else 0
        except (TypeError, ValueError):
            ct = 0
        grouped_fp_map[agg_dims_tuple][fp] = (issue_hit.meta.id, ct)
        if ct and (earliest_create_time is None or ct < earliest_create_time):
            earliest_create_time = ct

    if not grouped_fp_map or earliest_create_time is None:
        return

    # 匹配优先级排序：live config 对应 group 排第一，其余按 len 降序（具体优先 catch-all）
    def _match_order_key(item):
        agg_tuple, _fp_map = item
        is_live = 0 if (live_agg_dims_tuple is not None and agg_tuple == live_agg_dims_tuple) else 1
        return (is_live, -len(agg_tuple))

    sorted_groups = sorted(grouped_fp_map.items(), key=_match_order_key)

    # Step 2: 扫该策略 unlinked alerts，scan 下界 = max(earliest_create_time, now - 7 天)
    # 上限 7 天避免长生命周期策略下扫描范围爆炸；6 个月前漏写 alert 不会被周期任务回填，由 process 主路径兜底
    scan_lower_bound = max(earliest_create_time, int(time.time()) - _BACKFILL_ALERT_SCAN_MAX_LOOKBACK_SEC)
    base_search = (
        AlertDocument.search(all_indices=True)
        .filter("term", strategy_id=strategy_id)
        .filter("range", begin_time={"gte": scan_lower_bound})
        .exclude("exists", field="issue_id")
    )

    # Step 3: 内存分发（live 优先 + 时间边界 + len 降序 fallback）
    total = 0
    skipped_time = 0
    for hits in _iter_alert_hit_batches(base_search):
        update_docs = []
        for hit in hits:
            alert_dims = _extract_alert_dimensions(hit)
            try:
                alert_begin = int(getattr(hit, "begin_time", 0) or 0)
            except (TypeError, ValueError):
                alert_begin = 0

            for agg_dims_tuple, fp_map in sorted_groups:
                fp = gen_issue_fingerprint(strategy_id_int, list(agg_dims_tuple), alert_dims)
                if not fp or fp not in fp_map:
                    continue
                issue_id, issue_ct = fp_map[fp]
                # 时间边界：alert 必须晚于 Issue 出生，否则跳过（即使 break——避免回退到更通用 group 错绑）
                if alert_begin and issue_ct and alert_begin < issue_ct:
                    skipped_time += 1
                    break
                update_docs.append(AlertDocument(id=hit.id, issue_id=issue_id))
                break

        if not update_docs:
            continue
        try:
            AlertDocument.bulk_create(update_docs, action=BulkActionType.UPSERT)
            total += len(update_docs)
        except Exception:
            logger.exception("[issue] backfill failed, strategy(%s)", strategy_id)
            return

    if total or skipped_time:
        logger.info(
            "[issue] strategy(%s) backfilled %d unlinked alerts, skipped_time=%d "
            "(%d active issues, %d agg-dim groups, live_priority=%s)",
            strategy_id,
            total,
            skipped_time,
            sum(len(m) for m in grouped_fp_map.values()),
            len(grouped_fp_map),
            live_agg_dims_tuple is not None,
        )


def _extract_alert_dimensions(hit) -> dict:
    """从 ES hit 提取 AlertDocument.dimensions 为 {key: value} dict。

    与 IssueAggregationProcessor._get_alert_dimensions 对齐，保证两侧 fingerprint 计算一致。
    """
    result: dict = {}
    raw = hit.to_dict().get("dimensions") or []
    for dim in raw:
        if isinstance(dim, dict):
            key = dim.get("key", "")
            value = dim.get("value", "")
        else:
            key = getattr(dim, "key", "")
            value = getattr(dim, "value", "")
        if key:
            result[key] = value
    return result


def _allowed_scope_keys(aggregate_dimensions: list[str]) -> set[str] | None:
    """
    根据聚合维度决定 impact_scope 允许输出的 key 集合。

    返回值语义：
      - None  → aggregate_dimensions 为空，不收窄，全量输出
      - set() → 非空 dims 但无已知资源映射，收窄为空（输出 {}）
      - {...} → 允许输出的 key 集合

    APM 粒度规则（优先级从粗到细）：
      - app_name 在 dims → 允许 apm_app（应用级）
      - app_name + service_name 均在 dims → 额外允许 apm_service（服务级）

    K8S 粒度规则：
      - bcs_cluster_id / pod / node 等在 dims → 允许 cluster / node / pod
      - 额外含 service_name / service → 允许 service
    """
    if not aggregate_dimensions:
        return None

    dims = set(aggregate_dimensions)
    allowed: set[str] = set()

    if dims & {"bk_target_ip", "ip", "bk_host_id", "bk_cloud_id", "bk_target_cloud_id"}:
        allowed.update(["host", "set"])

    if dims & {"bk_target_service_instance_id", "bk_service_instance_id"}:
        allowed.update(["service_instances", "set"])

    # K8S：bcs_cluster_id 为必要锚点；service 需 service_name/service 显式在聚合维度中
    if dims & {"bcs_cluster_id", "pod", "pod_name", "node", "node_name"}:
        allowed.update(["cluster", "node", "pod"])
        if dims & {"service_name", "service"}:
            allowed.add("service")

    # APM：app_name → 应用级（apm_app）；service_name 额外在 dims 才开放服务级（apm_service）
    if "app_name" in dims:
        allowed.add("apm_app")
        if "service_name" in dims:
            allowed.add("apm_service")

    # 非空 dims 但无已知资源映射时，返回空集合而非 None：
    # None 表示"不收窄"，空集合表示"收窄为空"，两者语义不同
    return allowed


def _build_impact_scope(issue_id: str, aggregate_dimensions: list[str] | None = None) -> dict:
    """
    按关联告警汇总影响范围快照。

    aggregate_dimensions 来自 IssueDocument.aggregate_config["aggregate_dimensions"]，
    非空时按维度类型收窄输出 key；为空时全量输出。
    输出格式：每个资源维度均为 {count, instance_list, link_tpl}，
    支持 CMDB Set / Host / ServiceInstance / K8S 集群/节点/Pod/Service / APM 应用/服务。
    """
    sets: dict[str, dict] = {}
    pending_set_names: dict[str, int] = {}
    # 升级为 {key: {"display_name": str, "bk_biz_id": int|None}}，
    # 以便每条实例携带归属业务，统一拼装 ?bizId={bk_biz_id}#/... 跳转链接
    all_hosts: dict[str, dict] = {}
    all_sids: dict[str, dict] = {}
    k8s_clusters: dict[str, dict] = {}
    apm_apps: dict[str, dict] = {}

    base_search = AlertDocument.search(all_indices=True).filter("term", issue_id=issue_id)
    for hits in _iter_alert_hit_batches(base_search, sort_fields=["id"]):
        for hit in hits:
            hit_dict = hit.to_dict()

            # ── dimensions 解析（normalize "tags." 前缀）──────────────────────
            dim_map: dict[str, Any] = {}
            dim_topo_nodes: list[str] = []
            dim_cluster_display: str = ""

            for d in hit_dict.get("dimensions") or []:
                k, v = d.get("key", ""), d.get("value")
                if k == "bk_topo_node":
                    dim_topo_nodes.extend(v if isinstance(v, list) else ([str(v)] if v else []))
                elif k and v is not None:
                    dim_map[k] = v
                    if k.startswith("tags."):
                        dim_map[k[5:]] = v
                    if k in ("tags.bcs_cluster_id", "bcs_cluster_id"):
                        dim_cluster_display = _format_cluster_display(d.get("display_value", ""), str(v))

            # ── 关键字段提取 ──────────────────────────────────────────────────
            target_type = (
                hit_dict.get("target_type")
                or dim_map.get("target_type", "")
                or hit_dict.get("event", {}).get("target_type", "")
            )
            target = dim_map.get("target", "")
            host_key = str(
                hit_dict.get("bk_host_id")
                or dim_map.get("bk_host_id")
                or hit_dict.get("event", {}).get("bk_host_id")
                or ""
            )
            sid = str(
                hit_dict.get("bk_service_instance_id")
                or dim_map.get("bk_service_instance_id")
                or dim_map.get("bk_target_service_instance_id")
                or ""
            )

            # ── CMDB Set 统计 ────────────────────────────────────────────────
            # AlertDocument 顶层未声明 bk_biz_id 字段，业务 ID 实际存放在 event.bk_biz_id 中，
            # 与 Alert.bk_biz_id 的读取逻辑（top_event.get("bk_biz_id")）以及
            # alert/manager/tasks.py 中的取法保持一致。
            bk_biz_id = hit_dict.get("bk_biz_id") or (hit_dict.get("event") or {}).get("bk_biz_id")
            try:
                bk_biz_id = int(bk_biz_id) if bk_biz_id else None
            except (TypeError, ValueError):
                bk_biz_id = None
            if target_type in ("HOST", "SERVICE"):
                topo_nodes = hit_dict.get("bk_topo_node") or hit_dict.get("event", {}).get("bk_topo_node") or []
                if isinstance(topo_nodes, str):
                    topo_nodes = [topo_nodes]
                topo_translation = (
                    hit_dict.get("extra_info", {})
                    .get("origin_alarm", {})
                    .get("dimension_translation", {})
                    .get("bk_topo_node", {})
                    .get("display_value", [])
                )
            else:
                topo_nodes = dim_topo_nodes
                topo_translation = []

            set_nodes = [n for n in topo_nodes if str(n).startswith("set|")]
            for set_node in set_nodes:
                if set_node not in sets:
                    if topo_translation:
                        display_name = _build_set_display_name(set_node, topo_translation)
                    else:
                        display_name = ""
                        if bk_biz_id and set_node not in pending_set_names:
                            pending_set_names[set_node] = bk_biz_id
                    sets[set_node] = {"display_name": display_name, "hosts": set(), "service_instances": set()}

                entry = sets[set_node]
                if host_key:
                    entry["hosts"].add(host_key)
                    all_hosts.setdefault(
                        host_key,
                        {
                            "display_name": (
                                dim_map.get("ip")
                                or hit_dict.get("ip")
                                or hit_dict.get("event", {}).get("ip")
                                or host_key
                            ),
                            "bk_biz_id": bk_biz_id,
                        },
                    )
                if target_type == "SERVICE" and sid:
                    entry["service_instances"].add(sid)
                    all_sids.setdefault(
                        sid,
                        {
                            "display_name": _build_si_display_name(hit_dict, dim_map, sid),
                            "bk_biz_id": bk_biz_id,
                        },
                    )

            if target_type in ("HOST", "SERVICE") and host_key and host_key not in all_hosts:
                all_hosts[host_key] = {
                    "display_name": (
                        dim_map.get("ip") or hit_dict.get("ip") or hit_dict.get("event", {}).get("ip") or host_key
                    ),
                    "bk_biz_id": bk_biz_id,
                }

            # ── K8S Cluster 统计（与 CMDB Set 并行，不互斥）────────────────
            if target_type and target_type.startswith("K8S"):
                cluster_id = dim_map.get("bcs_cluster_id")
                if cluster_id:
                    entry = k8s_clusters.setdefault(
                        cluster_id,
                        {
                            "display_name": "",
                            "bk_biz_id": bk_biz_id,
                            "nodes": {},
                            "services": {},
                            "pods": {},
                        },
                    )
                    if dim_cluster_display and not entry["display_name"]:
                        entry["display_name"] = dim_cluster_display
                    if not entry.get("bk_biz_id") and bk_biz_id:
                        entry["bk_biz_id"] = bk_biz_id

                    if target_type == "K8S-NODE" and target:
                        entry["nodes"][target] = f"{cluster_id}/{target}"
                    elif target_type == "K8S-SERVICE" and target:
                        entry["services"][target] = f"{cluster_id}/{target}"
                    elif target_type == "K8S-POD" and target:
                        entry["pods"][target] = f"{cluster_id}/{target}"

                    if node := dim_map.get("node") or dim_map.get("node_name"):
                        entry["nodes"][node] = f"{cluster_id}/{node}"
                    if svc := dim_map.get("service") or dim_map.get("service_name"):
                        entry["services"][svc] = f"{cluster_id}/{svc}"
                    if pod := dim_map.get("pod") or dim_map.get("pod_name"):
                        entry["pods"][pod] = f"{cluster_id}/{pod}"

            # ── APM 统计 ────────────────────────────────────────────────────
            elif target_type == "APM-SERVICE":
                app_name = dim_map.get("app_name")
                service_name = dim_map.get("service_name")
                if not app_name and target and ":" in target:
                    app_name, service_name = target.split(":", 1)
                if app_name:
                    entry = apm_apps.setdefault(app_name, {"services": {}, "bk_biz_id": bk_biz_id})
                    if service_name:
                        entry["services"][service_name] = (f"{app_name}/{service_name}", bk_biz_id)

    # ── K8S set 展示名：循环结束后按业务批量填充 ────────────────────────────
    if pending_set_names:
        biz_to_set_nodes: dict[int, list[str]] = {}
        for set_node, biz_id in pending_set_names.items():
            biz_to_set_nodes.setdefault(biz_id, []).append(set_node)

        for biz_id, nodes in biz_to_set_nodes.items():
            bk_tenant_id = bk_biz_id_to_bk_tenant_id(biz_id)
            biz_obj = BusinessManager.get(biz_id)
            biz_name = biz_obj.bk_biz_name if biz_obj else str(biz_id)

            set_ids = [int(n.split("|")[1]) for n in nodes if "|" in n]
            set_map = SetManager.mget(bk_tenant_id=bk_tenant_id, bk_set_ids=set_ids)

            for set_node in nodes:
                set_id_str = set_node.split("|")[1] if "|" in set_node else ""
                set_obj = set_map.get(int(set_id_str)) if set_id_str else None
                set_name = set_obj.bk_set_name if set_obj else (set_id_str or set_node)
                sets[set_node]["display_name"] = f"{biz_name}/{set_name}"

    # ── 序列化 ──────────────────────────────────────────────────────────────
    result: dict[str, Any] = {}

    valid_sets = {k: v for k, v in sets.items() if k != "__unknown_set__"}
    if valid_sets:
        result["set"] = {
            "count": len(valid_sets),
            "instance_list": [
                {"set_id": _parse_set_id(snode), "display_name": d["display_name"]} for snode, d in valid_sets.items()
            ][:50],
            "link_tpl": None,
        }

    if all_hosts:
        result["host"] = {
            "count": len(all_hosts),
            "instance_list": [
                {"bk_host_id": int(hid), "bk_biz_id": data.get("bk_biz_id"), "display_name": data["display_name"]}
                for hid, data in all_hosts.items()
            ][:50],
            "link_tpl": "?bizId={bk_biz_id}#/performance/detail/{bk_host_id}",
        }

    if all_sids:
        result["service_instances"] = {
            "count": len(all_sids),
            "instance_list": [
                {
                    "bk_service_instance_id": int(si_id),
                    "bk_biz_id": data.get("bk_biz_id"),
                    "display_name": data["display_name"],
                }
                for si_id, data in all_sids.items()
            ][:50],
            "link_tpl": None,
        }

    if k8s_clusters:
        if len(k8s_clusters) > 1:
            result["cluster"] = {
                "count": len(k8s_clusters),
                "instance_list": [
                    {"bcs_cluster_id": cid, "bk_biz_id": d.get("bk_biz_id"), "display_name": d["display_name"]}
                    for cid, d in k8s_clusters.items()
                ][:50],
                "link_tpl": (
                    "?bizId={bk_biz_id}#/k8s-new?cluster={bcs_cluster_id}"
                    "&sceneId=kubernetes&scene=performance&activeTab=list"
                ),
            }
        else:
            cid, cdata = next(iter(k8s_clusters.items()))
            cluster_biz_id = cdata.get("bk_biz_id")
            if cdata["nodes"]:
                result["node"] = {
                    "count": len(cdata["nodes"]),
                    "instance_list": [
                        {"bcs_cluster_id": cid, "bk_biz_id": cluster_biz_id, "node": n, "display_name": dn}
                        for n, dn in cdata["nodes"].items()
                    ][:50],
                    "link_tpl": (
                        "?bizId={bk_biz_id}#/k8s-new?cluster={bcs_cluster_id}"
                        '&filterBy={{"node":["{node}"]}}&groupBy=["node"]'
                        "&sceneId=kubernetes&scene=capacity&activeTab=list"
                    ),
                }
            if cdata["services"]:
                result["service"] = {
                    "count": len(cdata["services"]),
                    "instance_list": [
                        {"bcs_cluster_id": cid, "bk_biz_id": cluster_biz_id, "service": s, "display_name": dn}
                        for s, dn in cdata["services"].items()
                    ][:50],
                    "link_tpl": (
                        "?bizId={bk_biz_id}#/k8s-new?cluster={bcs_cluster_id}"
                        '&filterBy={{"namespace":[],"service":["{service}"]}}&groupBy=["namespace","service"]'
                        "&sceneId=kubernetes&scene=network&activeTab=list"
                    ),
                }
            if cdata["pods"]:
                result["pod"] = {
                    "count": len(cdata["pods"]),
                    "instance_list": [
                        {"bcs_cluster_id": cid, "bk_biz_id": cluster_biz_id, "pod": p, "display_name": dn}
                        for p, dn in cdata["pods"].items()
                    ][:50],
                    "link_tpl": (
                        "?bizId={bk_biz_id}#/k8s-new?cluster={bcs_cluster_id}"
                        '&filterBy={{"namespace":[],"pod":["{pod}"]}}&groupBy=["namespace","pod"]'
                        "&sceneId=kubernetes&scene=performance&activeTab=list"
                    ),
                }

    if apm_apps:
        result["apm_app"] = {
            "count": len(apm_apps),
            "instance_list": [
                {"app_name": app, "bk_biz_id": data["bk_biz_id"], "display_name": app} for app, data in apm_apps.items()
            ][:50],
            "link_tpl": "?bizId={bk_biz_id}#/apm/application?filter-app_name={app_name}",
        }
        all_apm_services = [
            {"app_name": app_name, "service_name": svc, "bk_biz_id": biz_id, "display_name": dn}
            for app_name, app_data in apm_apps.items()
            for svc, (dn, biz_id) in app_data["services"].items()
        ]
        if all_apm_services:
            result["apm_service"] = {
                "count": len(all_apm_services),
                "instance_list": all_apm_services[:50],
                "link_tpl": (
                    "?bizId={bk_biz_id}#/apm/service?filter-app_name={app_name}&filter-service_name={service_name}"
                ),
            }

    # 聚合维度收窄：非空时仅保留与维度类型对应的 key
    allowed_keys = _allowed_scope_keys(aggregate_dimensions or [])
    if allowed_keys is not None:
        result = {k: v for k, v in result.items() if k in allowed_keys}

    return result


def _build_set_display_name(set_node: str, translation: list) -> str:
    """
    HOST/SERVICE 场景：从 origin_alarm.dimension_translation.bk_topo_node 提取 biz_name/set_name。
    有 bk_inst_id 时精确匹配，防止同一告警含多个 Set 时取错名称；
    bk_inst_id 缺失时直接信任该集群条目（dimension_translation 里的集群条目即对应当前 set）。
    K8S 宿主机场景由调用方循环结束后统一批量填充。
    """
    set_id = int(set_node.split("|")[1]) if "|" in set_node else None
    biz_name = set_name = ""
    for item in translation or []:
        obj = item.get("bk_obj_id", "") or item.get("bk_obj_name", "")
        name = item.get("bk_inst_name", "")
        if obj in ("biz", "业务"):
            biz_name = name
        elif obj in ("set", "集群") and set_id:
            inst_id = safe_int(item.get("bk_inst_id"), dft=None)
            # inst_id 缺失或无法解析时直接信任该条目（translation 中集群条目即为当前 set）
            if inst_id is None or inst_id == set_id:
                set_name = name
    if biz_name and set_name:
        return f"{biz_name}/{set_name}"
    return set_node


def _build_si_display_name(hit_dict: dict, dim_map: dict, sid: str) -> str:
    """服务实例展示名：优先从 target_key 提取，否则回退到 sid"""
    target_key = hit_dict.get("target_key", "")
    if target_key.startswith("服务实例名称 "):
        return target_key[len("服务实例名称 ") :]
    return str(sid)


def _parse_set_id(set_node: str) -> str:
    """set|5017605 → '5017605'"""
    return set_node.split("|")[1] if "|" in set_node else set_node


def _format_cluster_display(raw_display: str, cluster_id: str) -> str:
    """
    dimensions 中 bcs_cluster_id 的 display_value 格式为 "cluster_id(展示名)"，
    如 "BCS-K8S-41797(kihan-test-gz-0611)"，目标输出为 "展示名(cluster_id)"。
    """
    m = re.match(r"^(.+?)\((.+)\)$", raw_display or "")
    if m and m.group(1) == cluster_id:
        return f"{m.group(2)}({cluster_id})"
    return raw_display or cluster_id


def _iter_issue_hits_with_total():
    """逐页迭代活跃 Issue，同时从首批响应中提取 total（无额外 ES count 请求）。
    每次 yield (hit, total)，total 在首批确定后保持不变。
    """
    search = (
        IssueDocument.search(all_indices=True)
        .filter("terms", status=IssueStatus.ACTIVE_STATUSES)
        .sort("create_time", "id")
        .params(track_total_hits=True)
    )
    search_after = None
    total = 0
    while True:
        current = search.params(size=ISSUE_SCAN_PAGE_SIZE)
        if search_after:
            current = current.extra(search_after=search_after)
        response = current.execute()
        hits = response.hits
        if not hits:
            break
        if total == 0:
            total = getattr(getattr(hits, "total", None), "value", 0) or len(hits)
        for hit in hits:
            yield hit, total
        search_after = getattr(hits[-1].meta, "sort", None)
        if not search_after:
            break


def _iter_alert_hit_batches(base_search, sort_fields=None):
    sort_fields = sort_fields or ["begin_time", "id"]
    search = base_search.sort(*sort_fields)
    search_after = None
    while True:
        current = search.params(size=ALERT_SCAN_PAGE_SIZE)
        if search_after:
            current = current.extra(search_after=search_after)
        hits = current.execute().hits
        if not hits:
            break
        yield hits
        search_after = getattr(hits[-1].meta, "sort", None)
        if not search_after:
            break
