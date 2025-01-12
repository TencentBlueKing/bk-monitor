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
from datetime import datetime, timedelta

import arrow
from django.db import models

from bkmonitor.utils.itsm import ApprovalStatusEnum
from bkmonitor.utils.model_manager import AbstractRecordModel, Model
from constants.new_report import (
    ChannelEnum,
    ScenarioEnum,
    SendModeEnum,
    SendStatusEnum,
    SubscriberTypeEnum,
)


class ReportChannel(Model):
    """
    订阅渠道
    """

    report_id = models.IntegerField(verbose_name="订阅ID", db_index=True)
    channel_name = models.CharField(verbose_name="渠道名称", max_length=32, choices=ChannelEnum.get_choices())
    is_enabled = models.BooleanField(verbose_name="是否启用", default=True)
    subscribers = models.JSONField(verbose_name="订阅人", default=list)
    send_text = models.CharField(verbose_name="提示文案", max_length=256, default="", blank=True, null=True)

    class Meta:
        verbose_name = "订阅渠道"
        verbose_name_plural = "订阅渠道"
        db_table = "report_channel"


class ReportSendRecord(Model):
    """
    订阅发送记录
    """

    report_id = models.IntegerField(verbose_name="订阅ID", db_index=True)
    channel_name = models.CharField(verbose_name="渠道名称", max_length=32, choices=ChannelEnum.get_choices())
    send_results = models.JSONField(verbose_name="发送结果详情", default=list)
    send_status = models.CharField(verbose_name="发送状态", max_length=32, choices=SendStatusEnum.get_choices())
    send_time = models.DateTimeField(verbose_name="发送时间")
    send_round = models.IntegerField(verbose_name="发送轮次", default=0)

    class Meta:
        verbose_name = "订阅发送记录"
        verbose_name_plural = "订阅发送记录"
        db_table = "report_send_record"
        index_together = ["report_id", "send_round"]


class Report(AbstractRecordModel):
    """
    订阅报表
    """

    name = models.CharField(verbose_name="订阅名称", max_length=64)
    bk_biz_id = models.IntegerField(verbose_name="业务ID", default=0, db_index=True)
    scenario = models.CharField(verbose_name="订阅场景", max_length=32, choices=ScenarioEnum.get_choices())
    frequency = models.JSONField(verbose_name="发送频率", default=dict)
    content_config = models.JSONField(verbose_name="内容配置", default=dict)
    scenario_config = models.JSONField(verbose_name="场景配置", default=dict)
    start_time = models.IntegerField(verbose_name="开始时间", null=True)
    end_time = models.IntegerField(verbose_name="结束时间", null=True)
    send_mode = models.CharField(verbose_name="发送模式", max_length=32, choices=SendModeEnum.get_choices())
    subscriber_type = models.CharField(verbose_name="订阅人类型", max_length=32, choices=SubscriberTypeEnum.get_choices())
    send_round = models.IntegerField(verbose_name="最近一次发送轮次", default=0)
    is_manager_created = models.BooleanField(verbose_name="是否管理员创建", default=False)

    class Meta:
        verbose_name = "邮件订阅"
        verbose_name_plural = "邮件订阅"
        db_table = "report"

    @staticmethod
    def is_invalid(end_time, frequency):
        now_timestamp = arrow.now().timestamp
        if end_time and now_timestamp > end_time:
            return True
        if frequency["type"] == 1:
            now_datetime = datetime.now()
            run_time = datetime.strptime(frequency["run_time"], '%Y-%m-%d %H:%M:%S')
            # 过一个检测周期后失效，避免执行前失效
            threshold_time = run_time + timedelta(minutes=1)
            if now_datetime > threshold_time:
                return True
        return False


class ReportApplyRecord(AbstractRecordModel):
    """
    订阅审批记录
    """

    report_id = models.IntegerField(verbose_name="订阅ID", db_index=True)
    bk_biz_id = models.IntegerField(verbose_name="业务ID", db_index=True)
    approvers = models.JSONField("审批人", default=list)
    expire_time = models.DateTimeField("过期时间", null=True, default=None)
    approval_step = models.JSONField("当前步骤", default=list)
    approval_sn = models.CharField("审批单号", max_length=128, default="", null=True, blank=True)
    approval_url = models.CharField("审批地址", default="", max_length=1024, null=True, blank=True)
    status = models.CharField(
        "审批状态", max_length=32, choices=ApprovalStatusEnum.get_choices(), default=ApprovalStatusEnum.RUNNING.value
    )

    class Meta:
        verbose_name = "订阅审批记录"
        verbose_name_plural = "订阅审批记录"
        db_table = "report_apply_record"


class RenderImageTask(Model):
    """
    渲染图片任务
    """

    class Status:
        PENDING = "pending"
        RENDERING = "rendering"
        SUCCESS = "success"
        FAILED = "failed"

    STATUS = (
        (Status.PENDING, "待渲染"),
        (Status.RENDERING, "渲染中"),
        (Status.SUCCESS, "渲染成功"),
        (Status.FAILED, "渲染失败"),
    )

    class Type:
        DASHBOARD = "dashboard"

    TYPE = ((Type.DASHBOARD, "仪表盘"),)

    task_id = models.UUIDField(verbose_name="任务ID", default=uuid.uuid4, editable=False, db_index=True)
    create_time = models.DateTimeField(verbose_name="创建时间", auto_now_add=True)
    start_time = models.DateTimeField(verbose_name="开始时间", null=True)
    finish_time = models.DateTimeField(verbose_name="完成时间", null=True)
    image = models.ImageField(verbose_name="图片", null=True, upload_to="render/image/")
    options = models.JSONField(verbose_name="图片渲染参数", default=dict)
    type = models.CharField(verbose_name="类型", max_length=128, choices=TYPE)
    status = models.CharField(verbose_name="状态", max_length=128, choices=STATUS)
    error = models.TextField(verbose_name="错误信息", default="")
    username = models.CharField(verbose_name="用户名", max_length=128, default="")

    class Meta:
        verbose_name = "渲染图片任务"
        verbose_name_plural = "渲染图片任务"
        db_table = "render_image_task"
