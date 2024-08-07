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
from typing import List

from alarm_backends.core.alert import Alert, Event
from alarm_backends.core.alert.alert import AlertKey
from alarm_backends.core.cache import clear_mem_cache
from alarm_backends.core.cache.key import ALERT_UPDATE_LOCK
from alarm_backends.core.lock.service_lock import multi_service_lock
from alarm_backends.service.alert.manager.checker.ack import AckChecker
from alarm_backends.service.alert.manager.checker.action import ActionHandleChecker
from alarm_backends.service.alert.manager.checker.close import CloseStatusChecker
from alarm_backends.service.alert.manager.checker.next import NextStatusChecker
from alarm_backends.service.alert.manager.checker.recover import RecoverStatusChecker
from alarm_backends.service.alert.manager.checker.shield import ShieldStatusChecker
from alarm_backends.service.alert.manager.checker.upgrade import UpgradeChecker
from alarm_backends.service.alert.processor import BaseAlertProcessor
from bkmonitor.documents import AlertDocument
from bkmonitor.documents.base import BulkActionType
from core.prometheus import metrics

INSTALLED_CHECKERS = (
    NextStatusChecker,
    CloseStatusChecker,
    RecoverStatusChecker,
    ShieldStatusChecker,
    AckChecker,
    UpgradeChecker,
    ActionHandleChecker,
)


class AlertManager(BaseAlertProcessor):
    def __init__(self, alert_keys: List[AlertKey]):
        super(AlertManager, self).__init__()
        self.logger = logging.getLogger("alert.manager")
        self.alert_keys = alert_keys

    def fetch_alerts(self) -> List[Alert]:
        # 1. 根据告警ID，从ES拉出数据
        alerts = Alert.mget(self.alert_keys)

        # 2. 补充用户修改字段，这些字段只有在ES是最准的，需要刷进去
        fields = [
            "id",
            "assignee",
            "is_handled",
            "handle_stage",
            "is_ack",
            "is_ack_noticed",
            "ack_operator",
            "appointee",
            "supervisor",
            "extra_info",
        ]
        alert_docs = {
            alert_doc.id: alert_doc
            for alert_doc in AlertDocument.mget(
                ids=[alert.id for alert in alerts],
                fields=fields,
            )
        }
        for alert in alerts:
            if alert.id in alert_docs:
                for field in fields:
                    if field == "extra_info":
                        # 以DB为主，同时合并check阶段新增内容
                        extra_info = getattr(alert_docs[alert.id], field, None)
                        alert.data[field] = alert.data.get(field) or {}
                        alert.data[field].update(extra_info.to_dict() if extra_info else {})
                    else:
                        alert.data[field] = getattr(alert_docs[alert.id], field, None)
        return alerts

    def process(self):
        """
        处理入口
        """
        alerts = self.fetch_alerts()
        if not alerts:
            return

        lock_keys = [ALERT_UPDATE_LOCK.get_key(dedupe_md5=alert.dedupe_md5) for alert in alerts]

        with multi_service_lock(ALERT_UPDATE_LOCK, lock_keys) as lock:
            locked_alerts = []
            fail_locked_alert_ids = []
            for alert in alerts:
                if lock.is_locked(ALERT_UPDATE_LOCK.get_key(dedupe_md5=alert.dedupe_md5)):
                    locked_alerts.append(alert)
                else:
                    fail_locked_alert_ids.append(alert.id)
            # 加锁成功的告警，才会开始处理
            alerts_to_check = []
            alerts_to_update_directly = []
            for alert in locked_alerts:
                if alert.is_abnormal():
                    alerts_to_check.append(alert)
                else:
                    alerts_to_update_directly.append(alert)

            alerts_to_check = self.handle(alerts_to_check)

            if fail_locked_alert_ids:
                # 对加锁失败的告警，不进行操作，等下一轮的周期检测即可
                self.logger.info(
                    "[alert.manager get lock error] total(%s) is locked, will try later: %s",
                    len(fail_locked_alert_ids),
                    ", ".join(fail_locked_alert_ids),
                )

            # 4. 保存告警到ES
            saved_alerts = self.save_alerts(alerts_to_check, action=BulkActionType.UPSERT, force_save=True)

        # 5. 保存流水日志
        self.save_alert_logs(saved_alerts)

        # 6. 发送信号
        self.send_signal(saved_alerts)

        # 7. 指标上报
        for alert in saved_alerts:
            metrics.ALERT_MANAGE_PUSH_DATA_COUNT.labels(strategy_id=metrics.TOTAL_TAG, signal=alert.status).inc()

        # 8. 清理内存缓存
        clear_mem_cache("host_cache")
        # #### 需要检测的告警，处理结束

        if alerts_to_update_directly:
            # 某些情况下，会存在snapshot的告警处于终结状态，而 DB 的并没有，此时需要刷一波进DB
            self.logger.info("[refresh alert es] refresh ES directly: %s", alerts_to_update_directly)
            self.save_alerts(alerts_to_update_directly, action=BulkActionType.UPSERT, force_save=True)

    def handle(self, alerts: List[Alert]):
        # #### 需要检测的告警，处理开始
        # 2. 再处理 DB 和 Redis 缓存中存在的告警
        for checker_cls in INSTALLED_CHECKERS:
            checker = checker_cls(alerts=alerts)
            checker.check_all()

        # 3. 更新缓存，只更新当前dedupe_md5的alert_id和需要更新的alert_id一致的部分，或者cache不存在的部分
        active_alerts = self.list_alerts_content_from_cache(
            [Event(data=alert.top_event, do_clean=False) for alert in alerts]
        )
        active_alerts_mapping = {alert.dedupe_md5: alert.id for alert in active_alerts}
        update_count, finished_count = self.update_alert_cache(
            [
                alert
                for alert in alerts
                if alert.dedupe_md5 not in active_alerts_mapping or active_alerts_mapping[alert.dedupe_md5] == alert.id
            ]
        )
        self.logger.info("[alert.manager update alert cache]: updated(%s), finished(%s)", update_count, finished_count)
        # 4. 再把最新的内容刷回快照
        snapshot_count = self.update_alert_snapshot(alerts)
        self.logger.info("[alert.manager update alert snapshot]: %s", snapshot_count)

        return alerts
