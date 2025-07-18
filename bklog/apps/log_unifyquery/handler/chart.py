"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import time

from apps.api import UnifyQueryApi
from apps.log_unifyquery.handler.base import UnifyQueryHandler


class UnifyQueryChartHandler(UnifyQueryHandler):
    def __init__(self, params):
        self.sql = params["sql"]
        super().__init__(params)

    def init_base_dict(self):
        base_dict = super().init_base_dict()
        for q in base_dict["query_list"]:
            q["sql"] = self.sql
            q["table_id"] = f"bkdata_{q['table_id'].split('_', 1)[1]}"

    def get_chart_data(self):
        start_time = time.time()
        data = UnifyQueryApi.query_ts_raw(self.base_dict)
        return {
            "list": data["list"],
            "total_records": data["total"],
            "time_taken": time.time() - start_time,
        }
