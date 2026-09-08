"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
"""

import time
from collections import defaultdict

from django.db import transaction

from apps.api import TransferApi
from apps.feature_toggle.models import FeatureToggle
from apps.feature_toggle.plugins.constants import SCENE_SEARCH
from apps.log_databus.constants import ADMIN_REQUEST_USER, build_collector_scene_labels, detect_container_stream
from apps.log_databus.handlers.collector.base import CollectorHandler
from apps.log_databus.models import CollectorConfig, ContainerCollectorConfig
from apps.log_search.constants import CustomTypeEnum
from apps.log_search.models import TAG_TYPE_SCENE, IndexSetTag, LogIndexSet
from apps.utils.log import logger

# 特性开关 feature_config 中的标记：是否已完成首次全量校正并转正。
# 一旦为 True，周期任务不再自动翻开关，回滚到 debug/off 后也不会被任务重新打开。
SCENE_SEARCH_RELEASED_KEY = "scene_search_released"
COMPARE_MODE_LOCAL = "local"
COMPARE_MODE_REMOTE = "remote"


def get_container_streams(collector_config_ids: list[int]) -> dict[int, str]:
    """批量查询容器采集类型并解析 stream，避免 N+1。"""
    collector_types = defaultdict(set)
    for collector_config_id, collector_type in ContainerCollectorConfig.objects.filter(
        collector_config_id__in=collector_config_ids
    ).values_list("collector_config_id", "collector_type"):
        collector_types[collector_config_id].add(collector_type)
    return {
        collector_config_id: detect_container_stream(types) for collector_config_id, types in collector_types.items()
    }


def get_local_scene_labels(index_set_id: int | None) -> dict:
    """从本地 LogIndexSet.tag_ids 还原场景标签（纯 DB 查询，0 远端调用）。"""
    if not index_set_id:
        return {}
    try:
        index_set = LogIndexSet.objects.get(index_set_id=index_set_id)
    except LogIndexSet.DoesNotExist:
        return {}
    return dict(
        IndexSetTag.objects.filter(tag_id__in=index_set.tag_ids, tag_type=TAG_TYPE_SCENE).values_list("name", "value")
    )


def get_remote_scene_labels(table_id: str) -> dict:
    """读取 ResultTable 的场景标签，用于首次校正和人工巡检/修复。"""
    result_table = TransferApi.get_result_table({"table_id": table_id})
    return result_table.get("labels") or {}


def refresh_scene_labels(
    bk_biz_id: int | None = None,
    compare_mode: str = COMPARE_MODE_LOCAL,
    dry_run: bool = False,
    batch_size: int = 50,
    sleep: float = 0.5,
) -> dict:
    """刷新采集项的场景标签。

    compare_mode=local：仅对比本地 tag_ids，不一致才写远端 + 本地；周期任务使用此模式。
    compare_mode=remote：读取 ResultTable.labels 后再比较；首次校正和人工命令使用此模式。

    返回统计：{total, success, failed, skipped}。
    - failed 为本次写入失败的 RT；首次转正前会在下一轮按远端标签继续重试；
    - skipped 为稳态下本地已一致而跳过的数量。
    """
    if compare_mode not in {COMPARE_MODE_LOCAL, COMPARE_MODE_REMOTE}:
        raise ValueError(f"unsupported scene label compare mode: {compare_mode}")

    qs = CollectorConfig.objects.filter(table_id__isnull=False, index_set_id__isnull=False).exclude(table_id="")
    qs = qs.filter(is_active=True).exclude(custom_type=CustomTypeEnum.OTLP_TRACE.value)
    if bk_biz_id is not None:
        qs = qs.filter(bk_biz_id=bk_biz_id)
    qs = qs.order_by("collector_config_id")

    configs = qs.values_list(
        "collector_config_id",
        "table_id",
        "collector_config_name_en",
        "collector_scenario_id",
        "custom_type",
        "environment",
        "bcs_cluster_id",
        "bk_app_code",
        "bk_biz_id",
        "index_set_id",
        named=True,
    )

    success = failed = skipped = 0
    failed_result_table_ids = []
    total = qs.count()
    last_collector_config_id = 0
    while True:
        batch = list(configs.filter(collector_config_id__gt=last_collector_config_id)[:batch_size])
        if not batch:
            break

        container_streams = get_container_streams([cfg.collector_config_id for cfg in batch])
        for cfg in batch:
            labels = build_collector_scene_labels(
                collector_scenario_id=cfg.collector_scenario_id,
                custom_type=cfg.custom_type,
                environment=cfg.environment,
                bcs_cluster_id=cfg.bcs_cluster_id,
                container_stream=container_streams.get(cfg.collector_config_id, ""),
                bk_app_code=cfg.bk_app_code,
                table_id=cfg.table_id,
                collector_config_name_en=cfg.collector_config_name_en,
            )

            if dry_run:
                logger.info("[refresh_scene_labels][dry-run] %s -> %s", cfg.table_id, labels)
                success += 1
                continue

            try:
                if compare_mode == COMPARE_MODE_LOCAL:
                    current_labels = get_local_scene_labels(cfg.index_set_id)
                else:
                    current_labels = get_remote_scene_labels(cfg.table_id)
                if current_labels == labels:
                    skipped += 1
                    continue

                TransferApi.switch_result_table(
                    {
                        "table_id": cfg.table_id,
                        "bk_biz_id": cfg.bk_biz_id,
                        "operator": ADMIN_REQUEST_USER,
                        "labels": labels,
                    }
                )
                CollectorHandler.sync_scene_tags_to_index_set(cfg.index_set_id, labels)
                success += 1
                logger.info("[refresh_scene_labels] %s -> %s", cfg.table_id, labels)
            except Exception as e:  # pylint: disable=broad-except
                failed += 1
                failed_result_table_ids.append(cfg.table_id)
                logger.exception("[refresh_scene_labels] %s failed: %s", cfg.table_id, e)

        last_collector_config_id = batch[-1].collector_config_id
        if not dry_run and len(batch) == batch_size:
            time.sleep(max(sleep, 0))

    return {
        "total": total,
        "success": success,
        "failed": failed,
        "skipped": skipped,
        "failed_result_table_ids": failed_result_table_ids,
    }


def is_scene_search_released() -> bool:
    """是否已走过首次全量校正并转正（通过 feature_config 标记判断）。"""
    toggle = FeatureToggle.objects.filter(name=SCENE_SEARCH).first()
    if not toggle:
        return False
    return bool((toggle.feature_config or {}).get(SCENE_SEARCH_RELEASED_KEY))


def release_scene_search() -> bool:
    """记录场景检索已发布，必要时将 debug 开关转为 on。"""
    with transaction.atomic():
        toggle = FeatureToggle.objects.select_for_update().filter(name=SCENE_SEARCH).first()
        if not toggle:
            logger.error("[scene_search] toggle missing: %s", SCENE_SEARCH)
            return False

        feature_config = dict(toggle.feature_config or {})
        if feature_config.get(SCENE_SEARCH_RELEASED_KEY):
            return False

        if toggle.status not in {"debug", "on"}:
            logger.warning("[scene_search] skip automatic release because status=%s", toggle.status)
            return False

        feature_config[SCENE_SEARCH_RELEASED_KEY] = True
        update_kwargs = {"feature_config": feature_config}
        if toggle.status == "debug":
            update_kwargs["status"] = "on"

        # 带上旧状态，避免校正结束前人工修改开关状态时被任务覆盖。
        updated = FeatureToggle.objects.filter(pk=toggle.pk, status=toggle.status).update(**update_kwargs)
        return updated == 1


def run_scene_search_sync() -> dict:
    """周期任务执行体：首次按远端标签校正，后续按本地标签补差。"""
    if is_scene_search_released():
        result = refresh_scene_labels(compare_mode=COMPARE_MODE_LOCAL)
        logger.info("[scene_search] steady refresh done: %s", result)
        return result

    result = refresh_scene_labels(compare_mode=COMPARE_MODE_REMOTE)
    if result["failed"]:
        # 存在失败项时不打 released 标记、不翻开关，保持 debug，留给下一轮继续按远端重试。
        # 失败项通过人工命令 `refresh_result_table_labels --compare-remote` 排查修复，
        # 修复后下一轮 failed 归零即可自动转正。
        logger.warning(
            "[scene_search] %d result tables failed, defer release to next round; failed ids: %s",
            result["failed"],
            result["failed_result_table_ids"],
        )
        return result

    if release_scene_search():
        logger.info("[scene_search] released after first remote sync: %s", result)
    return result
