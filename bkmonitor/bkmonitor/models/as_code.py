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
import uuid

from django.db import models


def _get_file_path(instance, filename: str) -> str:
    """
    使用唯一ID替换文件名
    """
    if filename.endswith(".tar.gz") or filename.endswith(".tgz"):
        ext = ".tgz"
    else:
        ext = ".zip"
    filename = f"{uuid.uuid4()}{ext}"
    return "as_code/{filename}".format(filename=filename)


class AsCodeImportTask(models.Model):
    """
    AS 代码导入任务
    """

    bk_biz_id = models.IntegerField(verbose_name="业务ID")
    params = models.JSONField(verbose_name="导入参数", default=dict)
    file = models.FileField(verbose_name="配置压缩包", upload_to=_get_file_path)
    result = models.TextField(verbose_name="导入结果", null=True)

    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    update_time = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "AS 代码导入历史"
        verbose_name_plural = "AS 代码导入历史"
        ordering = ["-create_time"]
        db_table = "as_code_import_history"
