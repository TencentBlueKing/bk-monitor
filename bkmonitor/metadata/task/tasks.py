"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import logging
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils.translation import gettext as _
from tenacity import RetryError, retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from alarm_backends.service.scheduler.app import app
from constants.common import DEFAULT_TENANT_ID
from core.drf_resource import api
from core.prometheus import metrics
from metadata import models
from metadata.models import BkBaseResultTable, ClusterInfo, DataSource
from metadata.models.constants import (
    BASE_EVENT_RESULT_TABLE_FIELD_MAP,
    BASE_EVENT_RESULT_TABLE_FIELD_OPTION_MAP,
    BASE_EVENT_RESULT_TABLE_OPTION_MAP,
    BASEREPORT_RESULT_TABLE_FIELD_MAP,
    SYSTEM_PROC_DATA_LINK_CONFIGS,
    DataIdCreatedFromSystem,
)
from metadata.models.data_link.constants import (
    BASEREPORT_SOURCE_SYSTEM,
    BASEREPORT_USAGES,
    BKBASE_NAMESPACE_BK_MONITOR,
    DataLinkResourceStatus,
)
from metadata.models.data_link.data_link import DataLink
from metadata.models.data_link.service import get_data_link_component_status
from metadata.models.space.constants import EtlConfigs, SpaceTypes
from metadata.models.space.space import Space
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis
from metadata.models.vm.record import AccessVMRecord
from metadata.models.vm.utils import (
    create_fed_bkbase_data_link,
    get_vm_cluster_id_name,
    report_metadata_data_link_status_info,
)
from metadata.service.sync_metadata import (
    sync_es_metadata,
    sync_kafka_metadata,
    sync_vm_metadata,
)
from metadata.task.utils import bulk_handle
from metadata.tools.constants import TASK_FINISHED_SUCCESS, TASK_STARTED
from metadata.utils import consul_tools
from metadata.utils.redis_tools import RedisTools, bkbase_redis_client

logger = logging.getLogger("metadata")


@app.task(ignore_result=True, queue="celery_metadata_task_worker")
def refresh_custom_report_config(bk_biz_id=None):
    from metadata.task.custom_report import refresh_custom_report_2_node_man

    refresh_custom_report_2_node_man(bk_biz_id=bk_biz_id)


@app.task(ignore_result=True, queue="celery_metadata_task_worker")
def refresh_custom_log_report_config(log_group_id=None):
    from metadata.task.custom_report import refresh_custom_log_config

    refresh_custom_log_config(log_group_id=log_group_id)


@app.task(ignore_result=True, queue="celery_metadata_task_worker")
def access_to_bk_data_task(bk_tenant_id, table_id):
    try:
        bkdata_storage = models.BkDataStorage.objects.get(table_id=table_id)
    except models.BkDataStorage.DoesNotExist:
        models.BkDataStorage.create_table(bk_tenant_id=bk_tenant_id, table_id=table_id, is_sync_db=True)
        return

    bkdata_storage.check_and_access_bkdata()


@app.task(ignore_result=True, queue="celery_metadata_task_worker")
def create_statistics_data_flow(table_id, agg_interval):
    try:
        bkdata_storage = models.BkDataStorage.objects.get(table_id=table_id)
    except models.BkDataStorage.DoesNotExist:
        raise Exception(_("数据({})未接入到计算平台，请先接入后再试").format(table_id))

    bkdata_storage.create_statistics_data_flow(agg_interval)


@app.task(ignore_result=True, queue="celery_metadata_task_worker")
def create_full_cmdb_level_data_flow(table_id, bk_tenant_id=DEFAULT_TENANT_ID):
    try:
        bkdata_storage = models.BkDataStorage.objects.get(table_id=table_id, bk_tenant_id=bk_tenant_id)
    except models.BkDataStorage.DoesNotExist:
        raise Exception(_("数据({})未接入到计算平台，请先接入后再试").format(table_id))

    bkdata_storage.full_cmdb_node_info_to_result_table()


@app.task(ignore_result=True, queue="celery_metadata_task_worker")
@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(models.ESStorage.DoesNotExist),  # 目前只针对预设异常进行重试
    reraise=True,  # 重试失败后，抛出原始异常
)
def create_es_storage_index(table_id):
    """
    异步创建es索引
    由于异步触发时ESStorage可能还没就绪，添加重试机制
    最多重试4次，等待时间间隔呈指数增长：1s -> 2s -> 4s -> 8s (最大10s)
    """
    logger.info("table_id: %s start to create es index", table_id)
    try:
        es_storage = models.ESStorage.objects.get(table_id=table_id)
    except models.ESStorage.DoesNotExist:
        logger.error("table_id->[%s] not exists, will retry", table_id)
        raise models.ESStorage.DoesNotExist(f"table_id->[{table_id}] not exists")

    if not es_storage.index_exist():
        es_storage.create_index_and_aliases(es_storage.slice_gap)
    else:
        es_storage.update_index_and_aliases(ahead_time=es_storage.slice_gap)

    # 创建完 ES 相关配置后，需要刷新consul
    try:
        rt = models.ResultTable.objects.get(table_id=table_id)
        rt.refresh_etl_config()
    except models.ResultTable.DoesNotExist:
        logger.error("query table_id->[%s] not exists from ResultTable", table_id)

    logger.info("table_id: %s end to create es index", table_id)


@app.task(ignore_result=True, queue="celery_metadata_task_worker")
def delete_es_result_table_snapshot(table_id, target_snapshot_repository_name, bk_tenant_id=DEFAULT_TENANT_ID):
    models.ESStorage.objects.get(table_id=table_id, bk_tenant_id=bk_tenant_id).delete_all_snapshot(
        target_snapshot_repository_name
    )


@app.task(ignore_result=True, queue="celery_metadata_task_worker")
def retry_es_result_table_snapshot(table_id, target_snapshot_repository_name, bk_tenant_id=DEFAULT_TENANT_ID):
    models.ESStorage.objects.get(table_id=table_id, bk_tenant_id=bk_tenant_id).retry_snapshot(
        target_snapshot_repository_name
    )


@app.task(ignore_result=True, queue="celery_metadata_task_worker")
def restore_result_table_snapshot(indices_group_by_snapshot, restore_id):
    try:
        restore = models.EsSnapshotRestore.objects.get(restore_id=restore_id)
    except models.EsSnapshotRestore.DoesNotExist:
        raise ValueError(_("回溯不存在"))
    restore.create_es_restore(indices_group_by_snapshot)


@app.task(ignore_result=True, queue="celery_metadata_task_worker")
def delete_restore_indices(restore_id):
    try:
        restore = models.EsSnapshotRestore.objects.get(restore_id=restore_id)
    except models.EsSnapshotRestore.DoesNotExist:
        raise ValueError(_("回溯不存在"))
    restore.delete_restore_indices()


def update_time_series_metrics(time_series_metrics):
    data_id_list, table_id_list = [], []
    for time_series_group in time_series_metrics:
        try:
            is_updated = time_series_group.update_time_series_metrics()
            logger.info(
                "bk_data_id->[%s] metric add from redis success, is_updated: %s",
                time_series_group.bk_data_id,
                is_updated,
            )
            # 记录是否有更新，如果有更新则推送到redis
            if is_updated:
                data_id_list.append(time_series_group.bk_data_id)
                table_id_list.append(time_series_group.table_id)
        except Exception as e:
            logger.error(
                "data_id->[%s], table_id->[%s] try to update ts metrics from redis failed, error->[%s], "
                "traceback_detail->[%s]",
                # noqa
                time_series_group.bk_data_id,
                time_series_group.table_id,
                e,
                traceback.format_exc(),
            )
        else:
            logger.info("time_series_group->[%s] metric update from redis success.", time_series_group.bk_data_id)

    # 仅当指标有变动的结果表存在时，才进行路由配置更新
    if table_id_list:
        from metadata.models.space.space_table_id_redis import SpaceTableIDRedis

        space_client = SpaceTableIDRedis()
        space_client.push_table_id_detail(table_id_list=table_id_list, is_publish=True)
        logger.info("metric updated of table_id: %s", json.dumps(table_id_list))


# todo: es 索引管理，迁移至BMW
@app.task(ignore_result=True, queue="celery_long_task_cron")
def manage_es_storage(storage_record_ids, cluster_id: int = None):
    """
    ES索引轮转异步任务
    @param es_storages: 待轮转采集项
    @param cluster_id: 集群ID
    @return:
    """
    # 统计&上报 任务状态指标
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="manage_es_storage", status=TASK_STARTED, process_target=None
    ).inc()

    logger.info("manage_es_storage: start to manage_es_storage")
    start_time = time.time()

    es_storages = models.ESStorage.objects.filter(id__in=storage_record_ids)

    # 不再使用白名单，默认全量使用新方式轮转
    for es_storage in es_storages:
        logger.info(
            "manage_es_storage:cluster_id->[%s],table_id->[%s],start to rotate index",
            cluster_id,
            es_storage.table_id,
        )
        try:
            _manage_es_storage(es_storage)
            time.sleep(settings.ES_INDEX_ROTATION_SLEEP_INTERVAL_SECONDS)  # 等待一段时间，降低负载
            logger.info(
                "manage_es_storage:cluster_id->[%s],table_id->[%s],rotate index finished",
                cluster_id,
                es_storage.table_id,
            )
        except Exception as e:
            logger.error(
                "manage_es_storage:cluster_id->[%s],table_id->[%s],rotate index failed, error->[%s]",
                cluster_id,
                es_storage.table_id,
                e,
            )
            continue

    cost_time = time.time() - start_time

    # 统计&上报 任务状态指标
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="manage_es_storage", status=TASK_FINISHED_SUCCESS, process_target=None
    ).inc()

    # 统计耗时，并上报指标
    metrics.METADATA_CRON_TASK_COST_SECONDS.labels(task_name="manage_es_storage", process_target=None).observe(
        cost_time
    )
    metrics.report_all()
    logger.info("manage_es_storage:manage_es_storage cost time: %s", cost_time)


@app.task(ignore_result=True, queue="celery_long_task_cron")
def clean_disable_es_storage(es_storages, cluster_id: int = None):
    """
    停用采集项管理异步任务
    @param es_storages: 待处理采集项
    @param cluster_id: 集群ID
    @return:
    """

    # 统计&上报 任务状态指标
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="clean_disable_es_storage", status=TASK_STARTED, process_target=None
    ).inc()

    logger.info("clean_disable_es_storage: start to clean_disable_es_storage for cluster_id->[%s]", cluster_id)
    start_time = time.time()

    for es_storage in es_storages:
        logger.info(
            "clean_disable_es_storage:cluster_id->[%s],table_id->[%s],start to clean index",
            cluster_id,
            es_storage.table_id,
        )
        try:
            _clean_disable_es_storage(es_storage)
            time.sleep(settings.ES_INDEX_ROTATION_SLEEP_INTERVAL_SECONDS)  # 等待一段时间，降低负载
            logger.info(
                "clean_disable_es_storage:cluster_id->[%s],table_id->[%s],clean index finished",
                cluster_id,
                es_storage.table_id,
            )
        except Exception as e:
            logger.error(
                "clean_disable_es_storage:cluster_id->[%s],table_id->[%s],clean index failed, error->[%s]",
                cluster_id,
                es_storage.table_id,
                e,
            )
            continue

    cost_time = time.time() - start_time

    # 统计&上报 任务状态指标
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="clean_disable_es_storage", status=TASK_FINISHED_SUCCESS, process_target=None
    ).inc()

    # 统计耗时，并上报指标
    metrics.METADATA_CRON_TASK_COST_SECONDS.labels(task_name="clean_disable_es_storage", process_target=None).observe(
        cost_time
    )
    metrics.report_all()
    logger.info("clean_disable_es_storage:clean_disable_es_storage cost time: %s", cost_time)


def _clean_disable_es_storage(es_storage):
    """
    停用采集项管理异步子任务
    @param es_storage: 待处理采集项
    """
    logger.info("_clean_disable_es_storage: start to _clean_disable_es_storage,table_id->[%s]", es_storage.table_id)
    start_time = time.time()
    # 统计&上报 任务状态指标
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="_clean_disable_es_storage", status=TASK_STARTED, process_target=es_storage.table_id
    ).inc()
    try:
        es_storage.clean_index_v2()
        logger.info("_clean_disable_es_storage: table_id->[%s], clean index success", es_storage.table_id)
    except Exception as e:  # pylint: disable=broad-except
        logger.error(
            "_clean_disable_es_storage: table_id->[%s], clean index failed, error->[%s]", es_storage.table_id, e
        )

    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="_clean_disable_es_storage", status=TASK_FINISHED_SUCCESS, process_target=es_storage.table_id
    ).inc()

    cost_time = time.time() - start_time

    # 统计耗时，并上报指标
    metrics.METADATA_CRON_TASK_COST_SECONDS.labels(
        task_name="_clean_disable_es_storage", process_target=es_storage.table_id
    ).observe(cost_time)
    metrics.report_all()


def _manage_es_storage(es_storage):
    """
    NOTE: 针对结果表校验使用的es集群状态，不要统一校验
    """
    # 遍历所有的ES存储并创建index, 并执行完整的es生命周期操作

    #     if es_storage.is_red():
    #         logger.error(
    #             "es cluster health is red, skip index lifecycle; name: %s, id: %s, domain: %s",
    #             es_storage.storage_cluster.cluster_name,
    #             es_storage.storage_cluster.cluster_id,
    #             es_storage.storage_cluster.domain_name,
    #         )
    #         return

    # 统计&上报 任务状态指标
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="_manage_es_storage", status=TASK_STARTED, process_target=es_storage.table_id
    ).inc()

    start_time = time.time()
    try:
        # 先预创建各个时间段的index，
        # 1. 同时判断各个预创建好的index是否字段与数据库的一致
        # 2. 也判断各个创建的index是否有大小需要切片的需要
        logger.info("manage_es_storage:table_id->[%s] start to create index", es_storage.table_id)

        # 如果index_settings和mapping_settings为空，则说明对应配置信息有误，记录日志并触发告警
        if not es_storage.index_settings or es_storage.index_settings == "{}":
            logger.error(
                "manage_es_storage:table_id->[%s] need to create index,but index_settings invalid", es_storage.table_id
            )
            return
        if not es_storage.mapping_settings or es_storage.mapping_settings == "{}":
            logger.error(
                "manage_es_storage:table_id->[%s] need to create index,but mapping_settings invalid",
                es_storage.table_id,
            )
            return

        if not es_storage.index_exist():
            #   如果该table_id的index在es中不存在，说明要走初始化流程
            logger.info(
                "manage_es_storage:table_id->[%s] found no index in es,will create new one", es_storage.table_id
            )
            es_storage.create_index_and_aliases(es_storage.slice_gap)
        else:
            # 否则走更新流程
            logger.info("manage_es_storage:table_id->[%s] found index in es,now try to update it", es_storage.table_id)
            es_storage.update_index_and_aliases(ahead_time=es_storage.slice_gap)

        # 创建快照
        logger.info("manage_es_storage:table_id->[%s] try to create snapshot", es_storage.table_id)
        es_storage.create_snapshot()

        # 清理过期的index
        logger.info("manage_es_storage:table_id->[%s] try to clean index", es_storage.table_id)
        es_storage.clean_index_v2()

        # 清理历史ES集群中的过期Index
        logger.info("manage_es_storage:table_id->[%s] try to clean index in old es cluster", es_storage.table_id)
        es_storage.clean_history_es_index()

        # 清理过期快照
        logger.info("manage_es_storage:table_id->[%s] try to clean snapshot", es_storage.table_id)
        es_storage.clean_snapshot()

        # 重新分配索引数据
        logger.info("manage_es_storage:table_id->[%s] try to reallocate index", es_storage.table_id)
        es_storage.reallocate_index()

        logger.info(f"manage_es_storage:es_storage->[{es_storage.table_id}] cron task success")
    except RetryError as e:
        logger.error(
            f"manage_es_storage:es_storage index lifecycle failed,table_id->{es_storage.table_id},error->{e.__cause__}"
        )
        logger.exception(e)
    except Exception as e:  # pylint: disable=broad-except
        # 记录异常集群的信息
        logger.error(f"manage_es_storage:es_storage index lifecycle failed,table_id->{es_storage.table_id}")
        logger.exception(e)

    cost_time = time.time() - start_time

    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="_manage_es_storage", status=TASK_FINISHED_SUCCESS, process_target=es_storage.table_id
    ).inc()
    # 统计耗时，并上报指标
    metrics.METADATA_CRON_TASK_COST_SECONDS.labels(
        task_name="_manage_es_storage", process_target=es_storage.table_id
    ).observe(cost_time)
    metrics.report_all()  # 上报全部指标,包括索引轮转原因、轮转状态


# TODO: 多租户改造
@app.task(ignore_result=True, queue="celery_metadata_task_worker")
def push_and_publish_space_router(
    space_type: str | None = None,
    space_id: str | None = None,
    table_id_list: list | None = None,
):
    """推送并发布空间路由功能"""
    logger.info(
        "start to push and publish space_type: %s, space_id: %s, table_id_list: %s router",
        space_type,
        space_id,
        json.dumps(table_id_list),
    )
    from metadata.models.space.constants import (
        SPACE_TO_RESULT_TABLE_CHANNEL,
        SpaceTypes,
    )
    from metadata.models.space.ds_rt import get_space_table_id_data_id
    from metadata.models.space.space_table_id_redis import SpaceTableIDRedis

    # 获取空间下的结果表，如果不存在，则获取空间下的所有
    if not table_id_list:
        table_id_list = list(get_space_table_id_data_id(space_type, space_id).keys())

    space_client = SpaceTableIDRedis()
    # 更新空间下的结果表相关数据
    if space_type and space_id:
        # 更新相关数据到 redis
        space_client.push_space_table_ids(space_type=space_type, space_id=space_id, is_publish=True)
    else:
        # NOTE: 现阶段仅针对 bkcc 类型做处理
        spaces = list(models.Space.objects.filter(space_type_id=SpaceTypes.BKCC.value))
        # 使用线程处理
        bulk_handle(lambda space_list: space_client.push_multi_space_table_ids(space_list, is_publish=False), spaces)

        # 通知到使用方
        push_redis_keys = []
        for space in spaces:
            if settings.ENABLE_MULTI_TENANT_MODE:
                push_redis_keys.append(f"{space.space_type_id}__{space.space_id}|{space.bk_tenant_id}")
            else:
                push_redis_keys.append(f"{space.space_type_id}__{space.space_id}")
        RedisTools.publish(SPACE_TO_RESULT_TABLE_CHANNEL, push_redis_keys)

    # 更新数据
    space_client.push_data_label_table_ids(table_id_list=table_id_list, is_publish=True)
    space_client.push_table_id_detail(table_id_list=table_id_list, is_publish=True)

    logger.info("push and publish space_type: %s, space_id: %s router successfully", space_type, space_id)


def _access_bkdata_vm(
    bk_tenant_id: str,
    bk_biz_id: int,
    table_id: str,
    data_id: int,
    allow_access_v2_data_link: bool | None = False,
):
    """接入计算平台 VM 任务
    NOTE: 根据环境变量判断是否启用新版vm链路
    """
    from metadata.models.vm.utils import access_bkdata, access_v2_bkdata_vm

    # NOTE：只有当allow_access_v2_data_link为True，即单指标单表时序指标数据时，才允许接入V4链路
    if settings.ENABLE_V2_VM_DATA_LINK and allow_access_v2_data_link:
        logger.info("_access_bkdata_vm: start to access v2 bkdata vm, table_id->%s, data_id->%s", table_id, data_id)
        access_v2_bkdata_vm(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, table_id=table_id, data_id=data_id)
    else:
        logger.info("_access_bkdata_vm: start to access bkdata vm, table_id->%s, data_id->%s", table_id, data_id)
        access_bkdata(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, table_id=table_id, data_id=data_id)


@app.task(ignore_result=True, queue="celery_metadata_task_worker")
def access_bkdata_vm(
    bk_tenant_id: str,
    bk_biz_id: int,
    table_id: str,
    data_id: int,
    allow_access_v2_data_link: bool = False,
):
    """接入计算平台 VM 任务"""
    logger.info("bk_biz_id: %s, table_id: %s, data_id: %s start access bkdata vm", bk_biz_id, table_id, data_id)
    try:
        _access_bkdata_vm(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            table_id=table_id,
            data_id=data_id,
            allow_access_v2_data_link=allow_access_v2_data_link,
        )
    except RetryError as e:
        logger.error(
            "access_bkdata_vm: bk_biz_id: %s, table_id: %s, data_id: %s access vm failed, error: %s",
            bk_biz_id,
            table_id,
            data_id,
            e.__cause__,
        )
        return
    except Exception as e:  # pylint: disable=broad-except
        logger.error(
            "access_bkdata_vm: bk_biz_id: %s, table_id: %s, data_id: %s access vm failed, error: %s",
            bk_biz_id,
            table_id,
            data_id,
            e,
        )
        return

    # 推送空间路由
    if bk_biz_id != 0:
        space = Space.objects.get_space_info_by_biz_id(bk_biz_id=bk_biz_id)
        push_and_publish_space_router(space["space_type"], space["space_id"], table_id_list=[table_id])
    else:
        push_and_publish_space_router(table_id_list=[table_id])

    logger.info("bk_biz_id: %s, table_id: %s, data_id: %s end access bkdata vm", bk_biz_id, table_id, data_id)


@app.task(ignore_result=True, queue="celery_metadata_task_worker")
def push_space_to_redis(space_type: str, space_id: str):
    """异步推送创建的空间到 redis"""
    logger.info("async task start to push space_type: %s, space_id: %s to redis", space_type, space_id)

    try:
        from metadata.models.space.constants import SPACE_REDIS_PREFIX_KEY
        from metadata.utils.redis_tools import RedisTools

        RedisTools.push_space_to_redis(SPACE_REDIS_PREFIX_KEY, [f"{space_type}__{space_id}"])
    except Exception as e:
        logger.error("async task push space to redis error, %s", e)
        return

    logger.info("async task push space_type: %s, space_id: %s to redis successfully", space_type, space_id)


@app.task(ignore_result=True, queue="celery_metadata_task_worker")
def bulk_check_and_delete_ds_consul_config(data_sources):
    """
    并发检查V4数据源对应的Consul配置是否存在，若存在则进行删除
    @param data_sources: 待检查的数据源列表
    """
    # 统计&上报 任务状态指标
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="bulk_check_and_delete_ds_consul_config", status=TASK_STARTED, process_target=None
    ).inc()

    start_time = time.time()  # 记录开始时间

    logger.info("bulk_check_and_delete_ds_consul_config:async task start to check,len->[%s]", len(data_sources))

    with ThreadPoolExecutor(max_workers=10) as executor:
        executor.map(_check_and_delete_ds_consul_config, data_sources)

    cost_time = time.time() - start_time  # 总耗时
    logger.info(
        "bulk_check_and_delete_ds_consul_config:async task check and delete ds consul config success, cost_time->[%s]",
        cost_time,
    )

    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="bulk_check_and_delete_ds_consul_config", status=TASK_FINISHED_SUCCESS, process_target=None
    ).inc()
    metrics.METADATA_CRON_TASK_COST_SECONDS.labels(
        task_name="bulk_check_and_delete_ds_consul_config", process_target=None
    ).observe(cost_time)
    metrics.report_all()


def _check_and_delete_ds_consul_config(data_source: DataSource):
    """
    检查V4数据源对应的Consul配置是否存在，若存在则进行删除
    @param data_source: 待检查的数据源
    """
    # 统计&上报 任务状态指标
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="_check_and_delete_ds_consul_config", status=TASK_STARTED, process_target=None
    ).inc()
    start_time = time.time()
    logger.info("_check_and_delete_ds_consul_config:async task start to check,data_id->[%s]", data_source.bk_data_id)

    # 非V4数据源，跳过
    if data_source.created_from != DataIdCreatedFromSystem.BKDATA.value:
        logger.warning(
            "_check_and_delete_ds_consul_config:data_source->[%s],not from bkdata,skip", data_source.bk_data_id
        )
        return

    # 获取Consul句柄及对应的返回值
    hash_consul = consul_tools.HashConsul()
    index, consul_value = hash_consul.get(data_source.consul_config_path)

    # 若Consul配置不存在，跳过
    if consul_value is None:
        logger.info(
            "_check_and_delete_ds_consul_config:data_source->[%s],consul_config not exist,skip", data_source.bk_data_id
        )
        return

    # 删除Consul配置
    data_source.delete_consul_config()

    cost_time = time.time() - start_time  # 总耗时
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="_check_and_delete_ds_consul_config", status=TASK_FINISHED_SUCCESS, process_target=None
    ).inc()
    metrics.METADATA_CRON_TASK_COST_SECONDS.labels(
        task_name="_check_and_delete_ds_consul_config", process_target=None
    ).observe(cost_time)
    metrics.report_all()

    logger.info("_check_and_delete_ds_consul_config:data_source->[%s],consul_config deleted", data_source.bk_data_id)


@app.task(ignore_result=True, queue="celery_metadata_task_worker")
def bulk_refresh_data_link_status(bkbase_rt_records):
    """
    并发刷新链路状态
    """
    # 统计&上报 任务状态指标
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="bulk_refresh_data_link_status", status=TASK_STARTED, process_target=None
    ).inc()

    start_time = time.time()  # 记录开始时间
    logger.info(
        "bulk_refresh_data_link_status: start to refresh data_link status, bkbase_rt_records: %s", bkbase_rt_records
    )
    with ThreadPoolExecutor(max_workers=10) as executor:
        executor.map(_refresh_data_link_status, bkbase_rt_records)
    cost_time = time.time() - start_time  # 总耗时
    logger.info("bulk_refresh_data_link_status: end to refresh data_link status, cost_time: %s", cost_time)

    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="bulk_refresh_data_link_status", status=TASK_FINISHED_SUCCESS, process_target=None
    ).inc()
    metrics.METADATA_CRON_TASK_COST_SECONDS.labels(
        task_name="bulk_refresh_data_link_status", process_target=None
    ).observe(cost_time)
    metrics.report_all()


def _refresh_data_link_status(bkbase_rt_record: BkBaseResultTable):
    """
    刷新链路状态（各组件状态+整体状态）
    @param bkbase_rt_record: BkBaseResultTable 计算平台结果表
    """
    # 统计&上报 任务状态指标
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="_refresh_data_link_status", status=TASK_STARTED, process_target=bkbase_rt_record.data_link_name
    ).inc()

    # 1. 获取基本信息
    start_time = time.time()  # 记录开始时间
    bkbase_data_id_name = bkbase_rt_record.bkbase_data_name
    data_link_name = bkbase_rt_record.data_link_name
    bkbase_rt_name = bkbase_rt_record.bkbase_rt_name
    logger.info(
        "_refresh_data_link_status: data_link_name->[%s],bkbase_data_id_name->[%s],bkbase_rt_name->[%s]",
        data_link_name,
        bkbase_data_id_name,
        bkbase_rt_name,
    )
    data_link_ins = models.DataLink.objects.get(data_link_name=data_link_name)
    data_link_strategy = data_link_ins.data_link_strategy
    logger.info(
        "_refresh_data_link_status: data_link_name->[%s] data_link_strategy->[%s]",
        data_link_name,
        data_link_strategy,
    )

    # 2. 刷新数据源状态
    try:
        with transaction.atomic():
            data_id_config = models.DataIdConfig.objects.get(name=bkbase_data_id_name)
            data_id_status = get_data_link_component_status(
                bk_tenant_id=bkbase_rt_record.bk_tenant_id,
                kind=data_id_config.kind,
                namespace=data_id_config.namespace,
                component_name=data_id_config.name,
            )
            # 当和DB中的数据不一致时，才进行变更
            if data_id_config.status != data_id_status:
                logger.info(
                    "_refresh_data_link_status:data_link_name->[%s],data_id_config status->[%s] is different "
                    "with exist record,will change to->[%s]",
                    data_link_name,
                    data_id_config.status,
                    data_id_status,
                )
                data_id_config.status = data_id_status
                data_id_config.data_link_name = data_link_name
                data_id_config.save()
            report_metadata_data_link_status_info(
                data_link_name=data_link_name,
                biz_id=data_id_config.bk_biz_id,
                kind=data_id_config.kind,
                status=data_id_config.status,
            )
    except models.DataIdConfig.DoesNotExist:
        logger.error(
            "_refresh_data_link_status: data_link_name->[%s],data_id_config->[%s] does not exist",
            data_link_name,
            bkbase_data_id_name,
        )

    # 3. 根据链路套餐（类型）获取该链路需要的组件资源种类
    components = models.DataLink.STRATEGY_RELATED_COMPONENTS.get(data_link_strategy)
    all_components_ok = True

    # 4. 遍历链路关联的所有类型资源，查询并刷新其状态
    for component in components:
        try:
            with transaction.atomic():
                component_ins = component.objects.get(name=bkbase_rt_name)
                component_status = get_data_link_component_status(
                    bk_tenant_id=bkbase_rt_record.bk_tenant_id,
                    kind=component_ins.kind,
                    namespace=component_ins.namespace,
                    component_name=component_ins.name,
                )
                logger.info(
                    "_refresh_data_link_status: data_link_name->[%s],component->[%s],kind->[%s],status->[%s]",
                    data_link_name,
                    component_ins.name,
                    component_ins.kind,
                    component_status,
                )
                if component_status != DataLinkResourceStatus.OK.value:
                    all_components_ok = False
                # 和DB中数据不一致时，才进行更新操作
                if component_ins.status != component_status:
                    component_ins.status = component_status
                    component_ins.save()
                    logger.info(
                        "_refresh_data_link_status: data_link_name->[%s],component->[%s],kind->[%s],"
                        "status updated to->[%s]",
                        data_link_name,
                        component.name,
                        component.kind,
                        component_status,
                    )

            report_metadata_data_link_status_info(
                data_link_name=data_link_name,
                biz_id=component_ins.bk_biz_id,
                kind=component_ins.kind,
                status=component_ins.status,
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.error(
                "_refresh_data_link_status: data_link_name->[%s],component->[%s],kind->[%s] refresh failed,error->[%s]",
                data_link_name,
                component.name,
                component.kind,
                e,
            )

    # 5. 如果所有的component_ins状态都为OK，那么BkBaseResultTable也应设置为OK，否则为PENDING
    if all_components_ok:
        bkbase_rt_record.status = DataLinkResourceStatus.OK.value
    else:
        bkbase_rt_record.status = DataLinkResourceStatus.PENDING.value
    with transaction.atomic():
        bkbase_rt_record.save()

    report_metadata_data_link_status_info(
        data_link_name=data_link_name,
        biz_id=data_id_config.bk_biz_id,
        kind=data_id_config.kind,
        status=bkbase_rt_record.status,
    )

    cost_time = time.time() - start_time

    logger.info(
        "_refresh_data_link_status: data_link_name->[%s],all_components_ok->[%s],status updated to->[%s]",
        data_link_name,
        all_components_ok,
        bkbase_rt_record.status,
    )

    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="_refresh_data_link_status",
        status=TASK_FINISHED_SUCCESS,
        process_target=bkbase_rt_record.data_link_name,
    ).inc()

    # 6. 上报指标
    metrics.METADATA_CRON_TASK_COST_SECONDS.labels(
        task_name="_refresh_data_link_status", process_target=bkbase_rt_record.data_link_name
    ).observe(cost_time)
    metrics.report_all()

    logger.info(
        "_refresh_data_link_status: data_link_name->[%s] refresh status finished,cost time->[%s]",
        data_link_name,
        cost_time,
    )


@app.task(ignore_result=True, queue="celery_metadata_task_worker")
def bulk_create_fed_data_link(sub_clusters):
    from metadata.models import DataSource, DataSourceResultTable

    logger.info("bulk_create_fed_data_link: start to bulk create fed datalinks for->[%s]", sub_clusters)
    for sub_cluster_id in sub_clusters:
        # 打印日志记录更新的子集群ID
        logger.info("bulk_create_fed_data_link: sub_cluster_id->[%s],start to create fed datalink", sub_cluster_id)
        try:
            sub_cluster = models.BCSClusterInfo.objects.get(cluster_id=sub_cluster_id)
            ds = DataSource.objects.get(bk_tenant_id=sub_cluster.bk_tenant_id, bk_data_id=sub_cluster.K8sMetricDataID)
            table_id = DataSourceResultTable.objects.get(
                bk_tenant_id=sub_cluster.bk_tenant_id, bk_data_id=sub_cluster.K8sMetricDataID
            ).table_id
            vm_cluster = get_vm_cluster_id_name(
                bk_tenant_id=sub_cluster.bk_tenant_id,
                space_type=SpaceTypes.BKCC.value,
                space_id=str(sub_cluster.bk_biz_id),
            )

            logger.info(
                "bulk_create_fed_data_link: sub_cluster_id->[%s],data_id->[%s],table_id->[%s]",
                sub_cluster_id,
                sub_cluster.K8sMetricDataID,
                table_id,
            )

            create_fed_bkbase_data_link(
                bk_biz_id=sub_cluster.bk_biz_id,
                monitor_table_id=table_id,
                data_source=ds,
                storage_cluster_name=vm_cluster.get("cluster_name"),
                bcs_cluster_id=sub_cluster.cluster_id,
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.error("update_fed_bkbase data_link failed, error->[%s]", e)
            continue


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

    # 处理 ES 信息
    es_info = bkbase_metadata_dict.get("es")
    if es_info and "es" not in skip_types:
        with transaction.atomic():  # 单独事务
            logger.info(
                "sync_bkbase_v4_metadata: got es_info->[%s],bk_data_id->[%s],try to sync es info", es_info, bk_data_id
            )
            # TODO: 这里需要特别注意,新版协议中，es_info中的数据结构是 {key:[info1,info2]},这里的key对应计算平台侧的RT,在监控平台这边不可读
            # TODO：考虑到目前日志链路中，不存在1个DataId关联多个ES结果表的场景，因此这里默认只选取第一条元素的value
            es_info_value = next(iter(es_info.values()))
            sync_es_metadata(bk_tenant_id=bk_tenant_id, es_info=es_info_value, table_id=table_id)
            logger.info("sync_bkbase_v4_metadata: sync es info for bk_data_id->[%s] successfully", bk_data_id)

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


@app.task(ignore_result=True, queue="celery_metadata_task_worker")
def create_basereport_datalink_for_bkcc(bk_tenant_id: str, bk_biz_id: int, storage_cluster_name: str | None = None):
    """
    为单个业务创建基础采集数据链路
    @param bk_tenant_id: 租户ID
    @param bk_biz_id: 业务ID
    @param storage_cluster_name: 存储集群名称(VM)
    """

    logger.info(
        "create_basereport_datalink_for_bkcc: start to create basereport datalink,for bk_biz_id->[%s]", bk_biz_id
    )

    if not settings.ENABLE_MULTI_TENANT_MODE:
        logger.error("create_basereport_datalink_for_bkcc: multi tenant mode is not enabled,return!")
        return

    # 获取默认VM集群
    if not storage_cluster_name:
        cluster_info = models.ClusterInfo.objects.filter(
            bk_tenant_id=bk_tenant_id, cluster_type=models.ClusterInfo.TYPE_VM, is_default_cluster=True
        ).last()
        if not cluster_info:
            logger.error("create_basereport_datalink_for_bkcc: get default vm cluster failed,return!")
            return
        storage_cluster_name = cluster_info.cluster_name

    # source -- 数据渠道 sys / dbm / devx / perforce
    source = BASEREPORT_SOURCE_SYSTEM

    # 数据源名称 & 数据链路名称 & DataBus名称 & DataId 名称
    data_name = f"{bk_tenant_id}_{bk_biz_id}_{source}_base"

    try:
        data_source = models.DataSource.objects.get(data_name=data_name, bk_tenant_id=bk_tenant_id)
        logger.info(
            "create_basereport_datalink_for_bkcc: data_source found,bk_biz_id->[%s],data_name->[%s],bk_data_id->[%s]",
            bk_biz_id,
            data_name,
            data_source.bk_data_id,
        )
    except models.DataSource.DoesNotExist:
        logger.info(
            "create_basereport_datalink_for_bkcc: data_source not found,try to create it,bk_biz_id->[%s],"
            "data_name->[%s]",
            bk_biz_id,
            data_name,
        )
        data_source = models.DataSource.create_data_source(
            data_name=data_name,
            bk_tenant_id=bk_tenant_id,
            etl_config=EtlConfigs.BK_MULTI_TENANCY_BASEREPORT_ETL_CONFIG.value,
            operator="system",
            source_label="bk_monitor",
            type_label="time_series",
            bk_biz_id=bk_biz_id,
            created_from=DataIdCreatedFromSystem.BKDATA.value,
        )
        logger.info(
            "create_basereport_datalink_for_bkcc: data_source created,bk_biz_id->[%s],data_name->[%s],bk_data_id->[%s]",
            bk_biz_id,
            data_name,
            data_source.bk_data_id,
        )

    # TASK1 -- 监控平台侧元信息逻辑: DataSource, ResultTable, DataSourceResultTable, ResultTableField
    try:
        with transaction.atomic():
            # ResultTable 结果表
            result_tables_to_create = []

            result_table_usage_mapping = [
                {
                    "usage": usage,
                    "table_id": f"{bk_tenant_id}_{bk_biz_id}_{source}.{usage}",
                    "table_name": f"{bk_tenant_id}_{bk_biz_id}_{source}_{usage}",
                }
                for usage in BASEREPORT_USAGES
            ]

            result_table_ids = [t["table_id"] for t in result_table_usage_mapping]
            existing_rts = set(
                models.ResultTable.objects.filter(table_id__in=result_table_ids).values_list("table_id", flat=True)
            )

            for table in result_table_usage_mapping:
                if table["table_id"] in existing_rts:  # 已存在
                    logger.info(
                        "create_basereport_datalink_for_bkcc: table_id->[%s] already exists,skip!", table["table_id"]
                    )
                    continue
                logger.info(
                    "create_basereport_datalink_for_bkcc: table_id->[%s] not exists,try to create!", table["table_id"]
                )
                result_tables_to_create.append(
                    models.ResultTable(
                        table_id=table["table_id"],
                        bk_tenant_id=bk_tenant_id,
                        bk_biz_id=bk_biz_id,
                        table_name_zh=table["table_name"],
                        is_custom_table=False,
                        default_storage=models.ClusterInfo.TYPE_VM,
                        creator="system",
                        label="os",
                    )
                )

            if result_tables_to_create:  # 如果有需要创建的结果表,则批量创建
                logger.info(
                    "create_basereport_datalink_for_bkcc: creating result tables,bk_biz_id->[%s],bk_tenant_id->[%s]",
                    bk_biz_id,
                    bk_tenant_id,
                )
                models.ResultTable.objects.bulk_create(result_tables_to_create)

            # DataSourceResultTable 数据源-结果表映射
            dsrt_to_create = []
            existing_dsrt = set(
                models.DataSourceResultTable.objects.filter(
                    bk_data_id=data_source.bk_data_id, table_id__in=result_table_ids, bk_tenant_id=bk_tenant_id
                ).values_list("table_id", flat=True)
            )

            for table_id in result_table_ids:
                if table_id in existing_dsrt:
                    logger.info(
                        "create_basereport_datalink_for_bkcc: table_id->[%s] dsrt relation already exists,skip",
                        table_id,
                    )
                    continue

                dsrt_to_create.append(
                    models.DataSourceResultTable(
                        bk_tenant_id=bk_tenant_id, bk_data_id=data_source.bk_data_id, table_id=table_id
                    )
                )

            if dsrt_to_create:  # 批量创建
                logger.info(
                    "create_basereport_datalink_for_bkcc: creating data_source_to_result_table relations,"
                    "bk_biz_id->[%s],bk_tenant_id->[%s]",
                    bk_biz_id,
                    bk_tenant_id,
                )
                models.DataSourceResultTable.objects.bulk_create(dsrt_to_create)

            # ResultTableField 结果表字段配置
            existing_fields_qs = models.ResultTableField.objects.filter(
                table_id__in=result_table_ids, bk_tenant_id=bk_tenant_id
            )
            existing_field_keys = set((f.table_id, f.field_name) for f in existing_fields_qs)
            rt_field_to_create = []

            for table_info in result_table_usage_mapping:
                fields = BASEREPORT_RESULT_TABLE_FIELD_MAP.get(table_info["usage"], [])

                for field in fields:
                    key = (table_info["table_id"], field["field_name"])
                    if key in existing_field_keys:  # 如果 RT-字段 已经存在,则跳过
                        logger.info(
                            "create_basereport_datalink_for_bkcc: field already exists,table_id->[%s],field_name->[%s]",
                            table_info["table_id"],
                            field["field_name"],
                        )
                        continue

                    rt_field_to_create.append(
                        models.ResultTableField(
                            table_id=table_info["table_id"],
                            bk_tenant_id=bk_tenant_id,
                            field_name=field["field_name"],
                            field_type=field["field_type"],
                            description=field.get("description", ""),
                            unit=field.get("unit", ""),
                            tag=field.get("tag", ""),
                            is_config_by_user=field.get("is_config_by_user", False),
                            default_value=field.get("default_value"),
                            creator="system",
                            alias_name=field.get("alias_name", ""),
                            is_disabled=field.get("is_disabled", False),
                        )
                    )

            if rt_field_to_create:  # 如果有需要创建的字段,则批量创建
                logger.info("create_basereport_datalink_for_bkcc: creating rt fields,table_ids->[%s]", result_table_ids)
                models.ResultTableField.objects.bulk_create(rt_field_to_create)
    except Exception as e:  # pylint: disable=broad-except
        logger.exception(
            "create_basereport_datalink_for_bkcc: failed to create basereport datalink,for bk_biz_id->[%s],error->[%s]",
            bk_biz_id,
            e,
        )
        return

    # TASK2 -- 计算平台V4链路部分
    logger.info(
        "create_basereport_datalink_for_bkcc: now try to create bkbase part,bk_biz_id->[%s],bk_tenant_id->["
        "%s],bk_data_id->[%s]",
        bk_biz_id,
        bk_tenant_id,
        data_source.bk_data_id,
    )

    # 1. 创建DataLink 链路管理实例
    logger.info(
        "create_basereport_datalink_for_bkcc: now try to create data link instance,bk_biz_id->[%s],"
        "data_link_name->[%s]",
        bk_biz_id,
        data_name,
    )
    data_link_ins, created = models.DataLink.objects.get_or_create(
        data_link_name=data_name,
        namespace="bkmonitor",
        data_link_strategy=models.DataLink.BASEREPORT_TIME_SERIES_V1,
        bk_tenant_id=bk_tenant_id,
    )

    # 2. 申请数据链路配置 VmResultTable, VmResultTableBinding, DataBus, ConditionalSink
    try:
        data_link_ins.apply_data_link(
            data_source=data_source, storage_cluster_name=storage_cluster_name, bk_biz_id=bk_biz_id, source=source
        )
        data_link_ins.sync_basereport_metadata(
            bk_biz_id=bk_biz_id, storage_cluster_name=storage_cluster_name, source=source, datasource=data_source
        )
        logger.info(
            "create_basereport_datalink_for_bkcc: data link applied successfully,for bk_biz_id->[%s]", bk_biz_id
        )
    except Exception as e:  # pylint: disable=broad-except
        logger.exception(
            "create_basereport_datalink_for_bkcc: failed to apply data link,for bk_biz_id->[%s],error->[%s]",
            bk_biz_id,
            e,
        )
        return

    logger.info(
        "create_basereport_datalink_for_bkcc: finished creating basereport datalink,for bk_biz_id->[%s]", bk_biz_id
    )


@app.task(ignore_result=True, queue="celery_metadata_task_worker")
def create_base_event_datalink_for_bkcc(bk_tenant_id: str, bk_biz_id: int, storage_cluster_name: str | None = None):
    """
    创建Agent基础事件数据链路
    @param bk_tenant_id: 租户ID
    @param bk_biz_id: 业务ID
    @param storage_cluster_name: 存储集群名称(ES)
    """

    logger.info("create_base_event_datalink_for_bkcc: try to create base event datalink for bk_biz_id->[%s]", bk_biz_id)

    if not settings.ENABLE_MULTI_TENANT_MODE:
        logger.error("create_base_event_datalink_for_bkcc: multi tenant mode is not enabled,return!")
        return

    if storage_cluster_name:
        storage_cluster_id = models.ClusterInfo.objects.get(
            bk_tenant_id=bk_tenant_id, cluster_name=storage_cluster_name
        ).cluster_id
    else:
        # TODO 这里需要区分ES集群是否在计算平台有注册
        default_es_cluster = models.ClusterInfo.objects.filter(
            bk_tenant_id=bk_tenant_id, cluster_type=models.ClusterInfo.TYPE_ES, is_default_cluster=True
        ).last()
        if not default_es_cluster:
            logger.error("create_base_event_datalink_for_bkcc: get default es cluster failed,return!")
            return
        storage_cluster_name = default_es_cluster.cluster_name
        storage_cluster_id = default_es_cluster.cluster_id

    space_uid = f"{SpaceTypes.BKCC.value}__{bk_biz_id}"

    data_name = f"base_{bk_biz_id}_agent_event"

    # 数据源
    try:
        data_source = models.DataSource.objects.get(data_name=data_name, bk_tenant_id=bk_tenant_id)
    except models.DataSource.DoesNotExist:
        logger.info(
            "create_base_event_datalink_for_bkcc: data source not found,for bk_biz_id->[%s],try to create it,"
            "data_name->[%s]",
            bk_biz_id,
            data_name,
        )
        data_source = models.DataSource.create_data_source(
            data_name=data_name,
            etl_config=EtlConfigs.BK_MULTI_TENANCY_AGENT_EVENT_ETL_CONFIG.value,
            operator="system",
            source_label="bk_monitor",
            type_label="event",
            space_uid=space_uid,
            bk_biz_id=bk_biz_id,
            bk_tenant_id=bk_tenant_id,
            created_from=DataIdCreatedFromSystem.BKDATA.value,
        )

    logger.info(
        "create_base_event_datalink_for_bkcc: data source created,for bk_biz_id->[%s],bk_data_id->[%s]",
        bk_biz_id,
        data_source.bk_data_id,
    )

    table_id = f"base_{bk_tenant_id}_{bk_biz_id}_event"

    # TASK1 -- 监控平台侧元信息逻辑: DataSource,ResultTable,ResultTableField,ResultTableOption,ESStorage,ResultTalbeFieldOption
    try:
        with transaction.atomic():
            rt_queryset = models.ResultTable.objects.filter(table_id=table_id, bk_tenant_id=bk_tenant_id)

            if not rt_queryset:
                result_table = models.ResultTable.objects.create(
                    table_id=table_id,
                    bk_tenant_id=bk_tenant_id,
                    default_storage=models.ClusterInfo.TYPE_ES,
                    table_name_zh=f"{bk_tenant_id}_{bk_biz_id}_基础事件",
                    is_custom_table=False,
                    schema_type="free",
                    creator="system",
                    label="os",
                    bk_biz_id=bk_biz_id,
                    data_label="system_event",
                )
            else:
                result_table = rt_queryset.first()

            logger.info(
                "create_base_event_datalink_for_bkcc: result_table created,table_id->[%s]", result_table.table_id
            )

            result_table_field_to_create = []
            existing_fields = list(
                models.ResultTableField.objects.filter(table_id=table_id, bk_tenant_id=bk_tenant_id).values_list(
                    "field_name", flat=True
                )
            )

            fields = BASE_EVENT_RESULT_TABLE_FIELD_MAP.get("base_event", [])

            for field in fields:
                if field["field_name"] in existing_fields:
                    continue

                result_table_field_to_create.append(
                    models.ResultTableField(
                        table_id=table_id,
                        bk_tenant_id=bk_tenant_id,
                        field_name=field["field_name"],
                        field_type=field["field_type"],
                        description=field.get("description", ""),
                        unit=field.get("unit", ""),
                        tag=field.get("tag", ""),
                        is_config_by_user=field.get("is_config_by_user", False),
                        default_value=field.get("default_value"),
                        creator="system",
                        alias_name=field.get("alias_name", ""),
                        is_disabled=field.get("is_disabled", False),
                    )
                )

            if result_table_field_to_create:
                logger.info("create_base_event_datalink_for_bkcc: creating rt fields,table_id->[%s]", table_id)
                models.ResultTableField.objects.bulk_create(result_table_field_to_create)

            # ResultTableOption
            result_table_option_to_create = []

            existing_options = list(
                models.ResultTableOption.objects.filter(table_id=table_id, bk_tenant_id=bk_tenant_id).values_list(
                    "name", flat=True
                )
            )

            options = BASE_EVENT_RESULT_TABLE_OPTION_MAP.get("base_event", [])
            for option in options:
                if option["name"] in existing_options:
                    continue

                result_table_option_to_create.append(
                    models.ResultTableOption(
                        table_id=table_id,
                        bk_tenant_id=bk_tenant_id,
                        value=option["value"],
                        value_type=option["value_type"],
                        name=option["name"],
                        creator=option["creator"],
                    )
                )

            if result_table_option_to_create:
                logger.info("create_base_event_datalink_for_bkcc: creating rt options,table_id->[%s]", table_id)
                models.ResultTableOption.objects.bulk_create(result_table_option_to_create)

            field_options = BASE_EVENT_RESULT_TABLE_FIELD_OPTION_MAP.get("base_event", [])
            field_option_to_create = []
            existing_options = list(
                models.ResultTableFieldOption.objects.filter(table_id=table_id, bk_tenant_id=bk_tenant_id).values_list(
                    "field_name", "name"
                )
            )

            for field_option in field_options:
                if (field_option["field_name"], field_option["name"]) in existing_options:
                    continue

                field_option_to_create.append(
                    models.ResultTableFieldOption(
                        table_id=table_id,
                        bk_tenant_id=bk_tenant_id,
                        value_type=field_option["value_type"],
                        value=field_option["value"],
                        field_name=field_option["field_name"],
                        name=field_option["name"],
                        creator=field_option["creator"],
                    )
                )

            if field_option_to_create:
                logger.info("create_base_event_datalink_for_bkcc: creating rt field options,table_id->[%s]", table_id)
                models.ResultTableFieldOption.objects.bulk_create(field_option_to_create)

            dsrt_qs = models.DataSourceResultTable.objects.filter(
                bk_data_id=data_source.bk_data_id, table_id=table_id, bk_tenant_id=bk_tenant_id
            )
            if not dsrt_qs:
                logger.info(
                    "create_base_event_datalink_for_bkcc: creating data_source_result_table relation for "
                    "bk_data_id->[%s],table_id->[%s],bk_biz_id->[%s]",
                    data_source.bk_data_id,
                    table_id,
                    bk_biz_id,
                )
                models.DataSourceResultTable.objects.create(
                    bk_data_id=data_source.bk_data_id, table_id=table_id, bk_tenant_id=bk_tenant_id
                )

            # ESStorage
            es_storage = models.ESStorage.objects.filter(table_id=table_id, bk_tenant_id=bk_tenant_id).first()
            if not es_storage:
                es_storage = models.ESStorage.objects.create(
                    table_id=table_id,
                    bk_tenant_id=bk_tenant_id,
                    date_format="%Y%m%d",
                    slice_size=500,
                    slice_gap=1440,
                    retention=30,
                    index_settings=json.dumps(
                        {
                            "number_of_shards": settings.SYSTEM_EVENT_DEFAULT_ES_INDEX_SHARDS,
                            "number_of_replicas": settings.SYSTEM_EVENT_DEFAULT_ES_INDEX_REPLICAS,
                        }
                    ),
                    mapping_settings='{"dynamic_templates":[{"discover_dimension":{"path_match":"dimensions.*","mapping":{"type":"keyword"}}}]}',
                    source_type="log",
                    need_create_index=True,
                    index_set=table_id,
                    storage_cluster_id=storage_cluster_id,
                )

            logger.info("create_base_event_datalink_for_bkcc: es storage created,table_id->[%s]", es_storage.table_id)
    except Exception as e:  # pylint: disable=broad-except
        logger.exception(
            "create_base_event_datalink_for_bkcc: create base event datalink for bk_biz_id->[%s] failed,error->[%s]",
            bk_biz_id,
            e,
        )
        return

    # TASK2 -- 计算平台V4链路部分
    logger.info(
        "create_base_event_datalink_for_bkcc: now try to create data link instance,bk_biz_id->[%s],data_link_name->[%s]",
        bk_biz_id,
        data_name,
    )

    # 1. 创建DataLink 链路管理实例
    logger.info(
        "create_base_event_datalink_for_bkcc: now try to create data link instance,bk_biz_id->[%s],data_link_name->[%s]",
        bk_biz_id,
        data_name,
    )
    data_link_ins, _ = models.DataLink.objects.get_or_create(
        data_link_name=data_name,
        data_link_strategy=models.DataLink.BASE_EVENT_V1,
        bk_tenant_id=bk_tenant_id,
        defaults={"namespace": "bklog"},
    )

    # 2. 申请数据链路配置 ResultTableConfig,ESStorageBindingConfig,DataBusConfig
    try:
        data_link_ins.apply_data_link(
            data_source=data_source, table_id=table_id, storage_cluster_name=storage_cluster_name, bk_biz_id=bk_biz_id
        )
        # 这里应该无需再次sync_metadata
    except Exception as e:  # pylint: disable=broad-except
        logger.exception(
            "create_base_event_datalink_for_bkcc: create base event datalink for bk_biz_id->[%s] failed,error->[%s]",
            bk_biz_id,
            e,
        )

    logger.info(
        "create_base_event_datalink_for_bkcc: create base event datalink for bk_biz_id->[%s] success", bk_biz_id
    )


def _get_bk_biz_internal_data_ids(bk_tenant_id: str, bk_biz_id: int) -> list[dict[str, int | str]]:
    """
    获取业务内置数据ID
    """
    result: list[dict[str, int | str]] = []

    # 系统指标
    system_metric_data_source = DataSource.objects.filter(data_name=f"{bk_tenant_id}_{bk_biz_id}_sys_base").first()
    if system_metric_data_source:
        result.append({"task": "basereport", "dataid": system_metric_data_source.bk_data_id})

    # 系统事件
    system_event_data_source = DataSource.objects.filter(data_name=f"base_{bk_biz_id}_agent_event").first()
    if system_event_data_source:
        result.append({"task": "exceptionbeat", "dataid": system_event_data_source.bk_data_id})

    # 系统进程
    system_proc_data_source = DataSource.objects.filter(
        data_name=SYSTEM_PROC_DATA_LINK_CONFIGS["perf"]["data_name_tpl"].format(bk_biz_id=bk_biz_id)
    ).first()
    if system_proc_data_source:
        result.append({"task": "processbeat_perf", "dataid": system_proc_data_source.bk_data_id})

    system_proc_port_data_source = DataSource.objects.filter(
        data_name=SYSTEM_PROC_DATA_LINK_CONFIGS["port"]["data_name_tpl"].format(bk_biz_id=bk_biz_id)
    ).first()
    if system_proc_port_data_source:
        result.append({"task": "processbeat_port", "dataid": system_proc_port_data_source.bk_data_id})

    return result


@app.task(ignore_result=True, queue="celery_metadata_task_worker")
def process_gse_slot_message(message_id: str, bk_agent_id: str, content: str, received_at: str):
    """
    Celery异步任务--处理GSE投递的数据

    {
        # type 格式为 "动作名称"/"影响范围"/"操作内容"
        "type": "fetch/host/dataid", # 请求类型，暂时只有一种，后续可能扩展
        "cloudid": 0, # 发起请求的采集器主机 cloudid
        "bk_agent_id": "02000000005254003dd2ea1700473962076n", # 发起请求的采集器主机 agentid
        "ip": "127.0.0.1", # 发起请求的采集器主机 ip
        "bk_tenant_id" : "my-tenant_id", # 采集器读到的 CMDB 下发的文件中的租户 ID
        "params": "..." # 请求参数，不同的 type 对应着不同的参数
    }

    type: fetch/host/dataid
    {
        # metadata 可以内置这批 tasks 的数据格式以及元信息等，编写成一个独立的任务。
        "tasks": [
            "basereport", # 原 1001 dataid
            "processbeat_perf", # 原 1007 dataid
            "processbeat_port", # 原 1013 dataid
            "global_heartbeat", # 原 1100001 dataid
            "gather_up_beat",  # 原 1100017 dataid
            "timesync", # 原 1100030 dataid
            "dmesg", # 原 1100031 dataid
            "exceptionbeat", # 原 1000 dataid
        ]
    }
    """
    from alarm_backends.core.cache.cmdb import HostManager

    try:
        content_data = json.loads(content)
    except (ValueError, TypeError):
        logger.error(
            "process_gse_slot_message: content is not a valid json, message_id->%s, bk_agent_id->%s, content->%s",
            message_id,
            bk_agent_id,
            content,
        )
        return

    # 解析Content，Content内容为采集器与Metadata约定的协议
    if content_data.get("type") == "fetch/host/dataid":
        logger.info("process_gse_slot_message: start to fetch host dataid")

        bk_tenant_id = content_data.get("bk_tenant_id")

        if not bk_tenant_id:
            logger.warning(
                "process_gse_slot_message: bk_tenant_id is not found,message_id->%s,content->%s",
                message_id,
                content,
            )
            return

        host = HostManager.get_by_agent_id(bk_tenant_id=bk_tenant_id, bk_agent_id=bk_agent_id)
        if not host:
            logger.warning(
                "process_gse_slot_message: host not found,bk_tenant_id->%s,bk_agent_id->%s",
                bk_tenant_id,
                bk_agent_id,
            )
            return

        result: list[dict[str, int | str]] = _get_bk_biz_internal_data_ids(
            bk_tenant_id=bk_tenant_id, bk_biz_id=host.bk_biz_id
        )

        # 回调GSE接口,告知DataId
        api.gse.dispatch_message(
            bk_tenant_id=bk_tenant_id,
            message_id=message_id,
            agent_id_list=[bk_agent_id],
            content=json.dumps({"code": 0, "data": result}),
        )
        logger.info(
            "process_gse_slot_message: callback gse interface,message_id->%s,bk_agent_id->%s,content->%s,received_at->%s,result->%s",
            message_id,
            bk_agent_id,
            content,
            received_at,
            result,
        )
    else:
        logger.warning(
            "process_gse_slot_message: unknown content type,message_id->%s,bk_agent_id->%s,content->%s,received_at->%s",
            message_id,
            bk_agent_id,
            content,
            received_at,
        )


@app.task(ignore_result=True, queue="celery_metadata_task_worker")
def create_system_proc_datalink_for_bkcc(bk_tenant_id: str, bk_biz_id: int, storage_cluster_name: str | None = None):
    """
    创建系统进程数据链路

    Args:
        bk_biz_id: 业务ID
        storage_cluster_name: 存储集群名称(ES)
    """

    logger.info(
        "create_system_proc_datalink_for_bkcc: try to create system proc datalink for bk_biz_id->[%s]", bk_biz_id
    )

    # 如果未开启多租户模式，则不创建
    if not settings.ENABLE_MULTI_TENANT_MODE:
        return

    # 如果未指定存储集群，则使用默认的VM集群
    if not storage_cluster_name:
        cluster = models.ClusterInfo.objects.filter(
            bk_tenant_id=bk_tenant_id, cluster_type=models.ClusterInfo.TYPE_VM, is_default_cluster=True
        ).last()
        if not cluster:
            logger.error("create_system_proc_datalink_for_bkcc: get default vm cluster failed,return!")
            return
        storage_cluster_name = cluster.cluster_name
    else:
        cluster = models.ClusterInfo.objects.get(bk_tenant_id=bk_tenant_id, cluster_name=storage_cluster_name)

    data_name_to_etl_config = {
        "perf": EtlConfigs.BK_MULTI_TENANCY_SYSTEM_PROC_PERF_ETL_CONFIG.value,
        "port": EtlConfigs.BK_MULTI_TENANCY_SYSTEM_PROC_PORT_ETL_CONFIG.value,
    }

    data_name_to_data_link_strategy = {
        "perf": models.DataLink.SYSTEM_PROC_PERF,
        "port": models.DataLink.SYSTEM_PROC_PORT,
    }

    # 创建数据源和结果表
    for data_link_type, data_link_config in SYSTEM_PROC_DATA_LINK_CONFIGS.items():
        data_name: str = data_link_config["data_name_tpl"].format(bk_biz_id=bk_biz_id)
        etl_config = data_name_to_etl_config[data_link_type]
        table_id: str = data_link_config["table_id_tpl"].format(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id)
        fields: list[dict[str, Any]] = data_link_config["fields"]

        # 创建数据源
        data_source = models.DataSource.objects.filter(data_name=data_name, bk_tenant_id=bk_tenant_id).first()
        if not data_source:
            logger.info(
                "create_system_proc_datalink_for_bkcc: data source not found,for bk_biz_id->[%s],data_name->[%s]",
                bk_biz_id,
                data_name,
            )
            data_source = models.DataSource.create_data_source(
                data_name=data_name,
                etl_config=etl_config,
                operator="system",
                source_label="bk_monitor",
                type_label="time_series",
                space_uid=f"{SpaceTypes.BKCC.value}__{bk_biz_id}",
                bk_biz_id=bk_biz_id,
                bk_tenant_id=bk_tenant_id,
                created_from=DataIdCreatedFromSystem.BKDATA.value,
            )

        # 创建结果表
        _, created = models.ResultTable.objects.update_or_create(
            table_id=table_id,
            bk_tenant_id=bk_tenant_id,
            defaults={
                "data_label": data_link_config["data_label"],
                "table_name_zh": data_name,
                "is_custom_table": False,
                "default_storage": models.ClusterInfo.TYPE_VM,
                "creator": "system",
                "label": "os",
                "bk_biz_id": bk_biz_id,
            },
        )
        if created:
            logger.info("create_system_proc_datalink_for_bkcc: result table created,table_id->[%s]", table_id)

        # 创建数据源结果表关联
        _, created = models.DataSourceResultTable.objects.update_or_create(
            bk_data_id=data_source.bk_data_id, table_id=table_id, bk_tenant_id=bk_tenant_id
        )
        if created:
            logger.info(
                "create_system_proc_datalink_for_bkcc: data source result table relation created,bk_data_id->[%s],table_id->[%s],bk_biz_id->[%s]",
                data_source.bk_data_id,
                table_id,
                bk_biz_id,
            )

        # 创建AccessVMRecord
        vm_rt = f"{bk_biz_id}_base_{bk_biz_id}_{data_name_to_data_link_strategy[data_link_type]}"
        AccessVMRecord.objects.update_or_create(
            bk_tenant_id=bk_tenant_id,
            result_table_id=table_id,
            bk_base_data_id=data_source.bk_data_id,
            bk_base_data_name=data_name,
            defaults={
                "vm_cluster_id": cluster.cluster_id,
                "storage_cluster_id": cluster.cluster_id,
                "vm_result_table_id": vm_rt,
            },
        )

        # 创建结果表字段
        result_table_field_to_create = []
        existing_fields = list(
            models.ResultTableField.objects.filter(table_id=table_id, bk_tenant_id=bk_tenant_id).values_list(
                "field_name", flat=True
            )
        )

        for field in fields:
            # 如果字段已存在，则跳过
            if field["field_name"] in existing_fields:
                continue

            result_table_field_to_create.append(
                models.ResultTableField(
                    table_id=table_id,
                    bk_tenant_id=bk_tenant_id,
                    field_name=field["field_name"],
                    field_type=field["field_type"],
                    description=field.get("description", ""),
                    unit=field.get("unit", ""),
                    tag=field.get("tag", ""),
                    is_config_by_user=field.get("is_config_by_user", False),
                    default_value=field.get("default_value"),
                    creator="system",
                    alias_name=field.get("alias_name", ""),
                    is_disabled=field.get("is_disabled", False),
                )
            )

        if result_table_field_to_create:
            logger.info("create_system_proc_datalink_for_bkcc: creating result table fields,table_id->[%s]", table_id)
            models.ResultTableField.objects.bulk_create(result_table_field_to_create)

        # 创建数据链路
        data_link_ins, _ = models.DataLink.objects.get_or_create(
            data_link_name=data_name,
            namespace="bkmonitor",
            data_link_strategy=data_name_to_data_link_strategy[data_link_type],
            bk_tenant_id=bk_tenant_id,
        )

        # 申请数据链路配置
        try:
            data_link_ins.apply_data_link(
                data_source=data_source,
                table_id=table_id,
                storage_cluster_name=storage_cluster_name,
                bk_biz_id=bk_biz_id,
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.exception(
                "create_system_proc_datalink_for_bkcc: create system proc datalink for bk_biz_id->[%s] failed,error->[%s]",
                bk_biz_id,
                e,
            )

    logger.info(
        "create_system_proc_datalink_for_bkcc: create system proc datalink for bk_biz_id->[%s] success", bk_biz_id
    )


def check_bkcc_space_builtin_datalink(biz_list: list[tuple[str, int]]):
    """
    检查业务内置数据链路
    """

    # 如果未开启新版数据链路或空间内置数据链路，则不检查
    if not (settings.ENABLE_V2_VM_DATA_LINK and settings.ENABLE_SPACE_BUILTIN_DATA_LINK) or not biz_list:
        return

    logger.info("check_bkcc_space_builtin_datalink: start to check bkcc space builtin datalink")

    # 获取已存在的数据源名称
    exists_data_names: set[str] = set(
        DataSource.objects.filter(
            Q(data_name__endswith="_agent_event")
            | Q(data_name__endswith="_sys_base")
            | Q(data_name__endswith="_system_proc_port")
            | Q(data_name__endswith="_system_proc_perf")
        ).values_list("data_name", flat=True)
    )

    # 获取已存在的DataLink名称
    data_link_name_to_namespaces: dict[str, str] = dict(DataLink.objects.values_list("data_link_name", "namespace"))

    # 数据源名称模板到任务的映射
    data_name_tpl_to_task: dict[tuple[str, tuple[str, ...]], Any] = {
        ("bkmonitor", ("{bk_tenant_id}_{bk_biz_id}_sys_base",)): create_basereport_datalink_for_bkcc,
        ("bklog", ("base_{bk_biz_id}_agent_event",)): create_base_event_datalink_for_bkcc,
        ("bkmonitor", ("base_{bk_biz_id}_system_proc_port",)): create_system_proc_datalink_for_bkcc,
        ("bkmonitor", ("base_{bk_biz_id}_system_proc_perf",)): create_system_proc_datalink_for_bkcc,
    }

    # 遍历业务列表，检查是否存在对应的数据源名称，如果不存在，则执行对应任务创建数据源
    for bk_tenant_id, bk_biz_id in biz_list:
        for (namespace, data_name_tpls), task in data_name_tpl_to_task.items():
            data_names: list[str] = [
                data_name_tpl.format(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id) for data_name_tpl in data_name_tpls
            ]
            for data_name in data_names:
                if data_name not in exists_data_names:
                    logger.info(
                        "check_bkcc_space_builtin_datalink: data_source(%s) not found, bk_tenant_id->[%s], bk_biz_id->[%s], run task->[%s] to create",
                        data_name,
                        bk_tenant_id,
                        bk_biz_id,
                        task,
                    )
                    task(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id)
                    break

                if data_name not in data_link_name_to_namespaces:
                    # 如果数据链路不存在，则创建数据链路
                    logger.info(
                        "check_bkcc_space_builtin_datalink: data_link(%s) not found, bk_tenant_id->[%s], bk_biz_id->[%s], run task->[%s] to create",
                        data_name,
                        bk_tenant_id,
                        bk_biz_id,
                    )
                    task(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id)
                    break
                elif data_link_name_to_namespaces[data_name] != namespace:
                    # 如果数据链路存在，但命名空间不匹配，则调整命名空间后重建
                    datalink_ins = DataLink.objects.get(data_link_name=data_name)
                    datalink_ins.namespace = namespace
                    datalink_ins.save()
                    logger.info(
                        "check_bkcc_space_builtin_datalink: data_link(%s) namespace mismatch, bk_tenant_id->[%s], bk_biz_id->[%s], run task->[%s] to rebuild",
                        data_name,
                        bk_tenant_id,
                        bk_biz_id,
                        task,
                    )
                    for component_class in DataLink.STRATEGY_RELATED_COMPONENTS[datalink_ins.data_link_strategy]:
                        component_class.objects.filter(data_link_name=data_name).update(namespace=namespace)
                    task(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id)

    logger.info("check_bkcc_space_builtin_datalink: check bkcc space builtin datalink success")


def create_single_tenant_system_datalink(
    data_bk_biz_id: int | None = None, kafka_cluster_name: str = "kafka_outer_default"
):
    """创建单租户系统数据链路

    Note: 单租户全新部署的情况下，将1001指定为BKDATA来源的数据源，并将内置结果表指向固定的vmrt。
          清洗配置和vmrt内置生成

    Args:
        bk_biz_id: 业务ID
        kafka_cluster_name: 消息队列集群名称，默认使用kafka_outer_default
    """

    # 如果开启了多租户模式，则跳过
    if settings.ENABLE_MULTI_TENANT_MODE:
        logger.info("create_single_tenant_system_datalink: multi tenant mode is enabled,return!")
        return

    # 如果未指定业务ID，则使用默认业务ID
    if data_bk_biz_id is None:
        bk_biz_id = settings.DEFAULT_BKDATA_BIZ_ID
    else:
        bk_biz_id = data_bk_biz_id

    datasource = DataSource.objects.get(bk_data_id=settings.SNAPSHOT_DATAID)

    # 如果数据源创建来源不是BKDATA，则更新为BKDATA，停止transfer任务
    if datasource.created_from != DataIdCreatedFromSystem.BKDATA.value:
        datasource.created_from = DataIdCreatedFromSystem.BKDATA.value
        # 获取BKDATA使用的消息队列
        try:
            bkdata_mq_cluster = ClusterInfo.objects.get(
                cluster_type=ClusterInfo.TYPE_KAFKA, cluster_name=kafka_cluster_name
            )
        except ClusterInfo.DoesNotExist:
            logger.error(
                f"create_single_tenant_system_datalink: Kafka cluster with name '{kafka_cluster_name}' does not exist, aborting."
            )
            return
        datasource.mq_cluster_id = bkdata_mq_cluster.cluster_id
        # 删除consul配置
        datasource.delete_consul_config()
        # 注册到BKDATA
        datasource.register_to_bkbase(bk_biz_id=bk_biz_id, bkbase_data_name="basereport")
        datasource.save()

    # 获取默认的VM集群
    vm_cluster = ClusterInfo.objects.get(
        bk_tenant_id=datasource.bk_tenant_id, is_default_cluster=True, cluster_type=ClusterInfo.TYPE_VM
    )

    # 创建内置结果表对应的AccessVMRecord
    table_ids: list[str] = []
    for table in BASEREPORT_USAGES:
        table_id = f"system.{table}"
        table_ids.append(table_id)
        AccessVMRecord.objects.update_or_create(
            bk_tenant_id=datasource.bk_tenant_id,
            result_table_id=table_id,
            defaults={
                "data_type": AccessVMRecord.ACCESS_VM,
                "storage_cluster_id": vm_cluster.cluster_id,
                "bk_base_data_id": datasource.bk_data_id,
                "bk_base_data_name": datasource.data_name,
                "vm_result_table_id": f"{bk_biz_id}_sys_{table}",
            },
        )

    # 创建数据链路
    data_link_ins, _ = DataLink.objects.update_or_create(
        data_link_name="basereport",
        defaults={
            "data_link_strategy": DataLink.BASEREPORT_TIME_SERIES_V1,
            "namespace": BKBASE_NAMESPACE_BK_MONITOR,
            "bk_tenant_id": datasource.bk_tenant_id,
        },
    )
    data_link_ins.apply_data_link(
        data_source=datasource,
        storage_cluster_name=vm_cluster.cluster_name,
        bk_biz_id=bk_biz_id,
        source=BASEREPORT_SOURCE_SYSTEM,
        prefix=BASEREPORT_SOURCE_SYSTEM,
    )

    # 刷新查询路由表数据
    SpaceTableIDRedis().push_table_id_detail(bk_tenant_id=DEFAULT_TENANT_ID, table_id_list=table_ids, is_publish=True)
    SpaceTableIDRedis().push_multi_space_table_ids(
        spaces=list(Space.objects.filter(space_type_id=SpaceTypes.BKCC.value)),
        is_publish=True,
    )


def create_single_tenant_system_proc_datalink(
    data_bk_biz_id: int | None = None, kafka_cluster_name: str = "kafka_outer_default"
):
    """创建单租户系统进程数据链路

    Note: 单租户全新部署的情况下，将1007/1013指定为BKDATA来源的数据源，并将内置结果表指向固定的vmrt。
          清洗配置和vmrt内置生成

    Args:
        bk_biz_id: 业务ID
        kafka_cluster_name: 消息队列集群名称，默认使用kafka_outer_default
    """

    # 如果开启了多租户模式，则跳过
    if settings.ENABLE_MULTI_TENANT_MODE:
        logger.info("create_single_tenant_system_proc_datalink: multi tenant mode is enabled,return!")
        return

    # 如果未指定业务ID，则使用默认业务ID
    if data_bk_biz_id is None:
        bk_biz_id = settings.DEFAULT_BKDATA_BIZ_ID
    else:
        bk_biz_id = data_bk_biz_id

    # 获取默认的VM集群
    vm_cluster = ClusterInfo.objects.get(is_default_cluster=True, cluster_type=ClusterInfo.TYPE_VM)

    # 获取kafka集群
    try:
        bkdata_mq_cluster = ClusterInfo.objects.get(
            cluster_type=ClusterInfo.TYPE_KAFKA, cluster_name=kafka_cluster_name
        )
    except ClusterInfo.DoesNotExist:
        logger.error(
            f"create_single_tenant_system_proc_datalink: Kafka cluster with name '{kafka_cluster_name}' does not exist, aborting."
        )
        return

    # 数据ID到BKDATA数据源名称、数据链路策略的映射
    data_ids = [settings.PROCESS_PERF_DATAID, settings.PROCESS_PORT_DATAID]
    data_id_to_table_id = {
        settings.PROCESS_PERF_DATAID: "system.proc",
        settings.PROCESS_PORT_DATAID: "system.proc_port",
    }
    data_id_to_bkbase_data_name = {
        settings.PROCESS_PERF_DATAID: "system_proc_perf",
        settings.PROCESS_PORT_DATAID: "system_proc_port",
    }
    data_id_to_data_link_strategy = {
        settings.PROCESS_PERF_DATAID: DataLink.SYSTEM_PROC_PERF,
        settings.PROCESS_PORT_DATAID: DataLink.SYSTEM_PROC_PORT,
    }

    for data_id in data_ids:
        datasource = DataSource.objects.get(bk_data_id=data_id)
        if datasource.created_from != DataIdCreatedFromSystem.BKDATA.value:
            datasource.created_from = DataIdCreatedFromSystem.BKDATA.value
            # 切换到BKDATA使用的消息队列
            datasource.mq_cluster_id = bkdata_mq_cluster.cluster_id
            # 删除consul配置
            datasource.delete_consul_config()
            # 注册到BKDATA
            datasource.register_to_bkbase(bk_biz_id=bk_biz_id, bkbase_data_name=data_id_to_bkbase_data_name[data_id])
            datasource.save()

        # 创建内置结果表对应的AccessVMRecord
        AccessVMRecord.objects.update_or_create(
            bk_tenant_id=datasource.bk_tenant_id,
            result_table_id=data_id_to_table_id[data_id],
            defaults={
                "data_type": AccessVMRecord.ACCESS_VM,
                "storage_cluster_id": vm_cluster.cluster_id,
                "bk_base_data_id": datasource.bk_data_id,
                "bk_base_data_name": datasource.data_name,
                "vm_result_table_id": f"{bk_biz_id}_{data_id_to_bkbase_data_name[data_id]}",
            },
        )

        # 创建数据链路
        data_link_ins, _ = DataLink.objects.update_or_create(
            data_link_name=data_id_to_bkbase_data_name[data_id],
            defaults={
                "data_link_strategy": data_id_to_data_link_strategy[data_id],
                "namespace": BKBASE_NAMESPACE_BK_MONITOR,
                "bk_tenant_id": datasource.bk_tenant_id,
            },
        )
        data_link_ins.apply_data_link(
            data_source=datasource,
            storage_cluster_name=vm_cluster.cluster_name,
            bk_biz_id=bk_biz_id,
            table_id=data_id_to_table_id[data_id],
            prefix="",
        )

    # 刷新查询路由表数据
    SpaceTableIDRedis().push_table_id_detail(
        bk_tenant_id=DEFAULT_TENANT_ID, table_id_list=list(data_id_to_table_id.values()), is_publish=True
    )
    SpaceTableIDRedis().push_multi_space_table_ids(
        spaces=list(Space.objects.filter(space_type_id=SpaceTypes.BKCC.value)),
        is_publish=True,
    )
