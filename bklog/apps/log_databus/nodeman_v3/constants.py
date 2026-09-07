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

# 节点管理集成模式
NODEMAN_MODE_V2 = "v2"
NODEMAN_MODE_V3_FRESH = "v3_fresh"
NODEMAN_INTEGRATION_MODES = (NODEMAN_MODE_V2, NODEMAN_MODE_V3_FRESH)

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

# 资源类型：一个采集项对应一个部署策略
RESOURCE_TYPE_COLLECTOR_CONFIG = "collector_config"


class NodeManV3OperationType:
    """采集项控制面动作类型"""

    RECONCILE = "reconcile"
    REMOVE = "remove"

    CHOICES = (
        (RECONCILE, _("期望态收敛")),
        (REMOVE, _("子配置清理")),
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
