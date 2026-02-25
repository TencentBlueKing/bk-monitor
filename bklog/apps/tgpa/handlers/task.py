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

import math
import os

from django.utils.functional import cached_property

from apps.api import TGPATaskApi
from apps.tgpa.constants import TGPA_BASE_DIR, TGPATaskTypeEnum, TASK_LIST_BATCH_SIZE
from apps.tgpa.handlers.base import TGPAFileHandler
from apps.tgpa.models import TGPATask
from apps.utils.thread import MultiExecuteFunc


class TGPATaskHandler:
    def __init__(self, bk_biz_id, inst_id=None, task_info=None):
        self.bk_biz_id = bk_biz_id
        self.inst_id = inst_id
        self.task_info = task_info  # 通过接口获取到的任务信息
        # inst_id 和 task_info 不能同时为空
        if not inst_id:
            self.inst_id = task_info["id"]
        elif not task_info:
            self.task_info = self.get_task_info(inst_id)
        self.task_id = self.task_info["go_svr_task_id"]
        self.temp_dir = os.path.join(TGPA_BASE_DIR, str(self.bk_biz_id), "task", str(self.task_id), "temp")
        self.output_dir = os.path.join(TGPA_BASE_DIR, str(self.bk_biz_id), "task", str(self.task_id), "output")

    @cached_property
    def meta_fields(self):
        """
        需要注入到日志中的元数据维度
        """
        task_detail = {item["key"]: item["value"] for item in self.task_info["task_info"]}
        return {
            "task_id": self.task_info["go_svr_task_id"],
            "task_name": self.task_info["name"],
            "openid": self.task_info["openid"],
            "manufacturer": task_detail["manufacturer"],
            "sdk_version": task_detail["sdk_version"],
            "os_type": task_detail["os_type"],
            "os_version": task_detail["os_version"],
            "model": task_detail["model"],
            "cos_file_name": self.task_info["file_name"],
        }

    def get_task_info(self, inst_id):
        """
        获取任务信息
        """
        request_params = {
            "cc_id": self.bk_biz_id,
            "task_type": TGPATaskTypeEnum.BUSINESS_LOG_V2.value,
            "task_id": inst_id,
        }
        return TGPATaskApi.query_single_user_log_task_v2(request_params)["results"][0]

    @staticmethod
    def format_task_list(task_list):
        """
        格式化任务列表
        """
        result_list = []
        for task in task_list:
            # id 为数据库自增ID，task_id 为后台任务ID
            result_list.append(
                {
                    "id": task["id"],
                    "task_id": task["go_svr_task_id"],
                    "bk_biz_id": task["cc_id"],
                    "task_name": task["name"],
                    "log_path": task["log_path"],
                    "openid": task["openid"],
                    "create_type": task["create_type"],
                    "status": task["status"],
                    "status_name": task["statusText"],
                    "scene": task["scene"],
                    "scene_name": task["real_scene"],
                    "platform": task.get("user_client_type", ""),
                    "frequency": task["frequency"],
                    "trigger_duration": task["trigger_duration"],
                    "max_file_num": task["max_file_num"],
                    "start_time": task["start_time"],
                    "end_time": task["end_time"],
                    "comment": task["comment"],
                    "created_by": task["created_by"],
                    "created_at": task["created_at"],
                }
            )
        return result_list

    @staticmethod
    def get_task_count(bk_biz_id):
        """
        获取任务总数
        """
        params = {
            "cc_id": bk_biz_id,
            "task_type": TGPATaskTypeEnum.BUSINESS_LOG_V2.value,
            "offset": 0,
            "limit": 1,
        }
        result = TGPATaskApi.query_single_user_log_task_v2(params)
        return result["count"]

    @staticmethod
    def get_task_list(params, need_format=False):
        """
        获取任务列表
        """
        # 支持v1和v2业务日志捞取任务
        task_types = ",".join(
            [str(TGPATaskTypeEnum.BUSINESS_LOG_V1.value), str(TGPATaskTypeEnum.BUSINESS_LOG_V2.value)]
        )
        params["task_type"] = task_types
        # 第一次请求只获取1条数据，用于获取总数
        first_request_params = params.copy()
        first_request_params.update({"offset": 0, "limit": 1})
        result = TGPATaskApi.query_single_user_log_task_v2(first_request_params)
        count = result["count"]

        data = []
        if count > 0:
            total_requests = math.ceil(count / TASK_LIST_BATCH_SIZE)
            multi_execute_func = MultiExecuteFunc()

            for i in range(total_requests):
                request_params = params.copy()
                request_params.update({"offset": i * TASK_LIST_BATCH_SIZE, "limit": TASK_LIST_BATCH_SIZE})
                multi_execute_func.append(
                    result_key=f"request_{i}", func=TGPATaskApi.query_single_user_log_task_v2, params=request_params
                )

            results = multi_execute_func.run()
            for i in range(total_requests):
                if need_format:
                    data.extend(TGPATaskHandler.format_task_list(results[f"request_{i}"]["results"]))
                else:
                    data.extend(results[f"request_{i}"]["results"])

        return {"total": count, "list": data}

    @staticmethod
    def get_task_page(params):
        """
        分页获取任务列表，用于前端
        """
        # 支持v1和v2业务日志捞取任务
        task_types = ",".join(
            [str(TGPATaskTypeEnum.BUSINESS_LOG_V1.value), str(TGPATaskTypeEnum.BUSINESS_LOG_V2.value)]
        )
        request_params = {
            "cc_id": params["bk_biz_id"],
            "task_type": task_types,
            "offset": (params["page"] - 1) * params["pagesize"],
            "limit": params["pagesize"],
        }

        if params.get("ordering"):
            request_params["ordering"] = params["ordering"]

        condition_list = []

        if params.get("keyword"):
            condition_list.append(params["keyword"])
        if params.get("status"):
            condition_list.append(f"status={params['status']}")
        if params.get("scene"):
            condition_list.append(f"scene={params['scene']}")
        if params.get("created_by"):
            condition_list.append(f"created_by={params['created_by']}")

        if condition_list:
            request_params["search"] = ";".join(condition_list)

        result = TGPATaskApi.query_single_user_log_task_v2(request_params)
        task_list = TGPATaskHandler.format_task_list(result["results"])

        # 获取任务处理时间和处理状态
        task_ids = [task["task_id"] for task in task_list]
        tgpa_tasks = TGPATask.objects.filter(task_id__in=task_ids).values("task_id", "processed_at", "process_status")
        task_info_map = {str(item["task_id"]): item for item in tgpa_tasks}
        for task in task_list:
            task_info = task_info_map.get(task["task_id"], {})
            task["processed_at"] = task_info.get("processed_at", None)
            task["process_status"] = task_info.get("process_status", None)

        return {
            "total": result["count"],
            "list": task_list,
        }

    @staticmethod
    def get_username_list(bk_biz_id):
        """
        获取用户名列表
        """
        request_params = {
            "cc_id": bk_biz_id,
            "task_type": TGPATaskTypeEnum.BUSINESS_LOG_V2.value,
            "limit": 1,
        }
        result = TGPATaskApi.query_single_user_log_task_v2(request_params)
        return result["user_list"]

    def download_and_process_file(self):
        """
        下载并处理文件
        """
        file_handler = TGPAFileHandler(self.temp_dir, self.output_dir, self.meta_fields)
        file_handler.download_and_process_file(self.task_info["file_name"])
