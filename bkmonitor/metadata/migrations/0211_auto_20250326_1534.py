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

from django.db import migrations


def sync_event_es_router(apps, schema_editor):
    """直接调用 sync_event_es_route 方法执行同步"""
    from metadata.management.commands.sync_event_es_router import Command

    EventGroup = apps.get_model("metadata", "EventGroup")
    queryset = EventGroup.objects.filter(is_delete=False).order_by("bk_data_id")

    batch_size = 1000
    total = queryset.count()
    for begin_idx in range(0, total, batch_size):
        print(f"[sync_event_es_router] start to sync_event_es_route: begin_idx -> {begin_idx}")
        Command.sync_event_es_route(
            list(queryset.values("table_id", "event_group_name", "bk_data_id")[begin_idx : begin_idx + batch_size]),
            push_now=False,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0210_spacerelatedstorageinfo"),
    ]

    operations = [migrations.RunPython(code=sync_event_es_router)]
