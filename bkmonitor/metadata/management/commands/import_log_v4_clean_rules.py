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

from metadata import models


class Command(BaseCommand):
    """
    从 JSON 文件导入日志 V4 清洗规则到 ResultTableOption

    使用场景：
    配合 bklog 侧的 fix_log_v4_clean_rules 命令使用。
    先在 bklog pod 中运行 fix_log_v4_clean_rules 生成 JSON 文件，
    再在 monitor-api pod 中运行此命令导入 ResultTableOption。

    使用方法：
    python manage.py import_log_v4_clean_rules --input /tmp/clean_rules.json
    python manage.py import_log_v4_clean_rules --input /tmp/clean_rules.json
    """

    help = "import log v4 clean rules from json file into ResultTableOption"

    def add_arguments(self, parser):
        parser.add_argument(
            "--input",
            type=str,
            required=True,
            help="由 bklog 侧 fix_log_v4_clean_rules 命令导出的 JSON 文件路径",
        )

    def handle(self, *args, **options):
        input_path = options["input"]

        # 1. 读取 JSON 文件
        try:
            with open(input_path, "r", encoding="utf-8") as f:
                entries = json.load(f)
        except FileNotFoundError:
            raise CommandError(f"文件不存在：{input_path}")
        except json.JSONDecodeError as e:
            raise CommandError(f"JSON 解析失败：{e}")

        if not isinstance(entries, list):
            raise CommandError("JSON 文件内容应为数组格式")

        self.stdout.write(f"[开始] 读取到 {len(entries)} 条记录")

        success_count = 0
        failed_count = 0

        for entry in entries:
            bk_data_id = entry.get("bk_data_id")
            table_id = entry.get("table_id")
            v4_config = entry.get("v4_config")

            if not table_id or v4_config is None:
                failed_count += 1
                self.stdout.write(self.style.ERROR(f"[跳过] data_id={bk_data_id}: 缺少 table_id 或 v4_config"))
                continue

            try:
                self._import_single_entry(bk_data_id, table_id, v4_config)
                success_count += 1
            except Exception as e:
                failed_count += 1
                self.stdout.write(self.style.ERROR(f"[失败] data_id={bk_data_id}, table_id={table_id}: {str(e)}"))

        self.stdout.write(self.style.SUCCESS(f"\n[完成] 成功：{success_count}, 失败：{failed_count}"))

    def _import_single_entry(self, bk_data_id: int, table_id: str, v4_config: dict):
        """导入单条 clean_rules 到 ResultTableOption"""

        # 从 ResultTable 获取 bk_tenant_id
        try:
            result_table = models.ResultTable.objects.get(table_id=table_id)
            bk_tenant_id = result_table.bk_tenant_id
        except models.ResultTable.DoesNotExist:
            # 如果找不到，使用默认值
            bk_tenant_id = "system"

        option_name = models.ResultTableOption.OPTION_V4_LOG_DATA_LINK
        option_value = json.dumps(v4_config)

        self.stdout.write(
            f"\n[处理] data_id={bk_data_id}, table_id={table_id}, "
            f"bk_tenant_id={bk_tenant_id}, clean_rules={len(v4_config.get('clean_rules', []))} 条"
        )


        models.ResultTableOption.objects.update_or_create(
            bk_tenant_id=bk_tenant_id,
            table_id=table_id,
            name=option_name,
            defaults={
                "value": option_value,
                "value_type": models.ResultTableOption.TYPE_STRING,
                "creator": "import_log_v4_clean_rules",
            },
        )

        self.stdout.write(self.style.SUCCESS(f"  - ResultTableOption 写入成功"))
