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
import copy
import json
from typing import Dict, List, Optional, Tuple

from rest_framework.utils import encoders
from typing_extensions import TypedDict

from bkmonitor.action.serializers.assign import AssignRuleSlz
from bkmonitor.models import StrategyLabel
from bkmonitor.models.fta.assign import AlertAssignGroup, AlertAssignRule
from bkmonitor.utils.common_utils import logger
from constants.alert import DEFAULT_NOTICE_MESSAGE_TEMPLATE
from core.drf_resource import resource
from monitor_web.models.collecting import CollectConfigMeta
from monitor_web.strategies.default_settings.datalink.v1 import (
    DATALINK_GATHER_STATEGY_DESC,
    DEFAULT_DATALINK_COLLECTING_FLAG,
    DEFAULT_DATALINK_STRATEGIES,
    DEFAULT_RULE_GROUP_NAME,
    PLUGIN_TYPE_MAPPING,
    STAGE_STRATEGY_MAPPING,
    DataLinkStage,
    DatalinkStrategy,
    GatherType,
)
from monitor_web.strategies.user_groups import add_member_to_collecting_notice_group

DataLinkStrategyRule = TypedDict("DataLinkStrategyRule", {"user_groups": List[int]})

DataLinkStrategyInfo = TypedDict(
    "DataLinkStrategyInfo",
    {"strategy_id": int, "strategy_name": DatalinkStrategy, "strategy_desc": str, "rule": DataLinkStrategyRule},
)


class DatalinkDefaultAlarmStrategyLoader:
    """创建采集配置时，自动创建默认告警策略"""

    def __init__(self, collect_config: CollectConfigMeta, user_id: str):
        self.user_id = user_id
        self.collect_config = collect_config
        self.bk_biz_id = self.collect_config.bk_biz_id
        self.collect_config_id = self.collect_config.id
        self.collect_config_name = self.collect_config.name

    def check_strategy_exist(self, name: DatalinkStrategy) -> Optional[int]:
        """检测策略是否存在"""
        label = self.render_label(name)
        insts = StrategyLabel.objects.filter(bk_biz_id=self.bk_biz_id, label_name="/{}/".format(label))
        if insts.exists() == 0:
            return None
        return insts[0].strategy_id

    def render_label(self, name: DatalinkStrategy) -> str:
        """根据默认告警策略，生成唯一标签"""
        return name.render_label(collect_config_id=self.collect_config_id, bk_biz_id=self.bk_biz_id)

    def get_default_strategy(self):
        """获得默认告警策略 ."""
        return copy.deepcopy(DEFAULT_DATALINK_STRATEGIES)

    def init_notice_group(self) -> int:
        """获得告警通知组 ."""
        return add_member_to_collecting_notice_group(self.bk_biz_id, self.user_id)

    def run(self):
        if not self.get_gather_type():
            logger.info("Plugin ({}) has no initial strategy".format(self.collect_config.plugin.plugin_type))
            return

        # 获得默认告警策略
        strategies_list = self.get_default_strategy()
        if not strategies_list:
            return

        # 初始化默认告警组
        notice_group_id = self.init_notice_group()
        logger.info("Succeed to init notice group: {}, {}".format(notice_group_id, self.user_id))

        # 添加默认告警策略
        strategy_tuples: List[Tuple[int, DatalinkStrategy]] = []
        for item in strategies_list:
            name = item["_name"]
            strategy_id = self.check_strategy_exist(name)
            if strategy_id is not None:
                strategy_tuples.append((strategy_id, name))
                logger.info(
                    "Strategy(collect_config={}, {}) has existed, strategy_id={}".format(
                        self.collect_config_id, name, strategy_id
                    )
                )
                continue
            new_strategy_id = self.update_strategy(item)
            strategy_tuples.append((new_strategy_id, name))
            logger.info("Succeed to update strategy({}, {})".format(self.collect_config_id, name))

        # 添加告警分派规则
        self.update_rule_group([notice_group_id], strategy_tuples, force_update=False)
        logger.info("Succeed to update rule group, {}".format(strategy_tuples))

    def update_strategy(self, strategy: Dict) -> int:
        """加载默认告警策略 ."""
        _name: DatalinkStrategy = strategy.pop("_name")
        # 占位符渲染
        strategy_str = json.dumps(strategy, cls=encoders.JSONEncoder)
        strategy_str = strategy_str.replace("${{custom_label}}", self.render_label(_name))
        strategy_str = strategy_str.replace("${{bk_biz_id}}", str(self.bk_biz_id))
        strategy = json.loads(strategy_str)

        # 组装通知信息
        notice = strategy["notice"]
        notice["user_groups"] = []
        notice["config"]["template"] = DEFAULT_NOTICE_MESSAGE_TEMPLATE

        # 组装最终结构
        strategy_config = {
            "bk_biz_id": self.bk_biz_id,
            "name": strategy["name"],
            "source": DEFAULT_DATALINK_COLLECTING_FLAG,
            "scenario": "host_process",
            "type": "monitor",
            "labels": strategy["labels"],
            "detects": strategy["detects"],
            "items": strategy["items"],
            "notice": notice,
            "actions": [],
        }
        # 保存策略
        logger.info("Start to save strategy, %s", strategy_config)
        return resource.strategies.save_strategy_v2(**strategy_config)["id"]

    def update_rule_group(
        self, user_group_ids: List[int], strategy_tuples: List[Tuple[int, DatalinkStrategy]], force_update: bool = True
    ):
        """保存告警分派组"""
        rules = []
        for strategy_id, strategy_name in strategy_tuples:
            rule = {
                "bk_biz_id": self.bk_biz_id,
                "is_enabled": True,
                "user_groups": user_group_ids,
                "conditions": [
                    {"field": "alert.strategy_id", "value": [strategy_id], "method": "eq", "condition": "and"},
                    {
                        "field": "bk_collect_config_id",
                        "value": [self.collect_config_id],
                        "method": "eq",
                        "condition": "and",
                    },
                ],
                "actions": [
                    {
                        "action_type": "notice",
                        "upgrade_config": {"is_enabled": False, "user_groups": [], "upgrade_interval": 0},
                        "is_enabled": True,
                    }
                ],
                "additional_tags": [{"key": "idx", "value": self.build_rule_idx(strategy_id)}],
            }
            rule["user_type"] = "follower" if strategy_name == DatalinkStrategy.COLLECTING_SYS_ALARM else "main"
            rules.append(rule)

        tool = RuleGroupTool(bk_biz_id=self.bk_biz_id)
        tool.ensure_group()
        tool.ensure_rules(rules, force_update)

    def build_rule_idx(self, strategy_id: int):
        """构建分派规则唯一标识"""
        return "idx_{}_{}".format(strategy_id, self.collect_config_id)

    def load_strategy_map(self, stage: DataLinkStage) -> Dict[int, DataLinkStrategyInfo]:
        """基于采集配置加载告警配置信息"""
        map = {}
        gather_type = self.get_gather_type()
        if gather_type is None:
            return map

        tool = RuleGroupTool(bk_biz_id=self.bk_biz_id)
        for strategy_name in STAGE_STRATEGY_MAPPING[stage]:
            try:
                strategy_label = StrategyLabel.objects.get(
                    bk_biz_id=self.bk_biz_id, label_name=strategy_name.render_escaped_label()
                )
            except StrategyLabel.DoesNotExist:
                continue
            if not tool.ensure_group(auto_create=False):
                continue
            strategy_id = strategy_label.strategy_id
            rule = tool.get_rule_by_idx(self.build_rule_idx(strategy_id))
            if rule is None:
                continue
            map[strategy_id] = {
                "strategy_id": strategy_id,
                "strategy_desc": DATALINK_GATHER_STATEGY_DESC[(strategy_name, gather_type)],
                "stratey_name": strategy_name,
                "rule": {"user_groups": rule.user_groups},
            }
        return map

    def get_gather_type(self) -> GatherType:
        plugin_type = self.collect_config.plugin.plugin_type
        return PLUGIN_TYPE_MAPPING[plugin_type] if plugin_type in PLUGIN_TYPE_MAPPING else None


class RuleGroupTool:
    """业务下采集状态默认告警分派组"""

    def __init__(self, bk_biz_id: int):
        self.bk_biz_id = bk_biz_id
        self.group_name = DEFAULT_RULE_GROUP_NAME
        self.group_id = None
        self.rules: List[AlertAssignRule] = []

    def ensure_group(self, auto_create=True) -> bool:
        """确保分派组"""
        try:
            group = AlertAssignGroup.objects.get(bk_biz_id=self.bk_biz_id, source=DEFAULT_DATALINK_COLLECTING_FLAG)
            self.group_id = group.id
            self.rules = list(AlertAssignRule.objects.filter(bk_biz_id=self.bk_biz_id, assign_group_id=group.id))
        except AlertAssignGroup.DoesNotExist:
            if not auto_create:
                return False
            group = AlertAssignGroup.objects.create(
                name=DEFAULT_RULE_GROUP_NAME,
                bk_biz_id=self.bk_biz_id,
                is_builtin=True,
                source=DEFAULT_DATALINK_COLLECTING_FLAG,
            )
            logger.info("Succeed to create assign group, {}".format(DEFAULT_RULE_GROUP_NAME))
            self.group_id = group.id
            self.rules = []
        return True

    def ensure_rules(self, new_rules: List[Dict], force_update: bool = True):
        """确保分配规则生效"""
        for new_rule in new_rules:
            new_idx = new_rule["additional_tags"][0]["value"]
            existed_rule = self.get_rule_by_idx(new_idx)
            if existed_rule is None:
                new_rule["assign_group_id"] = self.group_id
                slz = AssignRuleSlz(data=new_rule)
                slz.is_valid(raise_exception=True)
                AlertAssignRule.objects.create(**slz.validated_data)
                logger.info("Succeed to create assign rule, {}".format(slz.validated_data))
            # 目前强制更新只支持用户组ID列表
            elif force_update:
                existed_rule.user_groups = new_rule["user_groups"]
                existed_rule.save()

    def get_rule_by_idx(self, idx: str) -> AlertAssignRule:
        for rule in self.rules:
            if rule.additional_tags[0]["value"] == idx:
                return rule
        return None
