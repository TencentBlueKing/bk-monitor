# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import operator
from collections import defaultdict
from datetime import datetime
from functools import reduce

from django.db.models import Q

from bkmonitor.models import (
    AlertAssignRule,
    DutyRule,
    DutyRuleRelation,
    StrategyActionConfigRelation,
    StrategyModel,
    UserGroup,
)
from constants.action import ActionPluginType


def get_action_config_strategy_dict(config_ids, strategies=None, bk_biz_id=None):
    """
    获取处理套餐与策略的统计数据
    :param config_ids: 套餐配置id
    :param strategies: 策略id
    :param bk_biz_id:对应的业务id
    :return:
    """
    relations = StrategyActionConfigRelation.objects.filter(config_id__in=list(config_ids))
    if strategies is not None:
        relations = relations.filter(strategy_id__in=list(strategies))

    valid_strategies = list(relations.values_list("strategy_id", flat=True).distinct())
    if bk_biz_id:
        valid_strategies = (
            StrategyModel.objects.filter(id__in=valid_strategies, bk_biz_id=bk_biz_id)
            .values_list("id", flat=True)
            .distinct()
        )
    else:
        valid_strategies = StrategyModel.objects.filter(id__in=valid_strategies).values_list("id", flat=True).distinct()
    strategy_count_of_config = defaultdict(list)
    valid_strategies = list(valid_strategies)
    for relation in relations.filter(strategy_id__in=valid_strategies):
        strategy_count_of_config[relation.config_id].append(relation.strategy_id)
    return {config_id: len(set(strategies)) for config_id, strategies in strategy_count_of_config.items()}


def get_action_config_rules(config_ids, bk_biz_id):
    """
    获取处理套餐对应的配置信息
    :param bk_biz_id: 业务ID
    :param config_ids:处理套餐ID
    :return:
    """
    if not config_ids:
        # 如果没有告警处理套餐，直接返回空
        return {}
    filters = [Q(actions__contains={"action_id": config_id}) for config_id in config_ids]
    action_config_rules = defaultdict(list)
    queryset = AlertAssignRule.objects.filter(bk_biz_id=bk_biz_id)
    for rule in queryset.filter(reduce(operator.or_, filters)).values("id", "actions"):
        for action in rule["actions"]:
            if action["action_type"] == ActionPluginType.NOTICE:
                continue
            action_config_rules[action["action_id"]].append(rule["id"])
    return action_config_rules


def get_strategy_user_group_dict(strategy_ids, bk_biz_id=None):
    """
    获取策略与告警组之间的关系
    :param strategy_ids:策略id列表
    :param bk_biz_id:指定的业务ID
    :return:
    """
    if not strategy_ids:
        # 不存在策略的情况下，直接返回
        return {}

    relations = StrategyActionConfigRelation.objects.filter(strategy_id__in=strategy_ids).values(
        "strategy_id", "user_groups"
    )
    if bk_biz_id:
        strategy_ids = (
            StrategyModel.objects.filter(id__in=strategy_ids, bk_biz_id=bk_biz_id)
            .values_list("id", flat=True)
            .distinct()
        )
    strategy_count_of_user_group = {}
    for relation in relations:
        strategy_id = relation["strategy_id"]
        if strategy_id not in strategy_ids:
            continue
        for user_group_id in relation["user_groups"]:
            if not user_group_id:
                continue
            if user_group_id not in strategy_count_of_user_group:
                strategy_count_of_user_group[user_group_id] = [strategy_id]
                continue
            strategy_count_of_user_group[user_group_id].append(strategy_id)
    return strategy_count_of_user_group


def get_user_group_strategies(user_groups, bk_biz_ids=None):
    """
    获取告警组对应的策略数统计
    """
    if not user_groups:
        # 如果没有告警组，直接返回
        return {}

    if bk_biz_ids is None:
        bk_biz_ids = set(UserGroup.objects.filter(id__in=user_groups).values_list("bk_biz_id", flat=True))

    if not bk_biz_ids:
        return {}

    strategies = list(StrategyModel.objects.filter(bk_biz_id__in=bk_biz_ids).values_list("id", flat=True))

    queryset = StrategyActionConfigRelation.origin_objects.filter(
        relate_type="NOTICE", strategy_id__in=strategies
    ).values("user_groups", "strategy_id", "is_deleted", "options")
    relations = []
    for relation in queryset:
        if relation["is_deleted"]:
            # 被删除的内容，忽略
            continue
        for group_id in user_groups:
            if group_id in relation["user_groups"]:
                # 如果告警组存在通知对象或者升级配置的对象中
                relations.append(relation)
                break
            upgrade_user_groups = relation["options"].get("upgrade_config", {}).get("user_groups")
            if upgrade_user_groups and group_id in upgrade_user_groups:
                relations.append(relation)
                break
    strategy_count_of_user_group = defaultdict(list)
    for relation in relations:
        if relation["options"].get("upgrade_config", {}).get("user_groups"):
            relation["user_groups"].extend(relation["options"]["upgrade_config"]["user_groups"])
        valid_groups = set(user_groups).intersection({group for group in relation["user_groups"] if group})
        strategy_id = relation["strategy_id"]
        for group_id in valid_groups:
            strategy_count_of_user_group[group_id].append(strategy_id)
    return strategy_count_of_user_group


def get_user_group_assign_rules(user_groups, bk_biz_ids=None):
    """
    获取告警组对应的策略数统计
    """
    if not user_groups:
        return {}

    if bk_biz_ids is None:
        bk_biz_ids = set(UserGroup.objects.filter(id__in=user_groups).values_list("bk_biz_id", flat=True))

    if not bk_biz_ids:
        return {}

    rule_queryset = AlertAssignRule.objects.filter(bk_biz_id__in=bk_biz_ids).values("user_groups", "id", "actions")
    rule_count_of_user_group = defaultdict(list)
    rules = []
    for rule in rule_queryset:
        for group_id in user_groups:
            if group_id in rule["user_groups"]:
                # 如果通知组包含一个告警组，则表示命中
                rules.append(rule)
                break
            upgrade_user_groups = []
            for action in rule["actions"]:
                if action["action_type"] == ActionPluginType.NOTICE:
                    upgrade_user_groups = action.get("upgrade_config", {}).get("user_groups")
                    break
            if upgrade_user_groups and group_id in upgrade_user_groups:
                rules.append(rule)
                break

    for rule in rules:
        for action in rule["actions"]:
            if action["action_type"] != ActionPluginType.NOTICE:
                continue
            if action.get("upgrade_config", {}).get("user_groups"):
                rule["user_groups"].extend(action["upgrade_config"]["user_groups"])
        valid_groups = set(user_groups).intersection(set(rule["user_groups"]))
        for group_id in valid_groups:
            rule_count_of_user_group[group_id].append(rule["id"])
    return rule_count_of_user_group


def get_assign_rule_related_resource_dict(assign_group_ids):
    """
    根据规则组信息获取对应的用户组ID
    """
    relations = {"action_ids": [], "user_groups": []}
    if assign_group_ids:
        for rule in AlertAssignRule.objects.filter(assign_group_id__in=assign_group_ids).only("actions", "user_groups"):
            relations["user_groups"].extend(rule.user_groups)
            for action in rule.actions:
                if action.get("upgrade_config"):
                    relations["user_groups"].extend(action["upgrade_config"]["user_groups"])
                if action.get("action_id"):
                    relations["action_ids"].append(action["action_id"])
    relations = {"action_ids": list(set(relations['action_ids'])), "user_groups": list(set(relations["user_groups"]))}
    return relations


def get_duty_rule_user_groups(duty_rule_ids):
    """获取轮值组关联的用户组"""
    if not duty_rule_ids:
        return {}

    duty_rule_user_groups = defaultdict(list)
    relations = []
    gp_ids = set()
    for relation in DutyRuleRelation.objects.filter(duty_rule_id__in=duty_rule_ids):
        relations.append(relation)
        gp_ids.add(relation.user_group_id)

    gp_ids = set(UserGroup.objects.filter(id__in=gp_ids, is_deleted=False).values_list("id", flat=True))

    for relation in relations:
        if relation.user_group_id in gp_ids:
            duty_rule_user_groups[relation.duty_rule_id].append(relation.user_group_id)

    return duty_rule_user_groups


def get_user_group_duty_rules(user_group_ids):
    """获取告警组关联的轮值组"""
    if not user_group_ids:
        return {}
    user_group_duty_rules = defaultdict(list)

    relations = []
    dr_ids = set()

    for relation in DutyRuleRelation.objects.filter(user_group_id__in=user_group_ids):
        relations.append(relation)
        dr_ids.add(relation.duty_rule_id)

    dr_ids = set(DutyRule.objects.filter(id__in=dr_ids, is_deleted=False).values_list("id", flat=True))

    for relation in relations:
        if relation.duty_rule_id in dr_ids:
            user_group_duty_rules[relation.user_group_id].append(relation.duty_rule_id)

    return user_group_duty_rules


def validate_time_range(value, format_str="%H:%M"):
    try:
        [start_time, end_time] = value.split("--")
        datetime.strptime(start_time, format_str)
        datetime.strptime(end_time, format_str)
    except ValueError:
        return False
    return True


def validate_datetime_range(value, format_str="%d %H:%M"):
    """
    校验前端的日期时间格式
    """
    try:
        [start_time, end_time] = value.split("--")
        datetime.strptime(start_time, format_str)
        datetime.strptime(end_time, format_str)
    except ValueError:
        return False
    return True
