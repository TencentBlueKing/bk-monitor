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
import time

from django.utils.translation import gettext as _
from elasticsearch.helpers import BulkIndexError

from alarm_backends.constants import CONST_MINUTES
from alarm_backends.core.alert import Alert, Event
from alarm_backends.core.alert.alert import AlertUIDManager
from alarm_backends.core.cache.assign import AssignCacheManager
from alarm_backends.core.cache.key import ALERT_UPDATE_LOCK
from alarm_backends.core.circuit_breaking.manager import AlertBuilderCircuitBreakingManager
from alarm_backends.core.lock.service_lock import multi_service_lock
from alarm_backends.service.alert.enricher import AlertEnrichFactory, EventEnrichFactory
from alarm_backends.service.alert.manager.tasks import send_check_task
from alarm_backends.service.alert.processor import BaseAlertProcessor
from bkmonitor.documents import AlertLog, EventDocument
from bkmonitor.documents.base import BulkActionType
from constants.action import AssignMode
from constants.alert import EventStatus
from core.prometheus import metrics


class AlertBuilder(BaseAlertProcessor):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger("alert.builder")
        circuit_breaking_manager = AlertBuilderCircuitBreakingManager()
        self.circuit_breaking_manager = circuit_breaking_manager

    def get_unexpired_events(self, events: list[Event]):
        """
        先判断关联事件是否已经过期
        """
        current_alerts = self.get_current_alerts(events)
        unexpired_events = []
        expired_events = []
        for event in events:
            alert: Alert = current_alerts.get(event.dedupe_md5)
            expired_time = alert.end_time - CONST_MINUTES if alert and alert.end_time else None
            if event.is_dropped() or event.is_expired(expired_time):
                # 如果事件已经被丢弃，或者已经过期，则不需要处理
                expired_events.append(event)
                self.logger.info(
                    "[event drop] event(%s) strategy(%s) is dropped or expired(%s), skip build alert",
                    event.event_id,
                    event.strategy_id,
                    expired_time,
                )
                continue
            unexpired_events.append(event)

        return unexpired_events

    def get_current_alerts(self, events: list[Event]):
        """
        获取关联事件对应的告警缓存内容
        """
        events_dedupe_md5_list = set({event.dedupe_md5 for event in events})
        if not events_dedupe_md5_list:
            return {}

        cached_alerts = self.list_alerts_content_from_cache(events)
        return {alert.dedupe_md5: alert for alert in cached_alerts}

    def dedupe_events_to_alerts(self, events: list[Event]):
        """
        将事件进行去重，生成告警并保存
        """

        def _report_latency(report_events):
            latency_logged = False
            for event in report_events:
                latency = event.get_process_latency()
                if not latency:
                    # 没有延迟数据，直接下一个
                    continue
                trigger_latency = latency.get("trigger_latency", 0)
                if trigger_latency > 0:
                    metrics.ALERT_PROCESS_LATENCY.labels(
                        bk_data_id=event.data_id,
                        topic=event.topic,
                        strategy_id=metrics.TOTAL_TAG,
                    ).observe(trigger_latency)
                    if trigger_latency > 60 and not latency_logged:
                        self.logger.warning(
                            "[trigger to alert.builder]big latency %s,  strategy(%s)",
                            trigger_latency,
                            event.strategy_id,
                        )
                        latency_logged = True
                if latency.get("access_latency"):
                    metrics.ACCESS_TO_ALERT_PROCESS_LATENCY.labels(
                        bk_data_id=event.data_id,
                        topic=event.topic,
                        strategy_id=metrics.TOTAL_TAG,
                    ).observe(latency["access_latency"])

        events = self.get_unexpired_events(events)
        if not events:
            return []
        lock_keys = [ALERT_UPDATE_LOCK.get_key(dedupe_md5=event.dedupe_md5) for event in events]

        with multi_service_lock(ALERT_UPDATE_LOCK, lock_keys) as lock:
            success_locked_events = []
            fail_locked_events = []
            # 区分出哪些告警加锁成功，哪些失败
            for event in events:
                if lock.is_locked(ALERT_UPDATE_LOCK.get_key(dedupe_md5=event.dedupe_md5)):
                    success_locked_events.append(event)
                else:
                    fail_locked_events.append(event)

            _report_latency(success_locked_events)

            # 对加锁成功的告警才能进行操作
            alerts = self.build_alerts(success_locked_events)
            alerts = self.enrich_alerts(alerts)
            update_count, finished_count = self.update_alert_cache(alerts)
            self.logger.info(
                "[alert.builder update alert cache]: updated(%s), finished(%s)", update_count, finished_count
            )

            snapshot_count = self.update_alert_snapshot(alerts)
            self.logger.info("[alert.builder update alert snapshot]: %s", snapshot_count)

            if fail_locked_events:
                from alarm_backends.service.alert.builder.tasks import (
                    dedupe_events_to_alerts,
                )

                # 对加锁失败的告警，丢到队列中，延后5s操作
                dedupe_events_to_alerts.apply_async(
                    kwargs={
                        "events": fail_locked_events,
                    },
                    countdown=5,
                )
                self.logger.info(
                    "[alert.builder locked] %s alerts is locked, retry in 5s: %s",
                    len(fail_locked_events),
                    ",".join([event.dedupe_md5 for event in fail_locked_events]),
                )

            alerts = self.save_alerts(alerts, action=BulkActionType.UPSERT, force_save=True)

        # TODO: 这里需要清理保存失败的告警的 Redis 缓存，否则会导致DB和 Redis 不一致
        self.save_alert_logs(alerts)
        self.send_periodic_check_task(alerts)

        alerts_to_send_signal = [alert for alert in alerts if alert.should_send_signal()]
        self.send_signal(alerts_to_send_signal)

        for alert in alerts:
            metrics.ALERT_PROCESS_PUSH_DATA_COUNT.labels(
                bk_data_id=alert.data_id,
                topic=alert.data_topic,
                strategy_id=metrics.TOTAL_TAG,
                is_saved="1" if alert.should_refresh_db() else "0",
            ).inc()

        return alerts

    def handle(self, events: list[Event]):
        """
        事件处理逻辑
        1. 保存事件数据到 ES
        2. 更新告警 Redis 缓存
        """
        events = self.enrich_events(events)
        events = self.save_events(events)
        alerts = self.dedupe_events_to_alerts(events)
        return alerts

    def send_periodic_check_task(self, alerts: list[Alert]):
        """
        对于新产生告警，立马触发一次状态检查。因为周期检测任务是1分钟跑一次，对于监控周期小于1分钟告警来说可能不够及时
        """
        alerts_params = [
            {
                "id": alert.id,
                "strategy_id": alert.strategy_id,
            }
            for alert in alerts
            if alert.is_new() and alert.strategy_id
        ]
        # 利用send_check_task 创建[alert.manager]延时任务
        send_check_task(alerts=alerts_params, run_immediately=False)
        self.logger.info("[alert.builder -> alert.manager] alerts: %s", ", ".join([str(alert.id) for alert in alerts]))

    def enrich_alerts(self, alerts: list[Alert]):
        """
        告警丰富
        注意：只需要对新产生的告警进行丰富
        """
        start_time = time.time()

        factory = AlertEnrichFactory(alerts)
        alerts = factory.enrich()
        AssignCacheManager.clear()

        self.logger.info(
            "[alert.builder enrich alerts] finished, total(%s), elapsed(%.3f)", len(alerts), time.time() - start_time
        )
        return alerts

    def enrich_events(self, events: list[Event]):
        """
        事件丰富
        """

        start_time = time.time()

        factory = EventEnrichFactory(events)
        events = factory.enrich()

        self.logger.info(
            "[alert.builder enrich event] finished, dropped(%d/%d), cost: (%.3f)",
            len([e for e in events if e.is_dropped()]),
            len(events),
            time.time() - start_time,
        )

        for event in events:
            if event.is_dropped():
                metrics.ALERT_PROCESS_DROP_EVENT_COUNT.labels(
                    bk_data_id=event.data_id, topic=event.topic, strategy_id=metrics.TOTAL_TAG
                ).inc()

        return events

    def save_events(self, events: list[Event]) -> list[Event]:
        if not events:
            return []
        dedupe_events = []
        # 先对相同uid的事件进行去重
        exist_uids = set()
        for event in events:
            if event.is_dropped() or event.id in exist_uids:
                # 忽略拥有重复uid的事件
                continue
            dedupe_events.append(event)
            exist_uids.add(event.id)

        # 保存事件信息
        event_documents = [event.to_document() for event in dedupe_events]

        # 保存出错的事件id集合
        error_uids = set()
        # uid重复导致保存出错的事件个数
        conflict_error_events_count = len(events) - len(dedupe_events)
        # 其他原因导致保存出错的事件个数
        other_error_events_count = 0

        start_time = time.time()
        try:
            EventDocument.bulk_create(event_documents)
        except BulkIndexError as e:
            for err in e.errors:
                # 记录保存失败的事件ID
                error_uids.add(err["create"]["_id"])
                if err["create"]["status"] == 409:
                    # status=409 一般是uid重复了，这种情况大多是因为 poller 拉取窗口重叠导致的
                    conflict_error_events_count += 1
                else:
                    # 其他的情况，一般是实际数据类型与es的 mapping 对不上，例如在 KeyWord 字段中存入了 Object
                    self.logger.error("[alert.builder save events ERROR] detail: %s", err)
                    other_error_events_count += 1

        created_events_count = len(event_documents) - len(error_uids)

        self.logger.info(
            "[alert.builder save event to ES] finished: total(%d), created(%d), duplicate(%d), failed(%d), cost: %.3f",
            len(events),
            created_events_count,
            conflict_error_events_count,
            other_error_events_count,
            time.time() - start_time,
        )

        # 过滤出保存成功的事件
        return [event for event in dedupe_events if event.id not in error_uids]

    def alert_qos_handle(self, alert: Alert):
        if not alert.is_blocked:
            # 对于未被流控的告警，只检查熔断规则
            circuit_breaking_blocked = False
            if self.circuit_breaking_manager:
                circuit_breaking_blocked = alert.check_circuit_breaking(self.circuit_breaking_manager)

            if circuit_breaking_blocked:
                # 告警触发熔断规则，需要流控, 结束当前告警。
                alert.update_qos_status(True)
                now_time = int(time.time())
                alert.set_end_status(
                    status=EventStatus.CLOSED,
                    op_type=AlertLog.OpType.ALERT_QOS,
                    description="告警命中熔断规则，被流控关闭",
                    end_time=now_time,
                    event_id=now_time,
                )
                self.logger.info(
                    f"[circuit breaking] [alert.builder] exists alert({alert.id}) strategy({alert.strategy_id}) "
                    f"is blocked by circuit breaking rules"
                )

            return alert

        # 对于已被流控的告警，先检查熔断规则状态
        circuit_breaking_blocked = False
        if self.circuit_breaking_manager:
            circuit_breaking_blocked = alert.check_circuit_breaking(self.circuit_breaking_manager)

        if circuit_breaking_blocked:
            self.logger.debug(f"[circuit breaking] [alert.builder] alert({alert.id}) still blocked by circuit breaking")
            return alert

        # 熔断规则未命中，继续检查QoS状态
        qos_result = alert.qos_check()
        if qos_result["is_blocked"]:
            # 仍被QoS流控
            return alert
        else:
            # 不满足熔断条件了，关闭当前告警，接下来直接产生一条新的告警
            self.logger.info("[alert.builder qos] alert(%s) will be closed: %s ", alert.id, qos_result["message"])
            alert.set_end_status(
                status=EventStatus.CLOSED,
                op_type=AlertLog.OpType.CLOSE,
                description=_("{message}, 当前告警关闭").format(message=qos_result["message"]),
                end_time=int(time.time()),
            )
            return alert

    def build_alerts(self, events: list[Event]) -> list[Alert]:
        """
        根据事件生成告警
        """
        if not events:
            return []

        # 根据这批事件的dedupe_md5，获取已经存在的告警
        current_alerts = self.get_current_alerts(events)
        new_alerts = {}
        # 对事件进行遍历，逐个更新告警内容
        for event in events:
            alert: Alert = current_alerts.get(event.dedupe_md5)
            if alert and alert.is_abnormal():
                # 存量告警处理
                # 当前事件已经关联了告警， 且告警处于未恢复状态
                # qos判定，如果判定qos解除， 则alert的状态变更为CLOSED
                alert = self.alert_qos_handle(alert)
                if alert.status == EventStatus.CLOSED:
                    # qos状态解除，创建新告警
                    new_alerts[alert.id] = alert
                    alert = Alert.from_event(event, circuit_breaking_manager=self.circuit_breaking_manager)
                else:
                    if alert.severity > event.severity and alert.severity_source != AssignMode.BY_RULE:
                        # 如果告警级别小于当前事件的级别，并且级别不是告警分派改变的，先将当前告警关闭，再创建一个新的告警
                        alert.set_end_status(
                            status=EventStatus.CLOSED,
                            op_type=AlertLog.OpType.CLOSE,
                            description=_("存在更高级别的告警，告警关闭"),
                            end_time=max(event.time, alert.latest_time),
                            event_id=event.id,
                        )
                        new_alerts[alert.id] = alert
                        alert = Alert.from_event(event, circuit_breaking_manager=self.circuit_breaking_manager)
                    elif alert.event_severity < event.severity:
                        # 如果当前告警关联的事件级别高于新的事件级别， 接丢弃当前的event, 并记录日志
                        alert.add_log(
                            op_type=AlertLog.OpType.EVENT_DROP,
                            event_id=event.id,
                            description=event.description,
                            time=event.time,
                            severity=event.severity,
                        )
                        event.drop()
                    else:
                        alert.update(event)

            else:
                # 新告警
                # 如果当前无告警缓存，或者当前告警存在关闭时间，则创建一个新告警
                if not event.is_abnormal():
                    # 如果当前没有正在产生的告警，且当前事件状态不是异常，则跳过处理
                    continue
                alert = Alert.from_event(event=event, circuit_breaking_manager=self.circuit_breaking_manager)
                self.logger.info(
                    "[alert.builder] event(%s) -> new alert(%s)",
                    event.event_id,
                    alert.id,
                )

            # 回写到 current_alerts 用于后续遍历继续更新
            current_alerts[event.dedupe_md5] = alert
            new_alerts[alert.id] = alert

        alerts = list(new_alerts.values())

        # 对于新创建的告警，需要对UID进行初始化【没啥意义，已经初始化过了】
        alerts_to_init = [alert for alert in alerts if alert.is_new()]
        AlertUIDManager.preload_pool(len(alerts_to_init))
        for alert in alerts_to_init:
            alert.init_uid()

        # 统计新创建的告警中被熔断流控的数量（用于日志记录）
        circuit_breaking_count = len([alert for alert in alerts_to_init if alert.is_blocked])
        self.logger.info(
            "[alert.builder build alerts] finished, new/total(%d/%d), circuit_breaking(%d)",
            len(alerts_to_init),
            len(alerts),
            circuit_breaking_count,
        )

        return alerts

    def process(self, events: list[Event] = None):
        """
        事件处理主入口
        """
        if not events:
            return
        self.handle(events)
