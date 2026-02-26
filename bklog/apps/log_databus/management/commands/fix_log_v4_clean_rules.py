# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

import json

from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _

from apps.log_databus.models import CollectorConfig, CleanStash
from apps.log_databus.handlers.etl_storage import EtlStorage
from apps.log_databus.handlers.collector_scenario import CollectorScenario
from apps.log_databus.constants import EtlConfig
from bkmonitor.metadata.models.result_table import ResultTable, ResultTableOption


class Command(BaseCommand):
    """
    修复日志 V4 清洗规则
    
    使用场景：
    当从 V3(Transfer) 迁移到 V4(BKBase) 链路时，如果因为脚本运行环境问题（如在 monitor-api pod 中无法导入 apps.log_databus）
    导致清洗规则使用了默认模板而非实际的采集项配置，可以使用此脚本重新生成正确的 clean_rules。
    
    使用方法：
    python manage.py fix_log_v4_clean_rules --data_id=1001
    python manage.py fix_log_v4_clean_rules --data_id=1001 --data_id=1002
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "--data_id",
            type=int,
            nargs="+",
            required=True,
            help="一个或多个需要修复的 bk_data_id，例如：--data_id=1001 或 --data_id=1001 1002 1003"
        )
        parser.add_argument(
            "--es_version",
            type=str,
            default="7",
            help="ES 版本号，默认为 7，可选值：7, 8 等"
        )

    def handle(self, **options):
        data_ids = options.get("data_id")
        es_version = options.get("es_version", "7")
        
        self.stdout.write(f"[开始] 修复 {len(data_ids)} 个 data_id 的 V4 清洗规则")
        self.stdout.write(f"[配置] ES 版本：{es_version}")
        
        success_count = 0
        failed_count = 0
        
        for bk_data_id in data_ids:
            try:
                self._fix_single_data_id(bk_data_id, es_version)
                success_count += 1
            except Exception as e:
                failed_count += 1
                self.stdout.write(self.style.ERROR(f"[失败] data_id={bk_data_id}: {str(e)}"))
        
        self.stdout.write(self.style.SUCCESS(f"\n[完成] 成功：{success_count}, 失败：{failed_count}"))

    def _fix_single_data_id(self, bk_data_id: int, es_version: str):
        """修复单个 data_id 的 V4 清洗规则"""
        
        # 1. 查找 CollectorConfig
        try:
            collector_config = CollectorConfig.objects.get(bk_data_id=bk_data_id)
        except CollectorConfig.DoesNotExist:
            raise Exception(f"未找到 bk_data_id={bk_data_id} 对应的 CollectorConfig")
        
        self.stdout.write(f"\n[处理] data_id={bk_data_id}, collector_config_id={collector_config.collector_config_id}")
        
        # 2. 查找 CleanStash（存储了原始的 etl_params 和 etl_fields）
        try:
            clean_stash = CleanStash.objects.get(collector_config_id=collector_config.collector_config_id)
        except CleanStash.DoesNotExist:
            raise Exception(f"未找到 collector_config_id={collector_config.collector_config_id} 对应的 CleanStash 记录")
        
        self.stdout.write(f"  - CleanStash 找到：clean_type={clean_stash.clean_type}")
        
        # 3. 获取 etl_config 类型
        etl_config = clean_stash.clean_type
        if etl_config not in [EtlConfig.BK_LOG_TEXT, EtlConfig.BK_LOG_JSON, 
                              EtlConfig.BK_LOG_DELIMITER, EtlConfig.BK_LOG_REGEXP]:
            raise Exception(f"不支持的 etl_config 类型：{etl_config}")
        
        # 4. 获取 CollectorScenario 和 built_in_config
        collector_scenario = CollectorScenario.get_instance(collector_scenario_id=collector_config.collector_scenario_id)
        built_in_config = collector_scenario.get_built_in_config(es_version=es_version, etl_config=etl_config)
        self.stdout.write(f"  - built_in_config 获取成功")
        
        # 5. 获取 EtlStorage 实例
        etl_storage = EtlStorage.get_instance(etl_config=etl_config)
        self.stdout.write(f"  - EtlStorage 实例获取成功：{etl_storage.__class__.__name__}")
        
        # 6. 生成 V4 clean_rules
        fields = clean_stash.etl_fields or []
        etl_params = clean_stash.etl_params or {}
        
        self.stdout.write(f"  - etl_fields 数量：{len(fields)}")
        self.stdout.write(f"  - etl_params 键：{list(etl_params.keys())}")
        
        v4_config = etl_storage.build_log_v4_data_link(
            fields=fields,
            etl_params=etl_params,
            built_in_config=built_in_config
        )
        
        self.stdout.write(f"  - clean_rules 数量：{len(v4_config.get('clean_rules', []))}")
        
        # 7. 写入 ResultTableOption
        table_id = collector_config.table_id
        if not table_id:
            raise Exception(f"collector_config 的 table_id 为空")
        
        # 从 ResultTable 获取 bk_tenant_id
        try:
            result_table = ResultTable.objects.get(table_id=table_id)
            bk_tenant_id = result_table.bk_tenant_id
        except ResultTable.DoesNotExist:
            # 如果找不到，使用默认值
            bk_tenant_id = "system"
        
        option_name = ResultTableOption.OPTION_V4_LOG_DATA_LINK
        
        ResultTableOption.objects.update_or_create(
            bk_tenant_id=bk_tenant_id,
            table_id=table_id,
            name=option_name,
            defaults={
                "value": json.dumps(v4_config),
                "value_type": ResultTableOption.TYPE_STRING,
                "creator": "fix_log_v4_clean_rules",
            }
        )
        
        self.stdout.write(self.style.SUCCESS(f"  - ResultTableOption 写入成功"))
        self.stdout.write(self.style.SUCCESS(f"[成功] data_id={bk_data_id} 修复完成"))
