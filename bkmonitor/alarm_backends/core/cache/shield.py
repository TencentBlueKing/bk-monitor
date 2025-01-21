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
import time

"""
告警屏蔽配置缓存
"""


from collections import defaultdict
from datetime import timedelta

import pytz

from alarm_backends.core.cache.base import CacheManager
from alarm_backends.core.cache.cmdb.business import BusinessManager
from bkmonitor.models import Shield
from bkmonitor.utils import extended_json, time_tools


class ShieldCacheManager(CacheManager):
    """
    告警屏蔽缓存
    """

    # 策略详情的缓存key
    CACHE_KEY_TEMPLATE = CacheManager.CACHE_KEY_PREFIX + ".shield.biz_{}"

    FAILURE_KEY_TEMPLATE = CacheManager.CACHE_KEY_PREFIX + ".shield.failure.{}"

    @classmethod
    def publish_failure(cls, module: str, target: str, duration: int):
        """
        发布故障事件并设置预期结束时间
        """
        expected_failure_end = int(time.time() + duration)
        cls.cache.hset(cls.FAILURE_KEY_TEMPLATE.format(module), target, expected_failure_end)

    @classmethod
    def get_last_failure_end(cls, module: str, target: str):
        """
        获取最近一次故障的结束时间
        """
        end_time = cls.cache.hget(cls.FAILURE_KEY_TEMPLATE.format(module), target) or 0
        return int(end_time)

    @classmethod
    def get_all_failures(cls, module: str):
        """
        获取模块下所有目标的故障
        """
        return cls.cache.hgetall(cls.FAILURE_KEY_TEMPLATE.format(module))

    @classmethod
    def get_shields_by_biz_id(cls, bk_biz_id):
        """
        按业务ID获取屏蔽配置列表
        :param bk_biz_id: 业务ID
        :return: [
            {
                'is_enabled': True,
                'bk_biz_id': 2,
                'update_time': datetime.datetime(2019, 10, 4, 8, 26, 34),
                'update_user': 'admin',
                'description': 'dsaf',
                'scope_type': 'instance',
                'begin_time': datetime.datetime(2019, 10, 3, 16, 0),
                'is_quick': False,
                'is_deleted': False,
                'failure_time': datetime.datetime(2019, 10, 10, 16, 0),
                'content': '',
                'create_user': 'admin',
                'create_time': datetime.datetime(2019, 10, 4, 8, 26, 34),
                'notice_config': {
                    'notice_way': ['mail'],
                    'notice_receiver': ['user#admin', 'group#bk_biz_developer'],
                    'notice_time': 5
                },
                'end_time': datetime.datetime(2019, 10, 10, 16, 0),
                'cycle_config': {
                    'day_list': [],
                    'type': 1,
                    'end_time': '',
                    'week_list': [],
                    'begin_time': ''
                },
                'dimension_config': {
                    'service_instance_id': [1, 2, 5, 6, 7, 10, 11]
                },
                'category': 'scope',
                'id': 1
            }
        ]
        """
        data = cls.cache.get(cls.CACHE_KEY_TEMPLATE.format(bk_biz_id))
        if data:
            data = extended_json.loads(data)
            for shield in data:
                shield["begin_time"] = shield["begin_time"].replace(tzinfo=pytz.UTC)
                shield["end_time"] = shield["end_time"].replace(tzinfo=pytz.UTC)
                shield["failure_time"] = shield["end_time"].replace(tzinfo=pytz.UTC)
            return data
        else:
            return []

    @classmethod
    def refresh(cls):
        now = time_tools.now()
        biz_list = BusinessManager.all()

        # 拉取生效的屏蔽配置，因为是缓存，把未来十分钟内会生效的屏蔽配置也拉进来
        shields = list(
            Shield.objects.filter(
                bk_biz_id__in=[biz.bk_biz_id for biz in biz_list],
                begin_time__lte=now + timedelta(minutes=10),
                end_time__gte=now,
                is_enabled=True,
            ).values()
        )

        # 按业务缓存
        shield_configs = defaultdict(list)
        for shield in shields:
            shield_configs[shield["bk_biz_id"]].append(shield)

        pipeline = cls.cache.pipeline()
        for biz in biz_list:
            bk_biz_id = biz.bk_biz_id
            if bk_biz_id in shield_configs:
                pipeline.set(
                    cls.CACHE_KEY_TEMPLATE.format(bk_biz_id),
                    extended_json.dumps(shield_configs[bk_biz_id]),
                    cls.CACHE_TIMEOUT,
                )
            else:
                pipeline.delete(cls.CACHE_KEY_TEMPLATE.format(bk_biz_id))
        pipeline.execute()


def main():
    ShieldCacheManager.refresh()
