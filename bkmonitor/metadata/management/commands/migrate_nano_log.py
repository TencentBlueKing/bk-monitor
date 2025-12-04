"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.core.management.base import BaseCommand

from metadata.task.migrate import migrate_nano_log_tables


class Command(BaseCommand):
    help = "migrate nano log"

    def add_arguments(self, parser):
        parser.add_argument("--bk_tenant_id", type=str, help="bk tenant id", default="system")
        parser.add_argument("--table_id", type=str, help="table id", required=True)

    def handle(self, *args, **options):
        table_id = options["table_id"]
        bk_tenant_id = options["bk_tenant_id"]

        migrate_results = migrate_nano_log_tables(bk_tenant_id=bk_tenant_id, table_ids=[table_id])

        success_table_ids = [table_id for table_id, result in migrate_results.items() if result[0]]
        failed_table_ids = [table_id for table_id, result in migrate_results.items() if not result[0]]

        self.stdout.write(self.style.SUCCESS(f"success table ids: {success_table_ids}"))
        self.stdout.write(self.style.ERROR(f"failed table ids: {failed_table_ids}"))
