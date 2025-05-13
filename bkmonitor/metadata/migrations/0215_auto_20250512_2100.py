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


def sync_trace_unify_query_router(apps, schema_editor):
    """直接调用 sync_event_es_route 方法执行同步"""
    from metadata.management.commands.sync_trace_unify_query_router import Command

    es_storage_model = apps.get_model("metadata", "ESStorage")
    result_table_model = apps.get_model("metadata", "ResultTable")
    result_table_option_model = apps.get_model("metadata", "ResultTableOption")
    Command.batch_sync_router(es_storage_model, result_table_model, result_table_option_model, push_now=False)


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0214_auto_20250427_1954"),
    ]

    operations = [migrations.RunPython(code=sync_trace_unify_query_router)]
