"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from collections import defaultdict

from django.core.management.base import BaseCommand
from datetime import datetime, timedelta
import json
import logging
from django.core.cache import cache
import tempfile
from apm_web.constants import ApmCacheKey
from constants.apm import TelemetryDataType

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Compare current week's data with last week's data and generate analysis results."

    def handle(self, *args, **options):
        """
        比较当前周与上一周的数据变化
        """
        logger.info("[WEEK_OVER_WEEK_ANALYSIS] command start")
    
        # 获取当前周的数据
        current_week_key = ApmCacheKey.APP_APPLICATION_STATUS_KEY.format(date=datetime.now().strftime("%Y%m%d"))
        current_week_data = cache.get(current_week_key)
        if not current_week_data:
            logger.warning("[WEEK_OVER_WEEK_ANALYSIS] current week data not found")
            self.stdout.write("Warning: Current week data not found.")
            return
    
        # 获取上一周的数据
        last_week_date = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
        last_week_key = ApmCacheKey.APP_APPLICATION_STATUS_KEY.format(date=last_week_date)
        last_week_data = cache.get(last_week_key)
        if not last_week_data:
            logger.warning("[WEEK_OVER_WEEK_ANALYSIS] last week data not found")
            self.stdout.write("Warning: Last week data not found.")
            return
    
        current_week_data = json.loads(current_week_data)
        last_week_data = json.loads(last_week_data)

        biz_map = defaultdict(dict)
        for app_id, current_status in current_week_data.items():

            last_status = last_week_data.get(app_id, {})
    
            # 对比四种数据的状态
            data_types = [TelemetryDataType.TRACE.value,
                          TelemetryDataType.METRIC.value,
                          TelemetryDataType.LOG.value,
                          TelemetryDataType.PROFILING.value]
            status_comparison = {}
            for data_type in data_types:
                current_data_status = current_status.get(data_type)
                last_data_status = last_status.get(data_type)
                if current_data_status != last_data_status:
                    status_comparison[data_type] = {
                        "current_status": current_data_status,
                        "last_status": last_data_status,
                    }
            # 仅当有变化时才记录该应用的结果
            if status_comparison:
                bk_biz_id = current_status.get("bk_biz_id")
                biz_map[bk_biz_id][app_id] = {
                    "app_name": current_status.get("app_name"),
                    "app_alias": current_status.get("app_alias"),
                    **status_comparison
                }

        logger.info("[WEEK_OVER_WEEK_ANALYSIS] command finished")
        
        # 创建临时文件并写入结果
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            temp_file.write(json.dumps(biz_map))
            temp_file_path = temp_file.name
        self.stdout.write(f"Analysis result saved to temporary file: {temp_file_path}")