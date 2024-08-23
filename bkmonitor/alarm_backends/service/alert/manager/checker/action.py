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
import math
import time

from alarm_backends.core.alert import Alert
from alarm_backends.core.cache.action_config import ActionConfigCacheManager
from alarm_backends.service.alert.manager.checker.base import BaseChecker
from alarm_backends.service.fta_action.tasks import create_interval_actions
from constants.action import ActionSignal, IntervalNotifyMode

logger = logging.getLogger("alert.manager")


class ActionHandleChecker(BaseChecker):
    """
    通知以及告警处理相关的状态检测
    """

    def check(self, alert: Alert):
        """
        进行告警异常时的通知处理检测
        """
        if not alert.is_handled:
            # step 1: 判断当前告警是否已经处理，如果没有处理过的，不走周期检测逻辑
            return

        if not alert.strategy:
            # step 2: 如果没有策略，表示是第三方告警或者策略已关闭或者删除，不做检测
            # logger.info("[ignore check action] alert(%s) no strategy", alert.id)
            return

        notice_relation = alert.strategy.get("notice", {})
        actions = [action for action in alert.strategy.get("actions", []) if ActionSignal.ABNORMAL in action["signal"]]
        if notice_relation:
            actions.append(notice_relation)
        cycle_handle_record = alert.get_extra_info("cycle_handle_record", {})
        signal = ActionSignal.NO_DATA if alert.is_no_data() else ActionSignal.ABNORMAL
        for action in actions:
            relation_id = str(action["id"])
            relation_record = cycle_handle_record.get(relation_id)
            if not relation_record:
                # 如果不在，可能是新加的，也有可能是历史数据，可以通过在ActionInstance表中找出
                relation_record = alert.get_latest_interval_record(action["config_id"], relation_id)
            if not relation_record:
                continue

            action_config = ActionConfigCacheManager.get_action_config_by_id(action["config_id"])
            if not self.check_interval_matched_actions(relation_record, action_config, alert):
                continue

            # 如果处理的最近异常点与当前告警异常点不一致并且满足周期调用的的场景，则创建周期任务
            execute_times = relation_record["execute_times"]
            create_interval_actions.delay(
                alert.strategy_id,
                signal,
                [alert.id],
                severity=alert.severity,
                relation_id=int(relation_id),
                execute_times=execute_times,
            )

            # 处理的时候的时候，记录最近的一次通知时间和通知次数，用来作为记录当前告警是否已经产生通知
            cycle_handle_record.update(
                {
                    str(relation_id): {
                        "last_time": int(time.time()),
                        "is_shielded": alert.is_shielded,
                        "latest_anomaly_time": alert.latest_time,
                        "execute_times": execute_times + 1,
                    }
                }
            )
            alert.update_extra_info("cycle_handle_record", cycle_handle_record)

    def check_interval_matched_actions(self, last_execute_info, action_config, alert):
        """
        判断周期间隔是否已经达到
        """
        try:
            execute_config = action_config["execute_config"]["template_detail"]
        except (KeyError, TypeError) as error:
            logger.error(
                "[check_interval_matched_actions] alert(%s) strategy(%s) error %s",
                alert.id,
                alert.strategy_id,
                str(error),
            )
            return False

        notify_interval = self.calc_action_interval(execute_config, last_execute_info["execute_times"])
        if notify_interval <= 0 or last_execute_info["last_time"] + notify_interval > int(time.time()):
            # 不满足创建周期任务条件的时候，直接返回
            return False
        if last_execute_info.get("latest_anomaly_time", 0) >= alert.latest_time:
            # 满足了周期条件之后，如果最近的异常点与上一次发送通知的异常点一致，则忽略
            return False
        logger.info(
            "[Send Task: create interval action] alert(%s) strategy(%s) last_execute_info: (%s), notify_interval: (%s)",
            alert.id,
            alert.strategy_id,
            last_execute_info,
            notify_interval,
        )
        return True

    @staticmethod
    def calc_action_interval(execute_config, execute_times):
        """
        计算周期任务间隔
        :param execute_config: 执行参数
        :param execute_times: 当前是第几次执行
        :return:
        """
        if execute_config.get("need_poll", True) is False:
            return 0

        try:
            notify_interval = int(execute_config.get("notify_interval", 0))
        except TypeError:
            notify_interval = 0

        interval_notify_mode = execute_config.get("interval_notify_mode", IntervalNotifyMode.STANDARD)
        if interval_notify_mode == IntervalNotifyMode.INCREASING:
            # 按照指数级别进行处理
            notify_interval = int(notify_interval * math.pow(2, execute_times - 1))
        return notify_interval
