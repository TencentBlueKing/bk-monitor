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

from alarm_backends.core.alert import Alert
from alarm_backends.service.alert.enricher import BaseAlertEnricher
from alarm_backends.service.fta_action.tasks.alert_assign import AlertAssigneeManager
from constants.action import AssignMode
from core.prometheus import metrics

logger = logging.getLogger("alert.builder")


class AssignInfoEnricher(BaseAlertEnricher):
    """
    告警分派动作
    """

    def enrich_alert(self, alert: Alert) -> Alert:
        strategy = alert.get_extra_info(key="strategy")
        # 有策略直接用策略的分派规则，没有策略的，默认用分派
        assign_mode = (
            strategy.get("notice", {}).get("options", {}).get("assign_mode") if strategy else [AssignMode.BY_RULE]
        )
        user_groups = strategy.get("notice", {}).get("user_groups") if strategy else []
        assign_labels = {
            "bk_biz_id": alert.bk_biz_id,
            "assign_type": "alert_builder",
            "notice_type": None,
            "alert_source": alert.top_event.get("plugin_id", ""),
        }
        with metrics.ALERT_ASSIGN_PROCESS_TIME.labels(**assign_labels).time():
            # 此处的enrich尽量不去适配告警通知组的内容
            exc = None
            assign_labels["rule_group_id"] = None
            try:
                assign_manager = AlertAssigneeManager(
                    alert=alert.to_document(),
                    notice_user_groups=user_groups,
                    assign_mode=assign_mode,
                    new_alert=alert.is_new(),
                ).match_manager
            except Exception as error:
                exc = error
                assign_manager = None
                logger.exception("[alert assign] alert(%s) assign failed, error info %s", alert.id, str(error))
            assign_labels["status"] = metrics.StatusEnum.from_exc(exc)
            if assign_manager:
                if assign_manager.matched_rule_info["severity"]:
                    alert.update_severity_source(assign_manager.severity_source)
                    alert.update_severity(assign_manager.matched_rule_info["severity"])
                    alert.add_log(**assign_manager.get_alert_log())
                alert.update_extra_info("matched_rule_info", assign_manager.matched_rule_info)
                if assign_manager.matched_rule_info["additional_tags"]:
                    alert.update_assign_tags(assign_manager.matched_rule_info["additional_tags"])
                assign_labels.update({"rule_group_id": assign_manager.matched_group_info.get("group_id")})
        metrics.ALERT_ASSIGN_PROCESS_COUNT.labels(**assign_labels).inc()
        return alert
