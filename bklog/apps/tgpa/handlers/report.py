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

from apps.api import BkDataQueryApi
from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.tgpa.constants import TGPA_REPORT_FILTER_FIELDS, TGPA_REPORT_SELECT_FIELDS, FEATURE_TOGGLE_TGPA_TASK
from apps.utils.thread import MultiExecuteFunc


class TGPAReportHandler:
    def __init__(self, bk_biz_id):
        self.bk_biz_id = bk_biz_id

    @staticmethod
    def _build_where_clause(bk_biz_id, keyword=None):
        """
        构建SQL WHERE子句

        :param bk_biz_id: 业务ID
        :param keyword: 搜索关键词
        :return: WHERE子句字符串
        """
        where_conditions = [f"cc_id={bk_biz_id}"]

        if keyword:
            # 转义特殊字符防止SQL注入
            escaped_keyword = keyword.replace("'", "''").replace("%", "\\%").replace("_", "\\_")
            keyword_conditions = [f"{field} like '%{escaped_keyword}%'" for field in TGPA_REPORT_FILTER_FIELDS]
            if keyword_conditions:
                where_conditions.append(f"({' OR '.join(keyword_conditions)})")

        return " AND ".join(where_conditions)

    @staticmethod
    def _build_query_sqls(result_table_id, where_clause, limit, offset):
        """
        构建查询SQL语句

        :param result_table_id: 结果表ID
        :param where_clause: WHERE子句
        :param limit: 每页数量
        :param offset: 偏移量
        :return: (count_sql, list_sql) 元组
        """
        count_sql = f"SELECT count(*) AS total FROM {result_table_id} WHERE {where_clause}"
        list_sql = (
            f"SELECT {', '.join(TGPA_REPORT_SELECT_FIELDS)} "
            f"FROM {result_table_id} "
            f"WHERE {where_clause} "
            f"ORDER BY report_time DESC "
            f"LIMIT {limit} OFFSET {offset}"
        )
        return count_sql, list_sql

    @staticmethod
    def get_file_list(params):
        """
        获取客户端日志上报文件列表

        :param params: 查询参数，包含page, pagesize, bk_biz_id, keyword(可选)
        :return: 包含total和list的字典
        """
        # 获取配置
        feature_toggle = FeatureToggleObject.toggle(FEATURE_TOGGLE_TGPA_TASK)
        feature_config = feature_toggle.feature_config
        result_table_id = feature_config.get("tgpa_report_result_table_id")
        download_url_prefix = feature_config.get("download_url_prefix", "")

        # 计算分页参数
        limit = params["pagesize"]
        offset = (params["page"] - 1) * limit

        # 构建SQL语句
        where_clause = TGPAReportHandler._build_where_clause(
            bk_biz_id=params["bk_biz_id"], keyword=params.get("keyword")
        )
        query_count_sql, query_list_sql = TGPAReportHandler._build_query_sqls(
            result_table_id=result_table_id, where_clause=where_clause, limit=limit, offset=offset
        )

        # 并行查询总数和列表
        multi_execute_func = MultiExecuteFunc()
        multi_execute_func.append(
            result_key="count", func=BkDataQueryApi.query, params={"sql": query_count_sql, "is_stag": True}
        )
        multi_execute_func.append(
            result_key="list", func=BkDataQueryApi.query, params={"sql": query_list_sql, "is_stag": True}
        )
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
