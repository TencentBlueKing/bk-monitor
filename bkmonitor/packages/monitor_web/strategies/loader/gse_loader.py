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

from typing import List, Optional

from bkmonitor.models import StrategyModel
from constants.action import ActionSignal
from constants.alert import DEFAULT_NOTICE_MESSAGE_TEMPLATE
from core.drf_resource import resource
from monitor_web.strategies.constant import (
    DEFAULT_ALARM_STRATEGY_ATTR_NAME_GSE,
    DEFAULT_ALARM_STRATEGY_LOADER_TYPE_GSE,
)
from monitor_web.strategies.default_settings import default_strategy_settings
from monitor_web.strategies.loader.base import DefaultAlarmStrategyLoaderBase
from monitor_web.strategies.user_groups import (
    create_default_notice_group,
    get_or_create_plugin_manager_group,
)

__all__ = ["GseDefaultAlarmStrategyLoader"]


class GseDefaultAlarmStrategyLoader(DefaultAlarmStrategyLoaderBase):
    """加载GSE默认告警策略"""

    CACHE = set()
    LOADER_TYPE = DEFAULT_ALARM_STRATEGY_LOADER_TYPE_GSE
    STRATEGY_ATTR_NAME = DEFAULT_ALARM_STRATEGY_ATTR_NAME_GSE

    def has_default_strategy_for_v1(self) -> bool:
        """判断第一个版本的内置业务是否已经接入 ."""
        return bool(StrategyModel.objects.filter(bk_biz_id=self.bk_biz_id, scenario="host_process").exists())

    def get_default_strategy(self):
        """获得默认告警策略 ."""
        strategies_list = default_strategy_settings.DEFAULT_GSE_PROCESS_EVENT_STRATEGIES_LIST
        if not strategies_list:
            return []
        return strategies_list

    def check_before_set_cache(self) -> bool:
        return True

    def get_notice_group(self, config_type: Optional[str] = None) -> List:
        """根据配置类型获得通知组ID ."""
        if config_type == "business":
            # 获得主备负责人通知组
            if "business" not in self.notice_group_cache:
                notice_group_id = create_default_notice_group(self.bk_biz_id)
                self.notice_group_cache["business"] = notice_group_id
            else:
                notice_group_id = self.notice_group_cache["business"]
        else:
            # 获得插件管理员组
            if "others" not in self.notice_group_cache:
                notice_group_id = get_or_create_plugin_manager_group(self.bk_biz_id)
                if notice_group_id:
                    self.notice_group_cache["others"] = notice_group_id
                else:
                    return []
            else:
                notice_group_id = self.notice_group_cache["others"]
        return [notice_group_id]

    def load_strategies(self, strategies: List) -> List:
        """
        执行进程托管类策略的内置操作
        5种事件，2种创建类型：
        1. 用户侧的进程托管类策略，创建5种事件对应的策略, 通知组默认使用主备负责人
        2. 平台侧的进程托管类策略，创建1种统一进程事件策略，通知组通知插件负责人
        """
        strategy_config_list = []
        for default_config in strategies:
            # 根据配置类型获得通知组ID
            config_type = default_config.get("type")
            notice_group_ids = self.get_notice_group(config_type)
            if not notice_group_ids:
                continue
            notice = {
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
            }
            detects = [
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
                        "status_setter": "close",
                    },
                }
            ]
            strategy_config = {
                "bk_biz_id": self.bk_biz_id,
                "name": str(default_config.get("name")),
                "scenario": default_config["result_table_label"],
                "source": "gse_process_deposit",
                "detects": detects,
                "items": [
                    {
                        "name": str(default_config.get("name")),
                        "no_data_config": {
                            "is_enabled": default_config.get("no_data_enabled", False),
                            "continuous": default_config.get("no_data_continuous", 5),
                        },
                        "algorithms": [{"level": default_config.get("level", 2), "config": [], "type": ""}],
                        "query_configs": [
                            {
                                "data_type_label": default_config.get("data_type_label"),
                                "data_source_label": default_config.get("data_source_label"),
                                "metric_id": default_config["metric_id"],
                                "result_table_id": default_config.get("result_table_id"),
                                "agg_condition": default_config.get("agg_condition"),
                                "agg_dimension": default_config.get("agg_dimension", []),
                                "agg_interval": default_config.get("agg_interval", 60),
                                "agg_method": default_config.get("agg_method", "AVG"),
                                "metric_field": default_config.get("metric_field"),
                                "unit": "",
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
                "notice": notice,
                "actions": [],
            }

            resource.strategies.save_strategy_v2(**strategy_config)

            strategy_config_list.append(strategy_config)

        return strategy_config_list
