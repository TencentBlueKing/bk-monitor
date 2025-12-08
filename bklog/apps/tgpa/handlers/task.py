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
import shutil
import zipfile
from pathlib import Path

import arrow
import magic
import ujson
from django.conf import settings
from django.utils.functional import cached_property
from qcloud_cos import CosConfig, CosS3Client

from apps.api import TGPATaskApi
from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.log_databus.constants import EtlConfig, ContainerCollectorType
from apps.log_databus.handlers.collector import CollectorHandler
from apps.log_databus.models import CollectorConfig
from apps.log_search.constants import CustomTypeEnum, CollectorScenarioEnum
from apps.tgpa.constants import (
    TGPA_BASE_DIR,
    TASK_LIST_BATCH_SIZE,
    TGPATaskTypeEnum,
    FEATURE_TOGGLE_TGPA_TASK,
    TGPA_TASK_ETL_FIELDS,
    TGPA_TASK_ETL_PARAMS,
    TGPA_TASK_COLLECTOR_CONFIG_NAME,
    TGPA_TASK_COLLECTOR_CONFIG_NAME_EN,
    LOG_FILE_EXPIRE_DAYS,
)
from apps.utils.bcs import Bcs
from apps.utils.log import logger
from apps.utils.thread import MultiExecuteFunc


class TGPATaskHandler:
    def __init__(self, bk_biz_id, task_id=None, task_info=None):
        self.bk_biz_id = bk_biz_id
        self.task_id = task_id
        self.task_info = task_info  # 通过接口获取到的任务信息
        # task_id 和 task_info 不能同时为空
        if not task_id:
            self.task_id = task_info["id"]
        elif not task_info:
            self.task_info = self.get_task_info(task_id)

        # 临时目录，用于存放下载的文件、解压后的文件
        self.temp_dir = os.path.join(TGPA_BASE_DIR, str(self.bk_biz_id), str(self.task_id), "temp")
        # 输出目录，用于存放处理后的文件
        self.output_dir = os.path.join(TGPA_BASE_DIR, str(self.bk_biz_id), str(self.task_id), "output")

    @cached_property
    def meta_fields(self):
        """
        需要注入到日志中的元数据维度
        """
        task_detail = {item["key"]: item["value"] for item in self.task_info["task_info"]}
        return {
            "task_id": self.task_info["id"],
            "task_name": self.task_info["name"],
            "openid": self.task_info["openid"],
            "manufacturer": task_detail["manufacturer"],
            "sdk_version": task_detail["sdk_version"],
            "os_type": task_detail["os_type"],
            "os_version": task_detail["os_version"],
        }

    def get_task_info(self, task_id):
        """
        获取任务信息
        """
        request_params = {
            "cc_id": self.bk_biz_id,
            "task_type": TGPATaskTypeEnum.BUSINESS_LOG_V2.value,
            "task_id": task_id,
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
    def get_task_list(params, need_format=False):
        """
        获取任务列表
        """
        params["task_type"] = TGPATaskTypeEnum.BUSINESS_LOG_V2.value  # 目前只支持这种类型的任务
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

    def download_file(self, file_name):
        """
        从腾讯云COS下载文件
        """
        config = CosConfig(
            SecretId=settings.TGPA_TASK_QCLOUD_SECRET_ID,
            SecretKey=settings.TGPA_TASK_QCLOUD_SECRET_KEY,
            Region=settings.TGPA_TASK_QCLOUD_COS_REGION,
            Domain=settings.TGPA_TASK_QCLOUD_COS_DOMAIN,
        )
        client = CosS3Client(config)
        response = client.get_object(Bucket=settings.TGPA_TASK_QCLOUD_COS_BUCKET, Key=file_name)

        save_path = os.path.join(self.temp_dir, file_name)
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, "wb") as f:
            f.write(response["Body"].get_raw_stream().read())

        return save_path

    @staticmethod
    def find_log_files(path):
        """
        在目录中查找日志文件，返回日志文件相对路径列表
        """
        dir_path = Path(path).resolve()
        if not dir_path.is_dir():
            return []

        file_paths = []
        mime = magic.Magic(mime=True)
        for file in dir_path.rglob("*"):
            if not file.is_file():
                continue
            try:
                mime_type = mime.from_file(str(file))
                if mime_type and mime_type.startswith("text/"):
                    file_paths.append(str(file.relative_to(dir_path)))
            except Exception:
                continue

        return file_paths

    def process_log_file(self, log_file_path: str):
        """
        转成json格式，并添加额外字段，输出到新的文件中
        :param log_file_path: 日志文件相对路径
        """
        input_path = os.path.join(self.temp_dir, log_file_path)
        output_path = os.path.join(self.output_dir, log_file_path)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with (
            open(input_path, encoding="utf-8") as input_file,
            open(output_path, "w", encoding="utf-8") as output_file,
        ):
            for line_num, line in enumerate(input_file, 1):
                log_content = line.strip()
                log_entry = {"message": log_content, "file": log_file_path, "lineno": line_num}
                log_entry.update(self.meta_fields)
                output_file.write(f"{ujson.dumps(log_entry, ensure_ascii=False)}\n")

    def download_and_process_file(self):
        """
        下载并处理文件
        """
        # 下载压缩包、解压
        compressed_file_path = self.download_file(self.task_info["file_name"])
        with zipfile.ZipFile(compressed_file_path, "r") as zip_ref:
            zip_ref.extractall(self.temp_dir)

        # 查找并处理日志文件，忽略异常，防止单个文件处理失败导致整个任务失败
        log_files = self.find_log_files(self.temp_dir)
        for log_file_path in log_files:
            try:
                self.process_log_file(log_file_path)
            except Exception as e:
                logger.exception("Failed to process log file %s: %s", log_file_path, e)

        # 清理临时文件
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @staticmethod
    def clear_expired_files(days=LOG_FILE_EXPIRE_DAYS):
        """
        清理过期文件和空目录
        :param days: 过期天数阈值，默认为3天
        """
        if not os.path.exists(TGPA_BASE_DIR):
            logger.warning("Directory does not exist, skip cleanup: %s", TGPA_BASE_DIR)
            return

        expire_time = arrow.now().shift(days=-days).timestamp()

        for root, dirs, files in os.walk(TGPA_BASE_DIR, topdown=False):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                try:
                    if os.path.getmtime(file_path) < expire_time:
                        os.remove(file_path)
                        logger.info("Deleted expired file: %s", file_path)
                except Exception as e:
                    logger.exception("Failed to delete file %s: %s", file_path, e)

            # 处理空目录
            for dir_name in dirs:
                dir_path = os.path.join(root, dir_name)
                try:
                    # 检查目录是否为空且过期，空目录会在下一个周期被删除
                    if not os.listdir(dir_path) and os.path.getmtime(dir_path) < expire_time:
                        os.rmdir(dir_path)
                        logger.info("Deleted empty directory: %s", dir_path)
                except Exception as e:
                    logger.exception("Failed to delete directory %s: %s", dir_path, e)

    @staticmethod
    def release_collector_config(bk_biz_id: int, bk_data_id: int):
        """
        采集配置下发
        """
        feature_toggle = FeatureToggleObject.toggle(FEATURE_TOGGLE_TGPA_TASK)
        feature_config = feature_toggle.feature_config
        bcs_cluster_id = feature_config.get("bcs_cluster_id")
        container_release_params = feature_config.get("container_release_params")

        container_release_params.update(
            {
                "dataId": bk_data_id,
                "path": [os.path.join(TGPA_BASE_DIR, str(bk_biz_id))],
                "logConfigType": ContainerCollectorType.CONTAINER,
            }
        )
        Bcs(bcs_cluster_id).save_bklog_config(
            bklog_config_name=f"bklog-client-log-{bk_biz_id}",
            bklog_config=container_release_params,
        )

    @staticmethod
    def get_or_create_collector_config(bk_biz_id: int):
        """
        获取或创建采集配置
        """
        if collector_config_obj := CollectorConfig.objects.filter(
            bk_biz_id=bk_biz_id, collector_config_name_en=TGPA_TASK_COLLECTOR_CONFIG_NAME_EN
        ).first():
            return collector_config_obj

        feature_toggle = FeatureToggleObject.toggle(FEATURE_TOGGLE_TGPA_TASK)
        storage_cluster_id = feature_toggle.feature_config.get("storage_cluster_id")
        etl_params = TGPA_TASK_ETL_PARAMS
        fields = TGPA_TASK_ETL_FIELDS

        # 创建容器自定义上报
        collector_create_result = CollectorHandler().custom_create(
            bk_biz_id=bk_biz_id,
            collector_config_name=TGPA_TASK_COLLECTOR_CONFIG_NAME,
            collector_config_name_en=TGPA_TASK_COLLECTOR_CONFIG_NAME_EN,
            custom_type=CustomTypeEnum.LOG.value,
            category_id="application_check",
            etl_config=EtlConfig.BK_LOG_JSON,
            etl_params=etl_params,
            fields=fields,
            storage_cluster_id=storage_cluster_id,
            collector_scenario_id=CollectorScenarioEnum.CLIENT.value,
        )
        # 采集配置下发
        TGPATaskHandler.release_collector_config(bk_biz_id, collector_create_result["bk_data_id"])

        return CollectorConfig.objects.get(collector_config_id=collector_create_result["collector_config_id"])

    @staticmethod
    def update_collector_config(
        bk_biz_id: int,
        storage_cluster_id: int = None,
        etl_params: dict = None,
        fields: list = None,
        release_collector_config: bool = False,
    ):
        """
        更新采集配置
        :param bk_biz_id: 业务ID
        :param storage_cluster_id: 存储集群ID
        :param etl_params: 清洗配置参数
        :param fields: 清洗字段列表
        :param release_collector_config: 是否下发采集配置（如果采集下发配置有更新，可以设置为 True 重新下发）
        """
        collector_config_obj = CollectorConfig.objects.filter(
            bk_biz_id=bk_biz_id, collector_config_name_en=TGPA_TASK_COLLECTOR_CONFIG_NAME_EN
        ).first()
        if not collector_config_obj:
            return

        feature_toggle = FeatureToggleObject.toggle(FEATURE_TOGGLE_TGPA_TASK)
        if not storage_cluster_id:
            storage_cluster_id = feature_toggle.feature_config.get("storage_cluster_id")
        if not etl_params:
            etl_params = TGPA_TASK_ETL_PARAMS
        if not fields:
            fields = TGPA_TASK_ETL_FIELDS

        CollectorHandler(data=collector_config_obj).custom_update(
            collector_config_name=TGPA_TASK_COLLECTOR_CONFIG_NAME,
            category_id=collector_config_obj.category_id,
            etl_config=EtlConfig.BK_LOG_JSON,
            etl_params=etl_params,
            fields=fields,
            storage_cluster_id=storage_cluster_id,
        )
        if release_collector_config:
            TGPATaskHandler.release_collector_config(bk_biz_id, collector_config_obj.bk_data_id)
