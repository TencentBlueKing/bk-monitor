"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
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
        return base_dict

    def get_chart_data(self):
        start_time = time.time()
        result = UnifyQueryApi.query_ts_raw(self.base_dict)
        for record in result["list"]:
            # 删除内置字段
            for key in ["__data_label", "__index", "__result_table"]:
                record.pop(key, None)

        result_table_options = list(result.get("result_table_options", {}).values())
        result_schema = result_table_options[0]["result_schema"] if result_table_options else []

        return {
            "list": result["list"],
            "total_records": result["total"],
            "time_taken": time.time() - start_time,
            "result_schema": result_schema,
        }

    def generate_sql(self):
        search_dict = copy.deepcopy(self.base_dict)
        search_dict["dry_run"] = True
        result = UnifyQueryApi.query_ts_raw(search_dict)
        result_table_options = list(result.get("result_table_options", {}).values())
        sql = result_table_options[0]["sql"] if result_table_options else ""
        return {
            "sql": sql,
            "additional_where_clause": sql,
        }
