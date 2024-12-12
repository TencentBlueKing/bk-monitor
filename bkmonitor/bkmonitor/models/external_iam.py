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

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _lazy

from bkmonitor.utils.model_manager import AbstractRecordModel

ACTION_CHOICES = (
    ("view_grafana", "view_grafana"),
    ("manage_grafana", "manage_grafana"),
)
STATUS_CHOICES = (
    ("no_status", "no_status"),
    ("approval", "approval"),
    ("success", "success"),
    ("failed", "failed"),
)


class ExternalPermission(AbstractRecordModel):
    """
    外部权限
    """

    STATUS_CHOICES = (
        ("available", "available"),
        ("invalid", "invalid"),
        ("expired", "expired"),
    )

    bk_biz_id = models.IntegerField(verbose_name="业务ID", db_index=True)
    authorized_user = models.CharField("被授权人", max_length=64)
    action_id = models.CharField("操作类型", max_length=32, choices=ACTION_CHOICES, db_index=True)
    resources = models.JSONField("资源列表", default=list)
    expire_time = models.DateTimeField("过期时间", null=True, default=None)

    class Meta:
        verbose_name = "外部权限"
        verbose_name_plural = "外部权限"
        db_table = "external_permission"
        index_together = (("authorized_user", "action_id", "bk_biz_id"),)

    def get_status(self, authorizer_role):
        from bk_dataview.permissions import GrafanaRole

        status = "available"

        # 判断是否过期
        if self.expire_time and timezone.now() > self.expire_time:
            status = "expired"

        # 判断授权人权限是否满足
        if self.action_id == "view_grafana":
            need_role = GrafanaRole.Viewer
        else:
            need_role = GrafanaRole.Editor
        if not authorizer_role or need_role > authorizer_role:
            status = "invalid"

        return status


class ExternalPermissionApplyRecord(AbstractRecordModel):
    """
    外部权限授权记录
    """

    bk_biz_id = models.IntegerField(verbose_name="业务ID", db_index=True)
    authorized_users = models.JSONField("被授权人列表", default=list)
    resources = models.JSONField("资源列表", default=list)
    action_id = models.CharField("操作类型", max_length=32, choices=ACTION_CHOICES, db_index=True)
    operate = models.CharField(
        "操作",
        choices=(
            ("delete", _lazy("删除")),
            ("create", _lazy("创建")),
            ("update", _lazy("更新")),
        ),
        db_index=True,
        max_length=12,
    )
    expire_time = models.DateTimeField("过期时间", null=True, default=None)
    approval_sn = models.CharField("审批单号", max_length=128, default="", null=True, blank=True)
    approval_url = models.CharField("审批地址", default="", max_length=1024, null=True, blank=True)
    status = models.CharField("状态", max_length=32, choices=STATUS_CHOICES, default="no_status")

    class Meta:
        verbose_name = "外部权限授权记录"
        verbose_name_plural = "外部权限授权记录"
        db_table = "external_permission_apply_record"
