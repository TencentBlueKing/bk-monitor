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
import re
import time
from datetime import datetime, timedelta

import redis
from django.conf import settings

from alarm_backends.core.lock.service_lock import share_lock
from metadata.task.tasks import sync_bkbase_v4_metadata
from metadata.utils.redis_tools import bkbase_redis_client

logger = logging.getLogger("metadata")


@share_lock(ttl=86400, identify="watch_bkbase_meta_redis_task")
def watch_bkbase_meta_redis_task():
    """
    周期监听 计算平台元数据Redis键变化事件
    """
    logger.info("watch_bkbase_meta_redis_task: Start watching bkbase meta redis")
    try:
        bkbase_redis = bkbase_redis_client()
        key_pattern = f'{settings.BKBASE_REDIS_PATTERN}:*'
        watch_bkbase_meta_redis(redis_conn=bkbase_redis, key_pattern=key_pattern, runtime_limit=86400)
    except Exception as e:  # pylint: disable=broad-except
        logger.exception("watch_bkbase_meta_redis_task: Error watching bkbase meta redis,error->[%s]", e)


def watch_bkbase_meta_redis(redis_conn, key_pattern, runtime_limit=86400):
    """
    监听 Redis 键的变化事件，并动态获取键的内容。
    @param redis_conn: Redis 连接实例
    @param key_pattern: 监听键的模式
    @param runtime_limit: 任务运行时间限制，单位秒,默认一天
    """
    # 构建键空间通知的订阅频道名称
    keyspace_channel = f"__keyspace@0__:{key_pattern}"
    logger.info("watch_bkbase_meta_redis: Start watching Redis for pattern -> [%s]", key_pattern)

    # 在任务开始时编译正则表达式,减少正则开销
    bkbase_pattern = settings.BKBASE_REDIS_PATTERN
    channel_regex = re.compile(rf"__keyspace@\d+__:{bkbase_pattern}:\d+$")

    # 计算任务结束时间
    start_time = datetime.now()
    end_time = start_time + timedelta(seconds=runtime_limit)

    while datetime.now() < end_time:  # 运行时间控制
        try:
            # 初始化 pubsub
            pubsub = redis_conn.pubsub()
            pubsub.psubscribe(keyspace_channel)  # 监听特定模式的键事件
            logger.info("watch_bkbase_meta_redis: Subscribed to Redis channel -> [%s]", keyspace_channel)

            # 开始监听消息
            for message in pubsub.listen():
                if datetime.now() >= end_time:  # 超出运行时间，退出监听
                    logger.info("watch_bkbase_meta_redis: Runtime limit reached, stopping listener.")
                    return

                # 仅处理匹配模式的消息
                if message['type'] != 'pmessage':
                    continue

                # 解码消息内容
                channel = (
                    message['channel'].decode('utf-8') if isinstance(message['channel'], bytes) else message['channel']
                )
                event = message['data'].decode('utf-8') if isinstance(message['data'], bytes) else message['data']

                # 使用正则表达式验证频道格式
                if not channel_regex.match(channel):
                    logger.warning("watch_bkbase_meta_redis：Invalid channel format: [%s]. Skipping...", channel)
                    continue

                # 提取具体的键名称
                key = ":".join(channel.split(":")[1:])  # 从频道名称中提取键名

                logger.info(
                    "watch_bkbase_meta_redis: Event -> [%s], Key -> [%s], Channel -> [%s]. Initiating sync_metadata.",
                    event,
                    key,
                    channel,
                )

                # Celery异步调用同步逻辑
                sync_bkbase_v4_metadata.delay(key=key)

        except redis.exceptions.ConnectionError as e:
            logger.error("watch_bkbase_meta_redis: Redis connection error->[%s]", e)
            logger.info("watch_bkbase_meta_redis: Retrying connection in 10 seconds...")
            time.sleep(10)  # 等待 10 秒后尝试重连

        except Exception as e:  # pylint: disable=broad-except
            logger.error("watch_bkbase_meta_redis: Unexpected error->[%s]", e, exc_info=True)
            logger.info("watch_bkbase_meta_redis: Retrying listener in 10 seconds...")
            time.sleep(10)  # 等待 10 秒后重试

        finally:
            try:
                pubsub.close()  # 确保 pubsub 在异常退出时被正确关闭
                logger.info("watch_bkbase_meta_redis: Pubsub connection closed.")
            except Exception as close_error:  # pylint: disable=broad-except
                logger.warning("watch_bkbase_meta_redis: Failed to close pubsub->[%s]", close_error)

    logger.info("watch_bkbase_meta_redis: Task completed after reaching runtime limit.")
