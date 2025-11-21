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

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.tgpa.constants import TGPATaskProcessStatusEnum


class TGPATask(models.Model):
    task_id = models.IntegerField(_("任务唯一标识"), unique=True, db_index=True)
    bk_biz_id = models.IntegerField(_("业务id"), db_index=True)
    log_path = models.TextField(_("日志路径"), null=True, blank=True)
    process_status = models.CharField(_("处理状态"), max_length=64, default=TGPATaskProcessStatusEnum.PENDING.value)
    processed_at = models.DateTimeField(_("处理时间"), auto_now_add=True)

    class Meta:
        verbose_name = _("TGPA任务")
        verbose_name_plural = _("TGPA任务")
