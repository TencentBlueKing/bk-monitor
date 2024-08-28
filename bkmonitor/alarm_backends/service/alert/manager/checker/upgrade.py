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

from alarm_backends.core.alert import Alert
from alarm_backends.core.cache.assign import AssignCacheManager
from alarm_backends.service.alert.manager.checker.base import BaseChecker
from alarm_backends.service.fta_action.tasks import create_actions
from alarm_backends.service.fta_action.tasks.alert_assign import (
    BackendAssignMatchManager,
)
from bkmonitor.action.alert_assign import UpgradeRuleMatch
from constants.action import ActionNoticeType, AssignMode
from core.prometheus import metrics

logger = logging.getLogger("alert.manager")


class UpgradeChecker(BaseChecker):
    """
    通知相关的状态检测
    """

    def check_all(self):
        super().check_all()
        AssignCacheManager.clear()

    @classmethod
    def need_origin_upgrade(cls, alert_doc, upgrade_config):
        current_time = int(time.time()) + 30  # 从未来的30s开始算起
        upgrade_notice = alert_doc.extra_info.to_dict().get("upgrade_notice", {})
        last_upgrade_time = upgrade_notice.get("last_upgrade_time", current_time)
        last_group_index = upgrade_notice.get("last_group_index")
        latest_upgrade_interval = current_time - last_upgrade_time
        upgrade_rule = UpgradeRuleMatch(upgrade_config)
        return upgrade_rule.need_upgrade(latest_upgrade_interval or alert_doc.duration, last_group_index)

    def check(self, alert: Alert):
        alert_doc = alert.to_document()
        notice_relation = alert_doc.strategy.get("notice", {}) if alert_doc.strategy else {}
        upgrade_notice = {
            "strategy_id": alert_doc.strategy_id,
            "signal": alert_doc.status.lower(),
            "alert_ids": [alert_doc.id],
            "severity": alert_doc.severity,
            "relation_id": notice_relation.get("id"),
            "notice_type": ActionNoticeType.UPGRADE,
        }
        upgrade_config = notice_relation.get("options", {}).get("upgrade_config") or {}
        assign_labels = {
            "bk_biz_id": alert.bk_biz_id,
            "assign_type": "alert_check",
            "notice_type": None,
            "alert_source": alert.top_event.get("plugin_id", ""),
        }
        rule_group_id = None
        exc = None
        with metrics.ALERT_ASSIGN_PROCESS_TIME.labels(**assign_labels).time():
            # 先判断是否有命中分派规则是否需要升级
            assign_mode = (
                notice_relation.get("options", {}).get("assign_mode") or [AssignMode.BY_RULE, AssignMode.ONLY_NOTICE]
                if alert_doc.strategy
                else [AssignMode.BY_RULE]
            )
            try:
                assign_manager = BackendAssignMatchManager(alert_doc, assign_mode=assign_mode)
            except BaseException as error:  # noqa
                exc = error
                logger.exception(
                    "[assign failed] alert(%s) strategy(%s) detail: %s", alert_doc.id, alert_doc.strategy_id, str(error)
                )
            matched_rules = assign_manager.get_matched_rules()
            need_upgrade = False
            if not matched_rules and AssignMode.ONLY_NOTICE in assign_mode:
                # 如果没有适配上规则，并且支持默认通知，则判断默认通知是否需要升级
                need_upgrade = self.need_origin_upgrade(alert_doc, upgrade_config)
            else:
                for rule in matched_rules:
                    rule_group_id = rule.assign_rule["assign_group_id"]
                    if rule.need_upgrade:
                        need_upgrade = True
                        break

        assign_labels.update({"rule_group_id": rule_group_id, "status": metrics.StatusEnum.from_exc(exc)})
        metrics.ALERT_ASSIGN_PROCESS_COUNT.labels(**assign_labels).inc()
        if need_upgrade:
            # 如果有的话，直接发送升级通知任务
            logger.info("[push upgrade action]  alert(%s) strategy(%s)", alert_doc.id, alert_doc.strategy_id)
            create_actions.delay(**upgrade_notice)
