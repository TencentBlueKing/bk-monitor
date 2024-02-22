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
import traceback
from typing import Dict, List, Optional

from django.utils.translation import ugettext as _

from alarm_backends.service.scheduler.app import app
from metadata import models
from metadata.models.space.constants import SPACE_REDIS_KEY
from metadata.task.utils import bulk_handle
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
                "data_id->[%s], table_id->[%s] try to update ts metrics from redis failed, error->[%s], traceback_detail->[%s]",  # noqa
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


@app.task(ignore_result=True, queue="celery_report_cron")
def manage_es_storage(es_storages):
    # 遍历所有的ES存储并创建index, 并执行完整的es生命周期操作
    for es_storage in es_storages:
        try:
            # 先预创建各个时间段的index，
            # 1. 同时判断各个预创建好的index是否字段与数据库的一致
            # 2. 也判断各个创建的index是否有大小需要切片的需要

            if not es_storage.index_exist():
                #   如果该table_id的index在es中不存在，说明要走初始化流程
                logger.info("table_id->[%s] found no index in es,will create new one", es_storage.table_id)
                es_storage.create_index_and_aliases(es_storage.slice_gap)
            else:
                # 否则走更新流程
                es_storage.update_index_and_aliases(ahead_time=es_storage.slice_gap)

            # 创建快照
            es_storage.create_snapshot()
            # 清理过期的index
            es_storage.clean_index_v2()
            # 清理过期快照
            es_storage.clean_snapshot()
            # 重新分配索引数据
            es_storage.reallocate_index()

            logger.debug("es_storage->[{}] cron task success.".format(es_storage.table_id))
        except Exception:
            logger.info(
                "es_storage->[{}] failed to cron task for->[{}]".format(es_storage.table_id, traceback.format_exc())
            )


@app.task(ignore_result=True, queue="celery_metadata_task_worker")
def publish_redis(space_type_id: Optional[str] = None, space_id: Optional[str] = None, table_id: Optional[str] = None):
    """通知redis数据更新

    TODO: 待移除
    """
    from metadata.models.space.space_redis import (
        push_and_publish_all_space,
        push_redis_data,
    )
    from metadata.utils.redis_tools import RedisTools

    # 如果指定空间，则更新空间信息
    if space_type_id is not None and space_id is not None:
        push_redis_data(space_type_id, space_id, table_id=table_id)
        space_uid = f"{space_type_id}__{space_id}"
        RedisTools.publish(SPACE_REDIS_KEY, [space_uid])

        logger.info("%s push and publish successfully", space_uid)
        return

    push_and_publish_all_space()
    logger.info("push and publish all space successfully")


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


@app.task(ignore_result=True, queue="celery_metadata_task_worker")
def access_bkdata_vm(
    bk_biz_id: int, table_id: str, data_id: int, space_type: Optional[str] = None, space_id: Optional[str] = None
):
    """接入计算平台 VM 任务"""
    logger.info("bk_biz_id: %s, table_id: %s, data_id: %s start access bkdata vm", bk_biz_id, table_id, data_id)
    try:
        from metadata.models.vm.utils import access_bkdata

        access_bkdata(bk_biz_id=bk_biz_id, table_id=table_id, data_id=data_id)
    except Exception as e:
        logger.error(
            "bk_biz_id: %s, table_id: %s, data_id: %s access vm failed, error: %s", bk_biz_id, table_id, data_id, e
        )
        return

    push_and_publish_space_router(space_type, space_id, table_id_list=[table_id])

    logger.info("bk_biz_id: %s, table_id: %s, data_id: %s end access bkdata vm", bk_biz_id, table_id, data_id)


@app.task(ignore_result=True, queue="celery_metadata_task_worker")
def push_space_to_redis(space_type: str, space_id: str):
    """异步推送创建的空间到 redis"""
    logger.info("async task start to push space_type: %s, space_id: %s to redis", space_type, space_id)

    try:
        from metadata.models.space.constants import SPACE_REDIS_KEY
        from metadata.utils.redis_tools import RedisTools

        RedisTools.push_space_to_redis(SPACE_REDIS_KEY, [f"{space_type}__{space_id}"])
    except Exception as e:
        logger.error("async task push space to redis error, %s", e)
        return

    logger.info("async task push space_type: %s, space_id: %s to redis successfully", space_type, space_id)
