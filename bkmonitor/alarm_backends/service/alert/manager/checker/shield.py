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
from typing import List

from alarm_backends.core.alert import Alert
from alarm_backends.service.alert.manager.checker.base import BaseChecker
from alarm_backends.service.converge.shield.shielder import AlertShieldConfigShielder
from alarm_backends.service.fta_action.tasks import create_actions
from bkmonitor.documents import AlertLog
from constants.alert import EventStatus

logger = logging.getLogger("alert.manager")


class ShieldStatusChecker(BaseChecker):
    """
    屏蔽状态检测
    """

    def __init__(self, alerts: List[Alert]):
        super().__init__(alerts)
        self.unshielded_actions = []
        self.need_notify_alerts = []
        self.alerts_dict = {alert.id: alert for alert in self.alerts}

    def check_all(self):
        success = 0
        failed = 0
        for alert in self.alerts:
            if self.is_enabled(alert):
                try:
                    self.check(alert)
                    success += 1
                except Exception as e:
                    logger.exception("alert(%s) run checker(%s) failed: %s", alert.id, self.__class__.__name__, e)
                    failed += 1
        logger.info("AlertChecker(%s) run finished, success(%s), failed(%s)", self.__class__.__name__, success, failed)

        if self.unshielded_actions:
            self.push_actions()

    def add_unshield_action(self, alert: Alert, config_id, relation_id):
        # 存在通知发送的时候，才创建通知动作
        cycle_handle_record = alert.get_extra_info("cycle_handle_record", {})
        handle_record = cycle_handle_record.get(str(relation_id))
        if not handle_record:
            # alert中没有获取到，则获取DB里的最近一次通知记录
            handle_record = alert.get_latest_interval_record(config_id=config_id, relation_id=str(relation_id)) or {}

        if handle_record and not handle_record.get("is_shielded"):
            # 上一次通知没有被屏蔽走常规的周期通知逻辑
            logger.info(
                "ignore to push unshielded action for alert(%s) "
                "because notification has been sent in the last cycle" % alert.id
            )
            return
        # 其他场景下需要进行通知
        logger.info("ready to push unshielded action for alert(%s)" % alert.id)
        execute_times = handle_record.get("execute_times", 0)
        self.unshielded_actions.append(
            {
                "strategy_id": alert.strategy_id,
                "signal": alert.status.lower(),
                "alert_ids": [alert.id],
                "severity": alert.severity,
                "relation_id": relation_id,
                "is_unshielded": True,
                "execute_times": handle_record.get("execute_times", 0),
            }
        )
        cycle_handle_record.update(
            {
                str(relation_id): {
                    "last_time": int(time.time()),
                    # 当前是解除屏蔽，所以此处一定是非屏蔽状态
                    "is_shielded": False,
                    "latest_anomaly_time": alert.latest_time,
                    "execute_times": execute_times + 1,
                }
            }
        )
        alert.update_extra_info("cycle_handle_record", cycle_handle_record)
        self.need_notify_alerts.append(alert.id)

    def check(self, alert: Alert):
        alert_doc = alert.to_document()
        shielder = AlertShieldConfigShielder(alert_doc)
        shield_result = shielder.is_matched()
        if (
            shield_result is False
            and alert_doc.is_shielded == shield_result
            and not alert.get_extra_info("need_unshield_notice")
        ):
            # 如果当前是否屏蔽状态与DB未屏蔽保持一致，或则不需要更新
            return

        if shield_result is False and alert_doc.status == EventStatus.ABNORMAL and alert_doc.strategy:
            # 解屏蔽之后， 如果告警明确处在异常期，需要直接进行通知发送（即未恢复期间不通知）
            need_unshield_notice = False
            notice_relation = alert_doc.strategy.get("notice", {})
            if alert_doc.is_shielded:
                if alert_doc.status_detail == EventStatus.RECOVERING:
                    logger.info(
                        "ignore push unshielded action for alert(%s) because of alert is in recovering period",
                        alert_doc.id,
                    )
                    alert.update_extra_info("ignore_unshield_notice", True)
                else:
                    # 如果是解除屏蔽 或者是解除屏蔽之后
                    need_unshield_notice = True
            elif alert.get_extra_info("need_unshield_notice"):
                need_unshield_notice = True
                alert.update_extra_info("need_unshield_notice", False)
            if need_unshield_notice and notice_relation:
                # 如果存在notice_relation并且需要创建解除屏蔽通知
                self.add_unshield_action(alert, notice_relation["config_id"], notice_relation["id"])

        shield_left_time = shielder.get_shield_left_time()
        shield_ids = shielder.list_shield_ids()
        alert.set("shield_id", shield_ids)
        alert.set("is_shielded", shield_result)
        alert.set("shield_left_time", shield_left_time)

    def push_actions(self):
        """
        重新推送action
        :return:
        """
        # 需要通知的告警
        need_notify_alerts = []

        # 需要推送的事件
        new_actions = []

        # QOS被放弃执行的数量
        qos_actions = 0

        # 不需要发送通知的
        noticed_alerts = []

        # 被qos的告警
        qos_alerts = []

        current_count = 0

        # step 1 确定有哪些需要发送的事件
        for action in self.unshielded_actions:
            alert_id = action["alert_ids"][0]
            if alert_id in noticed_alerts:
                # 如果当前告警ID存在发送过通知的有效周期任务，直接返回
                continue

            try:
                # 限流计数器，监控的告警以策略ID，信号，告警级别作为维度
                alert = self.alerts_dict.get(alert_id)
                is_qos, current_count = alert.qos_calc(action["signal"])
                if not is_qos:
                    # 没有过通知处理的，需要QOS限流
                    new_actions.append(action)
                    need_notify_alerts.append(alert_id)
                else:
                    # 达到阈值之后，触发流控
                    qos_actions += 1
                    qos_alerts.append(alert_id)
                    logger.info(
                        "unshielded alert(%s) qos triggered->alert_name(%s)->strategy(%s)-signal(%s)"
                        "-severity(%s)-relation_id(%s),"
                        " current_count->(%s)",
                        alert_id,
                        alert.alert_name,
                        action["strategy_id"],
                        action["signal"],
                        action["severity"],
                        action["relation_id"],
                        current_count,
                    )
            except BaseException as error:
                logger.exception("alert(%s) detect finished, but push actions failed, reason: %s", alert_id, error)

        if qos_alerts:
            # 如果有被qos的事件， 进行日志记录
            qos_log = Alert.create_qos_log(qos_alerts, current_count, qos_actions)
            AlertLog.bulk_create([qos_log])

        need_notify_alerts = set(need_notify_alerts)

        # step 3 推送事件
        for action in new_actions:
            create_actions.delay(**action)

        logger.info(
            "push action for unshielded alerts finished, push (%s) actions, qos (%s) actions",
            len(need_notify_alerts),
            qos_actions,
        )
