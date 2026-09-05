"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2026 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import itertools
import logging
import re
from collections import defaultdict

from django.db import migrations
from django.db.models import Q


logger = logging.getLogger("metadata")

BATCH_SIZE = 500
BIZ_EVENT_TABLE_ID_PATTERN = re.compile(r"^\d+_bkmonitor_event_\d+$")
CUSTOM_EVENT_TABLE_ID_PATTERN = re.compile(r"^(\d+_)?bkmonitor_event_\d+$")
NEED_ADD_TIME_VALUE = "true"
CUSTOM_EVENT_TIME_FIELD_VALUE = '{"name":"time","type":"date","unit":"millisecond"}'
DEFAULT_TIME_FIELD_VALUE = '{"name":"dtEventTimeStamp","type":"date","unit":"millisecond"}'


def query_table_options(result_table_option_model, database_alias, bk_tenant_id, table_ids, names):
    exists_options = {}
    for begin in range(0, len(table_ids), BATCH_SIZE):
        batch_table_ids = table_ids[begin : begin + BATCH_SIZE]
        options = (
            result_table_option_model.objects.using(database_alias)
            .filter(bk_tenant_id=bk_tenant_id, table_id__in=batch_table_ids, name__in=names)
            .only("table_id", "name", "value", "value_type")
        )
        for option in options:
            exists_options[(option.table_id, option.name)] = option
    return exists_options


def fill_esstorage_index_set(es_storage_model, database_alias, bk_tenant_id):
    es_storage_queryset = (
        es_storage_model.objects.using(database_alias)
        .filter(Q(index_set__isnull=True) | Q(index_set=""))
        .filter(Q(origin_table_id__isnull=True) | Q(origin_table_id=""))
        .filter(need_create_index=True, bk_tenant_id=bk_tenant_id)
        .exclude(table_id__startswith="bklog_index_set_")
    )

    update_objects = []
    for es_storage in es_storage_queryset.iterator(chunk_size=BATCH_SIZE):
        # 目标环境的 MySQL 不支持 REGEXP_LIKE，业务事件实体表在查询后通过 Python 正则排除。
        if BIZ_EVENT_TABLE_ID_PATTERN.match(es_storage.table_id):
            continue
        es_storage.index_set = es_storage.table_id.replace(".", "_")
        update_objects.append(es_storage)

    if update_objects:
        es_storage_model.objects.using(database_alias).bulk_update(
            update_objects,
            ["index_set"],
            batch_size=BATCH_SIZE,
        )

    return len(update_objects)


def fill_result_table_options(es_storage_model, result_table_option_model, database_alias, bk_tenant_id):
    es_storage_queryset = es_storage_model.objects.using(database_alias).filter(
        Q(origin_table_id__isnull=True) | Q(origin_table_id=""),
        need_create_index=True,
        bk_tenant_id=bk_tenant_id,
    )
    table_ids = [
        table_id
        for table_id in es_storage_queryset.values_list("table_id", flat=True).iterator(chunk_size=BATCH_SIZE)
        if not BIZ_EVENT_TABLE_ID_PATTERN.match(table_id)
    ]
    exists_options = query_table_options(
        result_table_option_model,
        database_alias,
        bk_tenant_id,
        table_ids,
        ["need_add_time", "time_field"],
    )

    need_add_time_options = []
    query_virtual_table_ids = []
    time_field_options = []
    for table_id in table_ids:
        if (table_id, "need_add_time") not in exists_options:
            need_add_time_options.append(
                result_table_option_model(
                    bk_tenant_id=bk_tenant_id,
                    table_id=table_id,
                    name="need_add_time",
                    value=NEED_ADD_TIME_VALUE,
                    value_type="bool",
                    creator="system",
                )
            )

        if (table_id, "time_field") in exists_options:
            continue
        if CUSTOM_EVENT_TABLE_ID_PATTERN.match(table_id):
            time_field_options.append(
                result_table_option_model(
                    bk_tenant_id=bk_tenant_id,
                    table_id=table_id,
                    name="time_field",
                    value=CUSTOM_EVENT_TIME_FIELD_VALUE,
                    value_type="dict",
                    creator="system",
                )
            )
            continue
        query_virtual_table_ids.append(table_id)

    if query_virtual_table_ids:
        virtual_tables = list(
            es_storage_model.objects.using(database_alias)
            .filter(bk_tenant_id=bk_tenant_id, origin_table_id__in=query_virtual_table_ids)
            .values_list("origin_table_id", "table_id")
        )
        origin_to_virtual_table_ids = defaultdict(list)
        for origin_table_id, virtual_table_id in virtual_tables:
            origin_to_virtual_table_ids[origin_table_id].append(virtual_table_id)

        virtual_table_options = query_table_options(
            result_table_option_model,
            database_alias,
            bk_tenant_id,
            list(itertools.chain.from_iterable(origin_to_virtual_table_ids.values())),
            ["time_field"],
        )
        for origin_table_id, virtual_table_ids in origin_to_virtual_table_ids.items():
            source_option = next(
                (
                    virtual_table_options[(virtual_table_id, "time_field")]
                    for virtual_table_id in virtual_table_ids
                    if (virtual_table_id, "time_field") in virtual_table_options
                ),
                None,
            )
            time_field_options.append(
                result_table_option_model(
                    bk_tenant_id=bk_tenant_id,
                    table_id=origin_table_id,
                    name="time_field",
                    value=source_option.value if source_option else DEFAULT_TIME_FIELD_VALUE,
                    value_type="dict",
                    creator="system",
                )
            )

    options_to_create = need_add_time_options + time_field_options
    if options_to_create:
        result_table_option_model.objects.using(database_alias).bulk_create(
            options_to_create,
            batch_size=BATCH_SIZE,
        )

    return len(options_to_create)


def backfill_esstorage_origin_table_options(apps, schema_editor):
    es_storage_model = apps.get_model("metadata", "ESStorage")
    result_table_option_model = apps.get_model("metadata", "ResultTableOption")
    database_alias = schema_editor.connection.alias

    bk_tenant_ids = list(
        es_storage_model.objects.using(database_alias)
        .filter(Q(origin_table_id__isnull=True) | Q(origin_table_id=""), need_create_index=True)
        .values_list("bk_tenant_id", flat=True)
        .distinct()
    )

    index_set_updated = 0
    option_created = 0
    for bk_tenant_id in bk_tenant_ids:
        index_set_updated += fill_esstorage_index_set(es_storage_model, database_alias, bk_tenant_id)
        option_created += fill_result_table_options(
            es_storage_model,
            result_table_option_model,
            database_alias,
            bk_tenant_id,
        )

    logger.info(
        "[fix_esstorage_origin_table_options] tenants: %s, index_set updated: %s, options created: %s",
        len(bk_tenant_ids),
        index_set_updated,
        option_created,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0276_custom_format_datalink"),
    ]

    operations = [
        migrations.RunPython(backfill_esstorage_origin_table_options, migrations.RunPython.noop),
    ]
