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

import os

from django.utils.functional import cached_property

from apps.api import BkDataQueryApi
from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.tgpa.constants import (
    TGPA_REPORT_FILTER_FIELDS,
    TGPA_REPORT_SELECT_FIELDS,
    FEATURE_TOGGLE_TGPA_TASK,
    TGPA_BASE_DIR,
    TGPA_REPORT_LIST_BATCH_SIZE,
)
from apps.tgpa.handlers.base import TGPAFileHandler
from apps.utils.thread import MultiExecuteFunc


class TGPAReportHandler:
    """客户端日志上报"""

    def __init__(self, bk_biz_id, report_info):
        self.bk_biz_id = bk_biz_id
        self.report_info = report_info
        self.file_name = self.report_info["file_name"]
        self.temp_dir = os.path.join(TGPA_BASE_DIR, str(self.bk_biz_id), "report", self.file_name, "temp")
        self.output_dir = os.path.join(TGPA_BASE_DIR, str(self.bk_biz_id), "report", self.file_name, "output")

    @cached_property
    def meta_fields(self):
        """
        需要注入到日志中的元数据维度
        """
        return {
            "task_id": None,
            "task_name": None,
            "openid": self.report_info.get("openid"),
            "manufacturer": self.report_info.get("manufacturer"),
            "sdk_version": self.report_info.get("os_sdk"),
            "os_type": self.report_info.get("os_type"),
            "os_version": self.report_info.get("os_version"),
            "cos_file_name": self.report_info["file_name"],
        }

    def download_and_process_file(self):
        """
        下载并处理文件
        """
        file_handler = TGPAFileHandler(self.temp_dir, self.output_dir, self.meta_fields)
        file_handler.download_and_process_file(self.file_name)

    @classmethod
    def _build_where_clause(cls, bk_biz_id, keyword=None, openid=None, file_name=None, start_time=None, end_time=None):
        """
        构建SQL WHERE子句
        """
        where_conditions = [f"cc_id={bk_biz_id}"]

        if keyword:
            keyword_conditions = [f"{field} like '%{keyword}%'" for field in TGPA_REPORT_FILTER_FIELDS]
            where_conditions.append(f"({' OR '.join(keyword_conditions)})")
        if start_time:
            where_conditions.append(f"dtEventTimeStamp >= '{start_time}'")
        if end_time:
            where_conditions.append(f"dtEventTimeStamp < '{end_time}'")
        if openid:
            where_conditions.append(f"openid='{openid}'")
        if file_name:
            where_conditions.append(f"file_name='{file_name}'")

        return " AND ".join(where_conditions)

    @classmethod
    def get_report_list(cls, params):
        """
        获取客户端日志上报文件列表
        """
        # 获取配置
        feature_toggle = FeatureToggleObject.toggle(FEATURE_TOGGLE_TGPA_TASK)
        feature_config = feature_toggle.feature_config
        result_table_id = feature_config.get("tgpa_report_result_table_id")
        download_url_prefix = feature_config.get("download_url_prefix", "")

        # 计算分页参数
        limit = params["pagesize"]
        offset = (params["page"] - 1) * limit

        # WHERE子句，这里时间范围过滤使用 dtEventTimeStamp，排序使用report_time，和TGPA保持一致
        where_clause = cls._build_where_clause(
            bk_biz_id=params["bk_biz_id"],
            keyword=params.get("keyword"),
            start_time=params.get("start_time"),
            end_time=params.get("end_time"),
        )
        # ORDER_BY子句
        order_by_clause = "report_time DESC"
        if params.get("order_field") and params.get("order_type"):
            if params["order_field"] == "file_size":
                order_by_clause = f"CAST(file_size AS INT) {params['order_type']}" + order_by_clause
            else:
                order_by_clause = f"{params['order_field']} {params['order_type']}" + order_by_clause

        query_count_sql = f"SELECT count(*) AS total FROM {result_table_id} WHERE {where_clause}"
        query_list_sql = (
            f"SELECT {', '.join(TGPA_REPORT_SELECT_FIELDS)} "
            f"FROM {result_table_id} "
            f"WHERE {where_clause} "
            f"ORDER BY {order_by_clause} "
            f"LIMIT {limit} OFFSET {offset}"
        )

        # 并行查询总数和列表
        multi_execute_func = MultiExecuteFunc()
        multi_execute_func.append(result_key="count", func=BkDataQueryApi.query, params={"sql": query_count_sql})
        multi_execute_func.append(result_key="list", func=BkDataQueryApi.query, params={"sql": query_list_sql})
        multi_result = multi_execute_func.run()

        # 处理返回结果
        count_result = multi_result.get("count", {})
        list_result = multi_result.get("list", {})

        total = 0
        if count_result.get("list") and len(count_result["list"]) > 0:
            total = count_result["list"][0].get("total", 0)

        data = list_result.get("list", [])
        for item in data:
            item["download_url"] = f"{download_url_prefix}{item.get('file_name', '')}"

        return {"total": total, "list": data}

    @classmethod
    def iter_report_list(cls, bk_biz_id, openid=None, file_name=None, start_time=None, end_time=None):
        """
        使用迭代器模式获取客户端日志上报文件列表
        """
        # 获取配置
        feature_toggle = FeatureToggleObject.toggle(FEATURE_TOGGLE_TGPA_TASK)
        feature_config = feature_toggle.feature_config
        result_table_id = feature_config.get("tgpa_report_result_table_id")
        batch_size = TGPA_REPORT_LIST_BATCH_SIZE

        # 构建WHERE子句
        where_clause = cls._build_where_clause(
            bk_biz_id=bk_biz_id, openid=openid, file_name=file_name, start_time=start_time, end_time=end_time
        )

        # 分批查询数据，这里排序和时间范围过滤统一使用dtEventTimeStamp（report_time并不是按照数据插入时间的顺序单调递增的）
        offset = 0
        while True:
            query_list_sql = (
                f"SELECT {', '.join(TGPA_REPORT_SELECT_FIELDS)} "
                f"FROM {result_table_id} "
                f"WHERE {where_clause} "
                f"ORDER BY dtEventTimeStamp DESC "
                f"LIMIT {batch_size} OFFSET {offset}"
            )

            list_result = BkDataQueryApi.query({"sql": query_list_sql})
            batch_data = list_result.get("list", [])
            if not batch_data:
                break
            yield from batch_data
            if len(batch_data) < batch_size:
                break

            offset += batch_size
