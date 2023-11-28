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


class ProfileUploadRecord(models.Model):
    """Profile upload record"""

    bk_biz_id = models.BigIntegerField("业务ID")
    app_name = models.CharField("应用名称", max_length=50)
    file_type = models.CharField(
        choices=[("perf_script", "perf_script"), ("pprof", "pprof"), ("jfr", "jfr")],
        max_length=50,
        db_index=True,
    )
    file_md5 = models.CharField("文件MD5", max_length=32, db_index=True)
    profile_id = models.CharField("profile ID", max_length=128)
    operator = models.CharField("操作人", max_length=128)
    uploaded_time = models.DateTimeField("上传时间", auto_now_add=True)
