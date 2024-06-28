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
from alarm_backends.core.cache import key


class Duplicate:
    def __init__(self, strategy_group_key, strategy_id=None):
        self.strategy_group_key = strategy_group_key
        self.record_ids_cache = {}
        self.pending_to_add = {}
        self.strategy_id = strategy_id

        self.client = key.ACCESS_DUPLICATE_KEY.client

    def get_record_ids(self, time):
        # 保证每个时间点仅调用一次redis， 即使无数据也缓存下来。
        dup_key = key.ACCESS_DUPLICATE_KEY.get_key(strategy_group_key=self.strategy_group_key, dt_event_time=time)
        if dup_key not in self.record_ids_cache:
            if self.strategy_id is not None:
                # Q：strategy_id setter 的作用是？
                # A:Redis 路由分片 - alarm_backends/core/storage/redis_cluster.py
                dup_key.strategy_id = self.strategy_id
            self.record_ids_cache[dup_key] = self.client.smembers(dup_key)

        return self.record_ids_cache[dup_key]

    def is_duplicate(self, record):
        """
        判断数据是否重复
        采用redis的集合功能。以分钟+维度作为key，值为record_id的集合
        """
        record_ids = self.get_record_ids(record.time)
        return str(record.record_id) in record_ids

    def add_record(self, record):
        # 原方案，将需要新增的点和已经存在的点放一起。然后再批量刷进redis。
        # 优化：仅把新增的点，单独列出（后续推到redis）。
        # 同步更新新的record到内存record_ids_cache中（但不再将缓存的所有点全推给redis）
        dup_key = key.ACCESS_DUPLICATE_KEY.get_key(
            strategy_group_key=self.strategy_group_key, dt_event_time=record.time
        )
        self.record_ids_cache.setdefault(dup_key, set()).add(record.record_id)
        self.pending_to_add.setdefault(dup_key, set()).add(record.record_id)

    def refresh_cache(self):
        # Q1：access 已经是按 item + 拉取周期拆分处理的，为什么这里要推一次 Redis
        # Q2：CheckPoint 已经控制了一个滑动窗口，按理说应该不会有重复？这里的业务背景是？
        # A1：是为了防止数据拉取周期之间数据点重复
        # A2：由于存在入库延迟，每次拉取是基于 last_check_point 往前一个周期拉数据，这里的去重逻辑可以过滤掉重叠窗口的重复数据点
        pipeline = self.client.pipeline(transaction=False)
        for dup_key, record_ids in self.pending_to_add.items():
            if self.strategy_id is not None:
                dup_key.strategy_id = self.strategy_id
            pipeline.sadd(dup_key, *record_ids)

        # duplicate point 对应过期时间也同步刷新
        for ttl_dup_key in self.record_ids_cache:
            ttl_dup_key.strategy_id = self.strategy_id
            pipeline.expire(ttl_dup_key, key.ACCESS_DUPLICATE_KEY.ttl)
        pipeline.execute()
