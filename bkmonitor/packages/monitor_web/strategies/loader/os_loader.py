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

from bk_monitor_base.strategy import get_metric_id
from django.conf import settings
from django.utils.translation import gettext as _

from bkmonitor.models import MetricListCache, StrategyModel
from constants.action import ActionSignal
from constants.alert import DEFAULT_NOTICE_MESSAGE_TEMPLATE
from constants.data_source import DataSourceLabel, DataTypeLabel
from constants.strategy import EVENT_DETECT_LIST, EVENT_QUERY_CONFIG_MAP
from core.drf_resource import resource
from monitor_web.strategies.constant import (
    DEFAULT_ALARM_STRATEGY_ATTR_NAME_OS,
    DEFAULT_ALARM_STRATEGY_LOADER_TYPE_OS,
)
from monitor_web.strategies.default_settings import default_strategy_settings
from monitor_web.strategies.loader.base import DefaultAlarmStrategyLoaderBase
from monitor_web.strategies.user_groups import (
    create_default_notice_group,
    get_or_create_gse_manager_group,
)

logger = logging.getLogger(__name__)

__all__ = ["OsDefaultAlarmStrategyLoader"]


class OsDefaultAlarmStrategyLoader(DefaultAlarmStrategyLoaderBase):
    """加载主机默认告警策略"""

    CACHE = set()
    LOADER_TYPE = DEFAULT_ALARM_STRATEGY_LOADER_TYPE_OS
    STRATEGY_ATTR_NAME = DEFAULT_ALARM_STRATEGY_ATTR_NAME_OS

    def has_default_strategy_for_v1(self) -> bool:
        """第一个版本的内置业务是否已经接入 ."""
        return bool(StrategyModel.objects.filter(bk_biz_id=self.bk_biz_id, scenario="os").exists())

    def get_default_strategy(self):
        """获得默认告警策略 ."""
        strategies_list = default_strategy_settings.DEFAULT_OS_STRATEGIES_LIST
        if not strategies_list:
            return []
        return strategies_list

    def check_before_set_cache(self) -> bool:
        return True

    def get_notice_group(self, config_type: str | None = None) -> list:
        """获得告警通知组 ."""
        notice_group_ids = self.notice_group_cache.get(config_type)
        if not notice_group_ids:
            notice_group_id = create_default_notice_group(self.bk_biz_id)
            notice_group_ids = [notice_group_id]
            self.notice_group_cache[config_type] = notice_group_ids
        return notice_group_ids

    def load_strategies(self, strategies: list) -> list:
        """加载默认告警策略 ."""
        # 查询监控内置的主机指标（时序）
        metrics = []
        metrics.extend(
            MetricListCache.objects.filter(
                bk_tenant_id=self.bk_tenant_id,
                result_table_label__in=["os", "host_process"],
                data_source_label=DataSourceLabel.BK_MONITOR_COLLECTOR,
                related_id="system",
            )
        )
        if settings.ENABLE_MULTI_TENANT_MODE:
            # 多租户：系统事件走 V4 分业务链路（custom 源，每个业务独立结果表 base_{tenant}_{biz}_event）
            metrics.extend(
                MetricListCache.objects.filter(
                    bk_tenant_id=self.bk_tenant_id,
                    bk_biz_id=self.bk_biz_id,
                    result_table_label__in=["os", "host_process"],
                    data_source_label=DataSourceLabel.CUSTOM,
                    data_type_label=DataTypeLabel.EVENT,
                )
            )
        else:
            # 单租户：系统事件为全局内置（bk_monitor 源，全局 system.event）
            metrics.extend(
                MetricListCache.objects.filter(
                    bk_tenant_id=self.bk_tenant_id,
                    result_table_label__in=["os", "host_process"],
                    data_source_label=DataSourceLabel.BK_MONITOR_COLLECTOR,
                    data_type_label=DataTypeLabel.EVENT,
                )
            )

        # 建立指标索引。custom 事件指标的 metric_id 由 custom_event_name 决定（非 metric_field），
        # 且 result_table_id 运行时才确定，故单独按事件名建索引供多租户事件策略匹配。
        metric_dict = {}
        custom_event_metrics = {}
        for metric in metrics:
            if (metric.data_source_label, metric.data_type_label) == (DataSourceLabel.CUSTOM, DataTypeLabel.EVENT):
                custom_event_metrics[metric.extend_fields.get("custom_event_name", "")] = metric
            else:
                metric_dict[
                    get_metric_id(
                        data_type_label=metric.data_type_label,
                        data_source_label=metric.data_source_label,
                        result_table_id=metric.result_table_id,
                        metric_field=metric.metric_field,
                    )
                ] = metric

        strategy_config_list = []
        for default_config in strategies:
            is_custom_event = (default_config["data_source_label"], default_config["data_type_label"]) == (
                DataSourceLabel.CUSTOM,
                DataTypeLabel.EVENT,
            )
            if is_custom_event:
                # 多租户系统事件：用事件名匹配（result_table_id 运行时按业务确定）
                metric = custom_event_metrics.get(default_config["metric_field"])
                if not metric:
                    continue
                custom_event_name = metric.extend_fields.get("custom_event_name", "")
                # metric_id 必须带 custom_event_name，否则退化为 __INDEX__（指向整表、检测时扫全部事件）
                metric_id = get_metric_id(
                    data_type_label=metric.data_type_label,
                    data_source_label=metric.data_source_label,
                    result_table_id=metric.result_table_id,
                    custom_event_name=custom_event_name,
                )
            else:
                metric_id = get_metric_id(
                    data_type_label=default_config["data_type_label"],
                    data_source_label=default_config["data_source_label"],
                    result_table_id=default_config.get("result_table_id", ""),
                    metric_field=default_config["metric_field"],
                )
                # 主机内置告警策略中的指标必须存在
                metric = metric_dict.get(metric_id)
                if not metric:
                    continue

            # 根据配置类型获得通知组ID
            config_type = default_config.get("type")
            # list 重新实例化列表，避免后面对列表的操作污染实例属性notice_group_cache
            notice_group_ids = list(self.get_notice_group(config_type))
            if not notice_group_ids:
                continue

            strategy_config = {
                "bk_biz_id": self.bk_biz_id,
                "name": str(default_config.get("name", metric.metric_field_name)),
                "scenario": default_config["result_table_label"],
                "detects": [
                    {
                        "expression": "",
                        "connector": "and",
                        "level": 2,
                        "trigger_config": {
                            "count": default_config["trigger_count"],
                            "check_window": default_config["trigger_check_window"],
                        },
                        "recovery_config": {
                            "check_window": default_config["recovery_check_window"],
                            "status_setter": default_config.get("recovery_status_setter", "recovery"),
                        },
                    }
                ],
                "items": [
                    {
                        "name": _(metric.metric_field_name),
                        "no_data_config": {
                            "is_enabled": default_config.get("no_data_enabled", False),
                            "continuous": default_config.get("no_data_continuous", 5),
                        },
                        "algorithms": [{"level": default_config.get("level", 2), "config": [], "type": ""}],
                        "query_configs": [
                            {
                                "metric_id": metric_id,
                                "data_type_label": metric.data_type_label,
                                "data_source_label": metric.data_source_label,
                                "result_table_id": metric.result_table_id,
                                "agg_condition": default_config.get("agg_condition", metric.default_condition),
                                "agg_dimension": default_config.get("agg_dimension", metric.default_dimensions),
                                "agg_interval": default_config.get("agg_interval", metric.collect_interval * 60),
                                "agg_method": default_config.get("agg_method", "AVG"),
                                "metric_field": metric.metric_field,
                                "unit": metric.unit,
                                "alias": "A",
                            }
                        ],
                        "target": [
                            [
                                {
                                    "field": "host_topo_node",
                                    "method": "eq",
                                    "value": [{"bk_inst_id": self.bk_biz_id, "bk_obj_id": "biz"}],
                                }
                            ]
                        ],
                    }
                ],
                "notice": {
                    "user_groups": notice_group_ids,
                    "signal": [ActionSignal.ABNORMAL],
                    "options": {
                        "converge_config": {
                            "need_biz_converge": True,
                        },
                        "start_time": "00:00:00",
                        "end_time": "23:59:59",
                    },
                    "config": {
                        "interval_notify_mode": "standard",
                        "notify_interval": 2 * 60 * 60,
                        "template": DEFAULT_NOTICE_MESSAGE_TEMPLATE,
                    },
                },
                "actions": [],
            }

            item = strategy_config["items"][0]
            # 非事件性策略配置阈值
            if metric.data_type_label != DataTypeLabel.EVENT:
                item["algorithms"][0]["config"].append(
                    [{"threshold": default_config["threshold"], "method": default_config["method"]}]
                )
                item["algorithms"][0]["type"] = "Threshold"
                item["algorithms"][0]["unit_prefix"] = default_config.get("unit_prefix", "")

            # 多租户系统事件（custom 源）：补 custom_event_name，使检测按事件名过滤
            # （缺失则退化为整表扫描、任意事件都触发误告警）。CustomEventDataSource 出 COUNT
            # 聚合，故按「周期内事件数 >= 1 即异常」配阈值。注：检测语义待 review / 联调确认。
            if is_custom_event:
                query_config = item["query_configs"][0]
                query_config["custom_event_name"] = custom_event_name
                query_config["agg_method"] = "COUNT"
                item["algorithms"][0]["config"] = [[{"threshold": 1, "method": "gte"}]]
                item["algorithms"][0]["type"] = "Threshold"

            # 主机重启、进程端口、PING不可达、实际上是时序性指标，需要做特殊处理
            if metric.metric_field in EVENT_DETECT_LIST:
                event_detect_config = EVENT_DETECT_LIST[metric.metric_field]
                item["query_configs"][0].update(EVENT_QUERY_CONFIG_MAP.get(metric.metric_field, {}))
                item["query_configs"][0]["data_type_label"] = DataTypeLabel.TIME_SERIES
                item["algorithms"][0]["type"] = event_detect_config[0]["type"]
                item["algorithms"][0]["config"] = event_detect_config[0]["config"]

            # GSE失联事件追加GSE管理员（多租户 V4 事件名为 AgentLost）
            if metric.metric_field in ("agent-gse", "AgentLost"):
                gse_notice_group_id = get_or_create_gse_manager_group(self.bk_biz_id)
                if gse_notice_group_id is not None:
                    strategy_config["notice"]["user_groups"].append(gse_notice_group_id)

            # 保存策略
            resource.strategies.save_strategy_v2(**strategy_config)

            strategy_config_list.append(strategy_config)

        return strategy_config_list
