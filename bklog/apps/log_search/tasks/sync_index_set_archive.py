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
from apps.api import TransferApi
from apps.log_databus.constants import ArchiveInstanceType
from apps.log_databus.models import ArchiveConfig
from apps.utils.log import logger
from celery.task import task

from apps.utils.thread import MultiExecuteFunc


@task(ignore_result=True)
def sync_index_set_archive(index_set_id: int = None, to_delete_indexes: list = None, to_append_indexes: list = None):
    """
    更新索引集归档配置
    """
    logger.info(f"[sync_index_set_archive] params->{index_set_id} | {to_delete_indexes} | {to_append_indexes}")
    if not index_set_id or (not to_delete_indexes and not to_append_indexes):
        logger.info(f"[sync_index_set_archive] Ahead Return")
        return

    try:
        archive_obj = ArchiveConfig.objects.get(
            instance_id=int(index_set_id),
            instance_type=ArchiveInstanceType.INDEX_SET.value
        )
    except ArchiveConfig.DoesNotExist:
        logger.info(f"[sync_index_set_archive] index_set_id->[{index_set_id}] ArchiveConfig DoesNotExist")
        return

    snapshot_days = archive_obj.snapshot_days

    multi_execute_func = MultiExecuteFunc()
    if to_delete_indexes:
        to_delete_table_ids = [index["result_table_id"] for index in to_delete_indexes]
        for table_id in to_delete_table_ids:
            params = {"table_id": table_id}
            multi_execute_func.append(
                result_key="delete_result_table_snapshot",
                func=TransferApi.delete_result_table_snapshot,
                params=params
            )
        logger.info(f"[sync_index_set_archive] to_delete_table_ids->{to_delete_table_ids}")

    if to_append_indexes:
        to_append_table_ids = [index["result_table_id"] for index in to_append_indexes]
        multi_execute_func = MultiExecuteFunc()
        for table_id in to_append_table_ids:
            params = {
                "table_id": table_id,
                "snapshot_days": snapshot_days
            }
            multi_execute_func.append(
                result_key="modify_result_table_snapshot",
                func=TransferApi.modify_result_table_snapshot,
                params=params
            )
        logger.info(f"[sync_index_set_archive] to_append_table_ids->{to_append_table_ids}")

    multi_result = multi_execute_func.run()
    logger.info(f"[sync_index_set_archive] multi_result->{multi_result}")
