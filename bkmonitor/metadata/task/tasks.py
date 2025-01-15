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

import json
import logging
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils.translation import gettext as _
from tenacity import RetryError

from alarm_backends.service.scheduler.app import app
from core.prometheus import metrics
from metadata import models
from metadata.models import BkBaseResultTable, DataSource
from metadata.models.constants import DataIdCreatedFromSystem
from metadata.models.data_link.constants import DataLinkResourceStatus
from metadata.models.data_link.service import get_data_link_component_status
from metadata.models.space.constants import SpaceTypes
from metadata.models.vm.utils import (
    create_fed_bkbase_data_link,
    get_vm_cluster_id_name,
    report_metadata_data_link_status_info,
)
from metadata.task.utils import bulk_handle
from metadata.tools.constants import TASK_FINISHED_SUCCESS, TASK_STARTED
from metadata.utils import consul_tools
from metadata.utils.redis_tools import RedisTools

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
def access_to_bk_data_task(table_id):
    try:
        bkdata_storage = models.BkDataStorage.objects.get(table_id=table_id)
    except models.BkDataStorage.DoesNotExist:
        models.BkDataStorage.create_table(table_id, is_sync_db=True)
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
def create_full_cmdb_level_data_flow(table_id):
    try:
        bkdata_storage = models.BkDataStorage.objects.get(table_id=table_id)
    except models.BkDataStorage.DoesNotExist:
        raise Exception(_("数据({})未接入到计算平台，请先接入后再试").format(table_id))

    bkdata_storage.full_cmdb_node_info_to_result_table()


@app.task(ignore_result=True, queue="celery_metadata_task_worker")
def create_es_storage_index(table_id):
    """
    异步创建es索引
    """
    logger.info("table_id: %s start to create es index", table_id)
    try:
        es_storage = models.ESStorage.objects.get(table_id=table_id)
    except models.ESStorage.DoesNotExist:
        logger.info("table_id->[%s] not exists", table_id)
        return

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
def delete_es_result_table_snapshot(table_id, target_snapshot_repository_name):
    models.ESStorage.objects.get(table_id=table_id).delete_all_snapshot(target_snapshot_repository_name)


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
def manage_es_storage(es_storages, cluster_id: int = None):
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
        if not es_storage.index_settings or es_storage.index_settings == '{}':
            logger.error(
                "manage_es_storage:table_id->[%s] need to create index,but index_settings invalid", es_storage.table_id
            )
            return
        if not es_storage.mapping_settings or es_storage.mapping_settings == '{}':
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

        logger.info("manage_es_storage:es_storage->[{}] cron task success".format(es_storage.table_id))
    except RetryError as e:
        logger.error(
            "manage_es_storage:es_storage index lifecycle failed,table_id->{},error->{}".format(
                es_storage.table_id, e.__cause__
            )
        )
        logger.exception(e)
    except Exception as e:  # pylint: disable=broad-except
        # 记录异常集群的信息
        logger.error("manage_es_storage:es_storage index lifecycle failed,table_id->{}".format(es_storage.table_id))
        logger.exception(e)

    cost_time = time.time() - start_time

    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="_manage_es_storage", status=TASK_FINISHED_SUCCESS, process_target=es_storage.table_id
    ).inc()
    # 统计耗时，并上报指标
    metrics.METADATA_CRON_TASK_COST_SECONDS.labels(
        task_name="_manage_es_storage", process_target=es_storage.table_id
    ).observe(cost_time)
    metrics.report_all()


@app.task(ignore_result=True, queue="celery_metadata_task_worker")
def push_and_publish_space_router(
    space_type: Optional[str] = None,
    space_id: Optional[str] = None,
    table_id_list: Optional[List] = None,
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
        space_type = SpaceTypes.BKCC.value
        space_ids = models.Space.objects.filter(space_type_id=space_type).values_list("space_id", flat=True)
        # 拼装数据
        space_list = [{"space_type": space_type, "space_id": space_id} for space_id in space_ids]
        # 使用线程处理
        bulk_handle(multi_push_space_table_ids, space_list)

        # 通知到使用方
        push_redis_keys = [f"{space_type}__{space_id}" for space_id in space_ids]
        RedisTools.publish(SPACE_TO_RESULT_TABLE_CHANNEL, push_redis_keys)

    # 更新数据
    space_client.push_data_label_table_ids(table_id_list=table_id_list, is_publish=True)
    space_client.push_table_id_detail(table_id_list=table_id_list, is_publish=True)

    logger.info("push and publish space_type: %s, space_id: %s router successfully", space_type, space_id)


def multi_push_space_table_ids(space_list: List[Dict]):
    """批量推送数据"""
    logger.info("start to multi push space table ids")
    from metadata.models.space.space_table_id_redis import SpaceTableIDRedis

    space_client = SpaceTableIDRedis()
    for space in space_list:
        try:
            space_client.push_space_table_ids(space_type=space["space_type"], space_id=space["space_id"])
        except Exception as e:
            logger.error("push space to redis error, %s", e)

    logger.info("multi push space table ids successfully")


def _access_bkdata_vm(
    bk_biz_id: int,
    table_id: str,
    data_id: int,
    bcs_cluster_id: Optional[str] = None,
    allow_access_v2_data_link: Optional[bool] = False,
):
    """接入计算平台 VM 任务
    NOTE: 根据环境变量判断是否启用新版vm链路
    """
    from metadata.models.vm.utils import access_bkdata, access_v2_bkdata_vm

    # NOTE：只有当allow_access_v2_data_link为True，即单指标单表时序指标数据时，才允许接入V4链路
    if (settings.ENABLE_V2_VM_DATA_LINK and allow_access_v2_data_link) or (
        bcs_cluster_id and bcs_cluster_id in settings.ENABLE_V2_VM_DATA_LINK_CLUSTER_ID_LIST
    ):
        logger.info("_access_bkdata_vm: start to access v2 bkdata vm, table_id->%s, data_id->%s", table_id, data_id)
        access_v2_bkdata_vm(bk_biz_id=bk_biz_id, table_id=table_id, data_id=data_id)
    else:
        logger.info("_access_bkdata_vm: start to access bkdata vm, table_id->%s, data_id->%s", table_id, data_id)
        access_bkdata(bk_biz_id=bk_biz_id, table_id=table_id, data_id=data_id)


@app.task(ignore_result=True, queue="celery_metadata_task_worker")
def access_bkdata_vm(
    bk_biz_id: int,
    table_id: str,
    data_id: int,
    space_type: Optional[str] = None,
    space_id: Optional[str] = None,
    allow_access_v2_data_link: Optional[bool] = False,
):
    """接入计算平台 VM 任务"""
    logger.info("bk_biz_id: %s, table_id: %s, data_id: %s start access bkdata vm", bk_biz_id, table_id, data_id)
    try:
        from metadata.models import BCSClusterInfo

        # 查询`data_id`所在的集群 ID 在启用新链路的白名单中
        fq = Q(K8sMetricDataID=data_id) | Q(CustomMetricDataID=data_id) | Q(K8sEventDataID=data_id)
        obj = BCSClusterInfo.objects.filter(fq).first()
        bcs_cluster_id = obj.cluster_id if obj else None

        _access_bkdata_vm(
            bk_biz_id=bk_biz_id,
            table_id=table_id,
            data_id=data_id,
            bcs_cluster_id=bcs_cluster_id,
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

    push_and_publish_space_router(space_type, space_id, table_id_list=[table_id])

    # 更新数据源依赖的 consul
    try:
        # 保证有 backend，才进行更新
        if (
            settings.ENABLE_V2_VM_DATA_LINK
            or (bcs_cluster_id and bcs_cluster_id in settings.ENABLE_V2_VM_DATA_LINK_CLUSTER_ID_LIST)
        ) and models.DataSourceResultTable.objects.filter(bk_data_id=data_id).exists():
            data_source = models.DataSource.objects.get(bk_data_id=data_id, is_enable=True)
            data_source.refresh_consul_config()
    except models.DataSource.DoesNotExist:
        logger.error("data_id: %s not found for vm link, please check data_id status", data_id)

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
                kind=data_id_config.kind, namespace=data_id_config.namespace, component_name=data_id_config.name
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
                    kind=component_ins.kind, namespace=component_ins.namespace, component_name=component_ins.name
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
                "_refresh_data_link_status: data_link_name->[%s],component->[%s],kind->[%s] refresh failed,"
                "error->[%s]",
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
            ds = DataSource.objects.get(bk_data_id=sub_cluster.K8sMetricDataID)
            table_id = DataSourceResultTable.objects.get(bk_data_id=sub_cluster.K8sMetricDataID).table_id
            vm_cluster = get_vm_cluster_id_name(space_type=SpaceTypes.BKCC.value, space_id=str(sub_cluster.bk_biz_id))

            logger.info(
                "bulk_create_fed_data_link: sub_cluster_id->[%s],data_id->[%s],table_id->[%s]",
                sub_cluster_id,
                sub_cluster.K8sMetricDataID,
                table_id,
            )

            create_fed_bkbase_data_link(
                monitor_table_id=table_id,
                data_source=ds,
                storage_cluster_name=vm_cluster.get("cluster_name"),
                bcs_cluster_id=sub_cluster.cluster_id,
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.error("update_fed_bkbase data_link failed, error->[%s]", e)
            continue
