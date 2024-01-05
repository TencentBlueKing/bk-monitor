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

from bkstorages.backends.bkrepo import BKRepoStorage
from django.utils.translation import ugettext_lazy as _

from apm_web.models import Application, ProfileUploadRecord
from apm_web.profile.converter import get_converter_by_input_type
from apm_web.profile.doris.handler import StorageHandler

logger = logging.getLogger("apm_web")


class ProfilingFileHandler:
    def __init__(self):
        self.bk_repo_storage = BKRepoStorage(bucket="bkmonitor_apm_profile")

    @classmethod
    def parse_file(cls, fh, file_type: str, profile_id: str, bk_biz_id: int, app_name: str):
        """
        :param fh : 文件句柄
        :param str file_type: 上传文件类型
        :param str profile_id: profile_id
        :param int bk_biz_id: 业务id
        :param str app_name: 应用名称
        """
        try:
            application = Application.objects.get(bk_biz_id=bk_biz_id, app_name=app_name)
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"application ({app_name}) not exists, error{e}")
            return

        try:
            converter = get_converter_by_input_type(file_type)(preset_profile_id=profile_id)
            data = fh.read()
            p = converter.convert(data)
        except Exception as e:
            logger.exception(f"convert profiling data failed, error: {e}")
            p = None

        param = {"file_type": file_type, "profile_id": profile_id, "bk_biz_id": bk_biz_id, "app_name": app_name}
        queryset = ProfileUploadRecord.objects.filter(**param)

        if p is None:
            queryset.update(status=_("解析失败"))
            logger.error(_("无法转换 profiling 数据"))
            return

        handler = StorageHandler(application, p)
        try:
            handler.save_profile()
        except Exception as e:  # pylint: disable=broad-except
            logger.exception(f"save profiling data to doris failed, error: {e}")
            queryset.update(status=_("解析失败"))
            return

        queryset.update(status=_("解析成功"))
