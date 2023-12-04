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
                enabled=True,
                category=category,
                effective_time=datetime.now(tz=user_group.tz_info).strftime("%Y-%m-%d %H:%M:00"),
            )
            DutyArrange.objects.filter(user_group_id=user_group.id).update(duty_rule_id=duty_rule.id)
            user_group.duty_rules = [duty_rule.id]
            migrated_user_group.append(user_group)
            DutyRuleRelation.objects.create(
                duty_rule_id=duty_rule.id, user_group_id=user_group.id, bk_biz_id=user_group.bk_biz_id
            )
            # 历史的轮值规则删除掉
            print("delete history plans of duty group({})".format(user_group.name))
            DutyPlan.objects.filter(user_group_id__in=user_group.id).delete()
        if migrated_user_group:
            # 如果有需要迁移修改的，需要更新一下用户组里的duty_rules
            UserGroup.objects.bulk_update(migrated_user_group, fields=["duty_rules"])
        print("migrate duty user group config done!!")
