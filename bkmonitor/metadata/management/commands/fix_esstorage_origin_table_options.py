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

from metadata import models
from metadata.migration_util import backfill_esstorage_origin_table_options


class Command(BaseCommand):
    help = "Backfill ESStorage index_set and ResultTableOption for origin ES tables."

    def add_arguments(self, parser):
        parser.add_argument("--bk_tenant_id", type=str, default=None, help="指定租户 ID，不传则处理所有租户")
        parser.add_argument("--batch_size", type=int, default=500, help="批处理大小")
        parser.add_argument("--dry_run", action="store_true", help="只统计待修复数量，不写入数据库")

    def handle(self, *args, **options):
        stats = backfill_esstorage_origin_table_options(
            es_storage_model=models.ESStorage,
            result_table_model=models.ResultTable,
            result_table_option_model=models.ResultTableOption,
            bk_tenant_id=options["bk_tenant_id"],
            batch_size=options["batch_size"],
            dry_run=options["dry_run"],
        )

        self.stdout.write(
            "scanned: {scanned}, index_set_updated: {index_set_updated}, option_created: {option_created}, "
            "option_updated: {option_updated}, time_field_skipped: {time_field_skipped}".format(**stats)
        )
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("dry run, no database changes applied"))
        else:
            self.stdout.write(self.style.SUCCESS("fix esstorage origin table options success"))
