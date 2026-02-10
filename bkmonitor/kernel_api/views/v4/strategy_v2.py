"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from bk_monitor_base.strategy import save_alarm_strategy_v2

from bkmonitor.utils.user import get_global_user
from constants.action import ActionSignal
from core.drf_resource import Resource, resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class SaveStrategyResource(Resource):
    def perform_request(self, validated_request_data):
        return save_alarm_strategy_v2(
            bk_biz_id=validated_request_data["bk_biz_id"],
            strategy_json=validated_request_data,
            operator=get_global_user() or "system",
        )


class SearchStrategyResource(Resource):
    def perform_request(self, validated_request_data):
        result = resource.strategies.get_strategy_list_v2(validated_request_data)

        result["notice_group_list"] = [
            {
                "notice_group_id": group["user_group_id"],
                "notice_group_name": group["user_group_name"],
                "count": group["count"],
            }
            for group in result["user_group_list"]
        ]

        for strategy in result["strategy_config_list"]:
            strategy.pop("actions", None)
            notice = strategy.pop("notice")
            anomaly_template = None
            recovery_template = None
            for template in notice["config"].get("template", ""):
                if template["signal"] == ActionSignal.ABNORMAL:
                    anomaly_template = template
                elif template["signal"] == ActionSignal.RECOVERED:
                    recovery_template = template

            strategy["actions"] = [
                {
                    "id": notice["config_id"],
                    "type": "notice",
                    "config": {
                        "alarm_start_time": notice["options"].get("start_time", "00:00:00"),
                        "alarm_end_time": notice["options"].get("end_time", "23:59:59"),
                        "alarm_interval": notice["config"].get("notify_interval", 7200) // 60,
                        "send_recovery_alarm": ActionSignal.RECOVERED in notice["signal"],
                    },
                    "notice_group_ids": notice["user_groups"],
                    "notice_template": {
                        "anomaly_template": anomaly_template["message_tmpl"] if anomaly_template else "",
                        "recovery_template": recovery_template["message_tmpl"] if recovery_template else "",
                    },
                }
            ]

        return result


class AlarmStrategyV2ViewSet(ResourceViewSet):
    """
    新版告警策略API
    """

    resource_routes = [
        ResourceRoute("POST", SearchStrategyResource, endpoint="search"),
        ResourceRoute("POST", SaveStrategyResource, endpoint="save"),
        ResourceRoute("POST", resource.strategies.delete_strategy_config, endpoint="delete"),
        ResourceRoute("POST", resource.strategies.update_partial_strategy_v2, endpoint="update_bulk"),
    ]
