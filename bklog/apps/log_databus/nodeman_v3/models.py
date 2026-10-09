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
    COLLECTOR_CONFIG_ID_NOT_APPLICABLE,
    NodeManV3DispatchStatus,
    NodeManV3OperationStatus,
    NodeManV3OperationType,
    NodeManV3ResultState,
    RESOURCE_TYPE_COLLECTOR_CONFIG,
)
from apps.models import JsonField, OperateRecordModel


class NodeManV3Binding(OperateRecordModel):
    """
    业务资源与节点管理 V3 部署策略的绑定关系。

    两种资源类型：

    - collector_config：一个采集项一条子配置策略。节点管理按 policy 隔离子配置记录
      （set = deploy_policy_<id>），因此「一采集项一策略」天然获得同机多采集项的隔离与精确反删。
    - collector_plugin：一个业务一条采集器安装策略，承载 specify_plugin。之所以不放进采集项策略，
      见 policy.build_plugin_install_payload 的说明（会导致同机后建采集项被静默剔除并删配置）。
    """

    resource_type = models.CharField(_("资源类型"), max_length=64, default=RESOURCE_TYPE_COLLECTOR_CONFIG)
    resource_key = models.CharField(_("资源标识"), max_length=255, db_index=True)
    bk_biz_id = models.IntegerField(_("业务ID"), db_index=True)
    bk_tenant_id = models.CharField(_("租户ID"), max_length=64, default="")

    # 安装策略不属于任何单个采集项，该字段为 COLLECTOR_CONFIG_ID_NOT_APPLICABLE
    collector_config_id = models.IntegerField(_("采集项ID"), db_index=True, default=COLLECTOR_CONFIG_ID_NOT_APPLICABLE)
    deploy_policy_id = models.BigIntegerField(_("部署策略ID"), null=True, default=None)
    policy_name = models.CharField(_("部署策略名称"), max_length=255, default="")
    # 期望态指纹，用于跳过无变化的收敛，避免每次保存采集项都触发一次全量下发
    policy_fingerprint = models.CharField(_("期望态指纹"), max_length=64, default="")
    # 最近一次下发给节点管理的 scopes。安装策略的目标范围要按业务并集所有启用中的采集项，
    # 从这里取而不是回头重算 CollectorConfig：重算会依赖调用方是否已经改过 is_active/target_nodes，
    # 顺序稍有差别就会算出与实际下发不一致的并集。
    desired_scopes = JsonField(_("最近下发的目标范围"), null=True, default=None)
    # 每次期望态变更递增；用于识别过期回调（老 generation 的状态不覆盖新一轮结果）
    generation = models.IntegerField(_("期望态版本"), default=0)
    is_enabled = models.BooleanField(_("采集项是否启用"), default=True)
    # 最近一次下发声明的子配置模板名。定时收敛要靠它推出主机上的落地文件名
    # （<模板名>_deploy_<policy_id><扩展名>）去做状态对账；不存这份快照就得在每轮定时任务里
    # 重建一遍订阅 steps，而重建依赖 bk_data_id 与 params 当前值，采集项改过参数之后
    # 推出来的文件名会与实际落地的那一份对不上。
    sub_config_template_names = JsonField(_("子配置模板名"), null=True, default=None)
    # 目标快照最近一次收敛时间
    target_snapshot_at = models.DateTimeField(_("目标快照时间"), null=True, default=None)
    # 最近一次兜底全量重放时间。即使目标没变也要周期性重放，用于补回「采集器当时不 running
    # 导致这一轮没下发」留下的空洞（analyze_specific_plugin_sub_config_template.go:113-117）
    last_heal_at = models.DateTimeField(_("兜底重放时间"), null=True, default=None)

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

    NodeMan v3.0.1-alpha.84 起，deploy_policy/execute 返回父 workflow_id。父流程只表示
    dispatch，实际部署结果需要沿 deploy_policy/workflow/list 的 children 下钻到 plugin
    workflow。parent_workflow_id 与 plugin_workflow_ids 保存新契约；trigger_id 与 workflow_id
    保留给 alpha.84 之前已经落库的任务，避免滚动升级期间历史状态页失效。

    这些 ID 都是字符串，无法写回 CollectorConfig.subscription_id（IntegerField），因此 V3
    模式下 subscription_id 保持为空，任务标识只落在这张表与 task_id_list。
    """

    operation = models.ForeignKey(
        NodeManV3Operation, verbose_name=_("操作"), on_delete=models.CASCADE, related_name="workflows"
    )
    parent_workflow_id = models.CharField(_("部署策略父工作流ID"), max_length=128, default="", db_index=True)
    plugin_workflow_ids = models.JSONField(_("插件子工作流ID列表"), default=list)
    # 旧契约兼容字段：workflow_id 表示 plugin 子 workflow，而不是 deploy-policy 父 workflow。
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

    @property
    def task_id(self) -> str:
        """返回可暴露给日志平台任务列表的稳定入口。"""
        return self.parent_workflow_id or self.workflow_id or self.trigger_id


class NodeManV3SubConfigTarget(OperateRecordModel):
    """
    采集项子配置的目标快照（期望态 vs 已生效）。

    状态页不能拿 bkunifylogbeat 进程 running 当成采集项已生效：同机多采集项共用一个进程，
    进程活着只说明别的采集项在跑。判定依据是该主机上是否存在本采集项的子配置文件
    （plugin/list_config_files 按 name 回读），以及本地记录的已生效代次。
    """

    binding = models.ForeignKey(
        NodeManV3Binding, verbose_name=_("绑定"), on_delete=models.CASCADE, related_name="targets"
    )
    bk_host_id = models.IntegerField(_("主机ID"), db_index=True)
    config_file_name = models.CharField(_("子配置文件名"), max_length=255)
    generation = models.IntegerField(_("期望态版本"), default=0)
    # 主机上那份子配置的真实内容 MD5，由 plugin/list_config_files 回读后写入。
    # 刻意**没有**配对的 desired_md5：这个 md5 是节点管理渲染完模板之后的文件内容摘要，
    # 而模板渲染发生在对方侧，我们本地只有 custom_config_context，算不出同一个值。
    # 留一个算不出来的期望字段在旁边，早晚会有人写成 `desired != applied 即未生效`
    # 而拿到 100% 误判。要做内容级对账得等节点管理支持提交端预渲染。
    applied_md5 = models.CharField(_("已生效内容MD5"), max_length=64, default="")
    applied_at = models.DateTimeField(_("生效时间"), null=True, default=None)
    is_desired = models.BooleanField(_("是否仍在期望范围内"), default=True)

    class Meta:
        app_label = "log_databus"
        verbose_name = _("节点管理V3子配置目标")
        verbose_name_plural = _("节点管理V3子配置目标")
        unique_together = ("binding", "bk_host_id", "config_file_name")
