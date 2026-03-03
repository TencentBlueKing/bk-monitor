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

from bk_monitor_base.strategy import list_strategy
from django.utils import translation
from django.utils.functional import cached_property

from bkmonitor.models import (
    MetricListCache,
    StrategyActionConfigRelation,
)
from constants.alert import EVENT_SEVERITY_DICT
from constants.data_source import DataSourceLabel
from core.drf_resource import resource
from core.statistics.metric import Metric, register
from monitor_web.statistics.v2.base import BaseCollector

logger = logging.getLogger(__name__)


class StrategyCollector(BaseCollector):
    """
    策略
    """

    @staticmethod
    def get_scenario_and_parent_scenario():
        parent_and_child_scenario_dict = {}
        total_scenario = resource.strategies.get_scenario_list()
        for parent_label in total_scenario:
            for child_label in parent_label["children"]:
                parent_and_child_scenario_dict[child_label["id"]] = parent_label["id"]
        return parent_and_child_scenario_dict

    @cached_property
    def strategy_configs_list(self):
        return list_strategy(bk_biz_ids=list(self.biz_info.keys()))["data"]

    def strategy_count(self, metric: Metric):
        """
        告警策略数
        """
        use_action_strategy_ids = set(
            StrategyActionConfigRelation.objects.filter(
                relate_type=StrategyActionConfigRelation.RelateType.ACTION
            ).values_list("strategy_id", flat=True)
        )
        parent_and_child_scenario_dict = self.get_scenario_and_parent_scenario()
        for strategy_config in self.strategy_configs_list:
            scenario = strategy_config["scenario"]
            use_notice_collect = (
                "1" if strategy_config["notice"]["options"]["converge_config"].get("need_biz_converge") else "0"
            )
            use_action = "1" if strategy_config["id"] in use_action_strategy_ids else "0"
            try:
                item = strategy_config["items"][0]
                query_config = item["query_configs"][0]
            except IndexError:
                continue
            status = "enabled" if strategy_config["is_enabled"] else "disabled"
            invalid_type = strategy_config.get("invalid_type")
            metric.labels(
                bk_biz_id=strategy_config["bk_biz_id"],
                bk_biz_name=self.get_biz_name(strategy_config["bk_biz_id"]),
                data_source_label=query_config["data_source_label"],
                data_type_label=query_config["data_type_label"],
                status=status,
                scenario=scenario,
                parent_scenario=parent_and_child_scenario_dict.get(scenario),
                use_notice_collect=use_notice_collect,
                use_action=use_action,
                valid_status=invalid_type if invalid_type else "valid",
            ).inc()

    @register(
        labelnames=(
            "bk_biz_id",
            "bk_biz_name",
            "data_source_label",
            "parent_scenario",
            "scenario",
            "use_action",
            "status",
            "valid_status",
            "plugin_id",
        )
    )
    def strategy_fta_source_count(self, metric: Metric):
        """
        第三方告警策略统计
        """
        use_action_strategy_ids = set(
            StrategyActionConfigRelation.objects.filter(
                relate_type=StrategyActionConfigRelation.RelateType.ACTION
            ).values_list("strategy_id", flat=True)
        )
        fta_metric_plugins = {}
        # key的组成： 同业务下可能存在相同的指标，但是来自不同的plugin
        for fta_metric in MetricListCache.objects.filter(data_source_label="bk_fta").only(
            "bk_biz_id", "metric_field", "extend_fields", "data_source_label", "data_type_label"
        ):
            metric_key = (
                f"{fta_metric.data_source_label}.{fta_metric.data_type_label}.{fta_metric.metric_field}"
                f"--{fta_metric.bk_biz_id}"
            )
            fta_metric_plugins[metric_key] = fta_metric.extend_fields.get("plugin_ids", [])
        for strategy_config in self.strategy_configs_list:
            try:
                item = strategy_config["items"][0]
                query_config = item["query_configs"][0]
            except IndexError:
                continue

            if query_config["data_source_label"] != DataSourceLabel.BK_FTA:
                continue
            parent_and_child_scenario_dict = self.get_scenario_and_parent_scenario()
            use_action = "1" if strategy_config["id"] in use_action_strategy_ids else "0"
            status = "enabled" if strategy_config["is_enabled"] else "disabled"
            invalid_type = strategy_config.get("invalid_type")
            scenario = strategy_config["scenario"]
            default_metric_key = f"{query_config['metric_id']}--0"
            biz_metric_key = f"{query_config['metric_id']}--{strategy_config['bk_biz_id']}"
            plugins = fta_metric_plugins.get(default_metric_key) or fta_metric_plugins.get(biz_metric_key, [])
            if not plugins:
                # 没有匹配到的时候，plugin_id直接忽略, 数据来源于先前缓存的内容
                metric.labels(
                    bk_biz_id=strategy_config["bk_biz_id"],
                    bk_biz_name=self.get_biz_name(strategy_config["bk_biz_id"]),
                    data_source_label=query_config["data_source_label"],
                    status=status,
                    scenario=scenario,
                    parent_scenario=parent_and_child_scenario_dict.get(scenario),
                    use_action=use_action,
                    plugin_id="None",
                    valid_status=invalid_type if invalid_type else "valid",
                ).inc()
            for plugin in plugins:
                metric.labels(
                    bk_biz_id=strategy_config["bk_biz_id"],
                    bk_biz_name=self.get_biz_name(strategy_config["bk_biz_id"]),
                    data_source_label=query_config["data_source_label"],
                    status=status,
                    scenario=scenario,
                    parent_scenario=parent_and_child_scenario_dict.get(scenario),
                    use_action=use_action,
                    plugin_id=plugin,
                    valid_status=invalid_type if invalid_type else "valid",
                ).inc()

    @register(labelnames=("bk_biz_id", "bk_biz_name", "level"))
    def strategy_level_count(self, metric: Metric):
        """
        告警等级策略数
        """
        language = translation.get_language()
        translation.activate("en")

        try:
            for strategy_config in self.strategy_configs_list:
                level = set()
                for detect in strategy_config["detects"]:
                    if detect["level"] not in level:
                        level.add(detect["level"])
                        metric.labels(
                            bk_biz_id=strategy_config["bk_biz_id"],
                            bk_biz_name=self.get_biz_name(strategy_config["bk_biz_id"]),
                            level=EVENT_SEVERITY_DICT.get(detect["level"], detect["level"]),
                        ).inc()
        except Exception as e:
            logger.exception(f"strategy_level_count error: {e}")

        translation.activate(language)

    @register(labelnames=("bk_biz_id", "bk_biz_name", "algorithm_type", "plan_id", "status", "valid_status"))
    def strategy_detect_algorithm_count(self, metric: Metric):
        """
        检测算法使用数
        """
        for strategy_config in self.strategy_configs_list:
            status = "enabled" if strategy_config["is_enabled"] else "disabled"
            invalid_type = strategy_config.get("invalid_type")
            valid_status = invalid_type if invalid_type else "valid"

            for item in strategy_config["items"]:
                algorithm_type = set()
                for algorithm in item["algorithms"]:
                    if algorithm["type"] == "":
                        # 系统事件类的告警算法类型可能为空，忽略
                        continue

                    if algorithm["type"] not in algorithm_type:
                        algorithm_type.add(algorithm["type"])
                        plan_id = 0
                        if isinstance(algorithm["config"], dict):
                            plan_id = algorithm["config"].get("plan_id", 0)
                        metric.labels(
                            bk_biz_id=strategy_config["bk_biz_id"],
                            bk_biz_name=self.get_biz_name(strategy_config["bk_biz_id"]),
                            algorithm_type=algorithm["type"],
                            plan_id=plan_id,
                            status=status,
                            valid_status=valid_status,
                        ).inc()
