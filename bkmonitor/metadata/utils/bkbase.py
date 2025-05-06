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
import time
from django.db import transaction
from metadata import models
from metadata.models import ClusterInfo

logger = logging.getLogger("metadata")


def _sync_bkbase_result_table_meta(round_iter, bkbase_rt_meta_list):
    """
    同步BkBase RT元信息至Metadata
    @param round_iter: 当前任务轮次
    @param bkbase_rt_meta_list: BkBase RT元信息列表
    """
    logger.info(
        "sync_bkbase_result_table_meta: start syncing bkbase rt meta,round->[%s],data_size->[%s]",
        round_iter,
        len(bkbase_rt_meta_list),
    )

    start_time = time.time()
    try:
        existing_bkbase_result_tables = {
            result_table.table_id: result_table
            for result_table in models.ResultTable.objects.filter(default_storage=ClusterInfo.TYPE_BKDATA)
        }
        existing_bkbase_table_ids = list(existing_bkbase_result_tables)
        existing_bkbase_rt_fields = {
            (field.table_id, field.field_name): field
            for field in models.ResultTableField.objects.filter(table_id__in=existing_bkbase_table_ids)
        }

        # 存储需要批量创建的 ResultTable 和 ResultTableField
        result_table_to_create = []
        result_table_field_to_create = []

        for data in bkbase_rt_meta_list:
            # 提取result_table_id和bk_biz_id
            bkbase_result_table_id = data.get("result_table_id")

            # 存储在监控平台Metadata中的结果表ID后会拼接.__default__
            bkmonitor_result_table_id = f"{bkbase_result_table_id}.__default__"
            bk_biz_id = data.get("bk_biz_id")

            # 1. 批量处理 ResultTable
            if bkmonitor_result_table_id not in existing_bkbase_result_tables:
                result_table_to_create.append(
                    models.ResultTable(
                        table_id=bkmonitor_result_table_id,
                        table_name_zh=data.get("result_table_name"),
                        is_custom_table=False,
                        schema_type="free",
                        default_storage=ClusterInfo.TYPE_BKDATA,
                        creator="system",
                        last_modify_user="system",
                        bk_biz_id=bk_biz_id,
                    )
                )

            # 2. 处理 fields 中的字段，提取 is_dimension 为 False 的字段并创建/更新 ResultTableField
            for field in data.get("fields", []):
                if not field.get("is_dimension", False):
                    field_name = field.get("field_name")
                    field_type = field.get("field_type")

                    # 3. 批量处理 ResultTableField
                    if (bkmonitor_result_table_id, field_name) not in existing_bkbase_rt_fields:
                        result_table_field_to_create.append(
                            models.ResultTableField(
                                table_id=bkmonitor_result_table_id,
                                field_name=field_name,
                                field_type=field_type,
                                creator="system",
                                is_config_by_user=False,
                                tag="metric",
                            )
                        )

        # 使用事务和批量操作减少DB操作次数
        with transaction.atomic():
            if result_table_to_create:
                models.ResultTable.objects.bulk_create(result_table_to_create)
                logger.info(
                    "_sync_bkbase_result_table_meta: round->[%s],bulk created->[%s] ResultTable",
                    round_iter,
                    len(result_table_to_create),
                )

            if result_table_field_to_create:
                models.ResultTableField.objects.bulk_create(result_table_field_to_create)
                logger.info(
                    "_sync_bkbase_result_table_meta: round->[%s],bulk created->[%s] ResultTableField",
                    round_iter,
                    len(result_table_field_to_create),
                )
    except Exception as e:  # pylint: disable=broad-except
        logger.error(
            "_sync_bkbase_result_table_meta: failed to sync bkbase rt meta,round->[%s],error->[%s]", round_iter, e
        )
        logger.exception(e)
        return

    cost_time = time.time() - start_time

    logger.info(
        "sync_bkbase_result_table_meta: syncing bkbase rt meta finished,round->[%s],cost_time->[%s]",
        round_iter,
        cost_time,
    )
