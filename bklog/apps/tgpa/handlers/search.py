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

import arrow

from apps.tgpa.constants import TGPA_MERGED_LIST_MAX_RESULT_WINDOW, TGPA_REPORT_TOTAL_COUNT_DAYS
from apps.tgpa.handlers.report import TGPAReportHandler
from apps.tgpa.handlers.task import TGPATaskHandler
from apps.utils.thread import MultiExecuteFunc


class TGPASearchHandler:
    """
    检索页面聚合查询处理器
    负责跨 task 和 report 两个数据源的聚合查询
    """

    @classmethod
    def get_openid_list(cls, params):
        """
        openid 列表查询
        """
        bk_biz_id = params["bk_biz_id"]
        keyword = params.get("keyword")
        start_time = params.get("start_time")
        end_time = params.get("end_time")

        # 并行从 task 和 report 数据源查询 openid 列表
        multi_execute = MultiExecuteFunc()
        multi_execute.append(
            result_key="task_openid_list",
            func=TGPATaskHandler.get_openid_list,
            params={"bk_biz_id": bk_biz_id, "keyword": keyword},
            multi_func_params=True,
        )
        multi_execute.append(
            result_key="report_openid_list",
            func=TGPAReportHandler.get_openid_list,
            params={"bk_biz_id": bk_biz_id, "keyword": keyword, "start_time": start_time, "end_time": end_time},
            multi_func_params=True,
        )
        results = multi_execute.run()

        # 合并、去重
        task_openid_list = results.get("task_openid_list", [])
        report_openid_list = results.get("report_openid_list", [])
        return sorted(set(task_openid_list) | set(report_openid_list))

    @staticmethod
    def _format_task_item(task):
        """将原始 task 数据格式化为统一的合并列表项"""
        task_detail = {item["key"]: item["value"] for item in task["task_info"]}
        return {
            "source": "task",
            "id": task["id"],
            "task_id": task["go_svr_task_id"],
            "openid": task.get("openid", ""),
            "file_name": task.get("file_name", ""),
            "os_type": task_detail.get("os_type", ""),
            "os_version": task_detail.get("os_version", ""),
            "sdk_version": task_detail.get("sdk_version", ""),
            "model": task_detail.get("model", ""),
            "xid": task.get("xid", ""),
            "report_time": task.get("created_at", ""),
            "process_status": task.get("process_status", ""),
            "processed_at": task.get("processed_at", ""),
        }

    @staticmethod
    def _format_report_item(report):
        """将原始 report 数据格式化为统一的合并列表项"""
        return {
            "source": "report",
            "id": None,
            "task_id": None,
            "openid": report.get("openid", ""),
            "file_name": report.get("file_name", ""),
            "os_type": report.get("os_type", ""),
            "os_version": report.get("os_version", ""),
            "sdk_version": report.get("os_sdk", ""),
            "model": report.get("model", ""),
            "xid": report.get("xid", ""),
            "report_time": report.get("report_time", ""),
            "process_status": report.get("process_status", ""),
            "processed_at": report.get("processed_at", ""),
        }

    @classmethod
    def get_merged_task_list(cls, params):
        """
        从 task 和 report 两个数据源查询任务列表，合并后返回
        因跨源归并分页，当两数据源时序交错较深时，靠后页的顺序可能不完全准确。
        """
        bk_biz_id = params["bk_biz_id"]
        task_id = params.get("task_id")
        openid = params.get("openid")
        if task_id is not None:
            task_id = str(task_id)
        start_time = params.get("start_time")
        end_time = params.get("end_time")
        page = params.get("page", 1)
        pagesize = params.get("pagesize", 10)

        # 各查 page * pagesize 条，确保归并后能正确切出第 page 页
        fetch_size = page * pagesize

        # 并行查询 task 和 report（没有 task_id 时才查 report）
        multi_execute = MultiExecuteFunc()
        multi_execute.append(
            result_key="task_result",
            func=TGPATaskHandler.get_task_page,
            params={
                "params": {
                    "bk_biz_id": bk_biz_id,
                    "page": 1,
                    "pagesize": fetch_size,
                    "openid": openid,
                    "task_id": task_id,
                    "start_time": start_time,
                    "end_time": end_time,
                    "ordering": "-created_at",
                },
                "need_format": False,
            },
            multi_func_params=True,
        )
        if not task_id:
            multi_execute.append(
                result_key="report_result",
                func=TGPAReportHandler.get_report_list,
                params={
                    "bk_biz_id": bk_biz_id,
                    "openid": openid,
                    "start_time": start_time,
                    "end_time": end_time,
                    "page": 1,
                    "pagesize": fetch_size,
                },
            )
        results = multi_execute.run()

        task_result = results.get("task_result", {"total": 0, "list": []})
        task_items = [cls._format_task_item(task) for task in task_result.get("list", [])]

        report_result = results.get("report_result", {"total": 0, "list": []})
        report_items = [cls._format_report_item(report) for report in report_result.get("list", [])]

        merged_list = task_items + report_items
        merged_list.sort(key=lambda x: x.get("report_time") or "", reverse=True)
        start_idx = (page - 1) * pagesize
        paged_list = merged_list[start_idx : start_idx + pagesize]

        # 限制深度分页
        total = min(
            TGPA_MERGED_LIST_MAX_RESULT_WINDOW,
            task_result.get("total", 0) + report_result.get("total", 0),
        )
        return {"total": total, "list": paged_list}

    @classmethod
    def get_client_info(cls, params):
        """
        获取客户端信息
        """
        bk_biz_id = params["bk_biz_id"]
        openid = params["openid"]
        start_time = params.get("start_time")
        end_time = params.get("end_time")

        multi_execute = MultiExecuteFunc()

        # 1. task 累计数量（openid 精确匹配，不限时间）
        multi_execute.append(
            result_key="total_task",
            func=TGPATaskHandler.get_task_page,
            params={
                "params": {
                    "bk_biz_id": bk_biz_id,
                    "page": 1,
                    "pagesize": 1,
                    "openid": openid,
                    "ordering": "-created_at",
                },
                "need_format": False,
                "add_process_info": False,
            },
            multi_func_params=True,
        )
        # 2. report 累计数量（暂定为最近 TGPA_REPORT_TOTAL_COUNT_DAYS 天内的数量）
        now = arrow.now()
        report_total_start_time = int(now.shift(days=-TGPA_REPORT_TOTAL_COUNT_DAYS).timestamp() * 1000)
        report_total_end_time = int(now.timestamp() * 1000)
        multi_execute.append(
            result_key="total_report",
            func=TGPAReportHandler.get_report_count,
            params={
                "bk_biz_id": bk_biz_id,
                "openid": openid,
                "start_time": report_total_start_time,
                "end_time": report_total_end_time,
            },
            multi_func_params=True,
        )
        # 3. 如果传了时间范围，查询时间范围内的数量
        if start_time or end_time:
            multi_execute.append(
                result_key="range_task",
                func=TGPATaskHandler.get_task_page,
                params={
                    "params": {
                        "bk_biz_id": bk_biz_id,
                        "page": 1,
                        "pagesize": 1,
                        "openid": openid,
                        "start_time": start_time,
                        "end_time": end_time,
                        "ordering": "-created_at",
                    },
                    "need_format": False,
                    "add_process_info": False,
                },
                multi_func_params=True,
            )
            multi_execute.append(
                result_key="range_report",
                func=TGPAReportHandler.get_report_count,
                params={
                    "bk_biz_id": bk_biz_id,
                    "openid": openid,
                    "start_time": start_time,
                    "end_time": end_time,
                },
                multi_func_params=True,
            )

        results = multi_execute.run()
        total_task_count = results.get("total_task", {}).get("total", 0)
        total_report_count = results.get("total_report", 0)
        range_task_count = results.get("range_task", {}).get("total", 0)
        range_report_count = results.get("range_report", 0)

        return {
            "total_count": total_task_count + total_report_count,
            "range_count": range_task_count + range_report_count,
        }
