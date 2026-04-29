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
import shutil
import uuid

import arrow
from django.conf import settings
from django.utils.functional import cached_property

from apps.api import TGPATaskApi
from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.tgpa.constants import (
    TGPA_BASE_DIR,
    TGPATaskTypeEnum,
    TGPATaskProcessStatusEnum,
    TASK_LIST_BATCH_SIZE,
    TGPA_DOWNLOAD_DIR,
    FEATURE_TGPA_FILE_DOWNLOAD_MAX_SIZE,
    FEATURE_TOGGLE_TGPA_TASK,
    TGPA_FILE_DOWNLOAD_CHUNK_SIZE,
    TGPA_REPORT_FILE_NAME_PREFIX,
    TGPA_OPENID_SUGGEST_LIMIT,
)
from apps.tgpa.handlers.base import TGPAFileHandler
from apps.tgpa.handlers.decrypt import get_decrypt_handler
from apps.tgpa.models import TGPATask


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
        # 解密处理器实例
        self.decrypt_handler = get_decrypt_handler(bk_biz_id)

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
            "task_type": TGPATaskTypeEnum.get_business_log_task_types(),
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
                    "file_name": task["file_name"],
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
            "task_type": TGPATaskTypeEnum.get_business_log_task_types(),
            "offset": 0,
            "limit": 1,
        }
        result = TGPATaskApi.query_single_user_log_task_v2(params)
        return result["count"]

    @staticmethod
    def iter_task_list(bk_biz_id, batch_size=TASK_LIST_BATCH_SIZE, **extra_params):
        """
        迭代获取任务列表，逐条返回任务数据
        :param bk_biz_id: 业务ID
        :param batch_size: 每批请求数据量，默认为TASK_LIST_BATCH_SIZE
        :param extra_params: 额外的查询参数，如 task_id 等，会直接传递给 API
        :return: 生成器，逐条yield任务数据
        """
        offset = 0
        while True:
            request_params = {
                "cc_id": bk_biz_id,
                "task_type": TGPATaskTypeEnum.get_business_log_task_types(),
                "offset": offset,
                "limit": batch_size,
                "ordering": "-id",
                **extra_params,
            }
            result = TGPATaskApi.query_single_user_log_task_v2(request_params)
            task_list = result.get("results", [])

            if not task_list:
                break
            yield from task_list

            if len(task_list) < batch_size:
                break

            offset += batch_size

    @staticmethod
    def add_task_process_info(task_list):
        """
        为任务列表补充处理时间和处理状态
        """
        # 获取任务处理时间和处理状态
        task_ids = [task["id"] for task in task_list]
        tgpa_tasks = TGPATask.objects.filter(id__in=task_ids).values("id", "processed_at", "process_status")
        task_info_map = {item["id"]: item for item in tgpa_tasks}
        for task in task_list:
            task_info = task_info_map.get(task["id"], {})
            task["processed_at"] = task_info.get("processed_at")
            task["process_status"] = task_info.get("process_status")
        return task_list

    @staticmethod
    def get_task_page(params, need_format=True, add_process_info=True):
        """
        分页获取任务列表
        """
        page = params.get("page", 1)
        pagesize = params.get("pagesize", 10)
        request_params = {
            "cc_id": params["bk_biz_id"],
            "task_type": TGPATaskTypeEnum.get_business_log_task_types(),
            "offset": (page - 1) * pagesize,
            "limit": pagesize,
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
        if params.get("openid"):
            condition_list.append(f"openid={params['openid']}")
        if params.get("task_id"):
            request_params["task_id"] = params["task_id"]

        if condition_list:
            request_params["search"] = ";".join(condition_list)

        start_time = params.get("start_time")
        end_time = params.get("end_time")
        start_str = (
            arrow.get(start_time / 1000).to(settings.TIME_ZONE).strftime("%Y-%m-%d %H:%M:%S") if start_time else ""
        )
        end_str = arrow.get(end_time / 1000).to(settings.TIME_ZONE).strftime("%Y-%m-%d %H:%M:%S") if end_time else ""
        if start_str or end_str:
            request_params["time_range"] = ",".join([start_str, end_str])

        result = TGPATaskApi.query_single_user_log_task_v2(request_params)
        task_list = result.get("results", [])
        if need_format:
            task_list = TGPATaskHandler.format_task_list(task_list)
        if add_process_info:
            task_list = TGPATaskHandler.add_task_process_info(task_list)

        return {
            "total": result["count"],
            "list": task_list,
        }

    @staticmethod
    def get_openid_list(bk_biz_id, keyword=None, limit=TGPA_OPENID_SUGGEST_LIMIT):
        """
        获取 openid 列表（从 task 数据源中查询）
        查询有限数量的任务并从中提取去重的 openid，用于联想场景，无需全量扫描。
        :param bk_biz_id: 业务ID
        :param keyword: 搜索关键字，用于过滤 openid
        :param limit: 最多返回的 openid 数量
        :return: 去重后的 openid 列表
        """
        request_params = {
            "cc_id": bk_biz_id,
            "task_type": TGPATaskTypeEnum.get_business_log_task_types(),
            "offset": 0,
            "limit": limit * 5,  # 多取一些以应对同一 openid 的多条任务，提高去重后命中 limit 的概率
            "ordering": "-created_at",
        }
        if keyword:
            request_params["search"] = f"openid:{keyword}"

        result = TGPATaskApi.query_single_user_log_task_v2(request_params)
        openid_set = set()
        for task in result.get("results", []):
            openid = task.get("openid")
            if openid:
                openid_set.add(openid)
                if len(openid_set) >= limit:
                    break
        return list(openid_set)

    @staticmethod
    def get_username_list(bk_biz_id):
        """
        获取用户名列表
        """
        request_params = {
            "cc_id": bk_biz_id,
            "task_type": TGPATaskTypeEnum.get_business_log_task_types(),
            "limit": 1,
        }
        result = TGPATaskApi.query_single_user_log_task_v2(request_params)
        return result["user_list"]

    @staticmethod
    def get_task_status(bk_biz_id, task_id_list):
        """
        获取任务处理状态
        :param bk_biz_id: 业务ID
        :param task_id_list: 后台任务ID列表
        :return: 任务处理状态列表
        """
        tgpa_tasks = TGPATask.objects.filter(bk_biz_id=bk_biz_id, task_id__in=task_id_list).values(
            "task_id", "process_status", "processed_at", "error_message"
        )
        task_info_map = {item["task_id"]: item for item in tgpa_tasks}
        return [
            {
                "task_id": task_id,
                "process_status": task_info_map.get(task_id, {}).get(
                    "process_status", TGPATaskProcessStatusEnum.INIT.value
                ),
                "processed_at": task_info_map.get(task_id, {}).get("processed_at"),
                "error_message": task_info_map.get(task_id, {}).get("error_message", ""),
            }
            for task_id in task_id_list
        ]

    def download_and_process_file(self):
        """
        下载并处理文件
        """
        file_handler = TGPAFileHandler(
            temp_dir=self.temp_dir,
            output_dir=self.output_dir,
            meta_fields=self.meta_fields,
            decrypt_handler=self.decrypt_handler,
            bk_biz_id=self.bk_biz_id,
        )
        file_handler.download_and_process_file(self.task_info["file_name"])

    @staticmethod
    def stream_download_file(bk_biz_id, file_name):
        """
        下载、解密、重新打包文件，并返回流式迭代器和文件信息
        :param bk_biz_id: 业务ID
        :param file_name: 文件名
        :return: (file_iterator, file_name, file_size)
        """
        feature_toggle = FeatureToggleObject.toggle(FEATURE_TOGGLE_TGPA_TASK)
        feature_config = feature_toggle.feature_config
        max_size = feature_config.get("tgpa_file_download_max_size", FEATURE_TGPA_FILE_DOWNLOAD_MAX_SIZE)
        file_info = TGPAFileHandler.get_file_info(file_name, bk_biz_id=bk_biz_id)
        decrypt_handler = get_decrypt_handler(bk_biz_id)
        # 用户上报文件不需要解密，直接流式转发（先直接在这个接口兼容，后续有其他需求再拆分模块）
        is_user_report_file = os.path.basename(file_name).startswith(TGPA_REPORT_FILE_NAME_PREFIX)
        if file_info["content_length"] > max_size or not decrypt_handler or is_user_report_file:
            # 文件大小超限或无需解密：直接从流式转发，不落盘，节省服务器磁盘和内存资源
            return (
                TGPAFileHandler.get_file_stream(file_name, bk_biz_id=bk_biz_id),
                os.path.basename(file_name),
                file_info["content_length"],
            )

        # 使用UUID作为临时目录标识，避免并发请求的目录冲突
        unique_id = uuid.uuid4().hex
        base_dir = os.path.join(TGPA_DOWNLOAD_DIR, str(bk_biz_id), unique_id)
        temp_dir = os.path.join(base_dir, "temp")
        output_dir = os.path.join(base_dir, "output")

        file_handler = TGPAFileHandler(temp_dir, output_dir, decrypt_handler=decrypt_handler, bk_biz_id=bk_biz_id)
        result_path = file_handler.download_and_repack_file(file_name)

        result_file_name = os.path.basename(result_path)
        file_size = os.path.getsize(result_path)

        def file_iterator(chunk_size=TGPA_FILE_DOWNLOAD_CHUNK_SIZE):
            """文件流式读取迭代器"""
            try:
                with open(result_path, "rb") as f:
                    while chunk := f.read(chunk_size):
                        yield chunk
            finally:
                shutil.rmtree(base_dir, ignore_errors=True)

        return file_iterator(), result_file_name, file_size
