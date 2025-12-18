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
import zipfile
from pathlib import Path

import arrow
import magic
import ujson
from django.conf import settings
from qcloud_cos import CosConfig, CosS3Client

from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.log_databus.constants import ContainerCollectorType, EtlConfig
from apps.log_databus.handlers.collector import CollectorHandler
from apps.log_databus.models import CollectorConfig
from apps.log_search.constants import CustomTypeEnum, CollectorScenarioEnum
from apps.tgpa.constants import (
    LOG_FILE_EXPIRE_DAYS,
    TGPA_BASE_DIR,
    FEATURE_TOGGLE_TGPA_TASK,
    TGPA_TASK_COLLECTOR_CONFIG_NAME_EN,
    TGPA_TASK_ETL_PARAMS,
    TGPA_TASK_ETL_FIELDS,
    TGPA_TASK_COLLECTOR_CONFIG_NAME,
    TGPA_TASK_SORT_FIELDS,
    TGPA_TASK_TARGET_FIELDS,
)
from apps.utils.bcs import Bcs
from apps.utils.log import logger


class TGPAFileHandler:
    """TGPA文件处理"""

    def __init__(self, temp_dir, output_dir, meta_fields=None):
        # temp_dir: 临时目录，处理完成后删除; output_dir: 输出目录，存放处理后的文件
        self.temp_dir = temp_dir
        self.output_dir = output_dir
        self.meta_fields = meta_fields or {}

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
            open(input_path, encoding="utf-8", errors="replace") as input_file,
            open(output_path, "w", encoding="utf-8") as output_file,
        ):
            for line_num, line in enumerate(input_file, 1):
                log_content = line.strip()
                log_entry = {"message": log_content, "file": log_file_path, "lineno": line_num}
                log_entry.update(self.meta_fields)
                output_file.write(f"{ujson.dumps(log_entry, ensure_ascii=False)}\n")

    def download_and_process_file(self, file_name):
        """
        下载并处理文件
        """
        # 下载压缩包、解压
        compressed_file_path = self.download_file(file_name)
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


class TGPACollectorConfigHandler:
    """TGPA采集配置处理"""

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
                "path": [os.path.join(TGPA_BASE_DIR, str(bk_biz_id), "**/*")],
                "logConfigType": ContainerCollectorType.CONTAINER,
            }
        )
        Bcs(bcs_cluster_id).save_bklog_config(
            bklog_config_name=f"bklog-client-log-{bk_biz_id}",
            bklog_config=container_release_params,
        )

    @classmethod
    def get_or_create_collector_config(cls, bk_biz_id: int) -> CollectorConfig:
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
            sort_fields=TGPA_TASK_SORT_FIELDS,
            target_fields=TGPA_TASK_TARGET_FIELDS,
            collector_scenario_id=CollectorScenarioEnum.CLIENT.value,
        )
        # 采集配置下发
        cls.release_collector_config(bk_biz_id, collector_create_result["bk_data_id"])

        return CollectorConfig.objects.get(collector_config_id=collector_create_result["collector_config_id"])

    @classmethod
    def update_collector_config(
        cls,
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
            sort_fields=TGPA_TASK_SORT_FIELDS,
            target_fields=TGPA_TASK_TARGET_FIELDS,
        )
        if release_collector_config:
            cls.release_collector_config(bk_biz_id, collector_config_obj.bk_data_id)
