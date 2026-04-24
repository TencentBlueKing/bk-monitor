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

import heapq
import itertools

import arrow

from apps.tgpa.constants import (
    TGPA_OPENID_SUGGEST_LIMIT,
    TGPA_MERGED_LIST_MAX_RESULT_WINDOW,
    TGPA_CLIENT_INFO_REPORT_DAYS,
)
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
        通过 keyword 分别从 task 和 report 查询 openid，合并去重后返回
        :param params: 包含 bk_biz_id, keyword(可选), start_time(可选), end_time(可选)
        :return: 去重排序后的 openid 列表
        """
        bk_biz_id = params["bk_biz_id"]
        keyword = params.get("keyword")
        start_time = params.get("start_time")
        end_time = params.get("end_time")

        # 并行从 task 和 report 数据源查询 openid 列表
        multi_execute = MultiExecuteFunc()
        multi_execute.append(
            "task_openid_list",
            TGPATaskHandler.get_openid_list,
            params={"bk_biz_id": bk_biz_id, "keyword": keyword},
            multi_func_params=True,
        )
        multi_execute.append(
            "report_openid_list",
            TGPAReportHandler.get_openid_list,
            params={"bk_biz_id": bk_biz_id, "keyword": keyword, "start_time": start_time, "end_time": end_time},
            multi_func_params=True,
        )
        results = multi_execute.run()

        task_openid_list = results.get("task_openid_list", [])
        report_openid_list = results.get("report_openid_list", [])

        # 合并去重、排序、截断
        merged_openid_set = set(task_openid_list) | set(report_openid_list)
        return sorted(merged_openid_set)[:TGPA_OPENID_SUGGEST_LIMIT]

    @staticmethod
    def _format_task_item(task):
        """将原始 task 数据格式化为统一的合并列表项"""
        return {
            "source": "task",
            "id": task["id"],
            "task_id": task["go_svr_task_id"],
            "openid": task.get("openid", ""),
            "file_name": task.get("file_name", ""),
            "status": task.get("status"),
            "status_name": task.get("statusText", ""),
            "created_at": task.get("created_at", ""),
            "raw": task,
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
            "status": report.get("status"),
            "status_name": "",
            "created_at": report.get("report_time", ""),
            "raw": report,
        }

    @staticmethod
    def _split_target(target):
        """将统一检索目标拆分为 task_id 或 openid"""
        if target is None:
            return None, None
        if isinstance(target, int) or (isinstance(target, str) and target.isdigit()):
            return str(target), None
        return None, target

    @classmethod
    def get_merged_task_list(cls, params):
        """
        根据统一检索目标从 task 和 report 查询并归并分页。
        """
        bk_biz_id = params["bk_biz_id"]
        target = params.get("target")
        task_id, openid = cls._split_target(target)
        start_time = params.get("start_time")
        end_time = params.get("end_time")
        page = params.get("page", 1)
        pagesize = params.get("pagesize", 10)

        # 各查 page * pagesize 条，确保归并后能正确切出第 page 页
        fetch_size = page * pagesize

        # 并行查询 task 和 report（没有 task_id 时才查 report）
        multi_execute = MultiExecuteFunc()
        multi_execute.append(
            "task_result",
            TGPATaskHandler.get_task_page_by_time,
            params={
                "bk_biz_id": bk_biz_id,
                "page": 1,
                "pagesize": fetch_size,
                "openid": openid,
                "task_id": task_id,
                "start_time": start_time,
                "end_time": end_time,
            },
            multi_func_params=True,
        )
        if not task_id:
            multi_execute.append(
                "report_result",
                TGPAReportHandler.get_report_list,
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
        task_items = [cls._format_task_item(task) for task in task_result["list"]]

        report_result = results.get("report_result", {"total": 0, "list": []})
        report_items = [cls._format_report_item(report) for report in report_result.get("list", [])]

        # ===== 归并排序（两路已按时间倒序），取当前页 =====
        merged = heapq.merge(task_items, report_items, key=lambda x: x.get("created_at") or "", reverse=True)
        start_idx = (page - 1) * pagesize
        paged_list = list(itertools.islice(merged, start_idx, start_idx + pagesize))

        total = min(TGPA_MERGED_LIST_MAX_RESULT_WINDOW, task_result["total"] + report_result["total"])
        return {"total": total, "list": paged_list}

    @classmethod
    def get_client_info(cls, params):
        """
        获取客户端信息：累计上报次数和时间范围内的上报次数
        合并 task 和 report 两个数据源的统计信息

        :param params: 包含 bk_biz_id, openid, start_time(可选), end_time(可选)
        :return: {
            "total_task_count": 累计 task 数量（全量）,
            "total_report_count": 累计 report 数量（近30天）,
            "total_count": 累计上报总次数,
            "range_task_count": 时间范围内 task 数量,
            "range_report_count": 时间范围内 report 数量,
            "range_count": 时间范围内上报总次数,
        }
        """
        bk_biz_id = params["bk_biz_id"]
        openid = params["openid"]
        start_time = params.get("start_time")
        end_time = params.get("end_time")

        # report 累计统计使用近30天作为时间范围
        now_ms = int(arrow.now().timestamp() * 1000)
        report_total_start_time = int(arrow.now().shift(days=-TGPA_CLIENT_INFO_REPORT_DAYS).timestamp() * 1000)

        # 并行查询：task 累计数量、report 累计数量（30天）、task 时间范围数量、report 时间范围数量
        multi_execute = MultiExecuteFunc()

        # 1. task 累计数量（openid 精确匹配，不限时间）
        multi_execute.append(
            "total_task",
            TGPATaskHandler.get_task_page_by_time,
            params={
                "bk_biz_id": bk_biz_id,
                "page": 1,
                "pagesize": 1,
                "openid": openid,
            },
            multi_func_params=True,
        )

        # 2. report 累计数量（近30天）
        multi_execute.append(
            "total_report",
            TGPAReportHandler.get_report_count,
            params={
                "bk_biz_id": bk_biz_id,
                "openid": openid,
                "start_time": report_total_start_time,
                "end_time": now_ms,
            },
            multi_func_params=True,
        )

        # 3. 时间范围内 task 数量
        if start_time or end_time:
            multi_execute.append(
                "range_task",
                TGPATaskHandler.get_task_page_by_time,
                params={
                    "bk_biz_id": bk_biz_id,
                    "page": 1,
                    "pagesize": 1,
                    "openid": openid,
                    "start_time": start_time,
                    "end_time": end_time,
                },
                multi_func_params=True,
            )

            # 4. 时间范围内 report 数量
            multi_execute.append(
                "range_report",
                TGPAReportHandler.get_report_count,
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

        # 如果没有传时间范围，时间范围内的数量等于累计数量
        if start_time or end_time:
            range_task_count = results.get("range_task", {}).get("total", 0)
            range_report_count = results.get("range_report", 0)
        else:
            range_task_count = total_task_count
            range_report_count = total_report_count

        return {
            "total_task_count": total_task_count,
            "total_report_count": total_report_count,
            "total_count": total_task_count + total_report_count,
            "range_task_count": range_task_count,
            "range_report_count": range_report_count,
            "range_count": range_task_count + range_report_count,
        }
