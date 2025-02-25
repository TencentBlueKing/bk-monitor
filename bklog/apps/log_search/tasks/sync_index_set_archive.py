# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""
from blueapps.core.celery.celery import app

from apps.api import TransferApi
from apps.log_databus.constants import ArchiveInstanceType
from apps.log_databus.models import ArchiveConfig
from apps.log_search.models import LogIndexSetData
from apps.utils.log import logger
from apps.utils.thread import MultiExecuteFunc


@app.task(ignore_result=True)
def sync_index_set_archive(index_set_id: int = None):
    """
    更新索引集归档配置
    """
    if not index_set_id:
        logger.info("[sync_index_set_archive] index_set_id is None ~~ Ahead Return")
        return

    try:
        archive_obj = ArchiveConfig.objects.get(
            instance_id=int(index_set_id), instance_type=ArchiveInstanceType.INDEX_SET.value
        )
    except ArchiveConfig.DoesNotExist:
        logger.info(f"[sync_index_set_archive] index_set_id->{index_set_id} ArchiveConfig DoesNotExist")
        return

    snapshot_days = archive_obj.snapshot_days
    target_snapshot_repository_name = archive_obj.target_snapshot_repository_name

    index_set_data_objs = LogIndexSetData.origin_objects.filter(index_set_id=int(index_set_id))

    if not index_set_data_objs:
        logger.info(f"[sync_index_set_archive] index_set_id->{index_set_id} index_set_data_objs is None ~ Ahead Return")
        return

    all_table_ids = set()

    deleted_table_ids = set()

    normal_table_ids = set()

    for _obj in index_set_data_objs:
        if _obj.is_deleted:
            deleted_table_ids.add(_obj.result_table_id)
        elif _obj.apply_status == LogIndexSetData.Status.NORMAL:
            normal_table_ids.add(_obj.result_table_id)
        all_table_ids.add(_obj.result_table_id)

    try:
        logger.info(f"[sync_index_set_archive] index_set_id->{index_set_id}, all_table_ids->{all_table_ids}")
        snapshot_info, *_ = TransferApi.list_result_table_snapshot_indices({"table_ids": list(all_table_ids)})
        logger.info(f"[sync_index_set_archive] snapshot_info->{snapshot_info}")
    except Exception as e:  # pylint: disable=broad-except
        logger.error(f"[sync_index_set_archive] request list_result_table_snapshot_indices error->{e}")
        return

    archived_table_ids = [snapshot["table_id"] for snapshot in snapshot_info]
    logger.info(f"[sync_index_set_archive] archived_table_ids->{archived_table_ids}")

    multi_execute_func = MultiExecuteFunc()

    # 处理需要在metadata删除归档配置的table_id
    logger.info(f"[sync_index_set_archive] index_set_id->{index_set_id}, deleted_table_ids->{deleted_table_ids}")
    for deleted_table_id in deleted_table_ids:
        if deleted_table_id in archived_table_ids:
            params = {"table_id": deleted_table_id}
            multi_execute_func.append(
                result_key=f"delete_result_table_snapshot_{deleted_table_id}",
                func=TransferApi.delete_result_table_snapshot,
                params=params,
            )

    # 处理需要在metadata新增归档配置的table_id
    logger.info(f"[sync_index_set_archive] index_set_id->{index_set_id}, normal_table_ids->{normal_table_ids}")
    for normal_table_id in normal_table_ids:
        if normal_table_id not in archived_table_ids:
            params = {
                "table_id": normal_table_id,
                "target_snapshot_repository_name": target_snapshot_repository_name,
                "snapshot_days": snapshot_days,
            }
            multi_execute_func.append(
                result_key=f"create_result_table_snapshot_{normal_table_id}",
                func=TransferApi.create_result_table_snapshot,
                params=params,
            )

    if multi_execute_func.task_list:
        logger.info(f"[sync_index_set_archive] index_set_id->{index_set_id} update archive begin~~")
        multi_result = multi_execute_func.run()
        logger.info(f"[sync_index_set_archive] multi_result->{multi_result}")

    return
