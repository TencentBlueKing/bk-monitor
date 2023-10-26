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

from django.conf import settings
from django.utils.functional import cached_property

from alarm_backends.core.cache import key


class Checkpoint(object):
    def __init__(self, strategy_group_key, client=None):
        self.strategy_group_key = strategy_group_key

        self.client = client or key.STRATEGY_CHECKPOINT_KEY.client

    @cached_property
    def _key(self):
        return key.STRATEGY_CHECKPOINT_KEY.get_key(strategy_group_key=self.strategy_group_key)

    def set(self, checkpoint):
        """
        缓存策略监控项最后一个处理时间
        """
        self.client.set(self._key, checkpoint, key.STRATEGY_CHECKPOINT_KEY.ttl)

    def get(self, min_last_checkpoint=0, interval=60):
        """
        获取监控最后一个处理时间

        策略：
            - 当第一次拉取 或者 距离上一次拉取间隔超过了最小值，以最小值为准
            - 其他情况则以缓存中的checkpoint为准
        """
        now = int(time.time())
        last_check_point = int(self.client.get(self._key) or 0)
        # 长时间没数据，我们需要一个数据拉取的起点
        time_shift = settings.MIN_DATA_ACCESS_CHECKPOINT
        if interval > 300:
            time_shift = max([interval * 5, settings.MIN_DATA_ACCESS_CHECKPOINT])
        if (now - last_check_point) > time_shift:
            return max(min_last_checkpoint, now - time_shift)
        return last_check_point

    def is_pass(self, timestamp):
        """
        是否需要检测
        """
        return self.get() < timestamp
