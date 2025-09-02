"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

"""
统计 { "状态" = "未恢复", "阶段" = "已确认" } 的告警数量
并打印

python manage.py total_alert.py --bk_biz_id=2
"""

from datetime import datetime, timedelta

from django.core.management.base import BaseCommand

from core.drf_resource import api
from packages.fta_web.alert.resources import SearchAlertResource


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--display_all", type=bool, default=False, help="是否显示全部业务")

    def handle(self, *args, **options):
        end_time = datetime.now()
        start_time = end_time - timedelta(days=5)
        display_all = options.get("display_all")

        #  获取业务信息
        biz_info = {biz.bk_biz_id: biz for biz in api.cmdb.get_business()}

        validated_request_data = {
            "bk_biz_ids": [],
            "status": ["NOT_SHIELDED_ABNORMAL"],
            "conditions": [{"key": "stage", "value": ["is_ack"]}],
            "query_string": "",
            "start_time": int(start_time.timestamp()),
            "end_time": int(end_time.timestamp()),
            "ordering": ["status"],
            "page": 1,
            "page_size": 5000,
            "show_overview": False,
            "show_aggs": False,
            "record_history": False,
        }

        biz_total = {}
        for bk_biz_id in biz_info.keys():
            validated_request_data["bk_biz_ids"] = [bk_biz_id]
            result = SearchAlertResource()(validated_request_data)
            biz_total[bk_biz_id] = result["total"]

        print("""按业务统计当前告警的数量
过滤条件: 
- 状态：未恢复
- 阶段：已确认

默认不输出告警为0的业务，如需显示全部，执行: python manage.py get_all_biz_alert_total --display_all=True

output:
业务id\t告警数量\t业务名称""")
        for biz in biz_info.values():
            bk_biz_id = biz.bk_biz_id
            bk_biz_name = biz.bk_biz_name
            if display_all:
                print(f"{bk_biz_id}\t{biz_total[bk_biz_id]}\t\t{bk_biz_name}")
            else:
                if biz_total[bk_biz_id] != 0:
                    print(f"{bk_biz_id}\t{biz_total[bk_biz_id]}\t\t{bk_biz_name}")
