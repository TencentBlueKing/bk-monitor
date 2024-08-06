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
import json
import logging
import time
from collections import defaultdict
from typing import List

from elasticsearch.helpers import BulkIndexError

from alarm_backends.core.alert import Alert, Event
from alarm_backends.core.alert.alert import AlertCache
from alarm_backends.core.cache.key import ALERT_CONTENT_KEY, ALERT_DEDUPE_CONTENT_KEY
from alarm_backends.service.composite.tasks import check_action_and_composite
from bkmonitor.documents import AlertDocument, AlertLog
from bkmonitor.documents.base import BulkActionType


class BaseAlertProcessor:
    """
    告警处理基类
    封装了一些通用逻辑
    """

    def __init__(self):
        self.logger = logging.getLogger("alert")

    def list_alerts_from_cache(self, dedupe_md5_list: List[str]) -> List[Alert]:
        """
        根据 dedupe_md5 从 Redis 缓存中批量获取
        :param dedupe_md5_list:
        :return:
        """
        # 注意： 这个函数是为了切换过程中，旧的数据保存在原来的redis key里，需要通过这种方式来获取，避免产生新的告警
        if not dedupe_md5_list:
            return []

        alert_data = ALERT_CONTENT_KEY.client.mget(
            [ALERT_CONTENT_KEY.get_key(dedupe_md5=md5) for md5 in dedupe_md5_list]
        )

        alerts = []

        # 对告警内容进行解析，记录在 mapping 中
        for index, alert in enumerate(alert_data):
            if not alert:
                continue
            dedupe_md5 = dedupe_md5_list[index]
            try:
                alert = json.loads(alert)
                alerts.append(Alert(alert))
            except Exception as e:
                self.logger.warning("dedupe_md5(%s) loads alert failed: %s, origin data: %s", dedupe_md5, e, alert)
        return alerts

    def list_alerts_content_from_cache(self, events: List[Event]) -> List[Alert]:
        """
        根据 策略ID和dedupe_md5 从 Redis 缓存中批量获取
        :param events: 告警关联事件信息
        :return:
        """
        if not events:
            return []

        strategy_dedupe_md5_dict = defaultdict(list)
        for event in events:
            strategy_dedupe_md5_dict[event.strategy_id or 0].append(event.dedupe_md5)
        cache_keys = []
        dedupe_md5_list = []
        for strategy_id, md5_list in strategy_dedupe_md5_dict.items():
            cache_keys.extend(
                [ALERT_DEDUPE_CONTENT_KEY.get_key(strategy_id=strategy_id, dedupe_md5=md5) for md5 in md5_list]
            )
            dedupe_md5_list.extend(md5_list)

        alert_data = [ALERT_DEDUPE_CONTENT_KEY.client.get(cache_key) for cache_key in cache_keys]

        alerts = []

        # 对告警内容进行解析，记录在 mapping 中
        not_existed_dedupe_md5_list = []
        for index, alert in enumerate(alert_data):
            if not alert:
                # 不存在的先记录下
                not_existed_dedupe_md5_list.append(dedupe_md5_list[index])
                continue

            dedupe_md5 = dedupe_md5_list[index]
            try:
                alert = json.loads(alert)
                alerts.append(Alert(alert))
            except Exception as e:
                self.logger.warning("dedupe_md5(%s) loads alert failed: %s, origin data: %s", dedupe_md5, e, alert)
        if not_existed_dedupe_md5_list:
            # 对于无法找到的告警列表，则通过原来的key进行检索
            # 这种情况主要是针对切换过程中，旧的数据保存在原来的redis key里
            alerts.extend(self.list_alerts_from_cache(not_existed_dedupe_md5_list))
        return alerts

    def update_alert_cache(self, alerts: List[Alert]):
        """
        更新告警信息到 redis 缓存
        """
        if not alerts:
            return
        update_count, finished_count = AlertCache.save_alert_to_cache(alerts)
        self.logger.info("update alert cache: updated(%s), finished(%s)", update_count, finished_count)

    def update_alert_snapshot(self, alerts: List[Alert]):
        if not alerts:
            return

        snapshot_count = AlertCache.save_alert_snapshot(alerts)
        self.logger.info("update alert snapshot: %s", snapshot_count)

    def save_alerts(self, alerts: List[Alert], action=BulkActionType.INDEX, force_save=False) -> List[Alert]:
        """
        将告警信息保存到 ES
        """

        # 根据 refresh_db 属性，可以分为两类告警
        # True: 发生重大变更的告警，如告警状态、告警级别等变更，这类告警需要及时入库
        # False (大多数): 为普通的收敛，例如更新一下该告警的代表性事件，此类告警无需实时更。走周期任务定时更新即可，从而减少在此处的处理耗时
        alert_documents = [
            alert.to_document(include_all_fields=False) for alert in alerts if force_save or alert.should_refresh_db()
        ]

        if not alert_documents:
            self.logger.info(
                "save alert document with action(%s): ignored(%d), saved(0), failed(0)", action, len(alerts)
            )
            return alerts

        start_time = time.time()
        errors = []
        try:
            AlertDocument.bulk_create(alert_documents, action=action)
        except BulkIndexError as e:
            self.logger.error("save alert document error: %s", e.errors)
            errors = e.errors

        self.logger.info(
            "save alert document with action(%s): ignored(%d), saved(%d), failed(%d), cost: %.3f",
            action,
            len(alerts) - len(alert_documents),
            len(alert_documents) - len(errors),
            len(errors),
            time.time() - start_time,
        )

        return [alert for alert in alerts]

    def save_alert_logs(self, alerts: List[Alert]):
        """
        保存流水日志
        """

        log_documents = []
        for alert in alerts:
            log_documents.extend(alert.list_log_documents())

        if not log_documents:
            return []

        start_time = time.time()
        errors = []
        try:
            AlertLog.bulk_create(log_documents)
        except BulkIndexError as e:
            self.logger.error("save alert log document error: %s", e.errors)
            errors = e.errors

        self.logger.info(
            "save alert log document: saved(%d), failed(%d), cost: %.3f",
            len(log_documents) - len(errors),
            len(errors),
            time.time() - start_time,
        )

    def send_signal(self, alerts: List[Alert]):
        # 发送告警信号
        if not alerts:
            return

        for alert in alerts:
            if alert.is_blocked:
                # 如果告警被熔断，不发送composite事件
                continue
            check_action_and_composite.delay(alert_key=alert.key, alert_status=alert.status)

        self.logger.info("send alert signals: total(%d)", len(alerts))
