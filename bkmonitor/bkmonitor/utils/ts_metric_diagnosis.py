"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

自定义时序指标同步排障核心逻辑。

可被 management command 和 bkm_cli 服务桥共同调用，不依赖 BaseCommand 或 stdout。

judge 枚举（与 bkm-cli metric-sync-layering check 对齐）：
  source      — transfer / BKData 侧没有该指标
  metadata    — source 有，但 TimeSeriesMetric / ResultTableField 缺失
  web_cache   — metadata 已同步，但 MetricListCache 未建立
  ok          — 三层均已命中（含策略侧缓存命中的情况）
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from metadata.utils.redis_tools import RedisTools
from utils.redis_client import RedisClient

_STAGE_PRIORITY: list[str] = ["source", "metadata", "web_cache", "ok"]


def diagnose_ts_metric_sync(
    data_id: int,
    metrics: list[str],
    window_seconds: int | None = None,
    history_seconds: int | None = None,
    redis_prefix: str = "BK_MONITOR_TRANSFER",
) -> dict[str, Any]:
    """诊断自定义时序指标在 source / metadata / web_cache 三层中的同步状态。

    同时支持 management command 和 bkm_cli 服务桥调用。

    Returns:
        dict 包含：
          judge    — 整体最严重阻塞层（multi-metric 时取最严重）
          context  — 环境上下文
          summary  — 聚合摘要
          metrics  — 逐指标诊断列表
    """
    from django.conf import settings

    if window_seconds is None:
        window_seconds = settings.FETCH_TIME_SERIES_METRIC_INTERVAL_SECONDS
    if history_seconds is None:
        history_seconds = settings.TIME_SERIES_METRIC_EXPIRED_SECONDS

    ts_group = _load_ts_group(data_id)
    redis_client = _make_redis_client(redis_prefix)
    report = _build_report(
        ts_group=ts_group,
        metrics=metrics,
        redis_client=redis_client,
        window_seconds=window_seconds,
        history_seconds=history_seconds,
        redis_prefix=redis_prefix,
    )

    # 顶层 judge：取所有指标中最严重的阻塞阶段
    stages = [m["diagnosis"]["stage"] for m in report["metrics"]]
    report["judge"] = _worst_stage(stages)
    return report


def _worst_stage(stages: list[str]) -> str:
    """多指标时取优先级最高的阻塞阶段（source > metadata > web_cache > ok）。"""
    for stage in _STAGE_PRIORITY:
        if stage in stages:
            return stage
    return "source"


def _load_ts_group(data_id: int) -> Any:
    from metadata import models

    try:
        return models.TimeSeriesGroup.objects.get(bk_data_id=data_id)
    except models.TimeSeriesGroup.DoesNotExist as exc:
        raise ValueError(f"data_id: {data_id} not found from TimeSeriesGroup") from exc


def _make_redis_client(prefix: str) -> Any:
    return RedisClient.from_envs(prefix=prefix)


def _build_report(
    ts_group: Any,
    metrics: list[str],
    redis_client: Any,
    window_seconds: int,
    history_seconds: int,
    redis_prefix: str,
) -> dict[str, Any]:
    from django.conf import settings
    from django.utils import timezone

    now_ts = timezone.now().timestamp()
    source_backend = _detect_source_backend(ts_group)
    metrics_key = f"{settings.METRICS_KEY_PREFIX}{ts_group.bk_data_id}" if source_backend == "redis" else ""
    dimensions_key = (
        f"{settings.METRIC_DIMENSIONS_KEY_PREFIX}{ts_group.bk_data_id}" if source_backend == "redis" else ""
    )

    recent_metric_infos = ts_group.get_metrics_from_redis(expired_time=window_seconds)
    history_metric_infos = ts_group.get_metrics_from_redis(expired_time=history_seconds)
    recent_metric_map = {item["field_name"]: item for item in recent_metric_infos}
    history_metric_map = {item["field_name"]: item for item in history_metric_infos}
    recent_members = (
        _get_recent_metric_members(
            redis_client=redis_client,
            metrics_key=metrics_key,
            begin_ts=now_ts - window_seconds,
            end_ts=now_ts,
        )
        if source_backend == "redis"
        else {}
    )

    metric_reports = [
        _build_metric_report(
            ts_group=ts_group,
            metric=metric,
            source_backend=source_backend,
            redis_client=redis_client,
            metrics_key=metrics_key,
            dimensions_key=dimensions_key,
            recent_metric_map=recent_metric_map,
            history_metric_map=history_metric_map,
            recent_members=recent_members,
        )
        for metric in metrics
    ]

    return {
        "context": {
            "data_id": ts_group.bk_data_id,
            "bk_biz_id": ts_group.bk_biz_id,
            "time_series_group_id": ts_group.time_series_group_id,
            "table_id": ts_group.table_id,
            "time_series_group_name": ts_group.time_series_group_name,
            "window_seconds": window_seconds,
            "history_seconds": history_seconds,
            "environment_code": getattr(settings, "ENVIRONMENT_CODE", ""),
            "process_role": os.environ.get("BKAPP_PROCESS_NAME", ""),
            "source": _build_source_context(
                source_backend=source_backend,
                redis_prefix=redis_prefix,
                metrics_key=metrics_key,
                dimensions_key=dimensions_key,
            ),
        },
        "summary": {
            "checked_metrics": len(metrics),
            "recent_metric_count": len(recent_metric_infos),
            "recent_metric_max_modify_time": max(
                (item["last_modify_time"] for item in recent_metric_infos),
                default=None,
            ),
        },
        "metrics": metric_reports,
    }


def _build_metric_report(
    ts_group: Any,
    metric: str,
    source_backend: str,
    redis_client: Any,
    metrics_key: str,
    dimensions_key: str,
    recent_metric_map: dict[str, dict[str, Any]],
    history_metric_map: dict[str, dict[str, Any]],
    recent_members: dict[str, float],
) -> dict[str, Any]:
    from bkmonitor.models.metric_list_cache import MetricListCache
    from constants.data_source import DataSourceLabel, DataTypeLabel
    from metadata import models

    redis_metric_score = redis_client.zscore(metrics_key, metric) if source_backend == "redis" else None
    redis_dimension_raw = redis_client.hget(dimensions_key, metric) if source_backend == "redis" else None
    redis_recent_detail = recent_metric_map.get(metric)
    redis_history_detail = history_metric_map.get(metric)

    ts_metric = models.TimeSeriesMetric.objects.filter(
        group_id=ts_group.time_series_group_id,
        field_name=metric,
    ).first()
    rt_field = models.ResultTableField.objects.filter(
        table_id=ts_group.table_id,
        field_name=metric,
    ).first()
    direct_metric_caches = list(
        MetricListCache.objects.filter(
            bk_biz_id=ts_group.bk_biz_id,
            result_table_id=ts_group.table_id,
            metric_field=metric,
            data_source_label=DataSourceLabel.CUSTOM,
            data_type_label=DataTypeLabel.TIME_SERIES,
        )
        .values("bk_biz_id", "result_table_id", "metric_field", "data_label", "last_update")
        .order_by("bk_biz_id")
    )
    strategy_metric_cache_candidates = list(
        MetricListCache.objects.filter(
            bk_biz_id=ts_group.bk_biz_id,
            metric_field=metric,
            data_type_label=DataTypeLabel.TIME_SERIES,
        )
        .exclude(
            result_table_id=ts_group.table_id,
            data_source_label=DataSourceLabel.CUSTOM,
        )
        .values(
            "bk_biz_id",
            "bk_tenant_id",
            "result_table_id",
            "metric_field",
            "metric_field_name",
            "data_source_label",
            "data_type_label",
            "result_table_label",
            "result_table_name",
            "related_name",
            "data_label",
            "last_update",
        )
        .order_by("data_source_label", "result_table_id", "metric_field")
    )
    web_metric_cache_candidates = [
        candidate
        for candidate in strategy_metric_cache_candidates
        if candidate["data_source_label"] == DataSourceLabel.BK_MONITOR_COLLECTOR
    ]
    web_metric_caches = direct_metric_caches or web_metric_cache_candidates

    diagnosis_stage, diagnosis_message, action = _diagnose_metric(
        ts_group=ts_group,
        source_backend=source_backend,
        redis_metric_score=redis_metric_score,
        redis_dimension_raw=redis_dimension_raw,
        redis_recent_detail=redis_recent_detail,
        redis_history_detail=redis_history_detail,
        ts_metric=ts_metric,
        rt_field=rt_field,
        direct_metric_caches=direct_metric_caches,
        web_metric_cache_candidates=web_metric_cache_candidates,
    )

    return {
        "metric": metric,
        "status": {
            "source_recent_discovered": redis_recent_detail is not None,
            "source_history_discovered": redis_history_detail is not None,
            "metadata_time_series_metric_exists": bool(ts_metric),
            "metadata_result_table_field_exists": bool(rt_field),
            "direct_metric_cache_exists": bool(direct_metric_caches),
            "web_metric_cache_exists": bool(web_metric_caches),
        },
        "details": {
            "source": _build_source_details(
                source_backend=source_backend,
                redis_metric_score=redis_metric_score,
                redis_dimension_raw=redis_dimension_raw,
                redis_recent_detail=redis_recent_detail,
                redis_history_detail=redis_history_detail,
                recent_members=recent_members,
                metric=metric,
            ),
            "metadata_time_series_metric": (
                {
                    "field_name": ts_metric.field_name,
                    "field_scope": ts_metric.field_scope,
                    "is_active": ts_metric.is_active,
                    "last_modify_time": ts_metric.last_modify_time,
                    "tag_list": ts_metric.tag_list,
                }
                if ts_metric
                else None
            ),
            "metadata_result_table_field": (
                {
                    "field_name": rt_field.field_name,
                    "field_type": rt_field.field_type,
                    "tag": rt_field.tag,
                    "description": rt_field.description,
                    "unit": rt_field.unit,
                }
                if rt_field
                else None
            ),
            "direct_metric_cache": direct_metric_caches,
            "web_metric_cache_candidates": web_metric_cache_candidates,
            "strategy_metric_cache_candidates": strategy_metric_cache_candidates,
        },
        "diagnosis": {
            "stage": diagnosis_stage,
            "message": diagnosis_message,
            "next_action": action,
        },
    }


def _get_recent_metric_members(
    redis_client: Any,
    metrics_key: str,
    begin_ts: float,
    end_ts: float,
) -> dict[str, float]:
    from collections.abc import Iterable

    members: Iterable[tuple[bytes | str, float]] = redis_client.zrangebyscore(
        metrics_key,
        begin_ts,
        end_ts,
        withscores=True,
    )
    return {(member.decode("utf-8") if isinstance(member, bytes) else str(member)): score for member, score in members}


def _diagnose_metric(
    ts_group: Any,
    source_backend: str,
    redis_metric_score: float | None,
    redis_dimension_raw: bytes | str | None,
    redis_recent_detail: dict[str, Any] | None,
    redis_history_detail: dict[str, Any] | None,
    ts_metric: Any | None,
    rt_field: Any | None,
    direct_metric_caches: list[dict[str, Any]],
    web_metric_cache_candidates: list[dict[str, Any]],
) -> tuple[str, str, str]:
    """根据各层检查结果推断故障环节。

    Returns:
        (stage, message, next_action)
        stage 枚举：source | metadata | web_cache | ok
    """
    if source_backend == "bkdata" and redis_recent_detail is None and redis_history_detail is None:
        return (
            "source",
            "source 层当前走 BKData 查询，但近期与历史窗口都没有发现该指标。",
            "建议先核对 BKData 侧 query_metric_and_dimension 返回是否包含该 metric，再确认 AccessVMRecord 与 RT 关联是否正确。",
        )
    if source_backend == "redis" and redis_metric_score is None and not redis_dimension_raw:
        return (
            "source",
            "source 层没有发现该指标，当前环境下 transfer Redis 两个 key 都未命中。",
            (
                "建议先核对实际上报 payload 是否带上该 metric、是否写入当前 DataID，"
                "并确认 api 与 transfer/metadata 是否处于同一环境。"
            ),
        )
    if source_backend == "redis" and redis_metric_score is not None and not redis_dimension_raw:
        return (
            "source",
            "source 层写入不完整，metrics zset 已有记录，但 metric_dimensions 中缺少维度信息。",
            "优先检查 transfer 指标发现逻辑是否只写入 zset，或 dimensions 解析/落 Redis 是否失败。",
        )
    if redis_history_detail is not None and redis_recent_detail is None:
        return (
            "source",
            f"历史窗口内存在该指标，但近期窗口未命中，说明最近没有持续上报，或当前 {source_backend} source 未返回最新数据。",
            "继续观察最近 2 小时实际流量，或让业务补打一条样本后重新执行本命令。",
        )
    if source_backend == "redis" and redis_recent_detail is None:
        return (
            "source",
            "Redis 中存在原始痕迹，但 metadata 可消费的近期指标明细未命中。",
            "优先检查 transfer 指标发现逻辑、非法指标名过滤、以及当前环境 Redis 配置是否正确。",
        )
    if ts_metric is None:
        return (
            "metadata",
            "source 层已命中，但 metadata 的 TimeSeriesMetric 中不存在该指标。",
            (
                f"建议到后台环境执行 `python manage.py refresh_ts_metric --data_id {ts_group.bk_data_id}`，"
                "并检查 update_time_series_metrics 定时任务是否正常。"
            ),
        )
    if rt_field is None:
        return (
            "metadata",
            "TimeSeriesMetric 已存在，但 ResultTableField 中没有该字段。",
            "说明 metadata 已发现指标，但结果表字段刷新阶段未落库，需检查 update_metrics 链路。",
        )
    # 策略侧缓存命中（非直连缓存），也属于 ok：页面侧通过不同 data_source_label 已能搜到
    if web_metric_cache_candidates:
        first_candidate = web_metric_cache_candidates[0]
        return (
            "ok",
            (
                f"该 TimeSeriesGroup 指标已在策略侧缓存中命中，"
                f"data_source_label={first_candidate['data_source_label']}，"
                "当前不属于指标缓存缺失问题。"
            ),
            (
                "若页面已能搜到该指标，可结束排查；"
                "若页面仍搜不到，请抓 get_metric_list 接口返回，继续核对 data_source_label、result_table_label 与查询条件。"
            ),
        )
    if not direct_metric_caches:
        return (
            "web_cache",
            (
                "metadata 已同步完成，但当前 api 环境下尚未命中该指标对应的策略侧 MetricListCache。"
                "这通常意味着页面侧缓存尚未刷新。"
            ),
            (f"建议在 api 环境执行 `update_metric_list_by_biz({ts_group.bk_biz_id})` 或等待策略指标缓存定时任务刷新。"),
        )
    return (
        "ok",
        f"source({source_backend})、metadata、web_cache 三层均已命中，当前环境下后端链路正常。",
        "如果页面仍查不到，请继续核对前端筛选条件、业务范围或租户差异。",
    )


def _detect_source_backend(ts_group: Any) -> str:
    from metadata import config as metadata_config

    table_id_white_list = RedisTools.get_list(metadata_config.METADATA_RESULT_TABLE_WHITE_LIST)
    if ts_group.table_id in table_id_white_list:
        return "bkdata"

    try:
        from metadata.models.constants import DataIdCreatedFromSystem

        if ts_group.data_source.created_from == DataIdCreatedFromSystem.BKDATA.value:
            return "bkdata"
    except Exception:
        pass

    return "redis"


def _build_source_context(
    source_backend: str,
    redis_prefix: str,
    metrics_key: str,
    dimensions_key: str,
) -> dict[str, Any]:
    if source_backend == "bkdata":
        return {
            "backend": "bkdata",
            "query_path": "bkdata.query_metric_and_dimension",
        }
    return {
        "backend": "redis",
        "query_path": "transfer.redis",
        "redis_config_prefix": redis_prefix,
        "metrics_key": metrics_key,
        "dimensions_key": dimensions_key,
    }


def _build_source_details(
    source_backend: str,
    redis_metric_score: float | None,
    redis_dimension_raw: bytes | str | None,
    redis_recent_detail: dict[str, Any] | None,
    redis_history_detail: dict[str, Any] | None,
    recent_members: dict[str, float],
    metric: str,
) -> dict[str, Any]:
    source_details: dict[str, Any] = {
        "backend": source_backend,
        "recent_detail": redis_recent_detail,
        "history_detail": redis_history_detail,
    }
    if source_backend == "redis":
        source_details["redis"] = {
            "metrics_zset_exists": redis_metric_score is not None,
            "metric_dimensions_exists": bool(redis_dimension_raw),
            "metric_score": redis_metric_score,
            "recent_score": recent_members.get(metric),
        }
    return source_details


def render_text(report: dict[str, Any]) -> str:
    """将诊断报告渲染为可读终端文本（management command 使用）。"""
    context = report["context"]
    summary = report["summary"]
    source_context = context["source"]
    process_role = context["process_role"] or "unknown"
    max_modify_time = _format_timestamp(summary["recent_metric_max_modify_time"])

    lines = [
        "=== 自定义时序指标同步排障报告 ===",
        f"DataID: {context['data_id']}",
        f"业务ID: {context['bk_biz_id']}",
        f"TimeSeriesGroup: {context['time_series_group_id']} ({context['time_series_group_name']})",
        f"结果表: {context['table_id']}",
        f"当前环境: ENVIRONMENT_CODE={context['environment_code']} PROCESS={process_role}",
        f"Source后端: {source_context['backend']}",
        f"Source查询: {source_context['query_path']}",
        "建议角色: 该命令优先在 api 角色执行，用来确认当前 web/api 环境看到的 source、metadata、缓存状态。",
        f"近期发现指标数: {summary['recent_metric_count']}",
        f"近期最大上报时间: {max_modify_time}",
        f"近期窗口: {context['window_seconds']}s, 历史窗口: {context['history_seconds']}s",
    ]

    if source_context["backend"] == "redis":
        lines.extend(
            [
                f"Redis前缀: {source_context['redis_config_prefix']}",
                f"metrics_key: {source_context['metrics_key']}",
                f"dimensions_key: {source_context['dimensions_key']}",
            ]
        )

    lines.append("")

    for metric_report in report["metrics"]:
        status = metric_report["status"]
        source_details = metric_report["details"]["source"]
        diagnosis = metric_report["diagnosis"]
        web_metric_cache_candidates = metric_report["details"]["web_metric_cache_candidates"]
        lines.extend(
            [
                f"[指标] {metric_report['metric']}",
                f"  结论环节: {diagnosis['stage']}",
                f"  结论说明: {diagnosis['message']}",
                f"  下一步: {diagnosis['next_action']}",
                f"  source.backend: {source_details['backend']}",
            ]
        )

        if source_details["backend"] == "redis":
            lines.extend(
                [
                    f"  source.redis.metrics_zset: {'是' if source_details['redis']['metrics_zset_exists'] else '否'}",
                    f"  source.redis.metric_dimensions: {'是' if source_details['redis']['metric_dimensions_exists'] else '否'}",
                ]
            )

        lines.extend(
            [
                f"  source.近期发现窗口: {'是' if status['source_recent_discovered'] else '否'}",
                f"  source.历史发现窗口: {'是' if status['source_history_discovered'] else '否'}",
                f"  metadata.TimeSeriesMetric: {'是' if status['metadata_time_series_metric_exists'] else '否'}",
                f"  metadata.ResultTableField: {'是' if status['metadata_result_table_field_exists'] else '否'}",
                f"  web.MetricListCache: {'是' if status['web_metric_cache_exists'] else '否'}",
                ("  缓存命中依据:" if status["web_metric_cache_exists"] else "  缓存未命中依据:"),
                (
                    "    - 当前业务下未找到该指标的策略侧缓存记录"
                    if not web_metric_cache_candidates
                    else "    - "
                    + "；".join(
                        f"data_source={item['data_source_label']}, "
                        f"result_table_label={item['result_table_label'] or '-'}, "
                        f"result_table_name={item['result_table_name'] or '-'}, "
                        f"result_table_id={item['result_table_id'] or '-'}"
                        for item in web_metric_cache_candidates
                    )
                ),
                "",
            ]
        )

    return "\n".join(lines)


def _format_timestamp(value: float | int | None) -> str:
    from django.utils import timezone

    if value is None:
        return "无"
    dt = datetime.fromtimestamp(value, tz=timezone.get_current_timezone())
    return f"{value} ({dt.strftime('%Y-%m-%d %H:%M:%S %Z')})"
