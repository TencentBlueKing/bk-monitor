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
        super().check_all()

        if self.unshielded_actions:
            self.push_actions()

    def add_unshield_action(self, alert: Alert, notice_relation: dict = None):
        if not notice_relation:
            return

        config_id = notice_relation.get("config_id")
        relation_id = notice_relation.get("relation_id")
        if not (config_id and relation_id):
            return

        # 存在通知发送的时候，才创建通知动作
        cycle_handle_record = alert.get_extra_info("cycle_handle_record", {})
        handle_record = cycle_handle_record.get(str(relation_id))
        if not handle_record:
            # alert中没有获取到，则获取DB里的最近一次通知记录
            handle_record = alert.get_latest_interval_record(config_id=config_id, relation_id=str(relation_id)) or {}

        if handle_record and not handle_record.get("is_shielded"):
            # 最近一次通知没有被屏蔽， 说明屏蔽未影响该告警的通知， 因此走正常周期通知逻辑。
            logger.info(
                "[ignore unshielded action] alert(%s) strategy(%s) " "最近一次通知没有被屏蔽, 无需发送接触屏蔽通知",
                alert.id,
                alert.strategy_id,
            )
            return
        # 其他场景下需要进行通知
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
        logger.info("[push unshielded action] alert(%s) strategy(%s)", alert.id, alert.strategy_id)

    def check(self, alert: Alert):
        # 1. 检查告警是否被屏蔽。
        shield_obj = AlertShieldConfigShielder(alert.to_document())
        match_shield = shield_obj.is_matched()
        notice_relation = None
        if alert.strategy:
            notice_relation = alert.strategy.get("notice", {})
        if not match_shield:
            # 2. 如果告警未命中屏蔽规则， 判定告警是否需要发送解除屏蔽通知。
            if alert.is_shielded:
                # 2.1 告警处于屏蔽中， 则开始解除屏蔽
                if alert.is_recovering():
                    # 2.1.1 告警处于恢复期， 抑制解除屏蔽通知
                    # 设置 ignore_unshield_notice 标记: 抑制解除屏蔽通知(告警恢复期)
                    alert.update_extra_info("ignore_unshield_notice", True)
                    logger.info("[ignore push action] alert(%s) strategy(%s) 告警处于恢复期", alert.id, alert.strategy_id)
                else:
                    # 2.1.2 推送解除屏蔽通知
                    self.add_unshield_action(alert, notice_relation)
            else:
                # 2.2 告警处于未屏蔽状态
                if alert.get_extra_info("need_unshield_notice"):
                    # 2.2.1 被要求通知，则发送一次通知。之后，不再发送。(recover 模块设置的标记)
                    self.add_unshield_action(alert, notice_relation)
                    alert.extra_info.pop("need_unshield_notice", False)

        # 获取剩余屏蔽时间和屏蔽ID列表
        shield_left_time = shield_obj.get_shield_left_time()
        shield_ids = shield_obj.list_shield_ids()
        # 更新告警文档中的屏蔽相关信息
        alert.set("shield_id", shield_ids)
        alert.set("is_shielded", match_shield)
        alert.set("shield_left_time", shield_left_time)

    def push_actions(self):
        """
        重新推送action
        :return:
        """
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

            # 限流计数器，监控的告警以策略ID，信号，告警级别作为维度
            alert = self.alerts_dict.get(alert_id)
            try:
                is_qos, current_count = alert.qos_calc(action["signal"])
                if not is_qos:
                    new_actions.append(action)
                else:
                    # 达到阈值之后，触发流控
                    qos_actions += 1
                    qos_alerts.append(alert_id)
                    logger.info(
                        "[action qos triggered] alert(%s) strategy(%s) signal(%s) severity(%s) " "qos_count: %s",
                        alert_id,
                        action["strategy_id"],
                        action["signal"],
                        action["severity"],
                        current_count,
                    )
            except BaseException as error:
                logger.exception(
                    "[push actions error] alert(%s) strategy(%s) reason: %s", alert_id, action["strategy_id"], error
                )

        if qos_alerts:
            # 如果有被qos的事件， 进行日志记录
            qos_log = Alert.create_qos_log(qos_alerts, current_count, qos_actions)
            AlertLog.bulk_create([qos_log])

        # step 3 推送事件
        for action in new_actions:
            create_actions.delay(**action)
            logger.info("[push actions] alert(%s) strategy(%s)", action["alert_ids"][0], action["strategy_id"])
