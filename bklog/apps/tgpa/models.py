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

from apps.tgpa.constants import TGPATaskProcessStatusEnum, TGPAReportSyncStatusEnum


class TGPATask(models.Model):
    """
    客户端日志捞取任务
    """

    task_id = models.IntegerField(_("后台任务id"), unique=True, db_index=True)
    bk_biz_id = models.IntegerField(_("业务id"), db_index=True)
    log_path = models.TextField(_("日志路径"), null=True, blank=True)
    task_status = models.CharField(_("任务状态"), max_length=64, null=True)
    file_status = models.CharField(_("文件状态"), max_length=64, null=True)
    process_status = models.CharField(_("处理状态"), max_length=64, default=TGPATaskProcessStatusEnum.INIT.value)
    processed_at = models.DateTimeField(_("处理时间"), null=True)
    error_message = models.TextField(_("错误信息"), null=True, blank=True)

    class Meta:
        verbose_name = _("TGPA任务")
        verbose_name_plural = _("TGPA任务")


class TGPAReportSyncRecord(models.Model):
    """
    客户端上报同步记录
    """

    bk_biz_id = models.IntegerField(_("业务id"), db_index=True)
    openid_list = models.JSONField(_("openid列表"), null=True)
    file_name_list = models.JSONField(_("文件名列表"), null=True)
    status = models.CharField(_("状态"), max_length=64, default=TGPAReportSyncStatusEnum.PENDING.value)
    error_message = models.TextField(_("错误信息"), null=True, blank=True)
    created_at = models.DateTimeField(_("创建时间"), auto_now_add=True, db_index=True)
    created_by = models.CharField(_("创建者"), max_length=32, default="")

    class Meta:
        verbose_name = _("客户端上报同步记录")
        verbose_name_plural = _("客户端上报同步记录")


class TGPAReport(models.Model):
    """
    客户端上报文件处理记录
    """

    bk_biz_id = models.IntegerField(_("业务id"), db_index=True)
    file_name = models.CharField(_("文件名"), max_length=512)
    openid = models.CharField(_("openid"), max_length=128, null=True, blank=True)
    processed_at = models.DateTimeField(_("处理时间"), null=True)
    process_status = models.CharField(_("处理状态"), max_length=64, default=TGPAReportSyncStatusEnum.PENDING.value)
    error_message = models.TextField(_("错误信息"), null=True, blank=True)
    record_id = models.IntegerField(_("同步记录id"), db_index=True)

    class Meta:
        verbose_name = _("客户端上报")
        verbose_name_plural = _("客户端上报")
        ordering = ("-processed_at",)
        unique_together = ("file_name", "record_id")
