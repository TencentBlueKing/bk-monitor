"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _


class UploadedFileStatus(models.TextChoices):
    # 已上传
    UPLOADED = "uploaded", _("已上传")
    # 解析失败
    PARSING_FAILED = "parsing_failed", _("解析失败")
    # 解析成功
    PARSING_SUCCEED = "parsing_succeed", _("已解析")
    # 存储成功
    STORE_SUCCEED = "store_succeed", _("已存储")
    # 存储失败
    STORE_FAILED = "store_failed", _("存储失败")


class ProfileUploadRecord(models.Model):
    """Profile upload record"""

    bk_biz_id = models.BigIntegerField("业务ID")
    app_name = models.CharField("应用名称", max_length=50, null=True)
    file_type = models.CharField(
        choices=[("perf_script", "perf_script"), ("pprof", "pprof"), ("jfr", "jfr")],
        max_length=50,
        db_index=True,
        null=True,
    )
    file_key = models.CharField("文件存储路径", max_length=1024)
    file_md5 = models.CharField("文件MD5", max_length=32, db_index=True)
    profile_id = models.CharField("profile ID", max_length=128)
    operator = models.CharField("操作人", max_length=128)
    uploaded_time = models.DateTimeField("上传时间", auto_now_add=True)
    file_name = models.CharField("新文件名称", max_length=50, default="")
    origin_file_name = models.CharField("上传文件名称", max_length=255, default="")
    # 文件大小, 单位Bytes
    file_size = models.BigIntegerField("文件大小", default=0)
    status = models.CharField(
        "状态", max_length=36, choices=UploadedFileStatus.choices, default=UploadedFileStatus.UPLOADED
    )
    service_name = models.CharField("服务名称", max_length=50, default="default")

    meta_info = models.JSONField("数据元信息", default=dict)

    content = models.TextField("运行信息", null=True)
    query_start_time = models.CharField("查询此文件的 profile 数据时的开始时间", max_length=128, null=True)
    query_end_time = models.CharField("查询此文件的 profile 数据时的结束时间", max_length=128, null=True)
