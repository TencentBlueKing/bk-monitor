"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import logging

from alarm_backends.core.alert import Alert, Event
from alarm_backends.core.alert.alert import AlertKey
from alarm_backends.core.cache import clear_mem_cache
from alarm_backends.core.cache.key import ALERT_DEDUPE_CONTENT_KEY, ALERT_UPDATE_LOCK
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
    def __init__(self, alert_keys: list[AlertKey]):
        super().__init__()
        self.logger = logging.getLogger("alert.manager")
        self.alert_keys = alert_keys

    def fetch_alerts(self) -> list[Alert]:
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

    def filter_alerts(self, alerts: list[Alert]) -> list[Alert]:
        """
        过滤不需要处理的告警
        :param alerts:
        :return:
        """
        # 1. 已关闭的告警 在ES拉取后到加锁处理前刚好被关闭了，此时拿到的这批alerts部分告警在redis已经是关闭状态了
        alert_dedupe_keys = [
            ALERT_DEDUPE_CONTENT_KEY.get_key(strategy_id=alert.strategy_id, dedupe_md5=alert.dedupe_md5)
            for alert in alerts
        ]
        fetched_alert_ids = set([alert.id for alert in alerts])

        alert_data = ALERT_DEDUPE_CONTENT_KEY.client.mget(alert_dedupe_keys)
        current_alerts_mapping = {}
        for current_alert_data in alert_data:
            if not current_alert_data:
                # 如果从缓存中获取不到告警，表示当前告警应该为最新的告警信息，跳过过滤
                continue
            try:
                current_alert = json.loads(current_alert_data)
                current_alert = Alert(current_alert)
            except Exception:
                # 如果从缓存中获取不到告警，表示当前告警应该为最新的告警信息，跳过过滤
                self.logger.warning("Failed to parse alert from cache: %s", current_alert_data)
                continue
            # 构造mapping，方便后续过滤
            current_alerts_mapping[current_alert.dedupe_md5] = current_alert
        new_alerts = []
        for alert in alerts:
            if alert.dedupe_md5 in current_alerts_mapping:
                # 如果缓存中存在当前告警，则使用缓存中的告警状态进行判断
                cache_alert = current_alerts_mapping.get(alert.dedupe_md5)
                if cache_alert and not cache_alert.is_abnormal():
                    # 如果缓存二次确认状态不为异常则过滤掉，拉取的都是异常告警，若不一致说明此时告警可能已经被关闭或者恢复
                    continue
            # 其他情况正常进行处理
            new_alerts.append(alert)
        # 打印过滤日志(包含过滤的告警id)
        filtered_alert_ids = set([alert.id for alert in alerts]) - set([alert.id for alert in new_alerts])
        self.logger.info(
            "[manager] Lock fetched alerts: %s,Filtered alerts: %s",
            ",".join(str(alert_id) for alert_id in fetched_alert_ids),
            ",".join(str(alert_id) for alert_id in filtered_alert_ids),
        )
        return new_alerts

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
            # 加锁成功的告警，过滤掉不需要处理的告警，才会开始处理
            locked_alerts = self.filter_alerts(locked_alerts)
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

    def handle(self, alerts: list[Alert]):
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
