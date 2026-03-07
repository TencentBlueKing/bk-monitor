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

from django.core.management.base import BaseCommand, CommandError

from bkmonitor.data_migrate import (
    apply_auto_increment_from_directory,
    export_biz_data_to_directory,
    import_biz_data_from_directory,
    replace_tenant_id_in_directory,
    sanitize_cluster_info_in_directory,
)


class Command(BaseCommand):
    help = "按目录结构导入导出监控业务迁移数据"

    def add_arguments(self, parser):
        parser.add_argument(
            "action",
            choices=["export", "import", "apply-sequences", "replace-tenant-id", "sanitize-cluster-info"],
            help="执行导出、导入、恢复游标或 handler 处理",
        )
        parser.add_argument("--directory", required=True, help="导出目录或导入目录")
        parser.add_argument(
            "--bk-biz-ids",
            nargs="+",
            type=int,
            help="导出时的业务 ID 列表，0 代表全局数据；仅 export 动作需要",
        )
        parser.add_argument("--format", default="json", help="导出文件格式，默认 json；仅 export 动作需要")
        parser.add_argument("--indent", type=int, default=2, help="导出文件缩进，默认 2；仅 export 动作需要")
        parser.add_argument(
            "--disable-atomic",
            action="store_true",
            help="导入时关闭按单文件事务处理；仅 import 动作需要",
        )
        parser.add_argument(
            "--biz-tenant-id-map",
            help='租户替换映射 JSON，形如 \'{"*":"tenant-a","2":"tenant-b"}\'；仅 replace-tenant-id 动作需要',
        )

    def handle(self, *args, **options):
        action = options["action"]
        directory = options["directory"]

        if action == "export":
            bk_biz_ids = options.get("bk_biz_ids") or []
            if not bk_biz_ids:
                raise CommandError("export 动作必须提供 --bk-biz-ids")

            export_biz_data_to_directory(
                directory_path=directory,
                bk_biz_ids=bk_biz_ids,
                format=options["format"],
                indent=options["indent"],
            )
            self.stdout.write(self.style.SUCCESS(f"export completed: {directory}"))
            return

        if action == "import":
            import_biz_data_from_directory(
                directory_path=directory,
                atomic=not options["disable_atomic"],
            )
            self.stdout.write(self.style.SUCCESS(f"import completed: {directory}"))
            return

        if action == "replace-tenant-id":
            raw_mapping = options.get("biz_tenant_id_map")
            if not raw_mapping:
                raise CommandError("replace-tenant-id 动作必须提供 --biz-tenant-id-map")
            try:
                loaded_mapping = json.loads(raw_mapping)
                biz_tenant_id_map = {
                    ("*" if str(biz_id) == "*" else int(biz_id)): tenant_id
                    for biz_id, tenant_id in loaded_mapping.items()
                }
            except (TypeError, ValueError, json.JSONDecodeError) as error:
                raise CommandError(f"--biz-tenant-id-map 不是合法 JSON 映射: {error}") from error

            replace_tenant_id_in_directory(
                directory_path=directory,
                biz_tenant_id_map=biz_tenant_id_map,
            )
            self.stdout.write(self.style.SUCCESS(f"replace tenant id completed: {directory}"))
            return

        if action == "sanitize-cluster-info":
            sanitize_cluster_info_in_directory(
                directory_path=directory,
            )
            self.stdout.write(self.style.SUCCESS(f"sanitize cluster info completed: {directory}"))
            return

        apply_auto_increment_from_directory(
            directory_path=directory,
        )
        self.stdout.write(self.style.SUCCESS(f"apply sequences completed: {directory}"))
