"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import redis
from django.conf import settings
from django.db import transaction

from alarm_backends.core.lock.service_lock import share_lock
from core.drf_resource import api
from core.prometheus import metrics
from metadata import models
from metadata.models.data_link.data_link_configs import ClusterConfig
from metadata.models.space.constants import SpaceStatus, SpaceTypes
from metadata.task.constants import BKBASE_V4_KIND_STORAGE_CONFIGS
from metadata.task.tasks import sync_bkbase_v4_metadata
from metadata.task.utils import chunk_list
from metadata.tools.constants import TASK_FINISHED_SUCCESS, TASK_STARTED
from metadata.tools.redis_lock import DistributedLock
from metadata.utils.bkbase import sync_bkbase_result_table_meta
from metadata.utils.redis_tools import RedisTools, bkbase_redis_client

logger = logging.getLogger("metadata")


DEFAULT_VM_EXPIRES_MS = 24 * 3600 * 90 * 1000


def watch_bkbase_meta_redis_task():
    """
    任务入口 计算平台元数据Redis键变化事件
    """
    bkbase_redis = bkbase_redis_client()

    # 检查bkbase redis配置是否存在
    if not bkbase_redis:
        logger.info("watch_bkbase_meta_redis_task: bkbase redis config is not set.")
        return

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
        key_pattern = f"{settings.BKBASE_REDIS_PATTERN}:*"
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
        pubsub = None
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
                if message["type"] != "pmessage":
                    continue

                # 解码消息内容
                channel = (
                    message["channel"].decode("utf-8") if isinstance(message["channel"], bytes) else message["channel"]
                )
                event = message["data"].decode("utf-8") if isinstance(message["data"], bytes) else message["data"]

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
                sync_bkbase_v4_metadata.delay(key=key, skip_types=["es"])

        except redis.ConnectionError as e:
            logger.error("watch_bkbase_meta_redis: Redis connection error->[%s]", e)
            logger.info("watch_bkbase_meta_redis: Retrying connection in 10 seconds...")
            time.sleep(settings.BKBASE_REDIS_RECONNECT_INTERVAL_SECONDS)  # 等待x秒后尝试重连
        except Exception as e:  # pylint: disable=broad-except
            logger.error("watch_bkbase_meta_redis: Unexpected error->[%s]", e, exc_info=True)
            logger.info("watch_bkbase_meta_redis: Retrying listener in 10 seconds...")
            time.sleep(settings.BKBASE_REDIS_RECONNECT_INTERVAL_SECONDS)  # 等待x秒后重试

        finally:
            try:
                if pubsub:
                    pubsub.close()  # 确保 pubsub 在异常退出时被正确关闭
                logger.info("watch_bkbase_meta_redis: Pubsub connection closed.")
            except Exception as close_error:  # pylint: disable=broad-except
                logger.warning("watch_bkbase_meta_redis: Failed to close pubsub->[%s]", close_error)

    logger.info("watch_bkbase_meta_redis: Task completed after reaching runtime limit.")


@share_lock(ttl=3600, identify="metadata_sync_all_bkbase_cluster_info")
def sync_all_bkbase_cluster_info():
    """
    同步 bkbase 集群信息
    VM / ES /Doris ...
    """
    logger.info("sync_all_bkbase_cluster_info: Start syncing cluster info from bkbase.")
    start_time = time.time()
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="sync_all_bkbase_cluster_info", status=TASK_STARTED, process_target=None
    ).inc()

    # 遍历所有存储类型配置
    for tenant in api.bk_login.list_tenant():
        for config in BKBASE_V4_KIND_STORAGE_CONFIGS:
            clusters = api.bkdata.list_data_link(
                bk_tenant_id=tenant["id"], namespace=config["namespace"], kind=config["kind"]
            )
            sync_bkbase_cluster_info(
                bk_tenant_id=tenant["id"],
                cluster_list=clusters,
                field_mappings=config["field_mappings"],
                cluster_type=config["cluster_type"],
            )
    cost_time = time.time() - start_time
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="sync_all_bkbase_cluster_info", status=TASK_FINISHED_SUCCESS, process_target=None
    ).inc()
    metrics.METADATA_CRON_TASK_COST_SECONDS.labels(
        task_name="sync_all_bkbase_cluster_info", process_target=None
    ).observe(cost_time)

    logger.info("sync_all_bkbase_cluster_info: Finished syncing cluster info from bkbase, cost time->[%s]", cost_time)


def sync_bkbase_cluster_info(bk_tenant_id: str, cluster_list: list, field_mappings: dict, cluster_type: str):
    """通用集群信息同步函数"""
    for cluster_data in cluster_list:
        try:
            cluster_spec = cluster_data.get("spec", {})
            cluster_metadata = cluster_data.get("metadata", {})

            # 动态获取字段映射（支持不同存储类型的字段差异）
            cluster_name = cluster_metadata["name"]
            domain_name = cluster_spec.get(field_mappings["domain_name"])
            port = cluster_spec.get(field_mappings["port"])
            username = cluster_spec.get(field_mappings["username"])
            password = cluster_spec.get(field_mappings["password"])
            namespace = cluster_metadata["namespace"]

            # 同步ClusterConfig
            cluster_config_data = copy.deepcopy(cluster_data)
            cluster_config_data.pop("status", None)
            ClusterConfig.objects.get_or_create(
                bk_tenant_id=bk_tenant_id,
                namespace=namespace,
                name=cluster_name,
                kind=ClusterConfig.CLUSTER_TYPE_TO_KIND_MAP[cluster_type],
                defaults={"origin_config": cluster_config_data},
            )

            # 设置集群配置
            default_settings = {}
            # 如果是VictoriaMetrics集群，需要获取过期时间
            if cluster_type == models.ClusterInfo.TYPE_VM:
                # 记录过期时间，单位为秒
                default_settings["retention_time"] = (cluster_spec.get("expiresMs") or DEFAULT_VM_EXPIRES_MS) // 1000
                # 记录集群所属业务ID，只有业务独立集群才会有对应字段，默认为None
                default_settings["bk_biz_id"] = cluster_spec.get("bkBizId")

            update_fields = {
                "port": port,
                "username": username,
                "password": password,
                "default_settings": default_settings,
            }

            with transaction.atomic():
                cluster = models.ClusterInfo.objects.filter(
                    bk_tenant_id=bk_tenant_id, cluster_type=cluster_type, cluster_name=cluster_name
                ).first()
                if cluster:
                    # 如果域名发生变化，为了防止出现问题，不进行更新并记录日志
                    if cluster.domain_name != domain_name:
                        logger.warning(
                            f"sync_bkbase_cluster_info: domain_name changed for {cluster_type} cluster: {cluster_name}, from {cluster.domain_name} to {domain_name}"
                        )
                        continue

                    # 更新集群信息
                    is_updated = False
                    for field, value in update_fields.items():
                        if value is not None and getattr(cluster, field) != value:
                            setattr(cluster, field, value)
                            is_updated = True

                    # 如果集群未被标记为已注册到bkbase平台，则标记为已注册
                    if not cluster.registered_to_bkbase:
                        cluster.registered_to_bkbase = True
                        is_updated = True

                    # 如果字段有更新，则保存模型
                    if is_updated:
                        logger.info(f"sync_bkbase_cluster_info: updated {cluster_type} cluster: {cluster_name}")
                        cluster.save()
                else:
                    # 创建新集群，默认为非默认集群
                    models.ClusterInfo.objects.create(
                        bk_tenant_id=bk_tenant_id,
                        cluster_type=cluster_type,
                        cluster_name=cluster_name,
                        display_name=cluster_name,
                        domain_name=domain_name,
                        port=port,
                        username=username or "",
                        password=password or "",
                        is_default_cluster=False,
                        default_settings=default_settings,
                        registered_system=models.ClusterInfo.BKDATA_REGISTERED_SYSTEM,
                        registered_to_bkbase=True,
                    )
                    logger.info(f"sync_bkbase_cluster_info: created new {cluster_type} cluster: {cluster_name}")
        except Exception as e:
            logger.error(f"sync_bkbase_cluster_info: failed to sync {cluster_type} cluster info, error->[{e}]")
            continue


@share_lock(identify="metadata_SyncBkbaseMetadataAll", ttl=7200)
def sync_bkbase_metadata_all():
    """
    全量同步BkBase元数据（并发）
    """
    logger.info("sync_bkbase_metadata_all: Start syncing metadata from bkbase.")
    start_time = time.time()
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="sync_bkbase_metadata_all", status=TASK_STARTED, process_target=None
    ).inc()

    # 获取BkBase数据一致性Redis中符合模式的所有key
    bkbase_redis = bkbase_redis_client()
    if not bkbase_redis:
        logger.warning("sync_bkbase_metadata_all: bkbase redis config is not set.")
        return

    cursor = 0
    matching_keys = []

    while True:
        cursor, keys = bkbase_redis.scan(
            cursor=cursor, match=f"{settings.BKBASE_REDIS_PATTERN}:*", count=settings.BKBASE_REDIS_SCAN_COUNT
        )
        decoded_keys = [k.decode("utf-8") if isinstance(k, bytes) else k for k in keys]
        matching_keys.extend(decoded_keys)
        if cursor == 0:
            break

    # 使用线程池并发发送任务
    def _send_task(key):
        try:
            sync_bkbase_v4_metadata.delay(key=key, skip_types=["es"])
        except Exception as e:
            logger.error(f"Failed to send task for key {key}: {e}")

    # 根据实际情况调整max_workers的数量
    with ThreadPoolExecutor(max_workers=10) as executor:
        executor.map(_send_task, matching_keys)

    logger.info("sync_bkbase_metadata_all: Finished syncing metadata from bkbase.")
    # 记录指标
    cost_time = time.time() - start_time
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="sync_bkbase_metadata_all", status=TASK_FINISHED_SUCCESS, process_target=None
    ).inc()
    metrics.METADATA_CRON_TASK_COST_SECONDS.labels(task_name="sync_bkbase_metadata_all", process_target=None).observe(
        cost_time
    )


@share_lock(identify="metadata_SyncBkBaseRtMetaInfoAll", ttl=10800)
def sync_bkbase_rt_meta_info_all():
    """
    全量同步计算平台RT元信息(调度)
    """
    if not settings.ENABLE_SYNC_BKBASE_META_TASK:
        logger.info("sync_bkbase_rt_meta_info_all: disabled by setting")
        return

    logger.info("sync_bkbase_rt_meta_info_all: start syncing bkbase rt meta info.")
    start_time = time.time()
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="sync_bkbase_rt_meta_info_all", status=TASK_STARTED, process_target=None
    ).inc()

    # 1. 获取全部仍处于活跃状态的业务ID列表
    # Q: 为什么需要屏蔽掉一些业务？
    # A：在计算平台自身的业务ID下，存在大量非监控平台使用的RT元信息，这些RT无需关注和同步
    active_biz_ids = list(
        models.Space.objects.filter(space_type_id=SpaceTypes.BKCC.value, status=SpaceStatus.NORMAL.value)
        .exclude(space_id__in=settings.SYNC_BKBASE_META_BLACK_BIZ_ID_LIST)
        .values_list("space_id", flat=True)
    )

    # 2. 按指定batch_size分片
    # Q:为什么要分批处理？
    # A:计算平台老Meta接口存在性能问题,全量拉取会超时且全量存放在内存中可能导致OOM
    biz_id_batches = chunk_list(data=active_biz_ids, size=settings.SYNC_BKBASE_META_BIZ_BATCH_SIZE)
    storages = settings.SYNC_BKBASE_META_SUPPORTED_STORAGE_TYPES
    logger.info(
        "sync_bkbase_rt_meta_info_all: start syncing bkbase rt meta serially,total rounds->[%s],support_storages->[%s]",
        len(biz_id_batches),
        storages,
    )

    # 3. 串行按业务批次拉取元信息列表并调用同步逻辑
    # Q:为什么不将全业务的全部元信息都拉出来然后再统一进行同步操作？
    # A:若全量取出至内存,大概率会导致OOM
    for idx, biz_id_batch in enumerate(biz_id_batches, start=1):
        logger.info("sync_bkbase_rt_meta_info_all: start syncing,round->[%s]", idx)
        try:
            bkbase_rt_meta_list = api.bkdata.bulk_list_result_table(bk_biz_id=biz_id_batch, storages=storages)
            sync_bkbase_result_table_meta(
                round_iter=idx, bkbase_rt_meta_list=bkbase_rt_meta_list, biz_id_list=biz_id_batch
            )
        except Exception as e:  # pylint:disable=broad-except
            logger.error(
                "sync_bkbase_rt_meta_info_all: round->[%s] failed,biz_ids->[%s],error->[%s]", idx, biz_id_batch, e
            )
            logger.exception(e)
            continue
        logger.info("sync_bkbase_rt_meta_info_all: end syncing,round->[%s]", idx)

    cost_time = time.time() - start_time
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="sync_bkbase_rt_meta_info_all", status=TASK_FINISHED_SUCCESS, process_target=None
    ).inc()
    metrics.METADATA_CRON_TASK_COST_SECONDS.labels(
        task_name="sync_bkbase_rt_meta_info_all", process_target=None
    ).observe(cost_time)
    logger.info("sync_bkbase_rt_meta_info_all: finished syncing bkbase rt meta info,cost->[%s]", cost_time)
