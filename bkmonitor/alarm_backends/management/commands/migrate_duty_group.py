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
from datetime import datetime

from django.core.management.base import BaseCommand

from bkmonitor.models import (
    DutyArrange,
    DutyPlan,
    DutyRule,
    DutyRuleRelation,
    UserGroup,
)
from constants.common import DutyCategory


class Command(BaseCommand):
    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument(
            "--bk_biz_ids", help="migrate duty user group config for these business, default migrate all"
        )

    def handle(self, *args, **options):
        bk_biz_ids = options.get("bk_biz_ids") or []
        print("migrate duty user group config business(%s)" % bk_biz_ids)
        group_queryset = UserGroup.objects.filter(need_duty=True)
        if bk_biz_ids:
            group_queryset.filter(bk_biz_id__in=bk_biz_ids)
        migrated_user_group = []
        migrated_duty_arranges = []
        deleted_duty_arranges = []
        duty_rule_relations = []
        for user_group in group_queryset:
            if user_group.duty_rules:
                # 新版本的，忽略
                print("new duty group({}), turn to next one".format(user_group.name))
                continue

            if not user_group.duty_arranges:
                print("empty duty group({}), turn to next one".format(user_group.name))
                continue

            print("start to migrate duty group({})".format(user_group.name))

            category = (
                DutyCategory.HANDOFF
                if any([d.need_rotation for d in user_group.duty_arranges])
                else DutyCategory.REGULAR
            )
            duty_rule = DutyRule.objects.create(
                bk_biz_id=user_group.bk_biz_id,
                name=user_group.name,
                labels=["migrate"],
                enabled=True,
                category=category,
                effective_time=datetime.now(tz=user_group.tz_info).strftime("%Y-%m-%d %H:%M:00"),
            )
            for arrange in DutyArrange.objects.filter(user_group_id=user_group.id):
                if not all([arrange.duty_time, arrange.duty_users]):
                    # 如果没有轮值人和轮值时间为无效内容，可以删除
                    deleted_duty_arranges.append(arrange.id)
                    continue
                arrange.duty_rule_id = duty_rule.id
                for duty_time in arrange.duty_time:
                    # 对历史的的work_time，需要转变为列表
                    if isinstance(duty_time["work_time"], str):
                        duty_time["work_time"] = [duty_time["work_time"]]
                migrated_duty_arranges.append(arrange)
            DutyArrange.objects.filter(user_group_id=user_group.id).update(duty_rule_id=duty_rule.id)
            user_group.duty_rules = [duty_rule.id]
            migrated_user_group.append(user_group)
            duty_rule_relations.append(
                DutyRuleRelation(duty_rule_id=duty_rule.id, user_group_id=user_group.id, bk_biz_id=user_group.bk_biz_id)
            )

        if not migrated_user_group:
            print("no duty user group need to migrate!!")
            return
        # 如果有需要迁移修改的，需要更新一下用户组里的duty_rules
        group_names = ",".join([group.name for group in migrated_user_group])
        group_ids = [group.id for group in migrated_user_group]
        print("create duty rule relations for duty groups({})".format(group_names))
        UserGroup.objects.bulk_update(migrated_user_group, fields=["duty_rules"])
        DutyArrange.objects.bulk_update(migrated_duty_arranges, fields=["duty_rule_id", "duty_time"])
        DutyRuleRelation.objects.bulk_create(duty_rule_relations)

        if deleted_duty_arranges:
            print("delete invalid duty_arranges")
            DutyArrange.objects.filter(id__in=deleted_duty_arranges).delete()
        # 历史的轮值规则删除掉
        print("delete history plans of duty group({})".format(group_names))
        DutyPlan.objects.filter(user_group_id__in=group_ids).delete()

        print("migrate duty user group config done!!")
