"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.db import migrations


OLD_SYNC_KEY = "GRAPH_RELATION_BKBASE_SYNC_BIZ_ID_WHITE_LIST"
OLD_QUERY_KEY = "GRAPH_RELATION_QUERY_V1BETA3_BIZ_ID_WHITE_LIST"
NEW_KEY = "GRAPH_RELATION_V4_BIZ_ID_WHITE_LIST"


def _normalize_biz_ids(raw_biz_ids) -> set[int]:
    if raw_biz_ids is None:
        return set()
    if isinstance(raw_biz_ids, str):
        values = raw_biz_ids.split(",")
    elif isinstance(raw_biz_ids, list | tuple | set):
        values = raw_biz_ids
    else:
        values = [raw_biz_ids]

    biz_ids = set()
    for value in values:
        try:
            biz_ids.add(int(str(value).strip()))
        except (TypeError, ValueError):
            continue
    return biz_ids


def migrate_graph_relation_v4_biz_id_white_list(apps, schema_editor):
    global_config = apps.get_model("bkmonitor", "GlobalConfig")
    keys = [OLD_SYNC_KEY, OLD_QUERY_KEY, NEW_KEY]
    configs = {config.key: config for config in global_config.objects.filter(key__in=keys)}

    old_sync_config = configs.get(OLD_SYNC_KEY)
    old_query_config = configs.get(OLD_QUERY_KEY)
    old_sync_biz_ids = _normalize_biz_ids(old_sync_config.value if old_sync_config else None)
    old_query_biz_ids = _normalize_biz_ids(old_query_config.value if old_query_config else None)
    # 仅保留原本已同时开启写入和查询的业务，避免迁移扩大灰度范围。
    migrated_value = sorted(old_sync_biz_ids & old_query_biz_ids)

    new_config = configs.get(NEW_KEY)
    if new_config:
        if new_config.value != migrated_value:
            new_config.value = migrated_value
            new_config.save(update_fields=["value"])
    else:
        global_config.objects.create(key=NEW_KEY, value=migrated_value)


class Migration(migrations.Migration):
    dependencies = [
        ("bkmonitor", "0203_add_via_issue_id_to_issue_merge_relation"),
    ]

    operations = [
        migrations.RunPython(migrate_graph_relation_v4_biz_id_white_list, migrations.RunPython.noop),
    ]
