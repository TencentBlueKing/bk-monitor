"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.core.management.base import BaseCommand, CommandError

from constants.common import DEFAULT_TENANT_ID
from metadata.models import ESStorage


class Command(BaseCommand):
    """将前一天的写别名移动到当前最新索引。"""

    help = "移动前一天的写别名到当前最新索引。默认仅在旧索引状态为 red 时执行；加 --force_move 可强制移动。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--table_id",
            type=str,
            required=True,
            help="结果表 ID，多个以半角逗号分隔",
        )
        parser.add_argument(
            "--bk_tenant_id",
            type=str,
            default=DEFAULT_TENANT_ID,
            help=f"租户 ID，默认 {DEFAULT_TENANT_ID}",
        )
        parser.add_argument(
            "--force_move",
            action="store_true",
            help="强制移动写别名；默认仅在旧索引状态为 red 时移动",
        )
        parser.add_argument(
            "--dry_run",
            action="store_true",
            help="只模拟执行，不实际更新别名",
        )

    def handle(self, *args, **options):
        table_ids = [table_id.strip() for table_id in options["table_id"].split(",") if table_id.strip()]
        if not table_ids:
            raise CommandError("参数 --table_id 不能为空")

        bk_tenant_id: str = options["bk_tenant_id"]
        force_move: bool = options["force_move"]
        dry_run: bool = options["dry_run"]

        es_storages = {
            es.table_id: es for es in ESStorage.objects.filter(table_id__in=table_ids, bk_tenant_id=bk_tenant_id)
        }
        missing_table_ids = [table_id for table_id in table_ids if table_id not in es_storages]
        if missing_table_ids:
            raise CommandError(f"未找到 ESStorage 配置, bk_tenant_id->[{bk_tenant_id}], table_ids->{missing_table_ids}")

        for table_id in table_ids:
            es_storage = es_storages[table_id]
            self.stdout.write(
                f"开始处理 table_id->[{table_id}], bk_tenant_id->[{bk_tenant_id}], "
                f"force_move->[{force_move}], dry_run->[{dry_run}]"
            )
            try:
                ESStorage.move_last_day_write_alias(
                    es_storage=es_storage,
                    force_move=force_move,
                    dry_run=dry_run,
                )
            except Exception as exc:  # pylint: disable=broad-except
                raise CommandError(f"处理 table_id->[{table_id}] 失败: {exc}") from exc

            self.stdout.write(self.style.SUCCESS(f"处理完成 table_id->[{table_id}]"))
