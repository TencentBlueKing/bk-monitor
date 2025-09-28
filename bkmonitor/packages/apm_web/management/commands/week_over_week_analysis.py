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
import logging
import os
import tempfile
from collections import defaultdict
from datetime import datetime, timedelta

from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandParser

from apm_web.constants import ApmCacheKey
from constants.apm import TelemetryDataType

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Compare current week's data with last week's data and generate analysis results."

    def add_arguments(self, parser: CommandParser):
        parser.add_argument(
            "--current_date",
            type=str,
            help="Specify the current date in YYYYMMDD format.",
        )
        parser.add_argument(
            "--last_date",
            type=str,
            help="Specify the last date in YYYYMMDD format.",
        )
        parser.add_argument(
            "--output_file",
            type=str,
            help="Specify the output file path. If not provided, a temporary file will be used.",
        )

    def handle(self, *args, **options):
        """
        比较当前周与上一周的数据变化
        """
        logger.info("[WEEK_OVER_WEEK_ANALYSIS] command start")

        # 获取用户输入的日期
        current_date_str = options.get("current_date")
        last_date_str = options.get("last_date")

        # 验证日期格式和范围
        try:
            current_date = datetime.strptime(current_date_str, "%Y%m%d").date() if current_date_str else None
            last_date = datetime.strptime(last_date_str, "%Y%m%d").date() if last_date_str else None
        except ValueError:
            print("Error: Invalid date format. Please use YYYYMMDD format.")
            return

        # 定义有效日期范围（前七天）
        today = datetime.now().date()
        valid_dates = [(today - timedelta(days=i)).strftime("%Y%m%d") for i in range(1, 8)]

        if current_date and current_date_str not in valid_dates:
            print(f"Error: Current date must be one of {valid_dates}.")
            return

        if last_date and last_date_str not in valid_dates:
            print(f"Error: Last date must be one of {valid_dates}.")
            return

        current_date_str = (
            current_date_str if current_date_str else (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
        )
        last_date_str = last_date_str if last_date_str else (datetime.now() - timedelta(days=8)).strftime("%Y%m%d")
        # 使用用户输入的日期或默认值（前一天和上一周）
        current_week_key = ApmCacheKey.APP_APPLICATION_STATUS_KEY.format(date=current_date_str)
        last_week_key = ApmCacheKey.APP_APPLICATION_STATUS_KEY.format(date=last_date_str)

        current_week_data = cache.get(current_week_key)
        if not current_week_data:
            logger.warning(f"[WEEK_OVER_WEEK_ANALYSIS] current_date: {current_date_str} data not found")
            print(f"Warning: current_date: {current_date_str} data not found")
            return

        last_week_data = cache.get(last_week_key)
        if not last_week_data:
            logger.warning(f"[WEEK_OVER_WEEK_ANALYSIS] last_date: {last_date_str} data not found")
            print(f"Warning: last_date: {last_date_str} data not found")
            return

        current_week_data = json.loads(current_week_data)
        last_week_data = json.loads(last_week_data)

        biz_map = defaultdict(dict)
        for app_id, current_status in current_week_data.items():
            last_status = last_week_data.get(app_id, {})

            # 对比四种数据的状态
            data_types = [
                TelemetryDataType.TRACE.value,
                TelemetryDataType.METRIC.value,
                TelemetryDataType.LOG.value,
                TelemetryDataType.PROFILING.value,
            ]
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
                    **status_comparison,
                }

        logger.info("[WEEK_OVER_WEEK_ANALYSIS] command finished")

        # 创建文件并写入结果
        if options.get("output_file"):
            output_path = os.path.abspath(options["output_file"])
            with open(output_path, "w") as output_file:
                output_file.write(json.dumps(biz_map))
            print(f"Analysis result saved to: {output_path}")
        else:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as temp_file:
                temp_file.write(json.dumps(biz_map))
                temp_file_path = temp_file.name
            print(f"Analysis result saved to temporary file: {temp_file_path}")
