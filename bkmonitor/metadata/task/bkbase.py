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
import json
import logging
import re
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, cast

import redis
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from alarm_backends.core.lock.service_lock import share_lock
from alarm_backends.service.scheduler.app import app
from constants.common import DEFAULT_TENANT_ID
from core.drf_resource import api
from core.prometheus import metrics
from metadata import models
from metadata.config import KAFKA_SASL_PROTOCOL
from metadata.models import BkBaseResultTable, ClusterInfo
from metadata.models.constants import DataIdCreatedFromSystem
from metadata.models.data_link.constants import (
    BKBASE_NAMESPACE_BK_LOG,
    BKBASE_NAMESPACE_BK_MONITOR,
    DataLinkKind,
    DataLinkResourceStatus,
)
from metadata.models.data_link.data_link_configs import (
    COMPONENT_CLASS_MAP,
    ClusterConfig,
    ResultTableConfig,
    SurrealDBBindingConfig,
)
from metadata.models.space.constants import SpaceStatus, SpaceTypes
from metadata.service.surrealdb_materialized_view import reconcile_materialized_views
from metadata.models.vm.utils import report_metadata_data_link_status_info
from metadata.service.sync_metadata import sync_kafka_metadata, sync_vm_metadata
from metadata.task.constants import BKBASE_V4_KIND_STORAGE_CONFIGS
from metadata.task.utils import chunk_list
from metadata.tools.constants import TASK_FINISHED_SUCCESS, TASK_STARTED
from metadata.tools.redis_lock import DistributedLock
from metadata.utils.bkbase import sync_bkbase_result_table_meta
from metadata.utils.redis_tools import RedisTools, bkbase_redis_client

logger = logging.getLogger("metadata")


DEFAULT_VM_EXPIRES_MS = 24 * 3600 * 90 * 1000
PUBSUB_POLL_TIMEOUT_SECONDS = 1.0


@app.task(ignore_result=True, queue="celery_metadata_task_worker")
def sync_bkbase_v4_metadata(key, skip_types: list[str] | None = None):
    """
    同步计算平台元数据信息至Metadata
    Redis中的数据格式
    redis_key
        kafka: {}
        vm: {rt1:{},rt2:{},rt3:{}}
        es: {rt1:[],rt2:[],rt3:[]}
    @param key: 计算平台对应的DataBusKey
    @param skip_types: 跳过同步的类型,默认跳过es类型
    """
    logger.info("sync_bkbase_v4_metadata: try to sync bkbase metadata,key->[%s]", key)
    start_time = time.time()
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="sync_bkbase_v4_metadata", status=TASK_STARTED, process_target=None
    ).inc()

    # 默认跳过es类型
    if skip_types is None:
        skip_types = []

    bkbase_redis = bkbase_redis_client()
    if not bkbase_redis:
        logger.warning("sync_bkbase_v4_metadata: bkbase redis config is not set.")
        return

    bk_base_data_id = key.split(":")[-1]  # 提取 bk_base_data_id

    try:
        vm_record = models.AccessVMRecord.objects.filter(bk_base_data_id=bk_base_data_id)
        if vm_record.exists():  # 若接入VM记录存在,说明是指标链路,常规流程,通过table_id获取监控平台DataId
            table_id = vm_record.first().result_table_id
            # 兼容 DataId--RT 一对多的边缘场景
            bk_data_id = models.DataSourceResultTable.objects.filter(table_id=table_id).first().bk_data_id
        else:  # 否则,说明是日志链路,日志链路中,无论是纯V4还是V3->V4,DataId是一样的
            bk_data_id = bk_base_data_id
    except Exception as e:  # pylint: disable=broad-except
        logger.error("sync_bkbase_v4_metadata: failed to get bk_data_id and table_id for key->[%s],error->[%s]", key, e)
        return

    bkbase_redis_data = bkbase_redis.hgetall(key)
    bkbase_metadata_dict = {
        key.decode("utf-8"): json.loads(value.decode("utf-8")) for key, value in bkbase_redis_data.items()
    }
    logger.info("sync_bkbase_v4_metadata: got bk_data_id->[%s],bkbase_metadata->[%s]", bk_data_id, bkbase_metadata_dict)

    try:
        ds = models.DataSource.objects.get(bk_data_id=bk_data_id)
        table_id = models.DataSourceResultTable.objects.get(bk_data_id=bk_data_id).table_id
        bk_tenant_id: str = ds.bk_tenant_id
    except models.DataSource.DoesNotExist:
        logger.error("sync_bkbase_v4_metadata: DataSource->[%s] does not exist", bk_data_id)
        return
    except models.DataSourceResultTable.DoesNotExist:
        logger.error("sync_bkbase_v4_metadata: DataSourceResultTable for bk_data_id->[%s] does not exist", bk_data_id)
        return

    if ds.created_from != DataIdCreatedFromSystem.BKDATA.value:
        logger.error("sync_bkbase_v4_metadata: bk_data_id->[%s] does not belong to bkbase v4", bk_data_id)
        return

    # 处理 Kafka 信息
    kafka_info = bkbase_metadata_dict.get("kafka")
    if kafka_info and "kafka" not in skip_types:
        with transaction.atomic():  # 单独事务
            logger.info(
                "sync_bkbase_v4_metadata: got kafka_info->[%s],bk_data_id->[%s],try to sync kafka info",
                kafka_info,
                bk_data_id,
            )
            sync_kafka_metadata(bk_tenant_id=bk_tenant_id, kafka_info=kafka_info, ds=ds, bk_data_id=bk_data_id)
            logger.info("sync_bkbase_v4_metadata: sync kafka info for bk_data_id->[%s] successfully", bk_data_id)

    # 处理 VM 信息
    vm_info = bkbase_metadata_dict.get("vm")
    if vm_info and "vm" not in skip_types:
        with transaction.atomic():  # 单独事务
            logger.info(
                "sync_bkbase_v4_metadata: got vm_info->[%s],bk_data_id->[%s],try to sync vm info", vm_info, bk_data_id
            )
            sync_vm_metadata(bk_tenant_id=bk_tenant_id, vm_info=vm_info)
            logger.info("sync_bkbase_v4_metadata: sync vm info for bk_data_id->[%s] successfully", bk_data_id)

    cost_time = time.time() - start_time
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="sync_bkbase_v4_metadata", status=TASK_FINISHED_SUCCESS, process_target=None
    ).inc()
    metrics.METADATA_CRON_TASK_COST_SECONDS.labels(task_name="sync_bkbase_metadata_all", process_target=None).observe(
        cost_time
    )
    logger.info(
        "sync_bkbase_v4_metadata: sync bkbase metadata for bk_data_id->[%s] successfully,cost->[%s]",
        bk_data_id,
        cost_time,
    )


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

    # 使用单调时钟控制运行时长，避免 pubsub 阻塞时无法及时退出。
    end_time = time.monotonic() + runtime_limit

    while time.monotonic() < end_time:  # 运行时间控制
        pubsub = None
        try:
            # 初始化 pubsub
            pubsub = redis_conn.pubsub()
            pubsub.psubscribe(keyspace_channel)  # 监听特定模式的键事件
            logger.info("watch_bkbase_meta_redis: Subscribed to Redis channel -> [%s]", keyspace_channel)

            # 轮询消息，避免 listen() 在无消息时无限阻塞，导致任务无法按 runtime_limit 退出。
            while time.monotonic() < end_time:
                remaining_seconds = max(end_time - time.monotonic(), 0)
                message = pubsub.get_message(timeout=min(PUBSUB_POLL_TIMEOUT_SECONDS, remaining_seconds))

                if message is None:
                    continue

                if time.monotonic() >= end_time:  # 超出运行时间，退出监听
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


def _normalize_bkbase_doris_owner(cluster: models.ClusterInfo, bk_biz_id: Any) -> list[str]:
    """根据 BKBase 的明确归属信息修正历史业务 Doris 集群，保留无归属信息的公共集群。"""
    if (
        cluster.cluster_type != models.ClusterInfo.TYPE_DORIS
        or bk_biz_id in (None, "")
        or cluster.registered_system
        not in {
            models.ClusterInfo.DEFAULT_REGISTERED_SYSTEM,
            models.ClusterInfo.BKDATA_REGISTERED_SYSTEM,
        }
    ):
        return []

    try:
        custom_option = json.loads(cluster.custom_option or "{}")
    except (TypeError, json.JSONDecodeError):
        logger.warning(
            "sync_bkbase_cluster_info: skip normalizing Doris cluster %s because custom_option is invalid JSON",
            cluster.cluster_name,
        )
        return []

    if not isinstance(custom_option, dict):
        logger.warning(
            "sync_bkbase_cluster_info: skip normalizing Doris cluster %s because custom_option is not an object",
            cluster.cluster_name,
        )
        return []

    update_fields = []
    if custom_option.get("bk_biz_id") != bk_biz_id:
        custom_option["bk_biz_id"] = bk_biz_id
        cluster.custom_option = json.dumps(custom_option)
        update_fields.append("custom_option")

    if cluster.registered_system == models.ClusterInfo.DEFAULT_REGISTERED_SYSTEM:
        cluster.registered_system = models.ClusterInfo.BKDATA_REGISTERED_SYSTEM
        update_fields.append("registered_system")

    return update_fields


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
    bk_biz_id = _get_attr_by_path(cluster_spec, field_mappings.get("bk_biz_id", ""))
    schema = _get_attr_by_path(cluster_spec, field_mappings.get("schema", ""))

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
    custom_option = ""

    if cluster_type == models.ClusterInfo.TYPE_VM:
        # 如果是VictoriaMetrics集群，需要获取过期时间和所属业务ID
        # 记录过期时间，单位为秒
        default_settings["retention_time"] = (cluster_spec.get("expiresMs") or DEFAULT_VM_EXPIRES_MS) // 1000
        # 记录集群所属业务ID，只有业务独立集群才会有对应字段，默认为None
        default_settings["bk_biz_id"] = bk_biz_id
    elif cluster_type == models.ClusterInfo.TYPE_DORIS:
        # 记录集群所属业务ID，只有业务独立集群才会有对应字段，默认为None
        default_settings["bk_biz_id"] = bk_biz_id
        if bk_biz_id is not None:
            custom_option = json.dumps({"bk_biz_id": bk_biz_id})
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
        "security_protocol": security_protocol,
        # "version": version,
        # "gse_stream_to_id": stream_to_id,
    }
    if schema:
        need_update_fields["schema"] = schema

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
            forced_update_fields = _normalize_bkbase_doris_owner(cluster, bk_biz_id)
            if forced_update_fields:
                is_updated = True
                update_fields.extend(forced_update_fields)

            for field, value in need_update_fields.items():
                if value is not None and getattr(cluster, field) != value:
                    setattr(cluster, field, value)
                    is_updated = True
                    update_fields.append(field)

            if custom_option and not cluster.custom_option:
                cluster.custom_option = custom_option
                is_updated = True
                update_fields.append("custom_option")

            # 如果集群未被标记为已注册到bkbase平台，则标记为已注册
            if not cluster.registered_to_bkbase:
                cluster.registered_to_bkbase = True
                is_updated = True
                update_fields.append("registered_to_bkbase")

            # 如果字段有更新，则保存模型
            if is_updated:
                save_fields = update_fields if update else forced_update_fields
                if save_fields:
                    logger.info(
                        "sync_bkbase_cluster_info: updated %s cluster: %s, fields: %s",
                        cluster_type,
                        cluster_name,
                        save_fields,
                    )
                    cluster.save(update_fields=save_fields)
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
                custom_option=custom_option,
                default_settings=default_settings,
                registered_system=models.ClusterInfo.BKDATA_REGISTERED_SYSTEM,
                registered_to_bkbase=True,
                version=version,
                schema=schema or None,
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


ComponentBatchKey = tuple[str, str, str]
DataLinkStatusKey = tuple[str, str]
ParsedComponentConfig = tuple[dict[str, Any], dict[str, Any]]
STORAGE_BINDING_KIND_MAP = {
    DataLinkKind.ESSTORAGEBINDING.value: DataLinkKind.ELASTICSEARCH.value,
    DataLinkKind.DORISBINDING.value: DataLinkKind.DORIS.value,
    DataLinkKind.VMSTORAGEBINDING.value: DataLinkKind.VMSTORAGE.value,
}
STORAGE_BINDING_CLUSTER_TYPE_MAP = {
    DataLinkKind.ESSTORAGEBINDING.value: ClusterInfo.TYPE_ES,
    DataLinkKind.DORISBINDING.value: ClusterInfo.TYPE_DORIS,
    DataLinkKind.VMSTORAGEBINDING.value: ClusterInfo.TYPE_VM,
}
DATA_LINK_DISCOVERY_NAMESPACES = (BKBASE_NAMESPACE_BK_MONITOR, BKBASE_NAMESPACE_BK_LOG)
STORAGE_BINDING_NAMESPACES = DATA_LINK_DISCOVERY_NAMESPACES
STORAGE_BINDING_FILTER_THRESHOLD = 1000


@dataclass
class DataLinkRefreshStats:
    created_count: int = 0
    updated_count: int = 0
    terminated_count: int = 0
    untrusted_batch_count: int = 0


def _normalize_data_link_tenant_id(bk_tenant_id: str | None) -> str:
    return bk_tenant_id or DEFAULT_TENANT_ID


def _parse_list_data_link_statuses(configs: Any) -> dict[str, str] | None:
    """解析 list_data_link 返回值；无法证明列表完整时返回 None。"""
    if not isinstance(configs, list) or not configs:
        return None

    statuses: dict[str, str] = {}
    for config in configs:
        if not isinstance(config, dict):
            return None
        metadata = config.get("metadata")
        status = config.get("status")
        if not isinstance(metadata, dict) or not isinstance(status, dict):
            return None
        name = metadata.get("name")
        phase = status.get("phase")
        if not isinstance(name, str) or not name or not isinstance(phase, str) or not phase or name in statuses:
            return None
        statuses[name] = phase
    return statuses


def _get_annotation_value(annotations: dict[str, Any], key: str) -> Any:
    """兼容 BKBase annotation key 的大小写/下划线差异。"""
    normalized_key = key.replace("_", "").lower()
    for annotation_key, value in annotations.items():
        if annotation_key.replace("_", "").lower() == normalized_key:
            return value
    return None


def _get_bkbase_components_config(
    bk_tenant_id: str,
    kind: str,
    namespace: str,
    config: dict[str, Any],
    result_table_ids: dict[str, str] | None = None,
) -> ParsedComponentConfig:
    """将 BKBase 组件配置转换为本地模型的基础字段和扩展字段。"""
    metadata = config["metadata"]
    annotations: dict[str, Any] = metadata.get("annotations", {})
    labels: dict[str, Any] = metadata.get("labels", {})
    bk_biz_id = int(labels.get("bk_biz_id", 0))
    name: str = metadata["name"]
    status: str = config["status"]["phase"]
    spec: dict[str, Any] = config["spec"]

    base_config: dict[str, Any] = {
        "data_link_name": "",
        "bk_tenant_id": bk_tenant_id,
        "namespace": namespace,
        "name": name,
        "bk_biz_id": bk_biz_id,
    }
    extra_config: dict[str, Any] = {"status": status}

    def _get_result_table_id(rt_name: str) -> str:
        if result_table_ids is not None:
            return result_table_ids.get(rt_name, "")
        return (
            ResultTableConfig.objects.filter(bk_tenant_id=bk_tenant_id, namespace=namespace, name=rt_name)
            .values_list("table_id", flat=True)
            .first()
            or ""
        )

    match kind:
        case DataLinkKind.DATAID.value:
            extra_config["bk_data_id"] = int(annotations.get("dataId") or annotations.get("DataId") or 0)
        case DataLinkKind.RESULTTABLE.value:
            extra_config["bkbase_table_id"] = _get_annotation_value(annotations, "ResultTableId") or ""
            if not extra_config["bkbase_table_id"]:
                extra_config["bkbase_table_id"] = f"{spec['bizId']}_{name}"
            extra_config["data_type"] = spec["dataType"]
        case DataLinkKind.VMSTORAGEBINDING.value:
            extra_config["vm_cluster_name"] = spec["storage"]["name"]
            extra_config["bkbase_result_table_name"] = spec["data"]["name"]
            extra_config["table_id"] = _get_result_table_id(spec["data"]["name"])
        case DataLinkKind.ESSTORAGEBINDING.value:
            extra_config["es_cluster_name"] = spec["storage"]["name"]
            extra_config["bkbase_result_table_name"] = spec["data"]["name"]
        case DataLinkKind.DORISBINDING.value:
            extra_config["doris_cluster_name"] = spec["storage"]["name"]
            extra_config["bkbase_result_table_name"] = spec["data"]["name"]
        case DataLinkKind.SURREALDBBINDING.value:
            extra_config["surrealdb_cluster_name"] = spec["storage"]["name"]
            extra_config["bkbase_result_table_name"] = spec["data"]["name"]
            extra_config["table_id"] = _get_result_table_id(spec["data"]["name"])
            extra_config["table_type"] = spec.get("table_type", "temporary")
            extra_config["vertices"] = spec.get("vertices", [])
            extra_config["relations"] = spec.get("relations", [])
        case DataLinkKind.DATABUS.value:
            extra_config["data_id_name"] = spec["sources"][0]["name"]
            extra_config["sink_names"] = [f"{sink['kind']}:{sink['name']}" for sink in spec["sinks"]]
            extra_config["consumer_group"] = spec.get("consumerGroup", "")
        case DataLinkKind.BASEREPORTSINK.value:
            vm_storage_binding_names = []
            for mapping in spec.get("mappings", []):
                for sink in mapping.get("sinks", []):
                    if sink.get("kind") == DataLinkKind.VMSTORAGEBINDING.value and sink.get("name"):
                        vm_storage_binding_names.append(sink["name"])
            extra_config["vm_storage_binding_names"] = list(dict.fromkeys(vm_storage_binding_names))
    return base_config, extra_config


def _should_update_bkbase_component_field(kind: str, field: str, value: Any) -> bool:
    if value:
        return True
    return kind == DataLinkKind.SURREALDBBINDING.value and field in {"vertices", "relations"} and value == []


def _parse_bkbase_component_configs(
    configs: Any, *, bk_tenant_id: str, namespace: str, kind: str
) -> dict[str, ParsedComponentConfig] | None:
    """完整解析可信的非空组件列表；任一配置不完整时拒绝整个批次。"""
    remote_statuses = _parse_list_data_link_statuses(configs)
    if remote_statuses is None:
        return None

    result_table_ids = None
    if kind in {DataLinkKind.VMSTORAGEBINDING.value, DataLinkKind.SURREALDBBINDING.value}:
        result_table_ids = dict(
            ResultTableConfig.objects.filter(bk_tenant_id=bk_tenant_id, namespace=namespace).values_list(
                "name", "table_id"
            )
        )

    parsed_configs: dict[str, ParsedComponentConfig] = {}
    try:
        for config in configs:
            base_config, extra_config = _get_bkbase_components_config(
                bk_tenant_id=bk_tenant_id,
                kind=kind,
                namespace=namespace,
                config=config,
                result_table_ids=result_table_ids,
            )
            parsed_configs[base_config["name"]] = (base_config, extra_config)
    except (AttributeError, KeyError, TypeError, ValueError):
        return None
    return parsed_configs


def _parse_storage_binding_reference(
    config: Any,
    *,
    bk_tenant_id: str,
    namespace: str,
    binding_kind: str,
) -> tuple[dict[str, Any], list[str]]:
    """解析 Storage Binding 引用，并返回基础检查结果和配置问题。"""
    storage_kind = STORAGE_BINDING_KIND_MAP.get(binding_kind, "")
    problems: list[str] = []

    if not isinstance(config, dict):
        config = {}
        problems.append("invalid_config")

    metadata = config.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
        problems.append("invalid_config")

    name = metadata.get("name")
    if not isinstance(name, str) or not name:
        name = ""
        problems.append("invalid_config")

    labels = metadata.get("labels", {})
    if not isinstance(labels, dict):
        labels = {}
        problems.append("invalid_config")

    annotations = metadata.get("annotations", {})
    if not isinstance(annotations, dict):
        annotations = {}
        problems.append("invalid_config")

    spec = config.get("spec")
    if not isinstance(spec, dict):
        spec = {}
        problems.append("invalid_config")

    storage = spec.get("storage")
    if not isinstance(storage, dict):
        storage = {}
        problems.append("invalid_config")

    storage_name = storage.get("name")
    if not isinstance(storage_name, str) or not storage_name:
        storage_name = ""
        problems.append("storage_name_missing")

    storage_namespace = storage.get("namespace") or namespace
    if not isinstance(storage_namespace, str) or not storage_namespace:
        storage_namespace = namespace
        problems.append("invalid_config")

    storage_tenant = storage.get("tenant")
    if storage_tenant is not None and not isinstance(storage_tenant, str):
        storage_tenant = None
        problems.append("invalid_config")

    expected_reference = ""
    if storage_kind and storage_name:
        reference_parts = [storage_kind]
        if storage_tenant and storage_tenant != "default":
            reference_parts.append(storage_tenant)
        reference_parts.extend([storage_namespace, storage_name])
        expected_reference = "/".join(reference_parts)

    issue = {
        "bk_tenant_id": bk_tenant_id,
        "namespace": namespace,
        "binding_kind": binding_kind,
        "name": name,
        "storage_kind": storage_kind,
        "storage_name": storage_name,
        "expected_reference": expected_reference,
        "related_res_asset": labels.get("related_res_asset"),
        "index1": annotations.get("index1"),
    }
    return issue, problems


def _check_storage_binding_reference(
    config: Any,
    *,
    bk_tenant_id: str,
    namespace: str,
    binding_kind: str,
) -> dict[str, Any] | None:
    """检查 Storage Binding 的存储资源引用是否与 spec.storage 一致。"""
    issue, problems = _parse_storage_binding_reference(
        config,
        bk_tenant_id=bk_tenant_id,
        namespace=namespace,
        binding_kind=binding_kind,
    )
    storage_name = issue["storage_name"]
    index1 = issue["index1"]
    if index1 and (not isinstance(index1, str) or index1.rsplit("/", 1)[-1] != storage_name):
        problems.append("index1_mismatch")

    related_res_asset = issue["related_res_asset"]
    if related_res_asset and (
        not isinstance(related_res_asset, str) or related_res_asset.rsplit("/", 1)[-1] != storage_name
    ):
        problems.append("related_res_asset_mismatch")

    if not problems:
        return None

    issue["problems"] = list(dict.fromkeys(problems))
    return issue


def _check_storage_binding_references(
    configs: list[Any],
    *,
    bk_tenant_id: str,
    namespace: str,
    binding_kind: str,
) -> list[dict[str, Any]]:
    """批量检查同租户、命名空间和类型下的 Storage Binding。"""
    issues = []
    for config in configs:
        issue = _check_storage_binding_reference(
            config,
            bk_tenant_id=bk_tenant_id,
            namespace=namespace,
            binding_kind=binding_kind,
        )
        if issue is not None:
            issues.append(issue)
    return issues


def _merge_storage_binding_issue(
    issues_by_key: dict[tuple[str, str, str], dict[str, Any]],
    unkeyed_issues: list[dict[str, Any]],
    issue: dict[str, Any],
) -> None:
    """按 namespace、kind、name 合并同一 Binding 的远端和本地检查结果。"""
    name = issue.get("name")
    if not name:
        unkeyed_issues.append(issue)
        return

    key = (issue["namespace"], issue["binding_kind"], name)
    existing = issues_by_key.get(key)
    if existing is None:
        issues_by_key[key] = issue
        return

    existing["problems"] = list(dict.fromkeys([*existing.get("problems", []), *issue.get("problems", [])]))
    for field, value in issue.items():
        if field != "problems":
            existing[field] = value


def _filter_queryset_by_keys(queryset, field: str, keys: set[str]):
    """键数量较小时在 DB 侧过滤，过大时保持单次 tenant 范围扫描。"""
    if len(keys) <= STORAGE_BINDING_FILTER_THRESHOLD:
        return queryset.filter(**{f"{field}__in": keys})
    return queryset


def _load_local_binding_table_ids(
    *,
    bk_tenant_id: str,
    remote_configs_by_batch: dict[tuple[str, str], list[Any]],
) -> tuple[
    dict[tuple[str, str, str], set[str]],
    dict[tuple[str, str, str], dict[str, Any]],
]:
    """批量加载远端 Binding 对应的本地 Binding table_id。"""
    table_ids_by_key: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    remote_config_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}

    for (namespace, binding_kind), configs in remote_configs_by_batch.items():
        for config in configs:
            issue, _ = _parse_storage_binding_reference(
                config,
                bk_tenant_id=bk_tenant_id,
                namespace=namespace,
                binding_kind=binding_kind,
            )
            if issue["name"] and issue["storage_name"]:
                remote_config_by_key[(namespace, binding_kind, issue["name"])] = config

    for binding_kind, component_class in ((kind, COMPONENT_CLASS_MAP[kind]) for kind in STORAGE_BINDING_KIND_MAP):
        remote_keys = {key for key in remote_config_by_key if key[1] == binding_kind}
        if not remote_keys:
            continue

        remote_names = {key[2] for key in remote_keys}
        queryset = component_class.objects.filter(
            bk_tenant_id=bk_tenant_id,
            namespace__in=STORAGE_BINDING_NAMESPACES,
        )
        queryset = _filter_queryset_by_keys(queryset, "name", remote_names)
        for row in queryset.values("namespace", "name", "table_id").iterator(chunk_size=1000):
            key = (row["namespace"], binding_kind, row["name"])
            if key in remote_keys:
                table_ids_by_key[key].add(row["table_id"] or "")

    return table_ids_by_key, remote_config_by_key


def _load_storage_cluster_ids(
    *,
    bk_tenant_id: str,
    binding_kind: str,
    table_ids: set[str],
) -> tuple[dict[str, set[int]], dict[str, set[str]]]:
    """批量加载 table_id 对应的本地集群 ID；第二个返回值是 Doris 表对应的缺失 origin table_id。"""
    cluster_ids_by_table_id: dict[str, set[int]] = defaultdict(set)
    missing_origin_table_ids: dict[str, set[str]] = defaultdict(set)
    if not table_ids:
        return cluster_ids_by_table_id, missing_origin_table_ids

    if binding_kind == DataLinkKind.ESSTORAGEBINDING.value:
        queryset = models.ESStorage.objects.filter(bk_tenant_id=bk_tenant_id)
        queryset = _filter_queryset_by_keys(queryset, "table_id", table_ids)
        for row in queryset.values("table_id", "storage_cluster_id").iterator(chunk_size=1000):
            if row["table_id"] not in table_ids:
                continue
            cluster_ids_by_table_id.setdefault(row["table_id"], set())
            if row["storage_cluster_id"] is not None:
                cluster_ids_by_table_id[row["table_id"]].add(row["storage_cluster_id"])
        return cluster_ids_by_table_id, missing_origin_table_ids

    if binding_kind == DataLinkKind.VMSTORAGEBINDING.value:
        queryset = models.AccessVMRecord.objects.filter(bk_tenant_id=bk_tenant_id)
        queryset = _filter_queryset_by_keys(queryset, "result_table_id", table_ids)
        for row in queryset.values("result_table_id", "vm_cluster_id", "storage_cluster_id").iterator(chunk_size=1000):
            if row["result_table_id"] not in table_ids:
                continue
            cluster_ids_by_table_id.setdefault(row["result_table_id"], set())
            cluster_id = row["vm_cluster_id"] or row["storage_cluster_id"]
            if cluster_id is not None:
                cluster_ids_by_table_id[row["result_table_id"]].add(cluster_id)
        return cluster_ids_by_table_id, missing_origin_table_ids

    rows_by_table_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    doris_queryset = models.DorisStorage.objects.filter(bk_tenant_id=bk_tenant_id)
    if len(table_ids) <= STORAGE_BINDING_FILTER_THRESHOLD:
        # 小批次先读取目标表，再一次性补齐虚拟表引用的 origin；查询次数与 Binding 数量无关。
        for row in (
            doris_queryset.filter(table_id__in=table_ids)
            .values("table_id", "origin_table_id", "storage_cluster_id")
            .iterator(chunk_size=1000)
        ):
            rows_by_table_id[row["table_id"]].append(row)

        origin_table_ids = {
            row["origin_table_id"]
            for rows in rows_by_table_id.values()
            for row in rows
            if row["origin_table_id"] and row["origin_table_id"] not in rows_by_table_id
        }
        if origin_table_ids:
            for row in (
                doris_queryset.filter(table_id__in=origin_table_ids)
                .values("table_id", "origin_table_id", "storage_cluster_id")
                .iterator(chunk_size=1000)
            ):
                rows_by_table_id[row["table_id"]].append(row)
    else:
        # 大批次避免对无索引关联字段分块查询，改为单次租户范围流式扫描。
        for row in doris_queryset.values("table_id", "origin_table_id", "storage_cluster_id").iterator(chunk_size=1000):
            rows_by_table_id[row["table_id"]].append(row)

    for table_id in table_ids:
        for row in rows_by_table_id.get(table_id, []):
            effective_table_id = row["origin_table_id"] or table_id
            effective_rows = rows_by_table_id.get(effective_table_id, [])
            if row["origin_table_id"] and not effective_rows:
                missing_origin_table_ids[table_id].add(row["origin_table_id"])
                continue
            cluster_ids_by_table_id.setdefault(table_id, set())
            for effective_row in effective_rows:
                if effective_row["storage_cluster_id"] is not None:
                    cluster_ids_by_table_id[table_id].add(effective_row["storage_cluster_id"])
    return cluster_ids_by_table_id, missing_origin_table_ids


def _normalize_cluster_domain(domain_name: Any) -> str:
    return domain_name.strip().lower() if isinstance(domain_name, str) else ""


def _is_ignored_vm_cmdb_binding(binding_name: str, table_id: str) -> bool:
    """VM CMDB 派生表不参与本地存储关联检查。"""
    return binding_name.endswith("_cmdb") or table_id.endswith("_cmdb")


def _check_local_storage_binding_references(
    *,
    bk_tenant_id: str,
    remote_configs_by_batch: dict[tuple[str, str], list[Any]],
) -> list[dict[str, Any]]:
    """批量检查远端 Binding 与本地 Storage/AccessVMRecord 最终指向的集群是否一致。"""
    table_ids_by_key, remote_config_by_key = _load_local_binding_table_ids(
        bk_tenant_id=bk_tenant_id,
        remote_configs_by_batch=remote_configs_by_batch,
    )
    local_issues: list[dict[str, Any]] = []
    issued_keys: set[tuple[str, str, str]] = set()
    resolved_keys: dict[tuple[str, str, str], str] = {}

    def add_issue(key: tuple[str, str, str], problems: list[str], **details) -> None:
        namespace, binding_kind, _ = key
        issue, _ = _parse_storage_binding_reference(
            remote_config_by_key[key],
            bk_tenant_id=bk_tenant_id,
            namespace=namespace,
            binding_kind=binding_kind,
        )
        issue.update(details)
        issue["problems"] = problems
        local_issues.append(issue)
        issued_keys.add(key)

    for key in remote_config_by_key:
        table_ids = table_ids_by_key.get(key)
        if table_ids is None:
            continue
        non_empty_table_ids = {table_id for table_id in table_ids if table_id}
        if not non_empty_table_ids:
            add_issue(key, ["local_table_id_missing"], table_ids=[])
            continue
        if len(non_empty_table_ids) > 1:
            add_issue(key, ["local_binding_ambiguous"], table_ids=sorted(non_empty_table_ids))
            continue
        table_id = next(iter(non_empty_table_ids))
        if key[1] == DataLinkKind.VMSTORAGEBINDING.value and _is_ignored_vm_cmdb_binding(key[2], table_id):
            continue
        resolved_keys[key] = table_id

    cluster_ids_by_kind_and_table: dict[tuple[str, str], set[int]] = {}
    for binding_kind in STORAGE_BINDING_KIND_MAP:
        kind_table_ids = {table_id for key, table_id in resolved_keys.items() if key[1] == binding_kind}
        if not kind_table_ids:
            continue
        cluster_ids_by_table_id, missing_origins_by_table_id = _load_storage_cluster_ids(
            bk_tenant_id=bk_tenant_id,
            binding_kind=binding_kind,
            table_ids=kind_table_ids,
        )
        for table_id, cluster_ids in cluster_ids_by_table_id.items():
            cluster_ids_by_kind_and_table[(binding_kind, table_id)] = cluster_ids
        if binding_kind == DataLinkKind.DORISBINDING.value and missing_origins_by_table_id:
            for key, table_id in resolved_keys.items():
                missing_origins = missing_origins_by_table_id.get(table_id)
                if key[1] == binding_kind and missing_origins:
                    add_issue(
                        key,
                        ["local_storage_origin_missing"],
                        table_ids=[table_id],
                        missing_origin_table_ids=sorted(missing_origins),
                    )

    comparable_keys: dict[tuple[str, str, str], int] = {}
    for key, table_id in resolved_keys.items():
        cluster_ids = cluster_ids_by_kind_and_table.get((key[1], table_id))
        if cluster_ids is None:
            # Doris origin 缺失已在上面输出更精确的问题。
            if key not in issued_keys:
                add_issue(key, ["local_storage_record_missing"], table_ids=[table_id], local_cluster_ids=[])
            continue
        if not cluster_ids:
            add_issue(key, ["local_cluster_id_missing"], table_ids=[table_id], local_cluster_ids=[])
            continue
        if len(cluster_ids) > 1:
            add_issue(
                key,
                ["local_storage_cluster_ambiguous"],
                table_ids=[table_id],
                local_cluster_ids=sorted(cluster_ids),
            )
            continue
        comparable_keys[key] = next(iter(cluster_ids))

    if not comparable_keys:
        return local_issues

    cluster_types = set(STORAGE_BINDING_CLUSTER_TYPE_MAP.values())
    cluster_by_id: dict[int, dict[str, Any]] = {}
    cluster_by_type_and_name: dict[tuple[str, str], dict[str, Any]] = {}
    for cluster in ClusterInfo.objects.filter(
        bk_tenant_id=bk_tenant_id,
        cluster_type__in=cluster_types,
    ).values("cluster_id", "cluster_type", "cluster_name", "domain_name"):
        cluster_by_id[cluster["cluster_id"]] = cluster
        cluster_by_type_and_name[(cluster["cluster_type"], cluster["cluster_name"])] = cluster

    for key, local_cluster_id in comparable_keys.items():
        table_id = resolved_keys[key]
        local_cluster = cluster_by_id.get(local_cluster_id)
        if local_cluster is None:
            add_issue(
                key,
                ["local_cluster_info_missing"],
                table_ids=[table_id],
                local_cluster_ids=[local_cluster_id],
            )
            continue

        issue, _ = _parse_storage_binding_reference(
            remote_config_by_key[key],
            bk_tenant_id=bk_tenant_id,
            namespace=key[0],
            binding_kind=key[1],
        )
        remote_cluster_name = issue["storage_name"]
        common_details = {
            "table_ids": [table_id],
            "local_cluster_ids": [local_cluster_id],
            "local_cluster_names": [local_cluster["cluster_name"]],
            "local_cluster_id": local_cluster_id,
            "local_cluster_name": local_cluster["cluster_name"],
            "local_domain_name": local_cluster["domain_name"],
        }
        if local_cluster["cluster_name"] == remote_cluster_name:
            continue

        cluster_type = STORAGE_BINDING_CLUSTER_TYPE_MAP[key[1]]
        remote_cluster = cluster_by_type_and_name.get((cluster_type, remote_cluster_name))
        if remote_cluster is None:
            add_issue(
                key,
                ["remote_cluster_info_missing"],
                **common_details,
                remote_cluster_id=None,
                remote_cluster_name=remote_cluster_name,
                remote_domain_name=None,
            )
            continue

        local_domain = _normalize_cluster_domain(local_cluster["domain_name"])
        remote_domain = _normalize_cluster_domain(remote_cluster["domain_name"])
        if local_domain and remote_domain and local_domain == remote_domain:
            continue

        add_issue(
            key,
            ["local_storage_cluster_mismatch"],
            **common_details,
            remote_cluster_id=remote_cluster["cluster_id"],
            remote_cluster_name=remote_cluster["cluster_name"],
            remote_domain_name=remote_cluster["domain_name"],
        )

    return local_issues


def batch_check_storage_binding_references(bk_tenant_id: str) -> list[dict[str, Any]]:
    """检查指定租户在 bkmonitor、bklog 下的 ES、Doris、VM Storage Binding 引用。"""
    issues_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    unkeyed_issues: list[dict[str, Any]] = []
    remote_configs_by_batch: dict[tuple[str, str], list[Any]] = {}
    for namespace in STORAGE_BINDING_NAMESPACES:
        for binding_kind in STORAGE_BINDING_KIND_MAP:
            configs = api.bkdata.list_data_link(
                bk_tenant_id=bk_tenant_id,
                namespace=namespace,
                kind=DataLinkKind.get_choice_value(binding_kind),
            )
            if not isinstance(configs, list):
                raise ValueError(
                    "batch_check_storage_binding_references: list_data_link returned invalid data, "
                    f"tenant={bk_tenant_id}, namespace={namespace}, kind={binding_kind}"
                )
            remote_configs_by_batch[(namespace, binding_kind)] = configs
            for issue in _check_storage_binding_references(
                configs,
                bk_tenant_id=bk_tenant_id,
                namespace=namespace,
                binding_kind=binding_kind,
            ):
                _merge_storage_binding_issue(issues_by_key, unkeyed_issues, issue)

    for issue in _check_local_storage_binding_references(
        bk_tenant_id=bk_tenant_id,
        remote_configs_by_batch=remote_configs_by_batch,
    ):
        _merge_storage_binding_issue(issues_by_key, unkeyed_issues, issue)
    return [*issues_by_key.values(), *unkeyed_issues]


def _mark_component_links_untrusted(components: list[Any], untrusted_links: set[DataLinkStatusKey]) -> None:
    for component in components:
        if component.data_link_name:
            untrusted_links.add((_normalize_data_link_tenant_id(component.bk_tenant_id), component.data_link_name))


def _get_data_link_discovery_tenant_ids() -> set[str]:
    """获取远端组件发现范围；失败时由本地批次继续兜底刷新。"""
    try:
        tenants = api.bk_login.list_tenant()
    except Exception as error:  # pylint: disable=broad-except
        logger.exception("bulk_refresh_data_link_status: list tenants failed, error->[%s]", error)
        return set()

    if not isinstance(tenants, list):
        logger.warning("bulk_refresh_data_link_status: ignore invalid tenant list->[%s]", tenants)
        return set()

    tenant_ids = set()
    for tenant in tenants:
        if not isinstance(tenant, dict) or not tenant.get("id"):
            logger.warning("bulk_refresh_data_link_status: ignore invalid tenant config->[%s]", tenant)
            continue
        tenant_ids.add(str(tenant["id"]))
    return tenant_ids


def _reconcile_data_link_components() -> tuple[
    dict[DataLinkStatusKey, list[str]],
    set[DataLinkStatusKey],
    dict[DataLinkStatusKey, int],
    DataLinkRefreshStats,
]:
    """通过远端批量列表统一发现、同步并刷新本地 DataLink 组件。"""
    statuses_by_link: dict[DataLinkStatusKey, list[str]] = defaultdict(list)
    untrusted_links: set[DataLinkStatusKey] = set()
    biz_id_by_link: dict[DataLinkStatusKey, int] = {}
    stats = DataLinkRefreshStats()
    discovery_tenant_ids = _get_data_link_discovery_tenant_ids()

    # ResultTable 必须先于依赖其 table_id 的 VM/SurrealDB Binding 落库。
    component_items = sorted(
        COMPONENT_CLASS_MAP.items(),
        key=lambda item: item[0] != DataLinkKind.RESULTTABLE.value,
    )
    for kind, component_class in component_items:
        components_by_batch: dict[ComponentBatchKey, list[Any]] = defaultdict(list)
        for component in component_class.objects.all().iterator(chunk_size=1000):
            batch_key = (
                _normalize_data_link_tenant_id(component.bk_tenant_id),
                component.namespace,
                kind,
            )
            components_by_batch[batch_key].append(component)

        batch_keys = set(components_by_batch)
        batch_keys.update(
            (bk_tenant_id, namespace, kind)
            for bk_tenant_id in discovery_tenant_ids
            for namespace in DATA_LINK_DISCOVERY_NAMESPACES
        )

        for bk_tenant_id, namespace, component_kind in sorted(batch_keys):
            components = components_by_batch.get((bk_tenant_id, namespace, component_kind), [])
            bkbase_kind = DataLinkKind.get_choice_value(component_kind)
            try:
                configs = api.bkdata.list_data_link(
                    bk_tenant_id=bk_tenant_id,
                    namespace=namespace,
                    kind=bkbase_kind,
                )
            except Exception as error:  # pylint: disable=broad-except
                logger.exception(
                    "bulk_refresh_data_link_status: list components failed, tenant->[%s], namespace->[%s], "
                    "kind->[%s], error->[%s]",
                    bk_tenant_id,
                    namespace,
                    component_kind,
                    error,
                )
                _mark_component_links_untrusted(components, untrusted_links)
                stats.untrusted_batch_count += 1
                continue

            try:
                parsed_configs = _parse_bkbase_component_configs(
                    configs,
                    bk_tenant_id=bk_tenant_id,
                    namespace=namespace,
                    kind=component_kind,
                )
            except Exception as error:  # pylint: disable=broad-except
                logger.exception(
                    "bulk_refresh_data_link_status: parse components failed, tenant->[%s], namespace->[%s], "
                    "kind->[%s], error->[%s]",
                    bk_tenant_id,
                    namespace,
                    component_kind,
                    error,
                )
                _mark_component_links_untrusted(components, untrusted_links)
                stats.untrusted_batch_count += 1
                continue

            if parsed_configs is None:
                logger.warning(
                    "bulk_refresh_data_link_status: list components returned empty or invalid data, "
                    "tenant->[%s], namespace->[%s], kind->[%s], skip batch",
                    bk_tenant_id,
                    namespace,
                    component_kind,
                )
                _mark_component_links_untrusted(components, untrusted_links)
                stats.untrusted_batch_count += 1
                continue

            remote_configs_by_name = {config["metadata"]["name"]: config for config in configs}

            if component_kind in STORAGE_BINDING_KIND_MAP:
                reference_issues = _check_storage_binding_references(
                    configs,
                    bk_tenant_id=bk_tenant_id,
                    namespace=namespace,
                    binding_kind=component_kind,
                )
                for issue in reference_issues:
                    logger.warning(
                        "bulk_refresh_data_link_status: storage binding reference check failed, issue->[%s]", issue
                    )

            components_by_name = {component.name: component for component in components}
            now = timezone.now()
            created_components = []
            changed_components = []
            update_fields = set()
            terminated_count = 0

            for name, (base_config, extra_config) in parsed_configs.items():
                component = components_by_name.get(name)
                if component is None:
                    created_components.append(component_class(**base_config, **extra_config))
                    continue

                is_updated = False
                for field, value in extra_config.items():
                    if (
                        _should_update_bkbase_component_field(component_kind, field, value)
                        and getattr(component, field) != value
                    ):
                        setattr(component, field, value)
                        update_fields.add(field)
                        is_updated = True
                if is_updated:
                    component.last_modify_time = now
                    changed_components.append(component)
                    update_fields.add("last_modify_time")

            remote_names = set(parsed_configs)
            for component in components:
                if component.name in remote_names or component.status == DataLinkResourceStatus.TERMINATED.value:
                    continue
                component.status = DataLinkResourceStatus.TERMINATED.value
                component.last_modify_time = now
                changed_components.append(component)
                update_fields.update({"status", "last_modify_time"})
                terminated_count += 1

            try:
                with transaction.atomic():
                    if created_components:
                        component_class.objects.bulk_create(created_components, batch_size=1000)
                    if changed_components:
                        component_class.objects.bulk_update(
                            changed_components,
                            sorted(update_fields),
                            batch_size=1000,
                        )
            except Exception as error:  # pylint: disable=broad-except
                logger.exception(
                    "bulk_refresh_data_link_status: reconcile components failed, tenant->[%s], namespace->[%s], "
                    "kind->[%s], error->[%s]",
                    bk_tenant_id,
                    namespace,
                    component_kind,
                    error,
                )
                _mark_component_links_untrusted(components, untrusted_links)
                stats.untrusted_batch_count += 1
                continue

            if component_kind == DataLinkKind.SURREALDBBINDING.value and settings.ENABLE_SURREALDB_MATERIALIZED_VIEW:
                materialized_view_components = {
                    component.name: component for component in [*components, *created_components]
                }
                for name, (_, extra_config) in parsed_configs.items():
                    component = materialized_view_components.get(name)
                    if not isinstance(component, SurrealDBBindingConfig):
                        continue
                    component.status = extra_config["status"]
                    try:
                        reconcile_materialized_views(component, remote_configs_by_name[name])
                    except Exception as error:  # pylint: disable=broad-except
                        logger.exception(
                            "bulk_refresh_data_link_status: reconcile surrealdb materialized views failed, "
                            "tenant->[%s], namespace->[%s], name->[%s], error->[%s]",
                            bk_tenant_id,
                            namespace,
                            name,
                            error,
                        )

            stats.created_count += len(created_components)
            stats.updated_count += len(changed_components) - terminated_count
            stats.terminated_count += terminated_count
            for component in [*components, *created_components]:
                if component.data_link_name and kind != DataLinkKind.DATAID.value:
                    link_key = (bk_tenant_id, component.data_link_name)
                    statuses_by_link[link_key].append(component.status)
                    biz_id_by_link.setdefault(link_key, component.bk_biz_id)
                report_metadata_data_link_status_info(
                    data_link_name=component.data_link_name,
                    biz_id=str(component.bk_biz_id),
                    kind=component.kind,
                    status=component.status,
                )

    return statuses_by_link, untrusted_links, biz_id_by_link, stats


def _refresh_bkbase_result_table_statuses(
    statuses_by_link: dict[DataLinkStatusKey, list[str]],
    untrusted_links: set[DataLinkStatusKey],
    biz_id_by_link: dict[DataLinkStatusKey, int],
) -> int:
    """根据可信的本地组件状态汇总刷新 BkBaseResultTable.status。"""
    bkbase_records = {
        (_normalize_data_link_tenant_id(record.bk_tenant_id), record.data_link_name): record
        for record in BkBaseResultTable.objects.all()
    }
    changed_records = []
    now = timezone.now()
    for link_key, component_statuses in statuses_by_link.items():
        if link_key in untrusted_links or not component_statuses:
            continue
        bkbase_record = bkbase_records.get(link_key)
        if bkbase_record is None:
            continue

        if all(status == DataLinkResourceStatus.OK.value for status in component_statuses):
            status = DataLinkResourceStatus.OK.value
        elif all(status == DataLinkResourceStatus.TERMINATED.value for status in component_statuses):
            status = DataLinkResourceStatus.TERMINATED.value
        else:
            status = DataLinkResourceStatus.PENDING.value

        if bkbase_record.status != status:
            bkbase_record.status = status
            bkbase_record.last_modify_time = now
            changed_records.append(bkbase_record)

        report_metadata_data_link_status_info(
            data_link_name=bkbase_record.data_link_name,
            biz_id=str(biz_id_by_link[link_key]),
            kind=DataLinkKind.RESULTTABLE.value,
            status=status,
        )

    if changed_records:
        BkBaseResultTable.objects.bulk_update(
            changed_records,
            ["status", "last_modify_time"],
            batch_size=1000,
        )
    return len(changed_records)


@app.task(ignore_result=True, queue="celery_metadata_task_worker")
def bulk_refresh_data_link_status():
    """批量发现、同步 DataLink 组件，并刷新组件及链路整体状态。"""
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="bulk_refresh_data_link_status", status=TASK_STARTED, process_target=None
    ).inc()

    start_time = time.time()
    logger.info("bulk_refresh_data_link_status: start to reconcile all data_link components")
    statuses_by_link, untrusted_links, biz_id_by_link, refresh_stats = _reconcile_data_link_components()
    changed_bkbase_count = _refresh_bkbase_result_table_statuses(
        statuses_by_link=statuses_by_link,
        untrusted_links=untrusted_links,
        biz_id_by_link=biz_id_by_link,
    )
    cost_time = time.time() - start_time
    logger.info(
        "bulk_refresh_data_link_status: finished, created components->[%s], updated components->[%s], "
        "terminated components->[%s], changed bkbase records->[%s], untrusted batches->[%s], "
        "untrusted links->[%s], cost_time->[%s]",
        refresh_stats.created_count,
        refresh_stats.updated_count,
        refresh_stats.terminated_count,
        changed_bkbase_count,
        refresh_stats.untrusted_batch_count,
        len(untrusted_links),
        cost_time,
    )
    for operation, count in (
        ("created", refresh_stats.created_count),
        ("updated", refresh_stats.updated_count),
        ("terminated", refresh_stats.terminated_count),
        ("bkbase_updated", changed_bkbase_count),
        ("untrusted_batch", refresh_stats.untrusted_batch_count),
    ):
        metrics.METADATA_DATA_LINK_REFRESH_TOTAL.labels(operation=operation).inc(count)

    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="bulk_refresh_data_link_status", status=TASK_FINISHED_SUCCESS, process_target=None
    ).inc()
    metrics.METADATA_CRON_TASK_COST_SECONDS.labels(
        task_name="bulk_refresh_data_link_status", process_target=None
    ).observe(cost_time)
    metrics.report_all()
