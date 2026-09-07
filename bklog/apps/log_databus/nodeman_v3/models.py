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

import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.log_databus.nodeman_v3.constants import (
    NodeManV3DispatchStatus,
    NodeManV3OperationStatus,
    NodeManV3OperationType,
    NodeManV3ResultState,
    RESOURCE_TYPE_COLLECTOR_CONFIG,
)
from apps.models import OperateRecordModel


class NodeManV3Binding(OperateRecordModel):
    """
    采集项与节点管理 V3 部署策略的绑定关系。

    一个采集项对应一个部署策略：节点管理按 policy 隔离子配置记录（set = policy_<id>），
    因此「一采集项一策略」天然获得同机多采集项的隔离与精确反删。
    """

    resource_type = models.CharField(_("资源类型"), max_length=64, default=RESOURCE_TYPE_COLLECTOR_CONFIG)
    resource_key = models.CharField(_("资源标识"), max_length=255, db_index=True)
    bk_biz_id = models.IntegerField(_("业务ID"), db_index=True)
    bk_tenant_id = models.CharField(_("租户ID"), max_length=64, default="")

    collector_config_id = models.IntegerField(_("采集项ID"), db_index=True)
    deploy_policy_id = models.BigIntegerField(_("部署策略ID"), null=True, default=None)
    policy_name = models.CharField(_("部署策略名称"), max_length=255, default="")
    # 期望态指纹，用于跳过无变化的收敛，避免每次保存采集项都触发一次全量下发
    policy_fingerprint = models.CharField(_("期望态指纹"), max_length=64, default="")
    # 每次期望态变更递增；用于识别过期回调（老 generation 的状态不覆盖新一轮结果）
    generation = models.IntegerField(_("期望态版本"), default=0)
    is_enabled = models.BooleanField(_("采集项是否启用"), default=True)

    class Meta:
        app_label = "log_databus"
        verbose_name = _("节点管理V3绑定")
        verbose_name_plural = _("节点管理V3绑定")
        unique_together = ("resource_type", "bk_tenant_id", "bk_biz_id", "resource_key")


class NodeManV3Operation(OperateRecordModel):
    """
    一次控制面动作（期望态收敛或子配置清理）。

    主键用 UUID 而非自增：operation_id 会作为出站审计的关联键传给节点管理，
    自增 ID 在多环境之间会撞号，导致审计对账时无法区分环境。
    """

    id = models.UUIDField(_("操作ID"), primary_key=True, default=uuid.uuid4, editable=False)
    binding = models.ForeignKey(
        NodeManV3Binding, verbose_name=_("绑定"), on_delete=models.CASCADE, related_name="operations"
    )
    operation_type = models.CharField(_("动作类型"), max_length=32, choices=NodeManV3OperationType.CHOICES)
    generation = models.IntegerField(_("期望态版本"), default=0)
    status = models.CharField(
        _("状态"),
        max_length=32,
        choices=NodeManV3OperationStatus.choices,
        default=NodeManV3OperationStatus.PENDING,
    )
    result_state = models.CharField(
        _("结果标记"), max_length=32, choices=NodeManV3ResultState.choices, null=True, default=None
    )
    request_summary = models.JSONField(_("请求摘要"), null=True, default=None)
    error_message = models.TextField(_("错误信息"), default="")

    class Meta:
        app_label = "log_databus"
        verbose_name = _("节点管理V3操作")
        verbose_name_plural = _("节点管理V3操作")
        indexes = [
            models.Index(fields=["binding", "generation"], name="idx_nmv3_oper_binding_gen"),
            models.Index(fields=["status", "updated_at"], name="idx_nmv3_oper_status"),
        ]


class NodeManV3Workflow(OperateRecordModel):
    """
    控制面动作在节点管理侧对应的执行批次。

    workflow_id 与 trigger_id 都是字符串，无法写回 CollectorConfig.subscription_id（IntegerField），
    因此 V3 模式下 subscription_id 保持为空，任务标识只落在这张表与 task_id_list
    （MultiStrSplitByCommaField 的 sub_type 默认是 str，可以存字符串 ID）。

    部署策略 execute 只返回 trigger_id，workflow_id 需要按 deploy_policy_id 反查
    （plugin/workflow/list 支持 deploy_policy_id 过滤），拿到后才能做 per-host 详情与重试。
    """

    operation = models.ForeignKey(
        NodeManV3Operation, verbose_name=_("操作"), on_delete=models.CASCADE, related_name="workflows"
    )
    trigger_id = models.CharField(_("触发器ID"), max_length=128, default="")
    workflow_id = models.CharField(_("工作流ID"), max_length=128, default="")
    dispatch_status = models.CharField(
        _("派发状态"),
        max_length=32,
        choices=NodeManV3DispatchStatus.choices,
        default=NodeManV3DispatchStatus.PREPARED,
    )
    normalized_status = models.CharField(
        _("归一状态"),
        max_length=32,
        choices=NodeManV3OperationStatus.choices,
        default=NodeManV3OperationStatus.PENDING,
    )
    status_summary = models.JSONField(_("状态摘要"), null=True, default=None)

    class Meta:
        app_label = "log_databus"
        verbose_name = _("节点管理V3工作流")
        verbose_name_plural = _("节点管理V3工作流")
        unique_together = ("operation", "trigger_id")


class NodeManV3SubConfigTarget(OperateRecordModel):
    """
    采集项子配置的目标快照（期望态 vs 已生效）。

    状态页不能拿 bkunifylogbeat 进程 running 当成采集项已生效：同机多采集项共用一个进程，
    进程活着只说明别的采集项在跑。判定依据是该主机上是否存在本采集项的子配置文件，
    以及文件内容 md5 是否与期望一致（plugin/list_config_files 返回 name 与 md5）。
    """

    binding = models.ForeignKey(
        NodeManV3Binding, verbose_name=_("绑定"), on_delete=models.CASCADE, related_name="targets"
    )
    bk_host_id = models.IntegerField(_("主机ID"), db_index=True)
    config_file_name = models.CharField(_("子配置文件名"), max_length=255)
    generation = models.IntegerField(_("期望态版本"), default=0)
    desired_md5 = models.CharField(_("期望内容MD5"), max_length=64, default="")
    applied_md5 = models.CharField(_("已生效内容MD5"), max_length=64, default="")
    applied_at = models.DateTimeField(_("生效时间"), null=True, default=None)
    is_desired = models.BooleanField(_("是否仍在期望范围内"), default=True)

    class Meta:
        app_label = "log_databus"
        verbose_name = _("节点管理V3子配置目标")
        verbose_name_plural = _("节点管理V3子配置目标")
        unique_together = ("binding", "bk_host_id", "config_file_name")
