"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any
from django.core.management.base import BaseCommand, CommandParser

from constants.apm import TelemetryDataType

from apm_web.meta.resources import SetupResource
from apm_web.handlers.backend_data_handler import telemetry_handler_registry
from apm_web.models import Application


class Command(BaseCommand):
    help = "便捷修改 apm 应用的 trace 数据源选项"

    def add_arguments(self, parser: CommandParser):
        parser.add_argument("-b", "--bk_biz_id", type=int, help="业务 ID", required=True)
        parser.add_argument("-a", "--app_name", type=str, help="应用名称", required=True)
        parser.add_argument(
            "-cluster",
            "--es_storage_cluster",
            type=int,
            help="es 存储集群 ID",
        )
        parser.add_argument(
            "-retention",
            "--es_retention",
            type=int,
            help="es 存储周期 / 过期时间（天）",
        )
        parser.add_argument(
            "-replica",
            "--es_number_of_replicas",
            type=int,
            help="es 副本数量",
        )
        parser.add_argument(
            "-shard",
            "--es_shards",
            type=int,
            help="es 索引分片数",
        )
        parser.add_argument(
            "-slice_size",
            "--es_slice_size",
            type=int,
            help="es 索引切分大小",
        )

    def handle(self, *args, **options):
        # 更新应用的 trace 数据源选项
        app: Application = Application.objects.get(bk_biz_id=options["bk_biz_id"], app_name=options["app_name"])
        storage_info: dict[str, Any] = telemetry_handler_registry(TelemetryDataType.TRACE.value, app=app).storage_info()
        self.stdout.write(f"exists_storage_info: {storage_info}")
        for k in ["es_storage_cluster", "es_retention", "es_number_of_replicas", "es_shards", "es_slice_size"]:
            if options[k] is None:
                continue
            self.stdout.write(f"{k}: {storage_info[k]} -> {options[k]}")
            storage_info[k] = options[k]
        self.stdout.write(f"will_update_storage_info: {storage_info}")

        # 更新
        SetupResource().request(
            bk_biz_id=options["bk_biz_id"], application_id=app.application_id, trace_datasource_option=storage_info
        )
        self.stdout.write("Update success.")
