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
import threading
import time
from datetime import datetime, timedelta

import redis
from django.conf import settings
from django.db import transaction

from alarm_backends.core.lock.service_lock import share_lock
from core.drf_resource import api
from core.prometheus import metrics
from metadata import models
from metadata.task.constants import BKBASE_V4_KIND_STORAGE_CONFIGS
from metadata.task.tasks import sync_bkbase_v4_metadata
from metadata.tools.constants import TASK_FINISHED_SUCCESS, TASK_STARTED
from metadata.tools.redis_lock import DistributedLock
from metadata.utils.redis_tools import RedisTools, bkbase_redis_client

logger = logging.getLogger("metadata")


def watch_bkbase_meta_redis_task():
    """
    任务入口 计算平台元数据Redis键变化事件
    """
    logger.info("watch_bkbase_meta_redis_task: Start watching bkbase meta redis")

    # 初始化分布式锁
    bkm_redis_client = RedisTools.metadata_redis_client
    lock = DistributedLock(
        redis_client=bkm_redis_client,
        lock_name=settings.BKBASE_REDIS_LOCK_NAME,
        timeout=settings.BKBASE_REDIS_WATCH_LOCK_EXPIRE_SECONDS,
    )

    if not lock.acquire():
        logger.info("watch_bkbase_meta_redis_task: Lock is held by another instance. Exiting.")
        return

    logger.info("watch_bkbase_meta_redis_task: Lock acquired. Starting watch loop.")
    # 创建停止事件
    stop_event = threading.Event()

    try:
        bkbase_redis = bkbase_redis_client()
        key_pattern = f'{settings.BKBASE_REDIS_PATTERN}:*'
        runtime_limit = settings.BKBASE_REDIS_TASK_MAX_EXECUTION_TIME_SECONDS  # 任务运行时间限制为一天

        # 启动锁续约线程
        def renew_lock():
            while not stop_event.is_set():
                lock.renew()
                logger.info("watch_bkbase_meta_redis_task: Lock is being renewed...")
                time.sleep(settings.BKBASE_REDIS_WATCH_LOCK_RENEWAL_INTERVAL_SECONDS)  # 每15秒续约一次锁

        # 启动守护线程进行锁续约
        renew_thread = threading.Thread(target=renew_lock)
        renew_thread.daemon = True  # 设置为守护线程
        renew_thread.start()

        # 执行watch_bkbase_meta_redis并在过程中进行续约
        watch_bkbase_meta_redis(
            redis_conn=bkbase_redis,
            key_pattern=key_pattern,
            runtime_limit=runtime_limit,
        )

    except Exception as e:  # pylint: disable=broad-except
        logger.exception("watch_bkbase_meta_redis_task: Error watching bkbase meta redis, error->[%s]", e)

    finally:
        # 确保在任务完成后释放锁
        stop_event.set()  # 设置停止事件来终止守护线程
        lock.release()  # 释放锁
        logger.info("Lock released successfully.")


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

            # 监听消息
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
            time.sleep(settings.BKBASE_REDIS_RECONNECT_INTERVAL_SECONDS)  # 等待x秒后尝试重连

        except Exception as e:  # pylint: disable=broad-except
            logger.error("watch_bkbase_meta_redis: Unexpected error->[%s]", e, exc_info=True)
            logger.info("watch_bkbase_meta_redis: Retrying listener in 10 seconds...")
            time.sleep(settings.BKBASE_REDIS_RECONNECT_INTERVAL_SECONDS)  # 等待x秒后重试

        finally:
            try:
                pubsub.close()  # 确保 pubsub 在异常退出时被正确关闭
                logger.info("watch_bkbase_meta_redis: Pubsub connection closed.")
            except Exception as close_error:  # pylint: disable=broad-except
                logger.warning("watch_bkbase_meta_redis: Failed to close pubsub->[%s]", close_error)

    logger.info("watch_bkbase_meta_redis: Task completed after reaching runtime limit.")


@share_lock(ttl=3600, identify="metadata_sync_bkbase_cluster_info")
def sync_bkbase_cluster_info():
    """
    同步 bkbase 集群信息
    VM / ES /Doris ...
    """
    logger.info("sync_bkbase_cluster_info: Start syncing cluster info from bkbase.")
    start_time = time.time()
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="sync_bkbase_cluster_info", status=TASK_STARTED, process_target=None
    ).inc()

    # 遍历所有存储类型配置
    for config in BKBASE_V4_KIND_STORAGE_CONFIGS:
        clusters = api.bkdata.list_data_bus_raw_data(namespace=config["namespace"], kind=config["kind"])
        _sync_cluster_info(
            cluster_list=clusters,
            field_mappings=config["field_mappings"],
            cluster_type=config["cluster_type"],
            storage_name=config["storage_name"],
        )
    cost_time = time.time() - start_time
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="sync_bkbase_cluster_info", status=TASK_FINISHED_SUCCESS, process_target=None
    ).inc()
    metrics.METADATA_CRON_TASK_COST_SECONDS.labels(task_name="sync_bkbase_cluster_info", process_target=None).observe(
        cost_time
    )

    logger.info("sync_bkbase_cluster_info: Finished syncing cluster info from bkbase, cost time->[%s]", cost_time)


def _sync_cluster_info(cluster_list: list, field_mappings: dict, cluster_type: str, storage_name: str):
    """通用集群信息同步函数"""
    for cluster_data in cluster_list:
        try:
            cluster_auth_info = cluster_data.get("spec", {})
            cluster_metadata = cluster_data.get("metadata", {})

            # 动态获取字段映射（支持不同存储类型的字段差异）
            domain_name = cluster_auth_info.get(field_mappings["domain_name"])
            if not models.ClusterInfo.objects.filter(domain_name=domain_name).exists():
                logger.info(f"sync_bkbase_cluster_info: create {storage_name} cluster, domain_name->[{domain_name}]")
                with transaction.atomic():
                    models.ClusterInfo.objects.create(
                        domain_name=domain_name,
                        port=cluster_auth_info.get(field_mappings["port"]),
                        username=cluster_auth_info.get(field_mappings["username"]),
                        password=cluster_auth_info.get(field_mappings["password"]),
                        cluster_name=cluster_metadata.get("name"),
                        is_default_cluster=False,
                        cluster_type=cluster_type,
                    )
        except Exception as e:
            logger.error(f"sync_bkbase_cluster_info: failed to sync {storage_name} cluster info, error->[{e}]")
            continue
