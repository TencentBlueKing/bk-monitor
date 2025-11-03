"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.conf import settings
import logging
from typing import Any

from django.db.models import QuerySet, Model

from django.db import migrations

from metadata.migration_util import parse_value, sync_index_set_to_es_storages

logger = logging.getLogger("metadata")

models: dict[str, type[Model] | None] = {
    "DataSource": None,
    "EventGroup": None,
    "ESStorage": None,
    "ResultTable": None,
    "ResultTableOption": None,
}

DEFAULT_BATCH_SIZE: int = 1000

INNER_EVENT_GROUPS: list[dict[str, int | str]] = [
    {
        "table_id": "gse_system_event",
        "event_group_name": "gse system event",
        "bk_data_id": 1000,
        "bk_tenant_id": "system",
    },
    {
        "table_id": "gse_custom_string",
        "event_group_name": "gse custom string",
        "bk_data_id": 1100000,
        "bk_tenant_id": "system",
    },
]

RESULT_TABLE_OPTIONS = {"need_add_time": True, "time_field": {"name": "time", "type": "date", "unit": "millisecond"}}


def batch_sync_router(batch_size: int = DEFAULT_BATCH_SIZE):
    """分批同步检索路由"""
    queryset: QuerySet = (
        models["EventGroup"]
        .objects.filter(is_delete=False)
        .values("table_id", "event_group_name", "bk_data_id", "bk_tenant_id")
        .order_by("bk_data_id")
    )

    total: int = queryset.count()
    for begin_idx in range(0, total, batch_size):
        logger.info(
            "[sync_event_es_router] started with begin_idx: %s, batch_size: %s, total: %s.",
            begin_idx,
            batch_size,
            total,
        )
        sync_router(list(queryset[begin_idx : begin_idx + batch_size]))


def sync_router(event_groups: list[dict[str, Any]]):
    # 未开启多租户才变更内置的 DataID。
    if not settings.ENABLE_MULTI_TENANT_MODE:
        event_groups = event_groups + INNER_EVENT_GROUPS

    table_ids: list[str] = list({event_group["table_id"] for event_group in event_groups})
    platform_data_ids: set[str] = set(
        models["DataSource"]
        .objects.filter(is_platform_data_id=1, bk_data_id__in=[e["bk_data_id"] for e in event_groups])
        .values_list("bk_tenant_id", "bk_data_id")
    )

    # Step-1: ESStorage 指定索引集。
    sync_index_set_to_es_storages(models["ESStorage"], table_ids)

    # Step-2: 平台数据源默认按业务 ID 进行查询隔离，增加 system_event / k8s_event 作为查询别名。
    to_be_updated_rts = []
    key_result_table_obj_map: dict[tuple[str, str], Model] = {
        (rt_obj.bk_tenant_id, rt_obj.table_id): rt_obj
        for rt_obj in models["ResultTable"].objects.filter(table_id__in=table_ids)
    }
    for event_group in event_groups:
        table_id: str = event_group["table_id"]
        bk_tenant_id: str = event_group["bk_tenant_id"]
        event_group_name: str = event_group["event_group_name"]

        if (bk_tenant_id, table_id) not in key_result_table_obj_map:
            continue

        rt_obj = key_result_table_obj_map[(bk_tenant_id, table_id)]
        if (bk_tenant_id, event_group["bk_data_id"]) in platform_data_ids:
            rt_obj.bk_biz_id_alias = "dimensions.bk_biz_id"

        # k8s_event
        if event_group_name.startswith("bcs") and event_group_name.endswith("event"):
            rt_obj.data_label = "k8s_event"

        # system_event
        if table_id == "gse_system_event":
            rt_obj.data_label = "system_event"

        if rt_obj.data_label or rt_obj.bk_biz_id_alias:
            to_be_updated_rts.append(rt_obj)

    if to_be_updated_rts:
        models["ResultTable"].objects.bulk_update(to_be_updated_rts, fields=["bk_biz_id_alias", "data_label"])
    logger.info("[sync_trace_unify_query_router] update rt -> %s", len(to_be_updated_rts))

    # Step-3：设置查询选项，例如事件字段、是否在查询索引中增加日期等。
    rt_option_map: dict[str, Any] = {
        f"{_rt_option['bk_tenant_id']}-{_rt_option['table_id']}-{_rt_option['name']}": _rt_option
        for _rt_option in models["ResultTableOption"]
        .objects.filter(table_id__in=table_ids)
        .values("id", "table_id", "name", "bk_tenant_id")
    }
    to_be_created_rt_options = []
    to_be_updated_rt_options = []
    for event_group in event_groups:
        table_id: str = event_group["table_id"]
        bk_tenant_id: str = event_group["bk_tenant_id"]

        for option_name, option_value in RESULT_TABLE_OPTIONS.items():
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


def sync_event_es_router(apps, schema_editor):
    """直接调用 sync_event_es_route 方法执行同步"""

    # 初始化数据库模型。
    for model_name in list(models.keys()):
        models[model_name] = apps.get_model("metadata", model_name)

    # 进行同步。
    batch_sync_router()


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0224_auto_20250512_2100"),
    ]

    operations = [migrations.RunPython(code=sync_event_es_router)]
