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


import hashlib
import os
import subprocess

from common.log import logger
from django.db import models
from monitor_web.models import OperateRecordModelBase


def generate_upload_path(instance, filename):
    return os.path.join(instance.relative_path, instance.actual_filename)


class UploadedFileInfo(OperateRecordModelBase):
    original_filename = models.CharField("原始文件名", max_length=255)
    actual_filename = models.CharField("文件名", max_length=255)
    relative_path = models.TextField("文件相对路径")
    file_data = models.FileField("文件内容", upload_to=generate_upload_path)
    file_md5 = models.CharField("文件内容MD5", max_length=50)
    is_dir = models.BooleanField("是否为目录", default=False)

    def generate_file_md5(self):
        if self.file_data:
            return hashlib.md5(self.file_data.file.read()).hexdigest()

    @property
    def file_type(self):
        file_command = ["file", "-b", self.file_data.path]
        try:
            stdout, stderr = subprocess.Popen(file_command, stdout=subprocess.PIPE).communicate()
        except Exception as e:
            logger.exception("不存在的文件，获取文件类型失败：%s" % e)
            return ""
        return stdout

    def save(self, *args, **kwargs):
        if not self.file_md5:
            self.file_md5 = self.generate_file_md5()

        return super(UploadedFileInfo, self).save(*args, **kwargs)
