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
from typing import Dict, List, Optional, Union

from alarm_backends.core.cache import key
from alarm_backends.core.control.item import Item
from alarm_backends.service.access.data.records import DataRecord
from alarm_backends.service.access.event.records.base import EventRecord


class PriorityChecker:
    """
    优先级检查，判断当前是否被抑制
    1. 根据优先级分组，获取优先级信息
    2. 比对时间戳，看是否过期，过期则覆盖，过期时间是一个固定的时间
    3. 比对维度优先级，如果优先级低则标记为抑制，否则更新优先级信息
    5. 设置一个删除时间，如果超过删除时间，删除优先级信息

    优先级信息是一个hashmap，key为维度分组，hash key为维度，hash value为优先级/时间戳的组合字段。

    数值越大，优先级越高，完全相同的一条数据检测到异常时以优先级高的策略为主？
    Q：不同的策略检测阈值可能不同，这里的实现是优先级低的数据点不推到检测队列，如果优先级高的策略同时检测阈值很高
    Q：会不会导致低优先级且符合告警条件的策略被忽略？
    A：会，目前告警优先级的设计是保留高优先级的点并推送到检测队列，丢弃低优先级的数据
    """

    def __init__(self, priority_group_key: str):
        self.priority_group_key = priority_group_key
        self.priority_cache = {}

        # 需要更新的优先级信息
        self.need_update = {}

        # 需要删除的优先级信息
        self.need_delete = []

        # redis client
        self.client = key.ACCESS_PRIORITY_KEY.client
        self.cache_key = key.ACCESS_PRIORITY_KEY.get_key(priority_group_key=self.priority_group_key)
        self.cache_ttl = key.ACCESS_PRIORITY_KEY.ttl

    def get_priority(self):
        """
        获取优先级信息
        """
        cache_key = key.ACCESS_PRIORITY_KEY.get_key(priority_group_key=self.priority_group_key)
        self.priority_cache = self.client.hgetall(cache_key)

    def get_priority_by_dimensions(self, dimensions_md5: str) -> Optional[str]:
        """
        获取维度优先级信息
        """
        cache_key = key.ACCESS_PRIORITY_KEY.get_key(priority_group_key=self.priority_group_key)
        return self.client.hget(cache_key, dimensions_md5)

    def is_inhibited(self, record: Union[DataRecord, EventRecord], item: Item) -> bool:
        """
        判断数据点是否被抑制，同时记录需要更新的优先级信息
        """
        now_timestamp = time.time()

        if isinstance(record, DataRecord):
            dimensions_md5 = record.record_id.split(".")[0]
        else:
            dimensions_md5 = record.md5_dimension
        strategy_priority = item.strategy.priority

        # 如果没有优先级信息，则更新优先级信息
        priority = self.priority_cache.get(dimensions_md5)
        if not priority:
            # 如果策略优先级为0，则不更新优先级信息，因为它已经是最小值了，没有存储的意义，减少内存占用
            if strategy_priority:
                self.need_update[dimensions_md5] = "{}:{}".format(strategy_priority, now_timestamp)
                self.priority_cache[dimensions_md5] = "{}:{}".format(strategy_priority, now_timestamp)
            return False

        priority, timestamp = priority.split(":")

        interval = item.strategy.get_interval()

        # 如果过期或优先级更高，则更新优先级信息
        if float(timestamp) + interval * 5 < now_timestamp or int(priority) <= strategy_priority:
            # 如果策略优先级为0，则不更新优先级信息，因为它已经是最小值了，没有存储的意义，减少内存占用
            if strategy_priority:
                self.need_update[dimensions_md5] = "{}:{}".format(strategy_priority, now_timestamp)
                self.priority_cache[dimensions_md5] = "{}:{}".format(strategy_priority, now_timestamp)
            return False

        return True

    @staticmethod
    def check_records(records: List[Union[DataRecord, EventRecord]]):
        """
        检查数据点是否被抑制
        """
        if not records:
            return

        priority_checkers: Dict[str, PriorityChecker] = {}
        for record in records:
            items = record.items
            # 判断数据点是否保留该item
            items = [
                item
                for item in items
                if record.is_retains[item.id]
                and item.strategy.priority is not None
                and item.strategy.priority_group_key
            ]
            # 按优先级由高到低为items排序
            items.sort(key=lambda x: x.strategy.priority, reverse=True)

            for item in items:
                priority_group_key = item.strategy.priority_group_key
                priority_checker = priority_checkers.get(priority_group_key)
                if not priority_checker:
                    priority_checker = PriorityChecker(priority_group_key)
                    priority_checkers[priority_group_key] = priority_checker
                    priority_checker.get_priority()

                # 记录是否被抑制
                record.inhibitions[item.id] = priority_checker.is_inhibited(record, item)

        # 同步优先级信息
        for priority_checker in priority_checkers.values():
            priority_checker.sync_priority(records[0].items[0])

    def sync_priority(self, item: Item):
        """
        批量同步优先级信息
        """
        interval = item.strategy.get_interval()

        # 删除过期的优先级信息
        for dimensions_md5, priority in self.priority_cache.items():
            priority, timestamp = priority.split(":")
            if float(timestamp) + interval * 10 < time.time():
                self.need_delete.append(dimensions_md5)

        # 更新优先级信息过期时间
        self.client.expire(self.cache_key, self.cache_ttl)

        if self.need_update:
            # 更新优先级信息
            self.client.hmset(self.cache_key, self.need_update)

        if self.need_delete:
            # 删除过期的优先级信息
            self.client.hdel(self.cache_key, *self.need_delete)
