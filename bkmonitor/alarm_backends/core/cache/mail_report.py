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


import json
import datetime
from collections import defaultdict

from core.drf_resource import api
from bkmonitor.models import Alert, Event, Strategy, Shield, NoticeGroup
from metadata.models import EventGroup
from alarm_backends.core.cache.key import MAIL_REPORT_GROUP_CACHE_KEY
from alarm_backends.core.cache.base import CacheManager
from bkmonitor.utils import extended_json


class MailReportCacheManager(CacheManager):
    """
    订阅报表 配置管理人员列表，配置管理人员所管理的业务，告警接收人，告警接收人所接收的业务
    """

    # 缓存key
    MAIL_REPORT_CACHE_KEY = MAIL_REPORT_GROUP_CACHE_KEY.get_key()

    @classmethod
    def fetch_groups_and_user_bizs(cls):
        """
        获取订阅报表配置管理组及其所辖业务、通知接收人及其所收通知业务
        :return: {
            "controller_group": {"users": [], "users_biz": []},
            "alert_group": {"users": [], "users_biz": []},
        }
        """
        data = cls.cache.get(cls.MAIL_REPORT_CACHE_KEY)
        if data:
            return extended_json.loads(data)
        else:
            return {
                "controller_group": {"users": [], "users_biz": []},
                "alert_group": {"users": [], "users_biz": []},
            }

    @classmethod
    def fetch_notify_receiver_group(cls):
        """
        获取告警组用户及其所属业务
        :return: 告警组用户列表, 用户对应的告警业务
        """
        # 存储用户对应的事件ID
        users_alert = defaultdict(list)
        # 存储所有事件ID
        all_events = []
        # 当前日期格式
        cur_date = datetime.datetime.now().date()
        # 前一月日期
        month_ago = cur_date - datetime.timedelta(weeks=4)

        alerts = Alert.objects.filter(create_time__gte=month_ago).values_list("event_id", "username")
        for alert in alerts:
            users_alert[alert[1]].append(alert[0])
            all_events.append(alert[0])

        # 用户对应的所有通知业务
        alerts = dict(alerts)
        users_bizs = defaultdict(set)
        events = Event.objects.filter(event_id__in=all_events).values_list("event_id", "bk_biz_id")
        for event in events:
            users_bizs[alerts.get(event[0])].add(event[1])

        return list(users_alert.keys()), users_bizs

    @classmethod
    def fetch_controller_group(cls):
        """
        获取所有配置(策略、采集配置、自定义事件、通知组、订阅报表)的创建者和编辑者
        :return: 配置管理组, 用户对应的配置业务
        """

        def merge_sets(users, user_sets):
            """
            合并集合
            :param users: 空集合
            :param user_tuples: [{"user1"}, {"user2"}]
            :return: {"user1", "user2"}
            """
            for user_set in user_sets:
                for user in user_set:
                    users.add(user)

        def merge_dicts(users_biz, user_biz_sets):
            """
            合并集合
            :param users_biz: 空集合
            :param user_biz_sets: [{"user1": {1, 2}}, {"user1": {3, 4}}]
            :return: {"user1": {1, 2, 3, 4}}
            """
            for item in user_biz_sets:
                for key, values in item.items():
                    merge_sets(users_biz[key], [values])

        def fetch_users_and_users_biz(config_list, bk_biz_id_col, create_user_col=None, update_user_col=None):
            users = set()
            users_bizs = defaultdict(set)
            for config in config_list:
                users.add(config[create_user_col])
                users.add(config[update_user_col])
                users_bizs[config[create_user_col]].add(config[bk_biz_id_col])
                users_bizs[config[update_user_col]].add(config[bk_biz_id_col])
            return users, users_bizs

        users = set()
        users_bizs = defaultdict(set)
        collector_config_users, collector_config_users_biz = fetch_users_and_users_biz(
            api.monitor.collect_config_list(), "bk_biz_id", "create_user", "update_user"
        )
        custom_event_users, custom_event_users_biz = fetch_users_and_users_biz(
            EventGroup.objects.filter(is_enable=True, is_delete=False).values(
                "creator", "last_modify_user", "bk_biz_id"
            ),
            "bk_biz_id",
            "creator",
            "last_modify_user",
        )
        shield_users, shield_users_biz = fetch_users_and_users_biz(
            Shield.objects.filter(is_enabled=True, is_deleted=False).values("create_user", "update_user", "bk_biz_id"),
            "bk_biz_id",
            "create_user",
            "update_user",
        )
        strategy_config_users, strategy_config_users_biz = fetch_users_and_users_biz(
            Strategy.objects.filter(is_enabled=True, is_deleted=False).values(
                "bk_biz_id", "create_user", "update_user"
            ),
            "bk_biz_id",
            "create_user",
            "update_user",
        )
        notice_group_users, notice_group_users_biz = fetch_users_and_users_biz(
            NoticeGroup.objects.filter(is_enabled=True, is_deleted=False).values(
                "bk_biz_id", "create_user", "update_user"
            ),
            "bk_biz_id",
            "create_user",
            "update_user",
        )
        merge_sets(
            users, [collector_config_users, custom_event_users, shield_users, strategy_config_users, notice_group_users]
        )
        merge_dicts(
            users_bizs,
            [
                collector_config_users_biz,
                custom_event_users_biz,
                shield_users_biz,
                strategy_config_users_biz,
                notice_group_users_biz,
            ],
        )
        return list(filter(None, set(users))), users_bizs

    @classmethod
    def refresh_mail_report_group(cls):
        """
        {
            "controller_group": {"users": [], "users_biz": []},
            "alert_group": {"users": [], "users_biz": []},
        }
        """
        controller_group, controller_group_user_biz = cls.fetch_controller_group()
        alert_receiver_group, alert_receiver_user_biz = cls.fetch_notify_receiver_group()

        pipeline = cls.cache.pipeline()
        data = {
            "controller_group": {"users": controller_group, "users_biz": controller_group_user_biz},
            "alert_group": {"users": alert_receiver_group, "users_biz": alert_receiver_user_biz},
        }
        pipeline.set(cls.MAIL_REPORT_CACHE_KEY, json.dumps(data), cls.CACHE_TIMEOUT)
        pipeline.execute()

    @classmethod
    def refresh(cls):
        cls.refresh_mail_report_group()


def main():
    MailReportCacheManager.refresh()
