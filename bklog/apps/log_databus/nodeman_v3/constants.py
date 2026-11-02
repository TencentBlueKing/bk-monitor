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

# 部署策略 spec 类型（契约见 NodeMan apigw/apidocs/zh/DeployPolicySvc_Create.md）
SPEC_TYPE_SPECIFY_PLUGIN = "specify_plugin"
SPEC_TYPE_SPECIFY_PLUGIN_SUB_CONFIG = "specify_plugin_sub_config"
SPEC_TYPE_SPECIFY_PLUGIN_SUB_CONFIG_TEMPLATE = "specify_plugin_sub_config_template"

# 部署策略 scope 类型
SCOPE_TYPE_INSTANCE = "instance"
SCOPE_TYPE_TOPO = "topo"
SCOPE_TYPE_SERVICE_TEMPLATE = "service_template"
SCOPE_TYPE_SET_TEMPLATE = "set_template"
SCOPE_TYPE_DYNAMIC_GROUP = "dynamic_group"

# 部署策略目标粒度：日志采集按主机下发
SCOPE_GRANULARITY_HOST = "host"

# 子配置落地文件名的中缀，与 NodeMan genDeployPolicySubConfigNameByConfigTemplateName 保持一致。
# 同机多采集项共用 bkunifylogbeat 与同名模板，靠「模板名 + 部署策略 ID」区分身份。
SUB_CONFIG_NAME_DEPLOY_INFIX = "_deploy_"

# 资源类型：一个采集项对应一条子配置策略；一个业务再共用一条采集器安装策略
RESOURCE_TYPE_COLLECTOR_CONFIG = "collector_config"
RESOURCE_TYPE_COLLECTOR_PLUGIN = "collector_plugin"

# 安装策略不属于任何单个采集项，binding.collector_config_id 用该值占位
COLLECTOR_CONFIG_ID_NOT_APPLICABLE = 0


class NodeManV3OperationType:
    """采集项控制面动作类型"""

    RECONCILE = "reconcile"
    REMOVE = "remove"
    PLUGIN_RECONCILE = "plugin_reconcile"

    CHOICES = (
        (RECONCILE, _("期望态收敛")),
        (REMOVE, _("子配置清理")),
        (PLUGIN_RECONCILE, _("采集器安装收敛")),
    )


class NodeManV3OperationStatus(models.TextChoices):
    """控制面 operation 状态"""

    PENDING = "pending", _("待派发")
    DISPATCHING = "dispatching", _("派发中")
    RUNNING = "running", _("执行中")
    SUCCESS = "success", _("成功")
    PARTIAL_FAILED = "partial_failed", _("部分失败")
    FAILED = "failed", _("失败")
    UNKNOWN = "unknown", _("未知")


class NodeManV3DispatchStatus(models.TextChoices):
    """写请求派发状态，用于崩溃恢复时判断能否重放"""

    PREPARED = "prepared", _("已落库未提交")
    SUBMITTING = "submitting", _("提交中")
    SUBMITTED = "submitted", _("已提交")
    DEFINITE_FAILED = "definite_failed", _("确定失败")
    UNKNOWN = "unknown", _("结果未知")


class NodeManV3ResultState(models.TextChoices):
    """能力缺失与写结果未知的标记"""

    UNSUPPORTED = "unsupported", _("能力未提供")
    WRITE_RESULT_UNKNOWN = "write_result_unknown", _("写结果未知")


class NodeManV3TargetState(models.TextChoices):
    """
    单台主机上「本采集项」的生效态。

    刻意不复用 V2 的 SUCCESS/FAILED/PENDING 三态：V2 的态是「订阅任务在这台机器上的执行结果」，
    而 V3 要回答的是「这台机器上本采集项的子配置现在是什么状态」，两者在以下场景会给出相反结论：

    - 任务成功但采集器后来被重启过，子配置记录已被节点管理删掉（见 analyze_specific_plugin_
      sub_config_template.go:228-236）：V2 口径显示成功，实际没在采
    - 任务失败但上一代配置仍在生效：V2 口径显示失败，实际仍在出数（只是版本旧）

    因此按「文件在不在 + 是哪一代」建模，STALE 与 FAILED 分开：STALE 仍在出数，不该在页面上翻红。
    """

    LATEST = "latest", _("已生效且最新")
    STALE = "stale", _("已生效但旧版")
    DISPATCHING = "dispatching", _("下发中")
    FAILED = "failed", _("失败")
    ABSENT = "absent", _("不存在")
    PENDING_REMOVAL = "pending_removal", _("待删除")


# 采集器进程不 running 时，节点管理不会把子配置下发到该主机，已有记录还会被删
# （analyze_specific_plugin_sub_config_template.go:113-117、:228-236）。
# 因此状态页必须先看进程，不能把「子配置不存在」直接判成下发失败，否则采集器重启期间整页翻红。
PROCESS_STATUS_RUNNING = "running"

# 主机（Agent）节点状态里的在线值，来自 HostState.node_status
# （init/running/damaged/busy/starting/upgrade/stopping/uninit/unknown，见 Topo_HostList.md）。
# 与 PROCESS_STATUS_RUNNING 恰好同字面量但是**两套不同的枚举**：一个描述插件进程，一个描述 Agent。
# 合用一个常量的话，节点管理改了任意一侧的取值，另一侧会跟着静默失效，所以刻意分开
HOST_NODE_STATUS_RUNNING = "running"

# 定时收敛的默认节奏。收敛不是节点管理自己做的：deploy_policy/execute 建的是一次性 trigger
# （internal/backend/manager/deploypolicy_manager.go:31 用 trigger.CategoryOnce），
# 主机加入/移出拓扑、采集器重启后子配置记录被删，都只能靠日志侧再执行一次策略补回。
TARGET_RECONCILE_INTERVAL_MINUTES = 10
# 兜底全量重放的间隔：即使目标集合没变，也要周期性重放一次期望态，
# 用于修复「采集器当时不 running 导致这一轮没下发」留下的空洞。
FULL_HEAL_INTERVAL_MINUTES = 60
# 单轮定时任务处理的 binding 上限，避免一个大业务把整轮 beat 占满
RECONCILE_BATCH_LIMIT = 200


# NodeMan operation 生命周期 state -> 采集状态
NODEMAN_V3_LIFE_CYCLE_STATE_MAPPING = {
    "init": NodeManV3OperationStatus.PENDING,
    "launched": NodeManV3OperationStatus.PENDING,
    "running": NodeManV3OperationStatus.RUNNING,
    "success": NodeManV3OperationStatus.SUCCESS,
    "failed": NodeManV3OperationStatus.FAILED,
    "timeout": NodeManV3OperationStatus.FAILED,
    "terminated": NodeManV3OperationStatus.FAILED,
}
