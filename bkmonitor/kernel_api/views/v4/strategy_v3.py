"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any

from bk_monitor_base.strategy import list_strategy
from rest_framework import serializers

from alarm_backends.management.commands.token import get_token_info
from constants.data_source import DATA_CATEGORY
from core.drf_resource import Resource, resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from monitor_web.strategies.resources import GetDevopsStrategyListResource, GetStrategyListV2Resource
from utils.strategy import fill_user_groups


class SearchStrategyWithoutBizResource(GetStrategyListV2Resource):
    class RequestSerializer(GetStrategyListV2Resource.RequestSerializer):
        bk_biz_id = serializers.IntegerField(required=False, label="业务ID")

    def perform_request(self, validated_request_data: dict[str, Any]):
        conditions: list[dict[str, Any]] = validated_request_data["conditions"]
        bk_biz_id: int = validated_request_data["bk_biz_id"]
        scenario: str | None = validated_request_data.get("scenario")
        page, page_size = validated_request_data.get("page"), validated_request_data.get("page_size")

        conditions = self.add_scenario_condition(conditions, scenario)
        # 按条件过滤策略
        strategy_ids = self.filter_by_conditions(bk_biz_id=bk_biz_id, conditions=conditions)

        # 分页
        offset, limit = 0, None
        if page and page_size:
            offset = (page - 1) * page_size
            limit = page * page_size

        strategies_result = list_strategy(
            bk_biz_id=bk_biz_id,
            conditions=[{"key": "id", "values": list(strategy_ids), "operator": "in"}],
            offset=offset,
            limit=limit,
        )
        strategy_configs = strategies_result["data"]
        total = strategies_result["count"]

        # 补充告警组信息
        if validated_request_data["with_user_group"]:
            fill_user_groups(strategy_configs, validated_request_data["with_user_group_detail"])

        # 补充策略所属数据源
        data_source_names = {
            (category["data_source_label"], category["data_type_label"]): category["name"] for category in DATA_CATEGORY
        }
        for strategy_config in strategy_configs:
            data_source_label = strategy_config["items"][0]["query_configs"][0]["data_source_label"]
            data_type_label = strategy_config["items"][0]["query_configs"][0]["data_type_label"]
            strategy_config["data_source_type"] = data_source_names.get((data_source_label, data_type_label), "")

        return {"list": strategy_configs, "total": total}


class QosCheckResource(Resource):
    class RequestSerializer(GetStrategyListV2Resource.RequestSerializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    def perform_request(self, validated_request_data: dict[str, Any]):
        messages = []
        qos_ret = get_token_info(validated_request_data["bk_biz_id"])
        for strategy_id, info in qos_ret.items():
            messages.append((strategy_id, info["strategy_name"], info["table_id"]))

        return messages


class AlarmStrategyV3ViewSet(ResourceViewSet):
    """
    V3版本告警策略API
    """

    resource_routes = [
        ResourceRoute("POST", resource.strategies.get_strategy_list_v2, endpoint="search"),
        ResourceRoute("POST", resource.strategies.save_strategy_v2, endpoint="save"),
        ResourceRoute("POST", resource.strategies.delete_strategy_config, endpoint="delete"),
        ResourceRoute("POST", resource.strategies.update_partial_strategy_v2, endpoint="update_bulk"),
        ResourceRoute("POST", SearchStrategyWithoutBizResource, endpoint="search_without_biz"),
        ResourceRoute("POST", resource.strategies.bulk_switch_strategy, endpoint="switch_by_labels"),
        ResourceRoute("GET", QosCheckResource, endpoint="qos_check"),
        ResourceRoute("GET", GetDevopsStrategyListResource, endpoint="get_devops_strategy_list"),
    ]
