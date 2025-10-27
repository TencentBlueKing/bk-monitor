"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from rest_framework import serializers

from alarm_backends.management.commands.token import get_token_info
from bkmonitor.models import StrategyModel
from bkmonitor.strategy.new_strategy import Strategy
from constants.data_source import DATA_CATEGORY
from core.drf_resource import Resource, resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from monitor_web.strategies.resources import GetStrategyListV2Resource, GetDevopsStrategyListResource


class SearchStrategyWithoutBizResource(GetStrategyListV2Resource):
    class RequestSerializer(GetStrategyListV2Resource.RequestSerializer):
        bk_biz_id = serializers.IntegerField(required=False, label="业务ID")

    def perform_request(self, params):
        strategies = StrategyModel.objects.all()

        # 按条件过滤策略
        strategies = self.filter_by_conditions(params["conditions"], strategies)

        # 按当前选择的监控对象过滤
        scenarios = set(params.get("scenario", []))
        for condition in params["conditions"]:
            if condition["key"] != "scenario":
                continue
            if not isinstance(condition["value"], list):
                values = [condition["value"]]
            else:
                values = condition["value"]
            scenarios.update(values)

        if scenarios:
            strategies = strategies.filter(scenario__in=scenarios)

        # 排序
        strategies = strategies.order_by("-update_time")

        strategy_count = strategies.count()

        # 分页
        if params.get("page") and params.get("page_size"):
            strategies = strategies[(params["page"] - 1) * params["page_size"] : params["page"] * params["page_size"]]

        # 生成策略配置
        strategy_objs = Strategy.from_models(strategies)
        for strategy_obj in strategy_objs:
            strategy_obj.restore()
        strategy_configs = [s.to_dict() for s in strategy_objs]

        # 补充告警组信息
        if params["with_user_group"]:
            Strategy.fill_user_groups(strategy_configs, params["with_user_group_detail"])

        # 补充策略所属数据源
        data_source_names = {
            (category["data_source_label"], category["data_type_label"]): category["name"] for category in DATA_CATEGORY
        }
        for strategy_config in strategy_configs:
            data_source_label = strategy_config["items"][0]["query_configs"][0]["data_source_label"]
            data_type_label = strategy_config["items"][0]["query_configs"][0]["data_type_label"]
            strategy_config["data_source_type"] = data_source_names.get((data_source_label, data_type_label), "")

        return {"list": strategy_configs, "total": strategy_count}


class QosCheckResource(Resource):
    class RequestSerializer(GetStrategyListV2Resource.RequestSerializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    def perform_request(self, params):
        messages = []
        qos_ret = get_token_info(params["bk_biz_id"])
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
