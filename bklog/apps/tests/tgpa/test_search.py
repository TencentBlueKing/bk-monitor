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

from unittest.mock import patch

from django.test import SimpleTestCase

from apps.tgpa.constants import TGPA_MERGED_LIST_MAX_RESULT_WINDOW
from apps.tgpa.handlers.search import TGPASearchHandler


class FakeMultiExecuteFunc:
    """同步执行任务，便于单测稳定断言"""

    def __init__(self, *args, **kwargs):
        self.results = {}
        self.task_list = []

    def append(self, result_key, func, params=None, use_request=True, multi_func_params=False):
        self.task_list.append(
            {
                "result_key": result_key,
                "func": func,
                "params": params,
                "multi_func_params": multi_func_params,
            }
        )

    def run(self, return_exception=False):
        for task in self.task_list:
            if task["params"] is None:
                result = task["func"]()
            elif task["multi_func_params"]:
                result = task["func"](**task["params"])
            else:
                result = task["func"](task["params"])
            self.results[task["result_key"]] = result
        return self.results


@patch("apps.tgpa.handlers.search.MultiExecuteFunc", FakeMultiExecuteFunc)
class TestTGPASearchHandler(SimpleTestCase):
    @staticmethod
    def _build_task(
        task_id,
        go_svr_task_id,
        openid,
        file_name,
        processed_at,
        created_at="",
        process_status="done",
        os_type="Android",
        os_version="14",
        sdk_version="1.0.0",
        model="Pixel 8",
        xid="",
    ):
        return {
            "id": task_id,
            "go_svr_task_id": go_svr_task_id,
            "openid": openid,
            "file_name": file_name,
            "task_info": [
                {"key": "os_type", "value": os_type},
                {"key": "os_version", "value": os_version},
                {"key": "sdk_version", "value": sdk_version},
                {"key": "model", "value": model},
            ],
            "xid": xid,
            "created_at": created_at or processed_at,
            "processed_at": processed_at,
            "process_status": process_status,
        }

    @staticmethod
    def _build_report(
        openid,
        file_name,
        report_time,
        process_status="pending",
        processed_at="",
        os_type="iOS",
        os_version="17.0",
        sdk_version="3.0.0",
        model="iPhone 15",
        xid="",
    ):
        return {
            "openid": openid,
            "file_name": file_name,
            "os_type": os_type,
            "os_version": os_version,
            "os_sdk": sdk_version,
            "model": model,
            "xid": xid,
            "report_time": report_time,
            "status": process_status,
            "processed_at": processed_at,
        }

    @patch("apps.tgpa.handlers.search.TGPAReportHandler.get_openid_list")
    @patch("apps.tgpa.handlers.search.TGPATaskHandler.get_openid_list")
    def test_get_openid_list_deduplicates_results(self, mock_task_get_openid_list, mock_report_get_openid_list):
        params = {
            "bk_biz_id": 2,
            "keyword": "open",
            "start_time": 1716000000000,
            "end_time": 1716600000000,
        }
        mock_task_get_openid_list.return_value = ["openid_1", "openid_2"]
        mock_report_get_openid_list.return_value = ["openid_2", "openid_3"]

        result = TGPASearchHandler.get_openid_list(params)

        self.assertCountEqual(result, ["openid_1", "openid_2", "openid_3"])
        mock_task_get_openid_list.assert_called_once_with(
            bk_biz_id=2, keyword="open", start_time=1716000000000, end_time=1716600000000
        )
        mock_report_get_openid_list.assert_called_once_with(
            bk_biz_id=2,
            keyword="open",
            start_time=1716000000000,
            end_time=1716600000000,
        )

    @patch("apps.tgpa.handlers.search.TGPAReportHandler.get_report_list")
    @patch("apps.tgpa.handlers.search.TGPATaskHandler.get_task_page")
    def test_get_merged_task_list_formats_and_paginates(self, mock_get_task_page, mock_get_report_list):
        params = {
            "bk_biz_id": 2,
            "openid": "openid_1",
            "start_time": 1716000000000,
            "end_time": 1716600000000,
            "page": 2,
            "pagesize": 2,
        }
        mock_get_task_page.return_value = {
            "total": 3,
            "list": [
                self._build_task(
                    1, "task-1", "openid_1", "task_1.zip", "2026-04-24 12:00:00", created_at="2026-04-24 12:00:00"
                ),
                self._build_task(
                    2, "task-2", "openid_1", "task_2.zip", "2026-04-24 09:00:00", created_at="2026-04-24 09:00:00"
                ),
                self._build_task(
                    3, "task-3", "openid_1", "task_3.zip", "2026-04-24 07:00:00", created_at="2026-04-24 07:00:00"
                ),
            ],
        }
        mock_get_report_list.return_value = {
            "total": 2,
            "list": [
                self._build_report("openid_1", "report_1.zip", "2026-04-24 11:00:00"),
                self._build_report("openid_1", "report_2.zip", "2026-04-24 08:00:00"),
            ],
        }

        result = TGPASearchHandler.get_merged_task_list(params)

        self.assertEqual(result["total"], 5)
        self.assertEqual(
            result["list"],
            [
                {
                    "source": "task",
                    "id": 2,
                    "task_id": "task-2",
                    "openid": "openid_1",
                    "file_name": "task_2.zip",
                    "os_type": "Android",
                    "os_version": "14",
                    "sdk_version": "1.0.0",
                    "model": "Pixel 8",
                    "xid": "",
                    "report_time": "2026-04-24 09:00:00",
                    "process_status": "done",
                    "processed_at": "2026-04-24 09:00:00",
                },
                {
                    "source": "report",
                    "id": None,
                    "task_id": None,
                    "openid": "openid_1",
                    "file_name": "report_2.zip",
                    "os_type": "iOS",
                    "os_version": "17.0",
                    "sdk_version": "3.0.0",
                    "model": "iPhone 15",
                    "xid": "",
                    "report_time": "2026-04-24 08:00:00",
                    "process_status": "pending",
                    "processed_at": "",
                },
            ],
        )
        mock_get_task_page.assert_called_once_with(
            params={
                "bk_biz_id": 2,
                "page": 1,
                "pagesize": 4,
                "openid": "openid_1",
                "task_id": None,
                "start_time": 1716000000000,
                "end_time": 1716600000000,
                "ordering": "-created_at",
            },
            need_format=False,
        )
        mock_get_report_list.assert_called_once_with(
            {
                "bk_biz_id": 2,
                "openid": "openid_1",
                "file_name": None,
                "start_time": 1716000000000,
                "end_time": 1716600000000,
                "page": 1,
                "pagesize": 4,
            }
        )

    @patch("apps.tgpa.handlers.search.TGPAReportHandler.get_report_list")
    @patch("apps.tgpa.handlers.search.TGPATaskHandler.get_task_page")
    def test_get_merged_task_list_skips_report_for_task_id(self, mock_get_task_page, mock_get_report_list):
        params = {
            "bk_biz_id": 2,
            "task_id": 12345,
            "page": 1,
            "pagesize": 10,
        }
        mock_get_task_page.return_value = {
            "total": TGPA_MERGED_LIST_MAX_RESULT_WINDOW + 5,
            "list": [self._build_task(1, "12345", "openid_1", "task_1.zip", "2026-04-24 12:00:00")],
        }

        result = TGPASearchHandler.get_merged_task_list(params)

        self.assertEqual(result["total"], TGPA_MERGED_LIST_MAX_RESULT_WINDOW)
        self.assertEqual(result["list"][0]["source"], "task")
        self.assertEqual(result["list"][0]["task_id"], "12345")
        mock_get_task_page.assert_called_once_with(
            params={
                "bk_biz_id": 2,
                "page": 1,
                "pagesize": 10,
                "openid": None,
                "task_id": "12345",
                "start_time": None,
                "end_time": None,
                "ordering": "-created_at",
            },
            need_format=False,
        )
        mock_get_report_list.assert_not_called()

    @patch("apps.tgpa.handlers.search.TGPAReportHandler.get_report_count")
    @patch("apps.tgpa.handlers.search.TGPATaskHandler.get_task_page")
    def test_get_client_info_without_range_returns_total_count(self, mock_get_task_page, mock_get_report_count):
        mock_get_task_page.return_value = {"total": 3, "list": []}
        mock_get_report_count.return_value = 4

        result = TGPASearchHandler.get_client_info({"bk_biz_id": 2, "openid": "openid_1"})

        self.assertEqual(result, {"total_count": 7, "range_count": 0})
        mock_get_task_page.assert_called_once_with(
            params={
                "bk_biz_id": 2,
                "page": 1,
                "pagesize": 1,
                "openid": "openid_1",
                "ordering": "-created_at",
            },
            need_format=False,
            add_process_info=False,
        )
        mock_get_report_count.assert_called_once()
        report_call_kwargs = mock_get_report_count.call_args.kwargs
        self.assertEqual(report_call_kwargs["bk_biz_id"], 2)
        self.assertEqual(report_call_kwargs["openid"], "openid_1")
        self.assertIsInstance(report_call_kwargs["start_time"], int)
        self.assertIsInstance(report_call_kwargs["end_time"], int)
        self.assertLess(report_call_kwargs["start_time"], report_call_kwargs["end_time"])

    @patch("apps.tgpa.handlers.search.TGPAReportHandler.get_report_count")
    @patch("apps.tgpa.handlers.search.TGPATaskHandler.get_task_page")
    def test_get_client_info_with_range_returns_total_and_range_count(
        self,
        mock_get_task_page,
        mock_get_report_count,
    ):
        mock_get_task_page.side_effect = [
            {"total": 3, "list": []},
            {"total": 1, "list": []},
        ]
        mock_get_report_count.side_effect = [4, 2]
        result = TGPASearchHandler.get_client_info(
            {
                "bk_biz_id": 2,
                "openid": "openid_1",
                "start_time": 1716000000000,
                "end_time": 1716600000000,
            }
        )
        self.assertEqual(result, {"total_count": 7, "range_count": 3})

    @patch("apps.tgpa.handlers.search.TGPAReportHandler.get_report_list")
    @patch("apps.tgpa.handlers.search.TGPATaskHandler.get_task_page")
    def test_get_merged_task_list_converts_enq_file_name_to_task_id(self, mock_get_task_page, mock_get_report_list):
        """file_name 为 ENQ_file_{task_id}.zip 格式时，应提取 task_id 并去掉 file_name"""
        params = {
            "bk_biz_id": 2,
            "file_name": "ENQ_file_3025221.zip",
            "page": 1,
            "pagesize": 10,
        }
        mock_get_task_page.return_value = {
            "total": 1,
            "list": [self._build_task(1, "3025221", "openid_1", "ENQ_file_3025221.zip", "2026-04-24 12:00:00")],
        }

        result = TGPASearchHandler.get_merged_task_list(params)

        # 验证结果正确返回
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["list"][0]["task_id"], "3025221")
        # 验证 task_id 被正确提取，file_name 不传给 task 接口
        mock_get_task_page.assert_called_once_with(
            params={
                "bk_biz_id": 2,
                "page": 1,
                "pagesize": 10,
                "openid": None,
                "task_id": "3025221",
                "start_time": None,
                "end_time": None,
                "ordering": "-created_at",
            },
            need_format=False,
        )
        # task_id 不为空时不查 report
        mock_get_report_list.assert_not_called()

    @patch("apps.tgpa.handlers.search.TGPAReportHandler.get_report_list")
    @patch("apps.tgpa.handlers.search.TGPATaskHandler.get_task_page")
    def test_get_merged_task_list_non_enq_file_name_not_converted(self, mock_get_task_page, mock_get_report_list):
        """file_name 不匹配 ENQ_file_{task_id}.zip 格式时，不传给 task 接口，仅传给 report 接口"""
        params = {
            "bk_biz_id": 2,
            "file_name": "some_other_file.zip",
            "page": 1,
            "pagesize": 10,
        }
        mock_get_task_page.return_value = {"total": 0, "list": []}
        mock_get_report_list.return_value = {"total": 0, "list": []}

        TGPASearchHandler.get_merged_task_list(params)

        # file_name 不匹配格式时，task 接口不传 file_name，task_id 仍为 None
        mock_get_task_page.assert_called_once_with(
            params={
                "bk_biz_id": 2,
                "page": 1,
                "pagesize": 10,
                "openid": None,
                "task_id": None,
                "start_time": None,
                "end_time": None,
                "ordering": "-created_at",
            },
            need_format=False,
        )
        # task_id 为 None，report 应该被查询，且 file_name 传给 report 接口
        mock_get_report_list.assert_called_once_with(
            {
                "bk_biz_id": 2,
                "openid": None,
                "file_name": "some_other_file.zip",
                "start_time": None,
                "end_time": None,
                "page": 1,
                "pagesize": 10,
            }
        )

    @patch("apps.tgpa.handlers.search.TGPAReportHandler.get_report_list")
    @patch("apps.tgpa.handlers.search.TGPATaskHandler.get_task_page")
    def test_get_merged_task_list_task_id_not_overridden_by_enq_file_name(
        self, mock_get_task_page, mock_get_report_list
    ):
        """task_id 已显式传入时，不应被 ENQ_file_{id}.zip 格式的 file_name 覆盖"""
        params = {
            "bk_biz_id": 2,
            "task_id": 111,
            "file_name": "ENQ_file_222.zip",
            "page": 1,
            "pagesize": 10,
        }
        mock_get_task_page.return_value = {
            "total": 1,
            "list": [self._build_task(1, "111", "openid_1", "ENQ_file_111.zip", "2026-04-24 12:00:00")],
        }

        result = TGPASearchHandler.get_merged_task_list(params)

        # task_id 应保持为调用方传入的 111，而非从 file_name 提取的 222
        self.assertEqual(result["list"][0]["task_id"], "111")
        mock_get_task_page.assert_called_once_with(
            params={
                "bk_biz_id": 2,
                "page": 1,
                "pagesize": 10,
                "openid": None,
                "task_id": "111",
                "start_time": None,
                "end_time": None,
                "ordering": "-created_at",
            },
            need_format=False,
        )
        # task_id 非空，不查 report
        mock_get_report_list.assert_not_called()
