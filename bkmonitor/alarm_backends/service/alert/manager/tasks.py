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
import logging
import time
from typing import Dict, List

from elasticsearch.helpers import BulkIndexError
from elasticsearch_dsl import Q

from alarm_backends.constants import CONST_ONE_DAY, CONST_ONE_HOUR
from alarm_backends.core.alert.alert import Alert, AlertCache, AlertKey
from alarm_backends.core.cache.strategy import StrategyCacheManager
from alarm_backends.core.cluster import get_cluster_bk_biz_ids
from alarm_backends.service.alert.manager.processor import AlertManager
from alarm_backends.service.scheduler.app import app
from bkmonitor.documents import AlertDocument, AlertLog
from bkmonitor.documents.base import BulkActionType
from constants.alert import EventStatus
from core.prometheus import metrics

logger = logging.getLogger("alert.manager")

# 批处理条数
BATCH_SIZE = 200
# 默认检测周期
DEFAULT_CHECK_INTERVAL = 60


def check_abnormal_alert():
    """
    拉取异常告警，对这些告警进行状态管理
    """
    search = (
        AlertDocument.search(all_indices=True)
        .filter(Q("term", status=EventStatus.ABNORMAL) & ~Q('term', is_blocked=True))
        .source(fields=["id", "strategy_id", "event.bk_biz_id"])
    )

    # 获取集群内的业务ID
    cluster_bk_biz_ids = set(get_cluster_bk_biz_ids())

    alerts = []
    # 这里用 scan 迭代的查询方式，目的是为了突破 ES 查询条数 1w 的限制
    for hit in search.params(size=5000).scan():
        if not getattr(hit, "id", None) or not getattr(hit, "event", None) or not getattr(hit.event, "bk_biz_id", None):
            continue
        # 只处理集群内的告警
        if hit.event.bk_biz_id not in cluster_bk_biz_ids:
            continue
        alerts.append({"id": hit.id, "strategy_id": getattr(hit, "strategy_id", None)})

    if alerts:
        send_check_task(alerts)


def check_blocked_alert():
    """
    拉取异常告警，对这些告警进行状态管理
    """
    current_time = int(time.time())
    end_time = current_time - CONST_ONE_HOUR
    start_time = current_time - CONST_ONE_DAY
    logger.info("[check_blocked_alert] begin %s - %s", start_time, end_time)
    search = (
        AlertDocument.search(start_time=start_time, end_time=end_time)
        .filter(Q("term", status=EventStatus.ABNORMAL) & Q('term', is_blocked=True))
        .source(fields=["id", "strategy_id", "event.bk_biz_id"])
    )

    # 获取集群内的业务ID
    cluster_bk_biz_ids = set(get_cluster_bk_biz_ids())

    alerts = []
    total = 0
    # 这里用 scan 迭代的查询方式，目的是为了突破 ES 查询条数 1w 的限制
    for hit in search.params(size=BATCH_SIZE).scan():
        if not getattr(hit, "id", None) or not getattr(hit, "event", None) or not getattr(hit.event, "bk_biz_id", None):
            continue
        # 只处理集群内的告警
        if hit.event.bk_biz_id not in cluster_bk_biz_ids:
            continue
        alerts.append({"id": hit.id, "strategy_id": getattr(hit, "strategy_id", None)})
        total += 1
        if total % BATCH_SIZE == 0:
            alert_keys = [AlertKey(alert_id=alert["id"], strategy_id=alert.get("strategy_id")) for alert in alerts]
            check_blocked_alert_finished(alert_keys)
            logger.info("[check_blocked_alert]  blocked alert processed (%s)", len(alert_keys))
            alerts = []

    alert_keys = [AlertKey(alert_id=alert["id"], strategy_id=alert.get("strategy_id")) for alert in alerts]
    check_blocked_alert_finished(alert_keys)
    total += len(alerts)
    logger.info("[check_blocked_alert]  blocked alert total count(%s)", total)


def check_blocked_alert_finished(alert_keys):
    alerts = Alert.mget(alert_keys)
    for alert in alerts:
        alert.move_to_next_status()

    alert_logs = []
    alert_documents = []
    closed_alerts = []
    updated_alert_snaps = []
    for alert in alerts:
        if alert.should_refresh_db():
            alert_logs.extend(alert.list_log_documents())
            alert_documents.append(alert.to_document())
            updated_alert_snaps.append(alert)
        if alert.status == EventStatus.CLOSED:
            closed_alerts.append(alert.id)
    if alert_documents:
        try:
            AlertDocument.bulk_create(alert_documents, action=BulkActionType.UPSERT)
        except BulkIndexError as e:
            logger.error(
                "[check_blocked_alert_finished] save blocked alert document failed, total count(%s), "
                " updated(%s), error detail: %s",
                len(alert_keys),
                len(alert_documents),
                e.errors,
            )
            return
    if updated_alert_snaps:
        AlertCache.save_alert_to_cache(updated_alert_snaps)
        AlertCache.save_alert_snapshot(updated_alert_snaps)

    if alert_logs:
        try:
            AlertLog.bulk_create(alert_logs)
        except BulkIndexError as e:
            logger.error(
                "[check_blocked_alert_finished] save alert log document total count(%s) error: %s",
                len(alert_logs),
                e.errors,
            )
    logger.info(
        "[check_blocked_alert_finished] update blocked alert next status succeed, "
        "total count(%s), updated(%s), closed(%s)",
        len(alerts),
        len(alert_documents),
        len(closed_alerts),
    )


def send_check_task(alerts: List[Dict], run_immediately=True):
    """
    生成告警检测任务
    :param alerts: 告警对象列表
    :param run_immediately: 是否立即发送一个检查任务
    """
    if not alerts:
        return

    alert_ids_with_interval = cal_alerts_check_interval(alerts)

    for check_interval, alerts in alert_ids_with_interval.items():
        countdown = 0 if run_immediately else check_interval
        while countdown < DEFAULT_CHECK_INTERVAL:
            # 通过创建延时任务来满足1分钟内进行多次检测，其中：
            # 监控周期<30s，一分钟检测4次
            # 监控周期<60s，一分钟检测2次
            # 其他情况，一分钟检测1次
            for index in range(0, len(alerts), BATCH_SIZE):
                handle_alerts.apply_async(
                    countdown=countdown,
                    expires=120,
                    kwargs={
                        "alert_keys": [
                            AlertKey(alert_id=alert["id"], strategy_id=alert.get("strategy_id"))
                            for alert in alerts[index : index + BATCH_SIZE]
                        ]
                    },
                )
            countdown += check_interval

    logger.info(
        "[check_abnormal_alert] alerts(%s/60s, %s/30s, %s/15s) sent to AlertManager",
        len(alert_ids_with_interval[60]),
        len(alert_ids_with_interval[30]),
        len(alert_ids_with_interval[15]),
    )


@app.task(ignore_result=True, queue="celery_alert_manager")
def handle_alerts(alert_keys: List[AlertKey]):
    """
    处理告警（异步任务）
    """
    exc = None
    if not alert_keys:
        return
    total = len(alert_keys)
    manager = AlertManager(alert_keys)
    start_time = time.time()
    try:
        manager.logger.info("[alert.manager start] with total alerts(%s)", total)
        manager.process()
    except Exception as e:
        manager.logger.exception("[alert.manager ERROR] detail: %s", e)
        exc = e
        cost = time.time() - start_time
    else:
        cost = time.time() - start_time
        manager.logger.info("[alert.manager end] cost: %s", cost)

    # 按单条告警进行统计耗时，因为这有两个入口：
    # 1. 周期维护未恢复的告警， 按 total=200 分批跑
    # 2. 产生新告警时，由alert.builder 立刻执行一次周期任务管理， total 较小。
    # 因此会存在耗时跟随total值的变化抖动。所以这里算单条告警的处理平均耗时才能体现出实际情况
    metrics.ALERT_MANAGE_TIME.labels(status=metrics.StatusEnum.from_exc(exc), exception=exc).observe(cost / total)
    metrics.ALERT_MANAGE_COUNT.labels(status=metrics.StatusEnum.from_exc(exc), exception=exc).inc(total)
    metrics.report_all()


def fetch_agg_interval(strategy_ids: List[int]):
    """
    根据策略ID获取每个策略的聚合周期
    """
    agg_interval_by_strategy = {}

    strategies = StrategyCacheManager.get_strategy_by_ids(strategy_ids)

    for strategy in strategies:
        for item in strategy["items"]:
            # 补充周期缓存
            if "query_configs" not in item:
                continue

            for config in item["query_configs"]:
                if "agg_interval" not in config:
                    continue
                if strategy["id"] in agg_interval_by_strategy:
                    # 如果一个策略存在多个agg_interval，则取最小值
                    agg_interval_by_strategy[strategy["id"]] = min(
                        agg_interval_by_strategy[strategy["id"]], config["agg_interval"]
                    )
                else:
                    agg_interval_by_strategy[strategy["id"]] = config["agg_interval"]
    return agg_interval_by_strategy


def cal_alerts_check_interval(alerts: List[Dict]):
    """
    计算告警的检查周期
    监控周期<30s，每15s检查一次
    监控周期<60s，每30s检查一次
    其他情况统一每60s检查一次
    """
    check_interval = {
        15: [],
        30: [],
        60: [],
    }

    strategy_ids = set()

    for alert in alerts:
        strategy_id = alert.get("strategy_id")
        if strategy_id:
            strategy_ids.add(strategy_id)

    agg_interval_config = fetch_agg_interval(strategy_ids=list(strategy_ids))

    for alert in alerts:
        strategy_id = alert.get("strategy_id")
        if not strategy_id or strategy_id not in agg_interval_config:
            # 告警没有策略ID，或者策略中没有周期配置，则按默认60秒检查一次
            check_interval[60].append(alert)
            continue

        agg_interval = agg_interval_config[strategy_id]
        if agg_interval < 30:
            check_interval[15].append(alert)
        elif agg_interval < 60:
            check_interval[30].append(alert)
        else:
            check_interval[60].append(alert)
    return check_interval
