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
from collections import defaultdict

from django.utils import translation
from django.utils.functional import cached_property

from bkmonitor.models import DutyArrange, UserGroup
from constants.alert import EVENT_SEVERITY_DICT
from core.statistics.metric import Metric, register
from monitor_web.statistics.v2.base import BaseCollector


class UserGroupCollector(BaseCollector):
    """
    告警组
    """

    @cached_property
    def user_groups(self):
        return UserGroup.objects.filter(bk_biz_id__in=list(self.biz_info.keys()))

    @cached_property
    def biz_groups_map(self) -> dict:
        biz_map = defaultdict(list)
        for user_group in self.user_groups:
            biz_map[user_group.bk_biz_id].append(user_group)

        return biz_map

    @cached_property
    def duty_arranges(self):
        return DutyArrange.objects.filter(is_deleted=False, is_enabled=True)

    @cached_property
    def duty_arrange_cache_map(self):
        return {x["user_group_id"]: x["users"] for x in self.duty_arranges.values("user_group_id", "users")}

    @register(labelnames=("bk_biz_id", "bk_biz_name", "need_duty"))
    def user_group_count(self, metric: Metric):
        """
        告警组配置数
        """
        for group in self.user_groups:
            metric.labels(
                bk_biz_id=group.bk_biz_id,
                bk_biz_name=self.get_biz_name(group.bk_biz_id),
                need_duty="1" if group.need_duty else "0",
            ).inc()

    @register(labelnames=("bk_biz_id", "bk_biz_name", "notice_way", "level"))
    def user_group_alert_notice_count(self, metric: Metric):
        """
        通知级别告警组配置数
        """
        language = translation.get_language()
        translation.activate("en")
        for group in self.user_groups:
            for time_config in group.alert_notice:
                for notify_config in time_config["notify_config"]:
                    UserGroup.translate_notice_ways(notify_config)
                    for notice_way in notify_config["type"]:
                        metric.labels(
                            bk_biz_id=group.bk_biz_id,
                            bk_biz_name=self.get_biz_name(group.bk_biz_id),
                            notice_way=notice_way,
                            level=EVENT_SEVERITY_DICT.get(notify_config["level"], notify_config["level"]),
                        ).inc()
        translation.activate(language)

    @register(labelnames=("bk_biz_id", "bk_biz_name", "notice_way", "phase"))
    def user_group_action_notice_count(self, metric: Metric):
        """
        执行阶段告警组配置数
        """
        phase_mappings = {
            "1": "failed",
            "2": "success",
            "3": "start",
        }
        for group in self.user_groups:
            for time_config in group.action_notice:
                for notify_config in time_config["notify_config"]:
                    UserGroup.translate_notice_ways(notify_config)
                    for notice_way in notify_config["type"]:
                        metric.labels(
                            bk_biz_id=group.bk_biz_id,
                            bk_biz_name=self.get_biz_name(group.bk_biz_id),
                            notice_way=notice_way,
                            phase=phase_mappings.get(str(notify_config["phase"]), notify_config["phase"]),
                        ).inc()

    @register(labelnames=("bk_biz_id", "bk_biz_name", "method"))
    def notice_receiver_count(self, metric: Metric):
        """告警接收人数"""
        for biz_id, groups in self.biz_groups_map.items():
            method_users_map = defaultdict(set)
            for group in groups:
                users = []
                for user_info in self.duty_arrange_cache_map.get(group.pk, []):
                    if user_info["type"] == "user":
                        users.append(user_info["id"])
                    elif user_info["type"] == "group":
                        users.extend(getattr(self.biz_info.get(group.bk_biz_id), user_info["id"], []))

                for time_config in group.alert_notice:
                    for notify_config in time_config["notify_config"]:
                        UserGroup.translate_notice_ways(notify_config)
                        for notice_way in notify_config["type"]:
                            method_users_map[notice_way] = method_users_map[notice_way].union(set(users))

            for notice_way, users_ in method_users_map.items():
                metric.labels(
                    bk_biz_id=biz_id,
                    bk_biz_name=self.get_biz_name(biz_id),
                    method=notice_way,
                ).inc(len(users_))
