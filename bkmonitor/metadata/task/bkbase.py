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
from typing import Any, cast

import redis
from django.conf import settings
from django.db import transaction

from alarm_backends.core.lock.service_lock import share_lock
from core.drf_resource import api
from core.prometheus import metrics
from metadata import models
from metadata.config import KAFKA_SASL_PROTOCOL
from metadata.models.data_link import utils as data_link_utils
from metadata.models.data_link.constants import (
    BKBASE_NAMESPACE_BK_LOG,
    BKBASE_NAMESPACE_BK_MONITOR,
    DataLinkKind,
    DataLinkResourceStatus,
)
from metadata.models.data_link.data_link_configs import ClusterConfig, DataLinkResourceConfigBase
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
    """同步 bkbase 集群信息 VM / ES /Doris ...

    Args:
        update: 是否更新集群信息，默认不更新
    """
    logger.info("sync_all_bkbase_cluster_info: Start syncing cluster info from bkbase.")
    start_time = time.time()
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="sync_all_bkbase_cluster_info", status=TASK_STARTED, process_target=None
    ).inc()

    # 遍历所有存储类型配置
    for tenant in api.bk_login.list_tenant():
        for storage_config in BKBASE_V4_KIND_STORAGE_CONFIGS:
            clusters = api.bkdata.list_data_link(
                bk_tenant_id=tenant["id"], namespace=storage_config["namespace"], kind=storage_config["kind"]
            )
            for cluster_data in clusters:
                try:
                    sync_bkbase_cluster_info(
                        bk_tenant_id=tenant["id"],
                        cluster_data=cluster_data,
                        field_mappings=storage_config["field_mappings"],
                        cluster_type=storage_config["cluster_type"],
                        update=settings.SYNC_BKBASE_CLUSTER_INFO_UPDATE,
                    )
                except Exception as e:
                    logger.error(
                        f"sync_bkbase_cluster_info: failed to sync {storage_config['cluster_type']} cluster info, error->[{e}]"
                    )
    cost_time = time.time() - start_time
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="sync_all_bkbase_cluster_info", status=TASK_FINISHED_SUCCESS, process_target=None
    ).inc()
    metrics.METADATA_CRON_TASK_COST_SECONDS.labels(
        task_name="sync_all_bkbase_cluster_info", process_target=None
    ).observe(cost_time)

    logger.info("sync_all_bkbase_cluster_info: Finished syncing cluster info from bkbase, cost time->[%s]", cost_time)


def _get_attr_by_path(data: dict[str, Any], path: str) -> Any:
    """根据路径获取数据

    Args:
        data: 数据
        path: 路径, 例如: "auth.sasl.username"

    Returns:
        value: 数据
    """
    paths = path.split(".")
    value: Any | None = data
    for key in paths:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return None
    return value


def sync_bkbase_cluster_info(
    bk_tenant_id: str, cluster_data: dict[str, Any], field_mappings: dict, cluster_type: str, update: bool = False
):
    """通用集群信息同步函数

    Args:
        bk_tenant_id: 租户ID
        cluster_data: 集群数据
        field_mappings: 字段映射
        cluster_type: 集群类型
        update: 是否更新集群信息
    """

    cluster_spec = cluster_data.get("spec", {})
    cluster_metadata = cluster_data.get("metadata", {})
    cluster_annotations = cluster_metadata.get("annotations", {})

    # 动态获取字段映射（支持不同存储类型的字段差异）
    cluster_name = cluster_metadata["name"]
    namespace = cluster_metadata["namespace"]
    domain_name = _get_attr_by_path(cluster_spec, field_mappings["domain_name"])
    port = _get_attr_by_path(cluster_spec, field_mappings["port"])
    username = _get_attr_by_path(cluster_spec, field_mappings["username"])
    password = _get_attr_by_path(cluster_spec, field_mappings["password"])
    version = _get_attr_by_path(cluster_spec, field_mappings.get("version", ""))

    # kafka 集群专用字段
    sasl_mechanisms = _get_attr_by_path(cluster_spec, field_mappings.get("sasl_mechanisms", ""))
    is_auth = _get_attr_by_path(cluster_spec, field_mappings.get("is_auth", ""))
    security_protocol: str | None = None
    stream_to_id = _get_attr_by_path(cluster_spec, field_mappings.get("stream_to_id", ""))
    v3_channel_id = _get_attr_by_path(cluster_spec, field_mappings.get("v3_channel_id", ""))

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

    if cluster_type == models.ClusterInfo.TYPE_VM:
        # 如果是VictoriaMetrics集群，需要获取过期时间和所属业务ID
        # 记录过期时间，单位为秒
        default_settings["retention_time"] = (cluster_spec.get("expiresMs") or DEFAULT_VM_EXPIRES_MS) // 1000
        # 记录集群所属业务ID，只有业务独立集群才会有对应字段，默认为None
        default_settings["bk_biz_id"] = cluster_spec.get("bkBizId")
    elif cluster_type == models.ClusterInfo.TYPE_KAFKA:
        # 如果是kafka集群，需要获取SASL认证信息
        if is_auth:
            security_protocol = KAFKA_SASL_PROTOCOL

        if v3_channel_id:
            default_settings["v3_channel_id"] = v3_channel_id

        # 如果stream_to_id不存在，则尝试从annotations中获取
        if not stream_to_id:
            stream_to_id = cluster_annotations.get("StreamToId")
            stream_to_id = int(stream_to_id) if stream_to_id else -1

        # 跳过inner角色集群的同步
        if cluster_spec.get("role") == "inner":
            return

    need_update_fields = {
        "port": port,
        "username": username,
        "password": password,
        "default_settings": default_settings,
        "sasl_mechanisms": sasl_mechanisms,
        "is_auth": is_auth,
        "gse_stream_to_id": stream_to_id,
        "security_protocol": security_protocol,
        "version": version,
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
                return

            # 更新集群信息
            is_updated = False
            update_fields: list[str] = []

            for field, value in need_update_fields.items():
                if value is not None and getattr(cluster, field) != value:
                    setattr(cluster, field, value)
                    is_updated = True
                    update_fields.append(field)

            # 如果集群未被标记为已注册到bkbase平台，则标记为已注册
            if not cluster.registered_to_bkbase:
                cluster.registered_to_bkbase = True
                is_updated = True
                update_fields.append("registered_to_bkbase")

            # 如果字段有更新，则保存模型
            if is_updated:
                if update:
                    logger.info(f"sync_bkbase_cluster_info: updated {cluster_type} cluster: {cluster_name}")
                    cluster.save(update_fields=update_fields)
                else:
                    logger.info(
                        f"sync_bkbase_cluster_info: updated {cluster_type} cluster: {cluster_name} but not saved because update is False"
                    )
        else:
            # 创建新集群，默认为非默认集群
            models.ClusterInfo.objects.create(
                bk_tenant_id=bk_tenant_id,
                cluster_type=cluster_type,
                cluster_name=cluster_name,
                display_name=cluster_name,
                domain_name=domain_name,
                port=port,
                security_protocol=security_protocol,
                sasl_mechanisms=sasl_mechanisms,
                is_auth=is_auth or False,
                username=username or "",
                password=password or "",
                is_default_cluster=False,
                default_settings=default_settings,
                registered_system=models.ClusterInfo.BKDATA_REGISTERED_SYSTEM,
                registered_to_bkbase=True,
                version=version,
                gse_stream_to_id=stream_to_id or -1,
            )
            logger.info(f"sync_bkbase_cluster_info: created new {cluster_type} cluster: {cluster_name}")


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
        # NOTE: `bkbase_redis_client()` 返回的 redis client 在类型存根中可能被标注为异步接口，
        # 会导致静态检查将 `scan()` 推断为 Awaitable，从而报“不能迭代”的错误。
        # 这里按运行时行为（同步 scan 返回 (cursor, keys)）做一次显式 cast，以消除误报。
        cursor, keys = cast(
            tuple[int, list[Any]],
            bkbase_redis.scan(
                cursor=cursor, match=f"{settings.BKBASE_REDIS_PATTERN}:*", count=settings.BKBASE_REDIS_SCAN_COUNT
            ),
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


def _safe_int(value: Any) -> int | None:
    """安全转换为 int。

    Args:
        value: 原始值

    Returns:
        转换后的 int 或 None
    """
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_component_common_fields(
    component: dict[str, Any], fallback_namespace: str
) -> tuple[str | None, str, int | None, str | None]:
    """提取组件的通用字段。

    list_data_link 返回的组件结构通常包含：
    - metadata.name / metadata.namespace
    - metadata.labels.bk_biz_id：业务ID（本地模型多数以其作为必填字段）
    - status.phase：组件运行状态（用于反向同步到本地 `status` 字段）

    Args:
        component: 组件配置
        fallback_namespace: 兜底命名空间

    Returns:
        name, namespace, bk_biz_id, status_phase
    """
    metadata = component.get("metadata", {})
    labels = metadata.get("labels", {})
    status_phase = component.get("status", {}).get("phase")
    name = metadata.get("name") or component.get("name")
    namespace = metadata.get("namespace") or fallback_namespace
    bk_biz_id = _safe_int(labels.get("bk_biz_id"))
    return name, namespace, bk_biz_id, status_phase


def _resolve_component_list(response: Any) -> list[dict[str, Any]]:
    """统一解析 list_data_link 返回结果。

    由于 API 在不同版本/网关下返回形态可能不一致，这里统一将返回值归一化为列表：
    - list：直接返回
    - dict：优先取 data，其次取 results
    - 其他：返回空列表

    Args:
        response: API 返回

    Returns:
        组件列表
    """
    if isinstance(response, list):
        return response
    if isinstance(response, dict):
        return cast(list[dict[str, Any]], response.get("data") or response.get("results") or [])
    return []


def _sync_component_record(
    model: type[DataLinkResourceConfigBase],
    lookup: dict[str, Any],
    base_fields: dict[str, Any],
    status_phase: str | None,
) -> bool:
    """同步单个组件记录。

    这里的同步策略是“幂等更新”：\n
    - 记录不存在：按 lookup + defaults 创建；若能取到 status_phase 则写入，否则默认 `PENDING`\n
    - 记录已存在：仅当字段发生变化时才 save(update_fields=...)\n
    这样可以避免无谓写入、降低同步任务对 DB 的压力。

    Args:
        model: 组件模型
        lookup: 查询条件
        base_fields: 基础字段
        status_phase: 状态字段

    Returns:
        是否发生变更
    """
    record = model.objects.filter(**lookup).first()
    updated_fields: list[str] = []
    if record is None:
        defaults = base_fields.copy()
        if status_phase:
            defaults["status"] = status_phase
        elif "status" not in defaults:
            defaults["status"] = DataLinkResourceStatus.PENDING.value
        model.objects.create(**lookup, **defaults)
        return True

    for field, value in base_fields.items():
        if value is None:
            continue
        if getattr(record, field) != value:
            setattr(record, field, value)
            updated_fields.append(field)

    if status_phase and record.status != status_phase:
        record.status = status_phase
        updated_fields.append("status")

    if updated_fields:
        record.save(update_fields=updated_fields)
        return True
    return False


def _parse_databus_fields(component: dict[str, Any], namespace: str, name: str) -> dict[str, Any] | None:
    """解析 Databus 组件基础字段。

    Databus 在 V4 配置里会挂接 sources（通常只有 1 个）。我们主要反向同步两类字段：\n
    - data_id_name：对应上游 DataId 组件的 name（用于后续推断 bk_data_id）\n
    - data_link_name：用于本地链路聚合的逻辑名\n

    注意：`data_link_name` 在不同命名空间下的语义不同：\n
    - bklog 命名空间：以 Databus 组件自身 name 作为链路名（与日志链路约定保持一致）\n
    - bkmonitor 命名空间：以 data_id_name 作为链路名（与监控时序链路约定保持一致）
    """
    spec = component.get("spec", {})
    sources = spec.get("sources") or []
    if not sources:
        return None
    data_id_name = sources[0].get("name")
    if not data_id_name:
        return None
    data_link_name = name if namespace == BKBASE_NAMESPACE_BK_LOG else data_id_name
    return {"data_id_name": data_id_name, "data_link_name": data_link_name}


def _parse_vm_binding_fields(component: dict[str, Any], _namespace: str, _name: str) -> dict[str, Any] | None:
    """解析 VM 存储绑定基础字段。

    VMStorageBinding 的核心是存储集群名（vm_cluster_name），用于后续通过 ClusterInfo 推断：\n
    - storage_type（VM）\n
    - storage_cluster_id
    """
    spec = component.get("spec", {})
    storage = spec.get("storage", {})
    vm_cluster_name = storage.get("name")
    if not vm_cluster_name:
        return None
    return {"vm_cluster_name": vm_cluster_name}


def _parse_es_binding_fields(component: dict[str, Any], _namespace: str, _name: str) -> dict[str, Any] | None:
    """解析 ES 存储绑定基础字段。

    ESStorageBinding 的核心是：\n
    - es_cluster_name：用于后续通过 ClusterInfo 推断集群 ID\n
    - timezone：索引写入时区（若缺失则用 0 兜底）
    """
    spec = component.get("spec", {})
    storage = spec.get("storage", {})
    es_cluster_name = storage.get("name")
    if not es_cluster_name:
        return None
    timezone = spec.get("write_alias", {}).get("TimeBased", {}).get("timezone")
    return {"es_cluster_name": es_cluster_name, "timezone": timezone or 0}


def _parse_result_table_fields(component: dict[str, Any], _namespace: str, _name: str) -> dict[str, Any] | None:
    """解析结果表基础字段。

    ResultTableConfig 可能包含 dataType（或 data_type）字段。\n
    - 若存在：同步到本地 data_type\n
    - 若不存在：返回空 dict，允许模型按默认值创建（避免因为缺字段导致整个 RT 记录被跳过）
    """
    spec = component.get("spec", {})
    data_type = spec.get("dataType") or spec.get("data_type")
    if not data_type:
        return {}
    return {"data_type": data_type}


def _sync_bkbase_components_base_fields(bk_tenant_id: str) -> dict[str, int]:
    """同步 V4 组件基础字段与状态。

    这是同步流程的“步骤 1”：\n
    - 直接调用 `api.bkdata.list_data_link` 拉取各类组件配置\n
    - 将组件的基础字段（kind/bk_biz_id/data_link_name 等）以及可解析出的关键关联字段反写到本地表\n
    - 同步组件状态（status.phase -> 本地 status）\n

    注意：此步骤只做“组件级别”的反向同步，不尝试构建 DataLink/BkBaseResultTable 关系。\n
    关系补全在步骤 2 中基于 DatabusConfig 进行推断与落库。

    Args:
        bk_tenant_id: 租户ID

    Returns:
        各组件变更计数
    """
    sync_configs = [
        {
            "kind": DataLinkKind.DATAID.value,
            "model": models.DataIdConfig,
            "namespaces": [BKBASE_NAMESPACE_BK_MONITOR, BKBASE_NAMESPACE_BK_LOG],
            "extra_parser": None,
        },
        {
            "kind": DataLinkKind.RESULTTABLE.value,
            "model": models.ResultTableConfig,
            "namespaces": [BKBASE_NAMESPACE_BK_MONITOR, BKBASE_NAMESPACE_BK_LOG],
            "extra_parser": _parse_result_table_fields,
        },
        {
            "kind": DataLinkKind.VMSTORAGEBINDING.value,
            "model": models.VMStorageBindingConfig,
            "namespaces": [BKBASE_NAMESPACE_BK_MONITOR],
            "extra_parser": _parse_vm_binding_fields,
        },
        {
            "kind": DataLinkKind.ESSTORAGEBINDING.value,
            "model": models.ESStorageBindingConfig,
            "namespaces": [BKBASE_NAMESPACE_BK_LOG],
            "extra_parser": _parse_es_binding_fields,
        },
        {
            "kind": DataLinkKind.DORISBINDING.value,
            "model": models.DorisStorageBindingConfig,
            "namespaces": [BKBASE_NAMESPACE_BK_LOG],
            "extra_parser": None,
        },
        {
            "kind": DataLinkKind.DATABUS.value,
            "model": models.DataBusConfig,
            "namespaces": [BKBASE_NAMESPACE_BK_MONITOR, BKBASE_NAMESPACE_BK_LOG],
            "extra_parser": _parse_databus_fields,
        },
        {
            "kind": DataLinkKind.CONDITIONALSINK.value,
            "model": models.ConditionalSinkConfig,
            "namespaces": [BKBASE_NAMESPACE_BK_MONITOR],
            "extra_parser": None,
        },
    ]

    updated_count_map: dict[str, int] = {}
    for config in sync_configs:
        kind = config["kind"]
        model = config["model"]
        namespaces = config["namespaces"]
        extra_parser = config["extra_parser"]
        kind_name = DataLinkKind.get_choice_value(kind)
        if not kind_name:
            logger.warning("sync_bkbase_components: unsupported kind->[%s]", kind)
            continue

        updated_count = 0
        for namespace in namespaces:
            try:
                # 以 “租户 + namespace + kind” 维度拉取 V4 组件配置列表
                response = api.bkdata.list_data_link(bk_tenant_id=bk_tenant_id, namespace=namespace, kind=kind_name)
            except Exception as e:  # pylint: disable=broad-except
                logger.error(
                    "sync_bkbase_components: list_data_link failed,tenant->[%s],kind->[%s],ns->[%s],error->[%s]",
                    bk_tenant_id,
                    kind_name,
                    namespace,
                    e,
                )
                continue

            for component in _resolve_component_list(response):
                name, component_ns, bk_biz_id, status_phase = _extract_component_common_fields(component, namespace)
                if not name or bk_biz_id is None:
                    # 没有 name / bk_biz_id 的配置无法被本地模型正确承载，直接跳过
                    logger.warning(
                        "sync_bkbase_components: missing name/bk_biz_id,tenant->[%s],kind->[%s],component->[%s]",
                        bk_tenant_id,
                        kind_name,
                        component,
                    )
                    continue

                # 本地配置表的通用字段：
                # - kind：组件类型枚举值
                # - bk_biz_id：组件所属业务（用于后续权限/归属等逻辑）
                # - data_link_name：链路聚合名（多数场景与组件 name 一致；Databus 例外）
                base_fields: dict[str, Any] = {"kind": kind, "bk_biz_id": bk_biz_id, "data_link_name": name}
                if extra_parser:
                    # 不同 kind 的组件存在额外的关键字段（例如 Databus 的 data_id_name）
                    extra_fields = extra_parser(component, component_ns, name)
                    if extra_fields is None:
                        logger.warning(
                            "sync_bkbase_components: skip due to missing base fields,tenant->[%s],kind->[%s],name->[%s]",
                            bk_tenant_id,
                            kind_name,
                            name,
                        )
                        continue
                    base_fields.update(extra_fields)

                # 组件的唯一定位：tenant + namespace + name
                lookup = {"bk_tenant_id": bk_tenant_id, "namespace": component_ns, "name": name}
                if _sync_component_record(model, lookup, base_fields, status_phase):
                    updated_count += 1

        updated_count_map[kind] = updated_count
    return updated_count_map


def _build_data_id_name_mapping(bk_tenant_id: str) -> dict[str, int]:
    """构建 data_id_name 到 bk_data_id 的映射。

    DataIdConfig.name 的命名规则在不同场景会带上固定前缀/后缀（见 `compose_bkdata_data_id_name`）。\n
    本函数从本地 DataSource 表中构造“可能的 data_id_name -> bk_data_id”映射，作为：\n
    - DataIdConfig.bk_data_id 缺失时的兜底推断来源

    Args:
        bk_tenant_id: 租户ID

    Returns:
        映射字典
    """
    mapping: dict[str, int] = {}
    data_sources = models.DataSource.objects.filter(bk_tenant_id=bk_tenant_id)
    for data_source in data_sources:
        default_name = data_link_utils.compose_bkdata_data_id_name(data_source.data_name)
        mapping[default_name] = data_source.bk_data_id
        fed_name = data_link_utils.compose_bkdata_data_id_name(
            data_source.data_name, models.DataLink.BCS_FEDERAL_SUBSET_TIME_SERIES
        )
        mapping[fed_name] = data_source.bk_data_id
    return mapping


def _infer_storage_type_and_cluster_id(
    bk_tenant_id: str, data_link_name: str, fallback_name: str | None = None
) -> tuple[str | None, int | None]:
    """根据存储绑定推断存储类型与集群ID。

    推断路径：\n
    1. 优先用 data_link_name 去绑定表（VMStorageBindingConfig/ESStorageBindingConfig/DorisStorageBindingConfig）查询\n
    2. 若查不到，且传入 fallback_name，则用组件 name 做一次兜底查询\n
       （用于兼容 data_link_name 与组件 name 不完全一致的历史/异常情况）\n
    3. 从绑定表拿到 cluster_name 后，再通过 ClusterInfo 找到 cluster_id\n

    注意：Doris 绑定场景目前仅能反查到存储类型与“某个” Doris 集群 ID（按现有数据模型兜底为 tenant 下第一条 Doris 集群）。\n
    如果后续 DorisBindingConfig 增强到可携带明确集群名，可再精确化这一推断。

    Args:
        bk_tenant_id: 租户ID
        data_link_name: 链路名称

    Returns:
        storage_type, storage_cluster_id
    """
    vm_binding = models.VMStorageBindingConfig.objects.filter(
        bk_tenant_id=bk_tenant_id, data_link_name=data_link_name
    ).first()
    if not vm_binding and fallback_name:
        vm_binding = models.VMStorageBindingConfig.objects.filter(bk_tenant_id=bk_tenant_id, name=fallback_name).first()
    if vm_binding:
        cluster = models.ClusterInfo.objects.filter(
            bk_tenant_id=bk_tenant_id,
            cluster_type=models.ClusterInfo.TYPE_VM,
            cluster_name=vm_binding.vm_cluster_name,
        ).first()
        return models.ClusterInfo.TYPE_VM, cluster.cluster_id if cluster else None

    es_binding = models.ESStorageBindingConfig.objects.filter(
        bk_tenant_id=bk_tenant_id, data_link_name=data_link_name
    ).first()
    if not es_binding and fallback_name:
        es_binding = models.ESStorageBindingConfig.objects.filter(bk_tenant_id=bk_tenant_id, name=fallback_name).first()
    if es_binding:
        cluster = models.ClusterInfo.objects.filter(
            bk_tenant_id=bk_tenant_id,
            cluster_type=models.ClusterInfo.TYPE_ES,
            cluster_name=es_binding.es_cluster_name,
        ).first()
        return models.ClusterInfo.TYPE_ES, cluster.cluster_id if cluster else None

    doris_binding = models.DorisStorageBindingConfig.objects.filter(
        bk_tenant_id=bk_tenant_id, data_link_name=data_link_name
    ).first()
    if not doris_binding and fallback_name:
        doris_binding = models.DorisStorageBindingConfig.objects.filter(
            bk_tenant_id=bk_tenant_id, name=fallback_name
        ).first()
    if doris_binding:
        cluster = models.ClusterInfo.objects.filter(
            bk_tenant_id=bk_tenant_id, cluster_type=models.ClusterInfo.TYPE_DORIS
        ).first()
        return models.ClusterInfo.TYPE_DORIS, cluster.cluster_id if cluster else None

    return None, None


def _infer_data_link_strategy(storage_type: str | None, namespace: str) -> str:
    """根据存储类型推断链路策略。

    这里的策略用于写入 DataLink.data_link_strategy：\n
    - ES/Doris 且在 bklog：视为日志链路（BK_LOG）\n
    - ES/Doris 且不在 bklog：视为事件链路（BK_STANDARD_V2_EVENT）\n
    - 其他：默认时序链路（BK_STANDARD_V2_TIME_SERIES）

    Args:
        storage_type: 存储类型
        namespace: 命名空间

    Returns:
        链路策略
    """
    if storage_type in (models.ClusterInfo.TYPE_ES, models.ClusterInfo.TYPE_DORIS):
        if namespace == BKBASE_NAMESPACE_BK_LOG:
            return models.DataLink.BK_LOG
        return models.DataLink.BK_STANDARD_V2_EVENT
    return models.DataLink.BK_STANDARD_V2_TIME_SERIES


def _sync_data_link_relationships(bk_tenant_id: str) -> dict[str, int]:
    """基于 Databus 关系补全链路与结果表记录。

        这是同步流程的“步骤 2”，核心思路是：以 DatabusConfig 为锚点补全关联关系。\n
    \n
        为什么以 DatabusConfig 为锚点：\n
        - Databus 表示 “DataId -> 下游存储/RT” 的关键连接点\n
        - 只有拿到 data_id_name 才能进一步推断 bk_data_id 与本地监控表（monitor_table_id）\n
    \n
        推断/落库链路：\n
        1) 读取 DataBusConfig（跳过 basereport：该场景由系统主动生成，不需要反向同步）\n
        2) 用 databus.data_id_name 找到 DataIdConfig，进而推断 bk_data_id\n
           - 优先 DataIdConfig.bk_data_id\n
           - 兜底：DataSource(data_name)->compose_bkdata_data_id_name->bk_data_id 映射\n
        3) 用 bk_data_id 通过 DataSourceResultTable 推断本地 `monitor_table_id`（table_id）\n
           - 监控侧同步表基本是“单指标单表”，所以取 first 作为唯一表\n
        4) 通过存储绑定（VM/ES/Doris）+ ClusterInfo 推断 storage_type/storage_cluster_id\n
        5) 确保 DataLink 存在并补齐字段（bk_data_id/table_ids/namespace/strategy）\n
        6) 找到 ResultTableConfig（优先 data_link_name，其次用 databus.name 兜底）\n
        7) 确保 BkBaseResultTable 存在并补齐关键字段：\n
           - bkbase_rt_name = ResultTableConfig.name\n
           - bkbase_data_name = DataIdConfig.name\n
           - bkbase_table_id = ResultTableConfig.table_id（计算平台 RT ID）\n
           - monitor_table_id = DataSourceResultTable.table_id（监控侧 RT 主键）\n
    \n
        更新策略：\n
        - DataLink：存在则按差异更新，不存在则创建（理论上 DatabusConfig 存在意味着 DataLink 应存在，但这里仍做兜底）\n
        - BkBaseResultTable：存在则仅补齐空值字段，避免覆盖已写入的元信息；不存在则创建\n

        Args:
            bk_tenant_id: 租户ID

        Returns:
            变更计数统计
    """
    updated_counts = {
        "data_link": 0,
        "bkbase_result_table": 0,
        "data_id": 0,
        "databus": 0,
    }

    data_id_name_map = _build_data_id_name_mapping(bk_tenant_id=bk_tenant_id)
    databus_configs = models.DataBusConfig.objects.filter(bk_tenant_id=bk_tenant_id)
    for databus in databus_configs:
        # data_link_name 是本地链路聚合的主键；Databus 若未填则退化为 name
        data_link_name = databus.data_link_name or databus.name
        if data_link_name == "basereport":
            continue

        data_id_name = databus.data_id_name
        if not data_id_name:
            logger.warning(
                "sync_data_link_relations: databus missing data_id_name,tenant->[%s],name->[%s]",
                bk_tenant_id,
                databus.name,
            )
            continue

        # 通过 databus.data_id_name 关联 DataIdConfig，作为 bk_data_id 推断的主入口
        data_id_config = models.DataIdConfig.objects.filter(
            bk_tenant_id=bk_tenant_id, namespace=databus.namespace, name=data_id_name
        ).first()
        if not data_id_config:
            logger.warning(
                "sync_data_link_relations: data_id_config not found,tenant->[%s],data_id_name->[%s]",
                bk_tenant_id,
                data_id_name,
            )
            continue

        # bk_data_id 优先取 DataIdConfig 已落库值，缺失时才用 DataSource 映射兜底
        bk_data_id = data_id_config.bk_data_id or data_id_name_map.get(data_id_name)
        if not bk_data_id:
            logger.warning(
                "sync_data_link_relations: bk_data_id missing,tenant->[%s],data_id_name->[%s]",
                bk_tenant_id,
                data_id_name,
            )
            continue

        # 反向同步：补齐 DataIdConfig 与 DatabusConfig 的 bk_data_id（便于后续链路推断）
        if data_id_config.bk_data_id != bk_data_id:
            data_id_config.bk_data_id = bk_data_id
            data_id_config.save(update_fields=["bk_data_id"])
            updated_counts["data_id"] += 1

        if databus.bk_data_id != bk_data_id:
            databus.bk_data_id = bk_data_id
            databus.save(update_fields=["bk_data_id"])
            updated_counts["databus"] += 1

        # monitor_table_id 无法直接从 V4 组件配置得到，只能通过 bk_data_id 在关联表中推断
        table_id = (
            models.DataSourceResultTable.objects.filter(bk_tenant_id=bk_tenant_id, bk_data_id=bk_data_id)
            .values_list("table_id", flat=True)
            .first()
        )
        if not table_id:
            logger.warning(
                "sync_data_link_relations: monitor table_id missing,tenant->[%s],bk_data_id->[%s]",
                bk_tenant_id,
                bk_data_id,
            )
            continue

        storage_type, storage_cluster_id = _infer_storage_type_and_cluster_id(
            bk_tenant_id=bk_tenant_id, data_link_name=data_link_name, fallback_name=databus.name
        )

        # DataLink：若存在则差异更新；若不存在则创建（兜底，避免数据缺口导致链路断裂）
        datalink = models.DataLink.objects.filter(bk_tenant_id=bk_tenant_id, data_link_name=data_link_name).first()
        if datalink:
            update_fields: list[str] = []
            if datalink.bk_data_id != bk_data_id:
                datalink.bk_data_id = bk_data_id
                update_fields.append("bk_data_id")
            if datalink.table_ids != [table_id]:
                datalink.table_ids = [table_id]
                update_fields.append("table_ids")
            if datalink.namespace != databus.namespace:
                datalink.namespace = databus.namespace
                update_fields.append("namespace")
            if update_fields:
                datalink.save(update_fields=update_fields)
                updated_counts["data_link"] += 1
        else:
            strategy = _infer_data_link_strategy(storage_type, databus.namespace)
            models.DataLink.objects.create(
                bk_tenant_id=bk_tenant_id,
                data_link_name=data_link_name,
                namespace=databus.namespace,
                data_link_strategy=strategy,
                bk_data_id=bk_data_id,
                table_ids=[table_id],
            )
            updated_counts["data_link"] += 1

        # ResultTableConfig：优先按 data_link_name 找；找不到时再用 databus.name 兜底（兼容历史数据）
        result_table_config = models.ResultTableConfig.objects.filter(
            bk_tenant_id=bk_tenant_id, data_link_name=data_link_name
        ).first()
        if not result_table_config:
            result_table_config = models.ResultTableConfig.objects.filter(
                bk_tenant_id=bk_tenant_id, name=databus.name
            ).first()
        if not result_table_config:
            logger.warning(
                "sync_data_link_relations: result_table_config not found,tenant->[%s],data_link_name->[%s]",
                bk_tenant_id,
                data_link_name,
            )
            continue

        if result_table_config.data_link_name != data_link_name:
            result_table_config.data_link_name = data_link_name
            result_table_config.save(update_fields=["data_link_name"])

        # BkBaseResultTable 字段定义说明：
        # - bkbase_rt_name：对应 ResultTableConfig.name（组件名）
        # - bkbase_data_name：对应 DataIdConfig.name（组件名）
        # - bkbase_table_id：对应 ResultTableConfig.table_id（计算平台 RT ID）
        # - monitor_table_id：通过 DataSourceResultTable 推断出来的监控侧 RT 主键
        bkbase_rt_defaults = {
            "bkbase_rt_name": result_table_config.name,
            "bkbase_data_name": data_id_config.name,
            "bkbase_table_id": result_table_config.table_id,
            "monitor_table_id": table_id,
            "storage_type": storage_type or models.ClusterInfo.TYPE_VM,
            "storage_cluster_id": storage_cluster_id,
            "bk_tenant_id": bk_tenant_id,
        }
        bkbase_rt = models.BkBaseResultTable.objects.filter(data_link_name=data_link_name).first()
        if not bkbase_rt:
            models.BkBaseResultTable.objects.create(data_link_name=data_link_name, **bkbase_rt_defaults)
            updated_counts["bkbase_result_table"] += 1
        else:
            # 仅“补齐空值”：避免覆盖其他流程（例如 apply_data_link/sync_metadata）已写入的元信息
            update_fields = []
            for field, value in bkbase_rt_defaults.items():
                if value is None:
                    continue
                if getattr(bkbase_rt, field) in (None, "", 0) and getattr(bkbase_rt, field) != value:
                    setattr(bkbase_rt, field, value)
                    update_fields.append(field)
            if update_fields:
                bkbase_rt.save(update_fields=update_fields)
                updated_counts["bkbase_result_table"] += 1

    return updated_counts


@share_lock(ttl=3600, identify="metadata_sync_bkbase_v4_datalink_components")
def sync_bkbase_v4_datalink_components():
    """定时同步 V4 链路组件与链路关系。

    调度入口：\n
    - 遍历全部租户（`bk_login.list_tenant`）\n
    - 每个租户执行两步：\n
      1) `_sync_bkbase_components_base_fields`：反向同步组件基础字段与状态\n
      2) `_sync_data_link_relationships`：基于 Databus 补全 DataLink 与 BkBaseResultTable\n

    该任务加了 share_lock，避免多实例并发跑导致重复写入与竞争。
    """
    logger.info("sync_bkbase_v4_datalink_components: start")
    start_time = time.time()
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="sync_bkbase_v4_datalink_components", status=TASK_STARTED, process_target=None
    ).inc()

    updated_summary: dict[str, int] = {}
    for tenant in api.bk_login.list_tenant():
        tenant_id = tenant.get("id")
        if not tenant_id:
            continue

        # Step 1：同步组件基础字段/状态
        base_updates = _sync_bkbase_components_base_fields(bk_tenant_id=tenant_id)
        # Step 2：基于 Databus 补全链路关系与结果表
        relation_updates = _sync_data_link_relationships(bk_tenant_id=tenant_id)
        for key, value in {**base_updates, **relation_updates}.items():
            updated_summary[key] = updated_summary.get(key, 0) + value

    cost_time = time.time() - start_time
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="sync_bkbase_v4_datalink_components", status=TASK_FINISHED_SUCCESS, process_target=None
    ).inc()
    metrics.METADATA_CRON_TASK_COST_SECONDS.labels(
        task_name="sync_bkbase_v4_datalink_components", process_target=None
    ).observe(cost_time)
    metrics.report_all()
    logger.info(
        "sync_bkbase_v4_datalink_components: finished,cost_time->[%s],updated_summary->[%s]",
        cost_time,
        updated_summary,
    )
