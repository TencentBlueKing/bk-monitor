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
from apm.management.commands.sync_trace_unify_query_router import Command


def sync_trace_unifyquery_router(apps, schema_editor):
    Command.sync_router([], 10, apps.get_model("apm", "TraceDataSource"), apps.get_model("apm", "DataLink"))


class Migration(migrations.Migration):
    dependencies = [
        ("apm", "0048_auto_20250418_1123"),
    ]

    operations = [migrations.RunPython(code=sync_trace_unifyquery_router)]
