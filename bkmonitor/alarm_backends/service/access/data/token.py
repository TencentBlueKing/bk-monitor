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
import logging

from django.conf import settings

from alarm_backends.core.cache.key import CONST_MINUTES, STRATEGY_TOKEN_BUCKET_KEY

__doc__ = """
描述：
    access模块令牌桶：对数据拉取耗时超预期的数据源进行降级。
实现方案：
    利用redis的key过期特性及decr的原子性，实现的滑动窗口令牌桶模型。
背景：
    access模块根据用户配置的监控策略，将数据源进行分组。每个strategy_group_key代表一个数据拉取任务。
    后台将周期发起数据拉起任务并给到celery worker执行。
    access下的时序数据源包含：监控自采数据（influxdb，ES），日志平台（ES），计算平台（tspider）。
    当其中某类数据源底层存储出现问题导致查询耗时过长时，会影响整个集群的worker的处理速度，
    导致任务队列堵塞，影响其他数据源的数据获取。同时没有降级能力，将加大问题存储的负载，出现雪崩效应。
实现：
    每个数据拉取任务都公平的被分配一定数量的token（值可配置）其中一个token表示1秒的时间，默认为每10分钟30s。
    token被记录在一个有着初始10分钟过期的key里。当token余额为正时，才能开启数据拉取任务，拉取结束后扣除对应拉取耗时的token。
    当token余额为负数时，后续在key有效期内，将被禁止再次执行拉取任务，同时追加对应比例的key过期时间补偿。
    例如：当前设置10分钟30s的滑动窗口。当token余额为-10的时候，将追加 600 / 30 * 10 = 200s 的过期时间。
管理工具：
    alarm_backends/management/commands/token.py
    后台执行./bin/manage.sh token
    将展示当前被降级的策略、表名及被限制时间
"""

from core.prometheus import metrics

logger = logging.getLogger("access.data")


class TokenBucket(object):
    def __init__(self, strategy_group_key, interval=60):
        self.strategy_group_key = strategy_group_key
        self.client = STRATEGY_TOKEN_BUCKET_KEY.client
        self.token_key = STRATEGY_TOKEN_BUCKET_KEY.get_key(strategy_group_key=strategy_group_key)
        # 每个access data task 在一个时间窗口的时间资源，单位：秒
        self.token_per_window = int(getattr(settings, "ACCESS_TIME_PER_WINDOW", 30))
        if interval < 60:
            # 按周期1分钟来分配token，当周期小于一分钟，等比例放大token
            self.token_per_window = int(self.token_per_window * (60 / interval))

    def touch(self):
        # 如果没有令牌：新的时间窗口或者新的策略组，申请新的令牌
        self.client.set(self.token_key, self.token_per_window, nx=True, ex=STRATEGY_TOKEN_BUCKET_KEY.ttl)
        return self.token_per_window

    def acquire(self):
        # 获取令牌
        token_remain = int(self.client.get(self.token_key) or self.touch())
        succeed = token_remain > 0
        if not succeed:
            # 没有令牌了
            remain_ttl = self.client.ttl(self.token_key) or 0
            logger.warning(
                f"strategy_group_key({self.strategy_group_key}):"
                f" no more token available, Recovery in {remain_ttl} seconds"
            )
            metrics.ACCESS_TOKEN_FORBIDDEN_COUNT.inc()
        return succeed

    def release(self, decrement):
        self.touch()
        token_remain = self.client.decr(self.token_key, int(decrement))
        logger.info(f"strategy_group_key({self.strategy_group_key}): token remain {token_remain}")
        if token_remain <= 0:
            # 令牌用完，根据令牌使用情况限制时间
            remain_ttl = self.client.ttl(self.token_key)
            if remain_ttl is None or remain_ttl < 0:
                # 申请新的令牌
                self.client.expire(self.token_key, 0)
                return
            # 欠的token，按比例补齐降级时间
            new_ttl = int(remain_ttl + abs(token_remain) * (STRATEGY_TOKEN_BUCKET_KEY.ttl / self.token_per_window))
            # 最大限制30 min
            new_ttl = min(new_ttl, 30 * CONST_MINUTES)
            self.client.expire(self.token_key, new_ttl)
            logger.warning(f"strategy_group_key({self.strategy_group_key}): token forbidden for {new_ttl} seconds")
