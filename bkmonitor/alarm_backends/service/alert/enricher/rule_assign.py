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

from alarm_backends.core.alert import Alert
from alarm_backends.service.alert.enricher import BaseAlertEnricher
from alarm_backends.service.fta_action.tasks.alert_assign import AlertAssigneeManager
from bkmonitor.documents import AlertLog
from constants.action import AssignMode
from constants.alert import AI_ANALYZE_TAG, NOISE_TAG
from core.prometheus import metrics

logger = logging.getLogger("alert.builder")


class AssignInfoEnricher(BaseAlertEnricher):
    """
    告警分派动作
    """

    def enrich_alert(self, alert: Alert) -> Alert:
        if alert.shield_end_close:
            # 屏蔽托管告警不执行分派，其他信息丰富仍由 factory 继续处理。
            return alert

        strategy = alert.get_extra_info(key="strategy")
        # 有策略直接用策略的分派规则，没有策略的，默认用分派
        notice = (strategy or {}).get("notice") or {}
        assign_mode = notice.get("options", {}).get("assign_mode") if strategy else [AssignMode.BY_RULE]
        user_groups = notice.get("user_groups") or []
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
            if exc is not None:
                status = "failed"
            elif assign_manager is None:
                status = "not_executed"
            else:
                status = "matched" if assign_manager.matched_rules else "unmatched"
            evaluated_at = int(time.time()) if status != "not_executed" else None
            alert.update_extra_info("dispatch_evaluation", {"status": status, "evaluated_at": evaluated_at})
            if assign_manager:
                if assign_manager.matched_rule_info["severity"]:
                    alert.update_severity_source(assign_manager.severity_source)
                    alert.update_severity(assign_manager.matched_rule_info["severity"])
                alert.update_extra_info("matched_rule_info", assign_manager.matched_rule_info)
                tags = list(assign_manager.matched_rule_info["additional_tags"])
                dispatch_result = assign_manager.matched_rule_info.get("dispatch_result", {})
                if dispatch_result.get("ai_analysis"):
                    tags.append({"key": AI_ANALYZE_TAG, "value": "true"})
                if dispatch_result.get("noise"):
                    tags.append({"key": NOISE_TAG, "value": "true"})
                    alert.add_log(
                        op_type=AlertLog.OpType.DISPATCH_NOISE,
                        description=_("告警命中分派规则组【{}】的噪声标记，已跳过自动通知和处理。").format(
                            assign_manager.matched_group_info.get("group_name", "")
                        ),
                        time=evaluated_at,
                    )
                elif assign_manager.matched_rules:
                    alert.add_log(**assign_manager.get_alert_log(evaluated_at=evaluated_at))
                if tags:
                    alert.update_assign_tags(tags)
                assign_labels.update({"rule_group_id": assign_manager.matched_group_info.get("group_id")})
        metrics.ALERT_ASSIGN_PROCESS_COUNT.labels(**assign_labels).inc()
        return alert
