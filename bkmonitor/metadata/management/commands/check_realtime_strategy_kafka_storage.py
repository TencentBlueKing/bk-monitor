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


from django.core.management.base import BaseCommand

from alarm_backends.core.cache.strategy import StrategyCacheManager
from metadata import models


class Command(BaseCommand):
    def handle(self, *args, **options):
        # 检测实时监控策略中对应rt的kafka存储是否创建, 没有创建则创建

        rt_ids = list(StrategyCacheManager.get_real_time_data_strategy_ids().keys())
        for table_id in rt_ids:
            if not models.storage.KafkaStorage.objects.filter(table_id=table_id).exists():
                models.storage.KafkaStorage.create_table(table_id, is_sync_db=True, **{"expired_time": 1800000})
                models.ResultTable.objects.get(table_id=table_id).refresh_etl_config()
                self.stdout.write(f"{table_id} kafka storage missing, created.")
        print("all realtime strategy storage check done.")
