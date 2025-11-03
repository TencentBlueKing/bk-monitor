"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
from typing import Any

from django.db.models import QuerySet, Q, Model

from django.db import migrations

from constants.apm import PreCalculateSpecificField, TRACE_RESULT_TABLE_OPTION, PRECALCULATE_RESULT_TABLE_OPTION
from metadata.migration_util import parse_value, sync_index_set_to_es_storages

logger = logging.getLogger("metadata")


DEFAULT_BATCH_SIZE: int = 1000

APM_PRECALCULATE_TABLE_PREFIX: str = "apm_global.precalculate_storage"


models: dict[str, type[Model] | None] = {"ESStorage": None, "ResultTable": None, "ResultTableOption": None}


def is_precalculate(table_id: str) -> bool:
    return table_id.startswith(APM_PRECALCULATE_TABLE_PREFIX)


def batch_sync_router(batch_size: int = DEFAULT_BATCH_SIZE):
    """分批同步检索路由"""
    queryset: QuerySet = (
        models["ResultTable"]
        .objects
        # 只过滤出 APM 相关的结果表。
        .filter(
            (Q(table_id__contains="bkapm") & Q(table_id__contains=".trace"))
            | Q(table_id__contains=APM_PRECALCULATE_TABLE_PREFIX)
        )
        .values("table_id", "bk_biz_id", "id", "bk_tenant_id")
        .order_by("table_id")
    )

    total: int = queryset.count()
    for begin_idx in range(0, total, batch_size):
        logger.info(
            "[sync_trace_unify_query_router] started with begin_idx: %s, batch_size: %s, total: %s.",
            begin_idx,
            batch_size,
            total,
        )
        result_table_infos: list[dict[str, Any]] = list(queryset[begin_idx : begin_idx + batch_size])
        sync_router(result_table_infos)


def sync_router(result_table_infos: list[dict[str, Any]]):
    table_ids: list[str] = []
    table_id__tenant_id_map: dict[str, str] = {}

    # Step-1: 预计算表默认按业务 ID 进行查询隔离。
    to_be_updated_rts = []
    for result_table_info in result_table_infos:
        table_id: str = result_table_info["table_id"]
        if is_precalculate(table_id=table_id):
            to_be_updated_rts.append(
                models["ResultTable"](
                    id=result_table_info["id"], bk_biz_id_alias=PreCalculateSpecificField.BIZ_ID.value
                )
            )

        table_ids.append(table_id)
        table_id__tenant_id_map[table_id] = result_table_info["bk_tenant_id"]

    if to_be_updated_rts:
        models["ResultTable"].objects.bulk_update(to_be_updated_rts, fields=["bk_biz_id_alias"])
    logger.info("[sync_trace_unify_query_router] update rt -> %s", len(to_be_updated_rts))

    # Step-2: ESStorage 指定索引集。
    sync_index_set_to_es_storages(models["ESStorage"], table_ids)

    # Step-3：设置查询选项，例如事件字段、是否在查询索引中增加日期等。
    rt_option_map: dict[str, Any] = {
        f"{_rt_option['bk_tenant_id']}-{_rt_option['table_id']}-{_rt_option['name']}": _rt_option
        for _rt_option in models["ResultTableOption"]
        .objects.filter(table_id__in=table_ids)
        .values("id", "table_id", "name", "bk_tenant_id")
    }
    to_be_created_rt_options = []
    to_be_updated_rt_options = []
    for table_id in table_ids:
        bk_tenant_id: str = table_id__tenant_id_map[table_id]

        if is_precalculate(table_id=table_id):
            result_table_options: dict[str, Any] = PRECALCULATE_RESULT_TABLE_OPTION
        else:
            result_table_options: dict[str, Any] = TRACE_RESULT_TABLE_OPTION

        for option_name, option_value in result_table_options.items():
            if option_name not in ["need_add_time", "time_field"]:
                continue

            value, value_type = parse_value(option_value)
            rt_option = models["ResultTableOption"](
                bk_tenant_id=bk_tenant_id, table_id=table_id, name=option_name, value=value, value_type=value_type
            )
            rt_option_key: str = f"{bk_tenant_id}-{table_id}-{option_name}"
            if rt_option_key in rt_option_map:
                rt_option.id = rt_option_map[rt_option_key]["id"]
                to_be_updated_rt_options.append(rt_option)
            else:
                to_be_created_rt_options.append(rt_option)

    if to_be_created_rt_options:
        models["ResultTableOption"].objects.bulk_create(to_be_created_rt_options)
    if to_be_updated_rt_options:
        models["ResultTableOption"].objects.bulk_update(to_be_updated_rt_options, fields=["value_type", "value"])

    logger.info(
        "[sync_trace_unify_query_router] update or create rt options: create -> %s, update -> %s",
        len(to_be_created_rt_options),
        len(to_be_updated_rt_options),
    )


def sync_trace_unify_query_router(apps, schema_editor):
    """直接调用 sync_event_es_route 方法执行同步"""

    # 初始化数据库模型。
    for model_name in list(models.keys()):
        models[model_name] = apps.get_model("metadata", model_name)

    # 进行同步。
    batch_sync_router()


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0223_merge_20250512_2000"),
    ]

    operations = [migrations.RunPython(code=sync_trace_unify_query_router)]
