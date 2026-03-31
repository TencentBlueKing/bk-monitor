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
from typing import Any

from alarm_backends.core.cache.cmdb import BusinessManager, SetManager
from alarm_backends.service.scheduler.app import app
from bkmonitor.documents.alert import AlertDocument
from bkmonitor.documents.base import BulkActionType
from bkmonitor.documents.issue import IssueDocument
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
    """
    start_ts = time.time()
    processed = 0
    failed = 0
    total = 0

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
            _process_single_issue(issue)
        except Exception:
            failed += 1
            logger.exception(
                "[issue] sync_issue_alert_stats: failed, strategy(%s) issue(%s)",
                issue.strategy_id,
                issue.id,
            )

    elapsed = time.time() - start_ts
    logger.info(
        "[issue] sync_issue_alert_stats: done, processed=%d/%d, failed=%d, elapsed=%.1fs",
        processed,
        total,
        failed,
        elapsed,
    )


def _process_single_issue(issue: IssueDocument):
    _backfill_unlinked_alerts(issue)

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
    agg_dims: list[str] = (agg_config or {}).get("aggregate_dimensions", [])
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


def _backfill_unlinked_alerts(issue: IssueDocument):
    """回填创建窗口期及其后的同策略未关联 Alert 的 issue_id（1:1 模型）"""
    issue_create_time = issue.create_time
    if not issue_create_time:
        return

    try:
        issue_create_time = int(issue_create_time)
    except (TypeError, ValueError):
        return

    base_search = (
        AlertDocument.search(all_indices=True)
        .filter("term", strategy_id=str(issue.strategy_id))
        .filter("range", begin_time={"gte": issue_create_time})
        .exclude("exists", field="issue_id")
    )

    total = 0
    for hits in _iter_alert_hit_batches(base_search):
        update_docs = [AlertDocument(id=hit.id, issue_id=issue.id) for hit in hits]
        try:
            AlertDocument.bulk_create(update_docs, action=BulkActionType.UPSERT)
            total += len(update_docs)
        except Exception:
            logger.exception("[issue] backfill failed, strategy(%s) issue(%s)", issue.strategy_id, issue.id)
            return

    if total:
        logger.info("[issue] backfilled %d unlinked alerts, strategy(%s) issue(%s)", total, issue.strategy_id, issue.id)


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
    all_hosts: dict[str, str] = {}
    all_sids: dict[str, str] = {}
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
            bk_biz_id = hit_dict.get("bk_biz_id")
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
                    all_hosts[host_key] = (
                        dim_map.get("ip") or hit_dict.get("ip") or hit_dict.get("event", {}).get("ip") or host_key
                    )
                if target_type == "SERVICE" and sid:
                    entry["service_instances"].add(sid)
                    all_sids.setdefault(sid, _build_si_display_name(hit_dict, dim_map, sid))

            if target_type in ("HOST", "SERVICE") and host_key and host_key not in all_hosts:
                all_hosts[host_key] = (
                    dim_map.get("ip") or hit_dict.get("ip") or hit_dict.get("event", {}).get("ip") or host_key
                )

            # ── K8S Cluster 统计（与 CMDB Set 并行，不互斥）────────────────
            if target_type and target_type.startswith("K8S"):
                cluster_id = dim_map.get("bcs_cluster_id")
                if cluster_id:
                    entry = k8s_clusters.setdefault(
                        cluster_id, {"display_name": "", "nodes": {}, "services": {}, "pods": {}}
                    )
                    if dim_cluster_display and not entry["display_name"]:
                        entry["display_name"] = dim_cluster_display

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
            "instance_list": [{"bk_host_id": int(hid), "display_name": dn} for hid, dn in all_hosts.items()][:50],
            "link_tpl": "/performance/detail/{bk_host_id}",
        }

    if all_sids:
        result["service_instances"] = {
            "count": len(all_sids),
            "instance_list": [
                {"bk_service_instance_id": int(si_id), "display_name": dn} for si_id, dn in all_sids.items()
            ][:50],
            "link_tpl": None,
        }

    if k8s_clusters:
        if len(k8s_clusters) > 1:
            result["cluster"] = {
                "count": len(k8s_clusters),
                "instance_list": [
                    {"bcs_cluster_id": cid, "display_name": d["display_name"]} for cid, d in k8s_clusters.items()
                ][:50],
                "link_tpl": "/k8s?filter-bcs_cluster_id={bcs_cluster_id}&sceneId=kubernetes&sceneType=overview",
            }
        else:
            cid, cdata = next(iter(k8s_clusters.items()))
            if cdata["nodes"]:
                result["node"] = {
                    "count": len(cdata["nodes"]),
                    "instance_list": [
                        {"bcs_cluster_id": cid, "node": n, "display_name": dn} for n, dn in cdata["nodes"].items()
                    ][:50],
                    "link_tpl": (
                        "/k8s?filter-bcs_cluster_id={bcs_cluster_id}"
                        "&filter-node_name={node}&dashboardId=node"
                        "&sceneId=kubernetes&sceneType=detail"
                    ),
                }
            if cdata["services"]:
                result["service"] = {
                    "count": len(cdata["services"]),
                    "instance_list": [
                        {"bcs_cluster_id": cid, "service": s, "display_name": dn} for s, dn in cdata["services"].items()
                    ][:50],
                    "link_tpl": (
                        "/k8s?filter-bcs_cluster_id={bcs_cluster_id}"
                        "&filter-service_name={service}&dashboardId=service"
                        "&sceneId=kubernetes&sceneType=detail"
                    ),
                }
            if cdata["pods"]:
                result["pod"] = {
                    "count": len(cdata["pods"]),
                    "instance_list": [
                        {"bcs_cluster_id": cid, "pod": p, "display_name": dn} for p, dn in cdata["pods"].items()
                    ][:50],
                    "link_tpl": (
                        "/k8s?filter-bcs_cluster_id={bcs_cluster_id}"
                        "&filter-pod_name={pod}&dashboardId=pod"
                        "&sceneId=kubernetes&sceneType=detail"
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
    通过 bk_inst_id 精确匹配当前 set_node，避免同一告警多 Set 时取错名称。
    K8S 宿主机场景由调用方循环结束后统一批量填充。
    """
    set_id = int(set_node.split("|")[1]) if "|" in set_node else None
    biz_name = set_name = ""
    for item in translation or []:
        obj = item.get("bk_obj_id", "") or item.get("bk_obj_name", "")
        name = item.get("bk_inst_name", "")
        if obj in ("biz", "业务"):
            biz_name = name
        elif obj in ("set", "集群") and set_id and int(item.get("bk_inst_id") or 0) == set_id:
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
