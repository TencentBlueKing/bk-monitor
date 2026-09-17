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

import arrow
from django.utils import timezone
from elasticsearch.helpers import BulkIndexError
from elasticsearch_dsl import Q

from alarm_backends.core.alert.alert import Alert, AlertCache, AlertKey
from alarm_backends.core.cache.key import ALERT_UPDATE_LOCK
from alarm_backends.core.cluster import get_cluster_bk_biz_ids
from alarm_backends.core.lock.service_lock import multi_service_lock
from alarm_backends.service.alert.manager.tasks import BATCH_SIZE, _search_after_hits
from alarm_backends.service.converge.shield.window import business_timezone, close_time_matcher
from bkmonitor.documents import AlertDocument, AlertLog
from bkmonitor.documents.base import BulkActionType
from bkmonitor.models import Shield
from constants.alert import EventStatus

logger = logging.getLogger("alert.manager")


def check_shield_end_close_alert():
    """托管告警独立扫描：只保留一批 ID，不进入普通状态检查链。"""
    search = (
        AlertDocument.search(all_indices=True)
        .filter(Q("term", status=EventStatus.ABNORMAL) & Q("term", shield_end_close=True))
        .source(fields=["id", "strategy_id", "event.bk_biz_id"])
    )
    biz_ids = set(get_cluster_bk_biz_ids())
    keys = []
    for hit in _search_after_hits(search, page_size=BATCH_SIZE):
        source = hit.get("_source") or {}
        if not source.get("id") or (source.get("event") or {}).get("bk_biz_id") not in biz_ids:
            continue
        keys.append(AlertKey(alert_id=source["id"], strategy_id=source.get("strategy_id")))
        if len(keys) == BATCH_SIZE:
            check_shield_end_close_finished(keys)
            keys = []
    if keys:
        check_shield_end_close_finished(keys)


def shield_is_active(shield, now):
    """只检查本轮配置的状态与时间；不重匹配维度，不回放短时变更。"""
    if shield.is_deleted or not shield.is_enabled:
        return False
    with timezone.override(business_timezone(shield.bk_biz_id)):
        matcher = close_time_matcher(shield.cycle_config, shield.begin_time, shield.end_time)
        return matcher.is_match(now)


def check_shield_end_close_finished(alert_keys):
    candidates = Alert.mget(alert_keys)
    if not candidates:
        return
    lock_keys = [ALERT_UPDATE_LOCK.get_key(dedupe_md5=alert.dedupe_md5) for alert in candidates]
    with multi_service_lock(ALERT_UPDATE_LOCK, lock_keys) as lock:
        keys = [
            alert.key for alert in candidates if lock.is_locked(ALERT_UPDATE_LOCK.get_key(dedupe_md5=alert.dedupe_md5))
        ]
        alerts = [
            alert
            for alert in Alert.mget(keys)
            if alert.is_abnormal()
            and alert.shield_end_close
            and lock.is_locked(ALERT_UPDATE_LOCK.get_key(dedupe_md5=alert.dedupe_md5))
        ]
        associations = {}
        for alert in alerts:
            config = alert.get_extra_info("shield_end_close_config") or {}
            shield_id = config.get("shield_id")
            if not isinstance(shield_id, int) or shield_id <= 0:
                logger.error("[shield_end_close] alert(%s) has no valid owner", alert.id)
                continue
            associations[alert.id] = shield_id
        if not associations:
            return
        # 原始 manager 包含软删除记录。缺失并不等价于明确删除，保留告警并告警日志。
        # SQL 异常直接抛出，整批不执行关闭；每批只进行一次配置查询。
        shields = Shield.origin_objects.in_bulk(set(associations.values()))
        now = arrow.now()
        active = {}
        for shield_id in set(associations.values()):
            shield = shields.get(shield_id)
            if shield is None:
                logger.error("[shield_end_close] owner shield(%s) is missing, keep alerts", shield_id)
                continue
            try:
                active[shield_id] = shield_is_active(shield, now)
            except Exception:
                logger.exception("[shield_end_close] owner shield(%s) has unreadable time config", shield_id)

        closed = []
        for alert in alerts:
            if active.get(associations.get(alert.id)) is not False:
                continue
            alert.set_end_status(
                EventStatus.CLOSED,
                AlertLog.OpType.CLOSE,
                description="屏蔽结束，期间产生的告警已关闭",
            )
            closed.append(alert)
        if not closed:
            return

        # 先持久化，再更新成功项的缓存。锁内按 ID 更新，避免旧告警覆盖后继去重身份。
        try:
            AlertDocument.bulk_create([alert.to_document() for alert in closed], action=BulkActionType.UPSERT)
        except BulkIndexError as exc:
            logger.error("[shield_end_close] partial save failure: %s", exc.errors)
            failed_ids = {str(result["_id"]) for error in exc.errors for result in error.values()}
            closed = [alert for alert in closed if str(alert.id) not in failed_ids]
        if not closed:
            return
        AlertCache.update_alert_to_cache(closed)
        AlertCache.save_alert_snapshot(closed)
        AlertLog.bulk_create([entry for alert in closed for entry in alert.list_log_documents()])
        logger.info("[shield_end_close] silently closed %s alerts", len(closed))
