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
import csv
import time
from io import StringIO

from django.conf import settings

from apps.api import UnifyQueryApi
from apps.log_search.constants import MAX_RESULT_WINDOW, MAX_ASYNC_COUNT
from apps.log_unifyquery.handler.base import UnifyQueryHandler


class UnifyQueryChartHandler(UnifyQueryHandler):
    def __init__(self, params):
        self.sql = params["sql"]
        super().__init__(params)

    def init_base_dict(self):
        # 拼接查询参数列表
        query_list = []
        for index, index_info in enumerate(self.index_info_list):
            query_dict = {
                "data_source": settings.UNIFY_QUERY_DATA_SOURCE,
                "reference_name": self.generate_reference_name(index),
                "conditions": self._transform_additions(index_info),
                "query_string": self.query_string,
                "sql": self.sql,
                "table_id": f"bklog_index_set_{index_info['index_set_id']}_analysis",
            }

            query_list.append(query_dict)

        return {
            "query_list": query_list,
            "metric_merge": " + ".join([query["reference_name"] for query in query_list]),
            "start_time": str(self.start_time),
            "end_time": str(self.end_time),
            "down_sample_range": "",
            "timezone": "UTC",  # 仅用于提供给 unify-query 生成读别名，对应存储入库时区
            "bk_biz_id": self.bk_biz_id,
        }

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
            "total_records": result.get("total", 0),
            "time_taken": time.time() - start_time,
            "result_schema": result_schema,
            "select_fields_order": [field["field_alias"] for field in result_schema],
        }

    def generate_sql(self):
        search_dict = copy.deepcopy(self.base_dict)
        search_dict["dry_run"] = True
        result = UnifyQueryApi.query_ts_raw(search_dict)
        result_table_options = list(result.get("result_table_options", {}).values())
        final_sql = result_table_options[0]["sql"] if result_table_options else ""

        return {
            "sql": self.sql,
            "additional_where_clause": final_sql,
        }

    def export_chart_data(self):
        search_params = copy.deepcopy(self.base_dict)
        search_params["limit"] = MAX_RESULT_WINDOW
        max_result_count = MAX_ASYNC_COUNT
        total_count = 0

        header_written = False  # 表头是否已经写入
        fields = []
        row_buffer = StringIO()
        csv_writer = csv.writer(row_buffer)
        while total_count < max_result_count:
            # 首次请求清空缓存
            search_params["clear_cache"] = total_count == 0
            search_result = UnifyQueryApi.query_ts_raw_with_scroll(search_params)
            if not search_result.get("list"):
                break
            # 写入表头
            if not header_written:
                result_table_options = list(search_result.get("result_table_options", {}).values())
                result_schema = result_table_options[0]["result_schema"] if result_table_options else []
                fields = [field["field_alias"] for field in result_schema]
                csv_writer.writerow(fields)
                header_written = True
            # 写入数据行到缓冲区
            for record in search_result["list"]:
                row_values = [record.get(field, "") for field in fields]
                csv_writer.writerow(row_values)
            # 获取缓冲区内容，重置缓冲区
            yield row_buffer.getvalue()
            row_buffer.seek(0)
            row_buffer.truncate()

            total_count += len(search_result["list"])
            if search_result.get("done", False):
                break
