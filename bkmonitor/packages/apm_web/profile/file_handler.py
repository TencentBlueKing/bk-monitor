# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import logging
import tempfile

from bkstorages.backends.bkrepo import BKRepoStorage
from django.utils.translation import ugettext_lazy as _

from apm_web.models import ProfileUploadRecord, UploadedFileStatus
from apm_web.profile.collector import CollectorHandler
from apm_web.profile.converter import get_converter_by_input_type

logger = logging.getLogger("apm_web")


class ProfilingFileHandler:
    def __init__(self):
        self.bk_repo_storage = BKRepoStorage()

    def get_file_data(self, key):
        with tempfile.TemporaryFile() as fp:
            self.bk_repo_storage.client.download_fileobj(key=key, fh=fp)
            fp.seek(0)
            data = fp.read()
        return data

    def parse_file(self, key, file_type: str, profile_id: str, bk_biz_id: int, service_name: str):
        """
        :param key : 文件完整路径
        :param str file_type: 上传文件类型
        :param str profile_id: profile_id
        :param int bk_biz_id: 业务id
        :param str service_name: 服务名
        """
        param = {"file_type": file_type, "profile_id": profile_id, "bk_biz_id": bk_biz_id}
        queryset = ProfileUploadRecord.objects.filter(**param)

        try:
            converter = get_converter_by_input_type(file_type)(
                preset_profile_id=profile_id,
                # Q: why we need to pass service_name manually?
                # A: because the data will be sent to collector with bk_data_token
                # which only contains bk_biz_id & app_name, service_name is required for cleaning in bk_base,
                # so add it into labels
                inject_labels={"service_name": service_name},
                init_first_empty_str=False,
            )
            # 从 bkrepo 中获取文件数据
            data = self.get_file_data(key)
            p = converter.convert(data)
        except Exception as e:  # noqa
            content = f"convert profiling data failed, error: {e}"
            logger.exception(content)
            queryset.update(content=content)
            p = None

        if p is None:
            queryset.update(status=UploadedFileStatus.PARSING_FAILED)
            logger.error(_("无法转换 profiling 数据"))
            return

        sample_type = converter.get_sample_type()

        meta_info = {
            "data_types": [{"key": sample_type["type"], "name": str(sample_type["type"]).upper()}],
            "sample_type": sample_type,
        }
        queryset.update(status=UploadedFileStatus.PARSING_SUCCEED, meta_info=meta_info)

        try:
            CollectorHandler.send_to_builtin_datasource(p)
        except Exception as e:  # pylint: disable=broad-except
            content = f"save profiling data to doris failed, error: {e}"
            logger.exception(content)
            queryset.update(status=UploadedFileStatus.STORE_FAILED, content=content)
            return

        queryset.update(status=UploadedFileStatus.STORE_SUCCEED)
