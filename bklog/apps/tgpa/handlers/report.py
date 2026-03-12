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

import arrow
from django.utils.functional import cached_property

from apps.api import BkDataQueryApi
from apps.log_esquery.esquery.builder.query_index_optimizer import QueryIndexOptimizer
from apps.log_esquery.esquery.client.QueryClientBkData import QueryClientBkData
from apps.log_search.models import Scenario
from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.tgpa.constants import (
    TGPA_REPORT_FILTER_FIELDS,
    TGPA_REPORT_SELECT_FIELDS,
    TGPA_REPORT_SOURCE_FIELDS,
    FEATURE_TOGGLE_TGPA_TASK,
    TGPA_BASE_DIR,
    TGPA_REPORT_LIST_BATCH_SIZE,
    TGPAReportSyncStatusEnum,
)
from apps.tgpa.handlers.base import TGPAFileHandler
from apps.tgpa.models import TGPAReport, TGPAReportSyncRecord


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
            "model": self.report_info.get("model"),
            "cos_file_name": self.report_info["file_name"],
        }

    def download_and_process_file(self):
        """
        下载并处理文件
        """
        file_handler = TGPAFileHandler(self.temp_dir, self.output_dir, self.meta_fields)
        file_handler.download_and_process_file(self.file_name)

    @classmethod
    def _get_feature_config(cls):
        """获取 TGPA 功能配置"""
        feature_toggle = FeatureToggleObject.toggle(FEATURE_TOGGLE_TGPA_TASK)
        return feature_toggle.feature_config

    @classmethod
    def _get_result_table_id(cls):
        """获取结果表ID"""
        return cls._get_feature_config().get("tgpa_report_result_table_id")

    @classmethod
    def _build_where_clause(cls, bk_biz_id, keyword=None, keyword_fields=None, start_time=None, end_time=None):
        """
        构建SQL WHERE子句（基础条件）

        :param bk_biz_id: 业务ID
        :param keyword: 搜索关键词
        :param keyword_fields: keyword需要搜索的字段列表，默认为TGPA_REPORT_FILTER_FIELDS中的所有字段
        :param start_time: 开始时间，默认为七天前
        :param end_time: 结束时间，默认为当前时间
        """
        where_conditions = [f"cc_id={bk_biz_id}"]

        if keyword:
            escaped_keyword = keyword.replace("\\", "\\\\").replace("'", "''").replace("%", "\\%").replace("_", "\\_")
            fields = keyword_fields if keyword_fields else TGPA_REPORT_FILTER_FIELDS
            keyword_conditions = [f"{field} LIKE '%{escaped_keyword}%' ESCAPE '\\'" for field in fields]
            where_conditions.append(f"({' OR '.join(keyword_conditions)})")

        # 默认时间范围：当前时间到七天前
        if not start_time:
            start_time = int(arrow.now().shift(days=-7).timestamp() * 1000)
        if not end_time:
            end_time = int(arrow.now().timestamp() * 1000)

        where_conditions.append(f"dtEventTimeStamp >= {start_time}")
        where_conditions.append(f"dtEventTimeStamp < {end_time}")

        return " AND ".join(where_conditions)

    @classmethod
    def _build_es_query(cls, bk_biz_id, keyword=None, keyword_fields=None, start_time=None, end_time=None):
        """
        构建ES DSL查询条件

        :param bk_biz_id: 业务ID
        :param keyword: 搜索关键词
        :param keyword_fields: keyword需要搜索的字段列表，默认为TGPA_REPORT_FILTER_FIELDS中的所有字段
        :param start_time: 开始时间，默认为七天前
        :param end_time: 结束时间，默认为当前时间
        """
        must_conditions = [{"term": {"cc_id": bk_biz_id}}]

        if keyword:
            fields = keyword_fields if keyword_fields else TGPA_REPORT_FILTER_FIELDS
            should_conditions = [{"wildcard": {field: {"value": f"*{keyword}*"}}} for field in fields]
            must_conditions.append({"bool": {"should": should_conditions, "minimum_should_match": 1}})

        # 默认时间范围：当前时间到七天前
        if not start_time:
            start_time = int(arrow.now().shift(days=-7).timestamp() * 1000)
        if not end_time:
            end_time = int(arrow.now().timestamp() * 1000)

        must_conditions.append({"range": {"dtEventTimeStamp": {"gte": start_time, "lt": end_time}}})
        return {"bool": {"must": must_conditions}}

    @classmethod
    def _get_optimized_index(cls, result_table_id, start_time=None, end_time=None):
        """
        获取经过时间优化后的索引名
        """
        if not start_time:
            start_time = int(arrow.now().shift(days=-7).timestamp() * 1000)
        if not end_time:
            end_time = int(arrow.now().timestamp() * 1000)

        optimizer = QueryIndexOptimizer(
            indices=result_table_id,
            scenario_id=Scenario.BKDATA,
            start_time=arrow.get(start_time / 1000),
            end_time=arrow.get(end_time / 1000),
        )
        return optimizer.index

    @classmethod
    def _parse_es_response(cls, es_response):
        """
        解析 bk-data ES查询返回结果
        """
        if not es_response or not isinstance(es_response, dict):
            return 0, []

        hits_wrapper = es_response.get("hits", {})

        # total 可能是数字或 {"value": N, "relation": "..."} 结构
        raw_total = hits_wrapper.get("total", 0)
        if isinstance(raw_total, dict):
            total = raw_total.get("value", 0)
        else:
            total = raw_total

        # 从每个 hit 中提取 _source 字段
        raw_hits = hits_wrapper.get("hits", [])
        items = [hit["_source"] for hit in raw_hits if "_source" in hit]

        return total, items

    @classmethod
    def get_report_count(cls, bk_biz_id, start_time=None, end_time=None):
        """
        获取客户端日志上报文件数量
        """
        result_table_id = cls._get_result_table_id()
        es_query = cls._build_es_query(bk_biz_id, start_time=start_time, end_time=end_time)
        body = {"query": es_query, "size": 0}
        index = cls._get_optimized_index(result_table_id, start_time=start_time, end_time=end_time)
        client = QueryClientBkData()
        es_response = client.query(index=index, body=body)
        total, _ = cls._parse_es_response(es_response)
        return total

    @classmethod
    def get_report_list(cls, params):
        """
        获取客户端日志上报文件列表
        """
        # 获取配置
        feature_config = cls._get_feature_config()
        result_table_id = feature_config.get("tgpa_report_result_table_id")
        download_url_prefix = feature_config.get("download_url_prefix", "")

        # 分页参数
        page_size = params["pagesize"]
        offset = (params["page"] - 1) * page_size

        es_query = cls._build_es_query(
            bk_biz_id=params["bk_biz_id"],
            keyword=params.get("keyword"),
            start_time=params.get("start_time"),
            end_time=params.get("end_time"),
        )

        # 构建排序条件
        sort_list = []
        order_field, order_type = params.get("order_field"), params.get("order_type")
        if order_field and order_type:
            if order_field == "file_size":
                # file_size 在 ES 中是 keyword 类型，直接排序会按字典序，需要转换为数值排序
                sort_list.append(
                    {
                        "_script": {
                            "type": "number",
                            "script": {
                                "source": "Long.parseLong(doc['file_size'].value)",
                                "lang": "painless",
                            },
                            "order": order_type.lower(),
                        }
                    }
                )
            else:
                sort_list.append({order_field: {"order": order_type.lower()}})
        sort_list.append({"dtEventTimeStamp": {"order": "desc"}})

        body = {
            "query": es_query,
            "sort": sort_list,
            "from": offset,
            "size": page_size,
            "_source": TGPA_REPORT_SOURCE_FIELDS,
        }

        # 查询ES并解析响应
        index = cls._get_optimized_index(
            result_table_id, start_time=params.get("start_time"), end_time=params.get("end_time")
        )
        client = QueryClientBkData()
        es_response = client.query(index=index, body=body)
        total, items = cls._parse_es_response(es_response)

        # 格式化字段别名: real_name -> file_path, cc_id -> bk_biz_id
        for item in items:
            if "real_name" in item:
                item["file_path"] = item.pop("real_name")
            if "cc_id" in item:
                item["bk_biz_id"] = item.pop("cc_id")

        # 补充下载地址和处理状态
        file_name_list = [item["file_name"] for item in items]
        status_map = cls.get_file_status_map(file_name_list=file_name_list)
        for item in items:
            item["download_url"] = f"{download_url_prefix}{item.get('file_name', '')}"
            item["status"] = status_map.get(item["file_name"], TGPAReportSyncStatusEnum.PENDING.value)

        return {"total": total, "list": items}

    @classmethod
    def iter_report_list(cls, bk_biz_id, openid_list=None, file_name_list=None, start_time=None, end_time=None):
        """
        使用迭代器模式获取客户端日志上报文件列表
        """
        # 获取配置
        result_table_id = cls._get_result_table_id()
        batch_size = TGPA_REPORT_LIST_BATCH_SIZE

        # 构建基础WHERE子句
        where_conditions = [cls._build_where_clause(bk_biz_id=bk_biz_id, start_time=start_time, end_time=end_time)]

        # 添加特殊的OR条件（openid_list 和 file_name_list 之间使用 OR 关系）
        or_conditions = []
        if openid_list:
            openid_conditions = [f"openid='{openid}'" for openid in openid_list]
            or_conditions.append(f"({' OR '.join(openid_conditions)})")
        if file_name_list:
            file_name_conditions = [f"file_name='{file_name}'" for file_name in file_name_list]
            or_conditions.append(f"({' OR '.join(file_name_conditions)})")

        if or_conditions:
            where_conditions.append(f"({' OR '.join(or_conditions)})")

        where_clause = " AND ".join(where_conditions)

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

    @classmethod
    def get_file_status_map(cls, file_name_list) -> dict:
        reports = TGPAReport.objects.filter(file_name__in=file_name_list)
        status_map = {}
        for report in reports:
            if report.file_name not in status_map:
                status_map[report.file_name] = report.process_status

        return status_map

    @classmethod
    def get_file_status(cls, file_name_list):
        """
        获取文件处理状态
        """
        status_map = cls.get_file_status_map(file_name_list)
        return [
            {"file_name": file_name, "status": status_map.get(file_name, TGPAReportSyncStatusEnum.PENDING.value)}
            for file_name in file_name_list
        ]

    @classmethod
    def update_process_status(cls, record_id):
        """
        更新文件处理状态
        """
        record_obj = TGPAReportSyncRecord.objects.get(id=record_id)
        if record_obj.status in [TGPAReportSyncStatusEnum.SUCCESS.value, TGPAReportSyncStatusEnum.FAILED.value]:
            return

        status_list = TGPAReport.objects.filter(record_id=record_id).values_list("process_status", flat=True).distinct()
        status_set = set(status_list)

        if TGPAReportSyncStatusEnum.PENDING.value in status_set:
            record_obj.status = TGPAReportSyncStatusEnum.RUNNING.value
        elif TGPAReportSyncStatusEnum.RUNNING.value in status_set:
            record_obj.status = TGPAReportSyncStatusEnum.RUNNING.value
        elif TGPAReportSyncStatusEnum.FAILED.value in status_set:
            record_obj.status = TGPAReportSyncStatusEnum.FAILED.value
        else:
            record_obj.status = TGPAReportSyncStatusEnum.SUCCESS.value

        record_obj.save(update_fields=["status"])
