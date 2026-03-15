"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import hashlib
import logging
import os
import subprocess
from functools import cached_property

from django.db import models
from django.utils.translation import gettext as _

from bkmonitor.utils.db.fields import ConfigDataField, JsonField, SymmetricJsonField
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from constants.common import DEFAULT_TENANT_ID
from monitor.constants import UPTIME_CHECK_DB, UptimeCheckProtocol
from monitor_web.models import OperateRecordModelBase

logger = logging.getLogger(__name__)


class OperateRecordModel(OperateRecordModelBase):
    class Meta:
        abstract = True


class RolePermission(OperateRecordModel):
    """
    角色权限（被用于iam权限升级）
    """

    biz_id = models.IntegerField("业务ID")
    role = models.CharField("角色", max_length=128)
    permission = models.CharField("权限", max_length=32, default="", blank=True)


# 配置相关使用key-value形式存储
# key的格式: '[dashboard_view_config]:menu_id=1'
class UserConfig(models.Model):
    """用户配置信息"""

    class Keys:
        FUNCTION_ACCESS_RECORD = "function_access_record"
        DEFAULT_BIZ_ID = "default_biz_id"

    username = models.CharField("用户名", max_length=30)
    key = models.CharField("key", max_length=255)
    value = ConfigDataField("配置信息")
    data_created = models.DateTimeField("创建时间", auto_now_add=True)
    data_updated = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = _("用户配置信息")
        unique_together = (("username", "key"),)


class ApplicationConfig(models.Model):
    """业务配置信息"""

    cc_biz_id = models.IntegerField("业务id")
    key = models.CharField("key", max_length=255)
    value = ConfigDataField("配置信息")
    data_created = models.DateTimeField("创建时间", auto_now_add=True)
    data_updated = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = _("业务配置信息")
        unique_together = (("cc_biz_id", "key"),)


class GlobalConfig(models.Model):
    """全局配置信息"""

    key = models.CharField("key", max_length=255, unique=True)
    value = ConfigDataField("配置信息")
    data_created = models.DateTimeField("创建时间", auto_now_add=True)
    data_updated = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = _("全局配置信息")


NODE_IP_TYPE_CHOICES = [(0, "all"), (4, "IPv4"), (6, "IPv6")]

NODE_IP_TYPE_DICT = {status: desc for (status, desc) in NODE_IP_TYPE_CHOICES}


class UptimeCheckNode(OperateRecordModel):
    bk_tenant_id = models.CharField("租户ID", default=DEFAULT_TENANT_ID, max_length=128)
    bk_biz_id = models.IntegerField("业务ID", default=0, db_index=True)
    is_common = models.BooleanField("是否为通用节点", default=False, db_index=True)
    biz_scope = JsonField("指定业务可见范围", default=[])
    ip_type = models.IntegerField("IP类型", default=4, choices=NODE_IP_TYPE_CHOICES)
    name = models.CharField("节点名称", max_length=50)

    ip = models.CharField("IP地址", blank=True, null=True, default="", max_length=64)
    bk_host_id = models.IntegerField("主机ID", null=True, blank=True)
    plat_id = models.IntegerField("云区域ID", blank=True, null=True, default=0)
    # 地点改为可选
    location = JsonField("地区", default="{}")
    carrieroperator = models.CharField("外网运营商", max_length=50, blank=True, null=True, default="")

    @property
    def full_table_name(self):
        return "{}_{}_{}".format(self.bk_biz_id, UPTIME_CHECK_DB, "heartbeat")

    @property
    def permission_exempt(self):
        return True

    class Meta:
        verbose_name = _("拨测节点")
        verbose_name_plural = _("拨测节点")

        index_together = [
            ["name", "bk_biz_id"],
        ]

    def get_title(self):
        return _("拨测节点（%s）") % self.name

    def __unicode__(self):
        return self.get_title()


class UptimeCheckTaskSubscription(OperateRecordModel):
    uptimecheck_id = models.IntegerField("拨测任务id", default=0)
    subscription_id = models.IntegerField("节点管理订阅ID", default=0)
    bk_biz_id = models.IntegerField("业务ID", default=0)

    class Meta:
        # 每个任务针对每个业务只能有一个item
        unique_together = (("uptimecheck_id", "bk_biz_id"),)


class UptimeCheckTask(OperateRecordModel):
    class Protocol:
        TCP = UptimeCheckProtocol.TCP
        UDP = UptimeCheckProtocol.UDP
        HTTP = UptimeCheckProtocol.HTTP
        ICMP = UptimeCheckProtocol.ICMP

    PROTOCOL_CHOICES = (
        (Protocol.TCP, "TCP"),
        (Protocol.UDP, "UDP"),
        (Protocol.HTTP, "HTTP(S)"),
        (Protocol.ICMP, "ICMP"),
    )

    class Status:
        NEW_DRAFT = "new_draft"
        RUNNING = "running"
        STOPED = "stoped"
        STARTING = "starting"
        STOPING = "stoping"
        START_FAILED = "start_failed"
        STOP_FAILED = "stop_failed"

    STATUS_CHOICES = (
        (Status.NEW_DRAFT, _("未保存")),
        (Status.RUNNING, _("运行中")),
        (Status.STOPED, _("未启用")),
        (Status.STARTING, _("启动中")),
        (Status.STOPING, _("停止中")),
        (Status.START_FAILED, _("启动失败")),
        (Status.STOP_FAILED, _("停止失败")),
    )
    permission_exempt = True

    bk_biz_id = models.IntegerField("业务ID", db_index=True)
    name = models.CharField("任务名称", max_length=128, db_index=True)
    protocol = models.CharField("协议", choices=PROTOCOL_CHOICES, max_length=10)
    labels = models.JSONField("自定义标签", default=dict, null=True, blank=True)
    indepentent_dataid = models.BooleanField("独立业务数据ID", default=False)
    check_interval = models.PositiveIntegerField("拨测周期(分钟)", default=5)
    # 地点变为可选项
    location = JsonField("地区", default="{}")

    nodes = models.ManyToManyField(UptimeCheckNode, verbose_name="拨测节点", related_name="tasks")
    status = models.CharField("当前状态", max_length=20, choices=STATUS_CHOICES, default=Status.NEW_DRAFT)
    config = SymmetricJsonField("拨测配置", null=True, blank=True)

    @property
    def full_table_name(self):
        return f"{self.bk_biz_id}_{UPTIME_CHECK_DB}_{self.protocol.lower()}"

    @cached_property
    def bk_tenant_id(self):
        return bk_biz_id_to_bk_tenant_id(self.bk_biz_id)

    class Meta:
        verbose_name = _("拨测任务")
        verbose_name_plural = _("拨测任务")

    def get_title(self):
        return _("拨测任务（%s）") % self.name

    def __unicode__(self):
        return self.get_title()


class UptimeCheckTaskCollectorLog(models.Model):
    """
    下发拨测任务时，获取节点管理中相关节点执行日志
    """

    task_id = models.IntegerField("拨测任务ID")
    error_log = JsonField("错误日志", default="{}")
    is_deleted = models.BooleanField("已删除", default=False)
    subscription_id = models.IntegerField("节点管理订阅ID", default=0)
    nodeman_task_id = models.IntegerField("节点管理任务ID", default=0)


class UptimeCheckGroup(OperateRecordModel):
    """
    拨测任务分组
    """

    name = models.CharField("分组名称", max_length=50)
    tasks = models.ManyToManyField(UptimeCheckTask, verbose_name="拨测任务", related_name="groups")
    logo = models.TextField("图片base64形式", default="", blank=True)
    bk_biz_id = models.IntegerField("业务ID", default=0)
    permission_exempt = True

    # 运行中任务
    # 如果停用分组中关联的某任务，那么被停用的任务既不在分组曲线中显示，也不会参与分组的可用率计算
    @property
    def running_tasks(self):
        return self.tasks.filter(status=UptimeCheckTask.Status.RUNNING)

    class Meta:
        verbose_name = _("拨测分组")
        verbose_name_plural = _("拨测分组")


def generate_upload_path(instance, filename):
    return os.path.join(instance.relative_path, instance.actual_filename)


class UploadedFile(OperateRecordModel):
    original_filename = models.CharField("原始文件名", max_length=255)
    actual_filename = models.CharField("文件名", max_length=255)
    relative_path = models.TextField("文件相对路径")
    file_data = models.FileField("文件内容", upload_to=generate_upload_path)

    @property
    def file_md5(self):
        return hashlib.md5(self.file_data.file.read()).hexdigest()

    @property
    def file_type(self):
        file_command = ["file", "-b", self.file_data.path]
        try:
            stdout, stderr = subprocess.Popen(file_command, stdout=subprocess.PIPE).communicate()
        except Exception as e:
            logger.exception(_("不存在的文件，获取文件类型失败：%s") % e)
            return ""
        return stdout
