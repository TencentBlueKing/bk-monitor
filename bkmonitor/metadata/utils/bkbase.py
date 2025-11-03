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
from django.db import transaction
from metadata import models
from metadata.models import ClusterInfo
from metadata.task.constants import BKBASE_RT_STORAGE_TYPES_OPTION_NAME

logger = logging.getLogger("metadata")


def sync_bkbase_result_table_meta(round_iter, bkbase_rt_meta_list, biz_id_list):
    """
    同步BkBase RT元信息至Metadata
    @param round_iter: 当前任务轮次
    @param bkbase_rt_meta_list: BkBase RT元信息列表
    @param biz_id_list: 本轮处理的业务ID列表
    """
    logger.info(
        "sync_bkbase_result_table_meta: start syncing bkbase rt meta,round->[%s],data_size->[%s],biz_id_list->[%s]",
        round_iter,
        len(bkbase_rt_meta_list),
        biz_id_list,
    )

    start_time = time.time()
    try:
        # 这里指定业务ID列表作为过滤条件,避免全量拉取数据可能导致的性能问题
        existing_bkbase_result_tables = {
            result_table.table_id: result_table
            for result_table in models.ResultTable.objects.filter(
                default_storage=ClusterInfo.TYPE_BKDATA, bk_biz_id__in=biz_id_list
            )
        }
        existing_bkbase_table_ids = list(existing_bkbase_result_tables)
        existing_bkbase_rt_fields = {
            (field.table_id, field.field_name): field
            for field in models.ResultTableField.objects.filter(table_id__in=existing_bkbase_table_ids)
        }

        # 存储需要批量创建的 ResultTable 和 ResultTableField
        result_table_to_create = []
        result_table_field_to_create = []
        result_table_options = []

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
                field_name = field.get("field_name")
                field_type = field.get("field_type")
                is_dimension = field.get("is_dimension", False)

                if field_type in ["string", "text"]:
                    is_dimension = True

                tag = "dimension" if is_dimension else "metric"

                # 3. 批量处理 ResultTableField
                if (bkmonitor_result_table_id, field_name) not in existing_bkbase_rt_fields:
                    result_table_field_to_create.append(
                        models.ResultTableField(
                            table_id=bkmonitor_result_table_id,
                            field_name=field_name,
                            field_type=field_type,
                            creator="system",
                            is_config_by_user=False,
                            tag=tag,
                        )
                    )

            # 3. 记录结果表的存储类型,记录为列表
            storage_types = list(data.get("storages", {}).keys())
            result_table_options.append(
                {
                    "table_id": bkmonitor_result_table_id,
                    "name": BKBASE_RT_STORAGE_TYPES_OPTION_NAME,
                    "value_type": "list",
                    "value": json.dumps(storage_types),
                    "creator": "system",
                }
            )

        existing_options = models.ResultTableOption.objects.filter(
            name=BKBASE_RT_STORAGE_TYPES_OPTION_NAME, table_id__in=[opt["table_id"] for opt in result_table_options]
        )

        existing_options_dict = {opt.table_id: opt for opt in existing_options}

        options_to_create = []
        options_to_update = []

        for opt in result_table_options:
            existing_opt = existing_options_dict.get(opt["table_id"])
            if existing_opt:
                if existing_opt.value != opt["value"]:
                    existing_opt.value = opt["value"]
                    options_to_update.append(existing_opt)
            else:
                options_to_create.append(models.ResultTableOption(**opt))

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

            if options_to_create:
                models.ResultTableOption.objects.bulk_create(options_to_create)
                logger.info(
                    "_sync_bkbase_result_table_meta: round -> [%s], bulk created -> [%s] ResultTableOption",
                    round_iter,
                    len(options_to_create),
                )

            if options_to_update:
                models.ResultTableOption.objects.bulk_update(options_to_update, ["value"], batch_size=100)
                logger.info(
                    "_sync_bkbase_result_table_meta: round -> [%s], bulk updated -> [%s] ResultTableOption",
                    round_iter,
                    len(options_to_update),
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
