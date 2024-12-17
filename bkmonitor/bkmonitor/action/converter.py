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
from collections import defaultdict
from typing import List

from django.conf import settings
from django.db import transaction
from django.utils.translation import gettext as _

from bkmonitor import models
from constants.action import (
    DEFAULT_CONVERGE_CONFIG,
    ActionSignal,
    NoticeWay,
    NotifyStep,
)


class ActionConverter:
    def get_model(self, model_name):
        return self.models.get(model_name, getattr(models, model_name))

    def __init__(self, **migrate_models):
        self.models = migrate_models
        self.notice_groups = {}
        for notice_group in self.get_model("NoticeGroup").objects.all():
            self.notice_groups[notice_group.id] = notice_group

        self.action_notice = defaultdict(list)
        for item in self.get_model("ActionNoticeMapping").objects.all():
            if item.notice_group_id not in self.notice_groups:
                continue
            self.action_notice[item.action_id].append(self.notice_groups[item.notice_group_id])

        self.actions = defaultdict(list)
        for action in self.get_model("Action").objects.all():
            self.actions[action.strategy_id].append(action)

        self.no_data_configs = {}
        for item in self.get_model("ItemModel").objects.all():
            if item.no_data_config["is_enabled"]:
                self.no_data_configs[item.strategy_id] = True

        self.strategies = {}
        for strategy in self.get_model("StrategyModel").objects.all().values("name", "id", "bk_biz_id"):
            self.strategies[strategy["id"]] = strategy

        self.notice_templates = {}
        for template in self.get_model("NoticeTemplate").objects.all():
            self.notice_templates[template.action_id] = template.anomaly_template

        # 套餐缓存
        self.new_action_cache = {}
        self.actions_to_create = []
        self.user_groups_to_create = {}

        last_action_config = self.get_model("ActionConfig").objects.order_by("-id").first()
        # 自增ID计数器
        if last_action_config:
            self.action_id_offset = max(last_action_config.id, 1000)
        else:
            self.action_id_offset = 1000

    def gen_action_id(self):
        self.action_id_offset += 1
        return self.action_id_offset

    def migrate_user_groups(self):
        user_group_ids = set(self.get_model("UserGroup").objects.values_list("id", flat=True))

        user_groups = []
        duty_arranges = []
        for notice_group in self.notice_groups.values():
            if notice_group.id in user_group_ids:
                # 如果已经迁移过，则忽略
                continue
            notice_ways = [
                {"level": int(level), "type": notice_type} for level, notice_type in notice_group.notice_way.items()
            ]
            wxwork_group = notice_group.wxwork_group or {}
            for level_notice_way in notice_ways:
                if str(level_notice_way["level"]) in wxwork_group:
                    level_notice_way["type"].append("wxwork-bot")
                    level_notice_way["chatid"] = wxwork_group[str(level_notice_way["level"])]

            user_group = self.get_model("UserGroup")(
                id=notice_group.id,
                name=notice_group.name,
                bk_biz_id=notice_group.bk_biz_id,
                desc=notice_group.message,
                source=notice_group.source,
                update_time=notice_group.update_time,
                update_user=notice_group.update_user,
                create_time=notice_group.create_time,
                create_user=notice_group.create_user,
                alert_notice=[
                    {
                        "time_range": "00:00:00--23:59:59",
                        "notify_config": notice_ways,
                    }
                ],
                action_notice=[
                    {
                        "time_range": "00:00:00--23:59:59",
                        "notify_config": [
                            {
                                "phase": phase,
                                "type": [NoticeWay.MAIL],
                            }
                            for phase in [NotifyStep.BEGIN, NotifyStep.SUCCESS, NotifyStep.FAILURE]
                        ],
                    }
                ],
            )

            duty_arrange = self.get_model("DutyArrange")(
                user_group_id=notice_group.id,
                users=[
                    {"type": receiver.split("#")[0], "id": receiver.split("#")[-1]}
                    for receiver in notice_group.notice_receiver
                ],
            )
            user_groups.append(user_group)
            duty_arranges.append(duty_arrange)

            self.user_groups_to_create[notice_group.id] = user_group

        self.get_model("DutyArrange").objects.bulk_create(duty_arranges)

    def migrate(self, strategy_ids=None):
        with transaction.atomic(settings.BACKEND_DATABASE_NAME):
            self.migrate_user_groups()

            config_relations = []

            if strategy_ids:
                strategies = {
                    strategy_id: self.strategies[strategy_id]
                    for strategy_id in strategy_ids
                    if strategy_id in self.strategies
                }
            else:
                strategies = self.strategies

            migrate_result = {
                "success": 0,
                "failed": 0,
                "skipped": 0,
            }
            converted_strategies = set(
                self.get_model("StrategyActionConfigRelation").objects.values_list("strategy_id", flat=True)
            )
            for strategy_id, strategy in strategies.items():
                if strategy_id in converted_strategies:
                    # 如果已经迁移过了，则忽略
                    migrate_result["skipped"] += 1
                    continue
                try:
                    strategy_actions = self.actions[strategy_id]
                    for action in strategy_actions:
                        notice_groups = self.action_notice[action.id]

                        # 通知套餐迁移
                        relation = self.get_or_create_notice_action(strategy, action, notice_groups)
                        config_relations.append(relation)

                        for group in notice_groups:
                            if not group.webhook_url:
                                continue
                            # webhook 套餐迁移
                            relation = self.get_or_create_webhook(strategy, group, action, notice_groups)
                            config_relations.append(relation)

                        migrate_result["success"] += 1
                except Exception as e:
                    print("error handling strategy(%s), reason: %s", (strategy_id, e))
                    migrate_result["failed"] += 1

            # 批量创建套餐
            self.get_model("ActionConfig").objects.bulk_create(self.actions_to_create)

            # 批量创建套餐和策略的关联关系
            self.get_model("StrategyActionConfigRelation").objects.bulk_create(config_relations)

            # 批量创建用户组
            self.get_model("UserGroup").objects.bulk_create(list(self.user_groups_to_create.values()))

            return migrate_result

    def get_or_create_notice_action(
        self, strategy: dict, action: models.Action, all_notice_groups: List[models.NoticeGroup]
    ):
        alarm_interval = int(action.config["alarm_interval"])
        action_config = {
            "execute_config": {
                "template_detail": {
                    "notify_interval": alarm_interval * 60,
                    "interval_notify_mode": "standard",
                    "template": [
                        {
                            "signal": signal,
                            "message_tmpl": self.notice_templates.get(action.id, ""),
                            "title_tmpl": "{{business.bk_biz_name}} - {{alarm.name}}{{alarm.display_type}}",
                        }
                        for signal in [ActionSignal.ABNORMAL, ActionSignal.RECOVERED, ActionSignal.CLOSED]
                    ],
                },
                "timeout": 600,
            },
            "plugin_id": 1,
            "bk_biz_id": strategy["bk_biz_id"],
        }

        strategy_name = strategy["name"]
        strategy_id = strategy["id"]

        action_config["name"] = _("告警通知")
        action_config["desc"] = _("迁移的通知套餐, 原策略: {}({})").format(strategy_name, strategy_id)

        action_obj = self.get_model("ActionConfig")(id=self.gen_action_id(), **action_config)
        self.actions_to_create.append(action_obj)

        signals = [ActionSignal.ABNORMAL]
        if action.config.get("send_recovery_alarm"):
            # 通知配置
            signals.append(ActionSignal.RECOVERED)
        if self.no_data_configs.get(strategy_id):
            # 无数据配置
            signals.append(ActionSignal.NO_DATA)

        relation = self.get_model("StrategyActionConfigRelation")(
            strategy_id=strategy_id,
            relate_type="NOTICE",
            signal=signals,
            config_id=action_obj.id,
            user_groups=[group.id for group in all_notice_groups],
            options={
                "start_time": action.config["alarm_start_time"],
                "end_time": action.config["alarm_end_time"],
                "converge_config": copy.deepcopy(DEFAULT_CONVERGE_CONFIG),
            },
        )

        return relation

    def get_or_create_webhook(
        self,
        strategy: dict,
        notice_group: models.NoticeGroup,
        action: models.Action,
        all_notice_groups: List[models.NoticeGroup],
    ):
        action_config = {
            "plugin_id": 2,
            "bk_biz_id": strategy["bk_biz_id"],
            "create_user": "system",
            "update_user": "system",
            "execute_config": {
                "template_detail": {
                    "method": "POST",
                    "url": notice_group.webhook_url,
                    "headers": [],
                    "authorize": {"auth_type": "none", "auth_config": {}},
                    "body": {
                        "data_type": "raw",
                        "params": [],
                        "content": "{{alarm.callback_message}}",
                        "content_type": "json",
                    },
                    "query_params": [],
                    "need_poll": True,
                    "notify_interval": int(action.config["alarm_interval"]) * 60,
                    "failed_retry": {"is_enabled": True, "max_retry_times": 3, "retry_interval": 3, "timeout": 3},
                },
                "timeout": 600,
            },
        }

        strategy_name = strategy["name"]
        strategy_id = strategy["id"]

        if notice_group.id in self.new_action_cache:
            action_obj = self.new_action_cache[notice_group.id]
        else:
            action_config["name"] = "[webhook] {}({})".format(notice_group.name, notice_group.id)
            action_config["desc"] = _("迁移的回调套餐, 原策略: {}({}), 原通知组: {}({})").format(
                strategy_name, strategy_id, notice_group.name, notice_group.id
            )
            action_obj = self.get_model("ActionConfig")(id=self.gen_action_id(), **action_config)
            self.new_action_cache[notice_group.id] = action_obj
            self.actions_to_create.append(action_obj)
            self.user_groups_to_create[notice_group.id].webhook_action_id = action_obj.id

        relation = self.get_model("StrategyActionConfigRelation")(
            strategy_id=strategy_id,
            relate_type="ACTION",
            signal=[ActionSignal.ABNORMAL, ActionSignal.RECOVERED, ActionSignal.CLOSED, ActionSignal.NO_DATA],
            config_id=action_obj.id,
            user_groups=[group.id for group in all_notice_groups],
            options={
                "start_time": action.config["alarm_start_time"],
                "end_time": action.config["alarm_end_time"],
                "converge_config": {
                    "is_enabled": False,
                },
            },
        )

        return relation
