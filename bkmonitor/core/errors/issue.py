"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

"""
Issue 业务错误

错误码段：3327xxx（当前未被其他模块占用）
"""
from django.utils.translation import gettext_lazy as _lazy

from core.errors.common import CommonError


class IssueError(CommonError):
    """Issue 错误基类"""

    code = 3327000
    name = _lazy("Issue 错误")
    message_tpl = "{message}"


class IssueRenameConflictError(IssueError):
    """重命名 Issue 冲突（同业务下已存在同名 Issue）"""

    code = 3327001
    status_code = 409  # Conflict 语义（业务错误码仍以 body.code 为准，前端据此识别）
    name = _lazy("Issue 重名")
    message_tpl = "{message}"


class SourceAnalysisUpstreamUnavailableError(IssueError):
    code = 3327002
    name = _lazy("源码分析上游服务不可用")
    message_tpl = _lazy("源码分析依赖的上游服务暂时不可用，请稍后重试")


class SourceAnalysisConfigNotFoundError(IssueError):
    code = 3327003
    name = _lazy("源码分析业务配置不存在")
    message_tpl = _lazy("请先配置源码分析使用的蓝盾项目和代码库")


class SourceAnalysisRepositoryInvalidError(IssueError):
    code = 3327004
    name = _lazy("源码分析代码库无效")
    message_tpl = _lazy("所选代码库不存在、不属于该蓝盾项目或不是 Git 代码库")


class SourceAnalysisResourceNotFoundError(IssueError):
    code = 3327005
    name = _lazy("源码分析资源不可用")
    message_tpl = _lazy("存在当前用户不可用的源码分析资源")


class SourceAnalysisRuleIncompleteError(IssueError):
    code = 3327006
    name = _lazy("源码分析规则配置不完整")
    message_tpl = _lazy("启用规则必须配置匹配条件和至少一个智能体")


class SourceAnalysisRulePriorityConflictError(IssueError):
    code = 3327007
    name = _lazy("源码分析规则优先级冲突")
    message_tpl = _lazy("该业务下已存在相同优先级的源码分析规则")


class SourceAnalysisDefaultRuleCannotDeleteError(IssueError):
    code = 3327008
    name = _lazy("源码分析默认规则不可删除")
    message_tpl = _lazy("默认规则不可删除")


class SourceAnalysisDefaultRulePriorityImmutableError(IssueError):
    code = 3327009
    name = _lazy("源码分析默认规则优先级不可修改")
    message_tpl = _lazy("默认规则优先级不可修改")


class SourceAnalysisFlowInitializationFailedError(IssueError):
    code = 3327010
    name = _lazy("源码分析流程初始化失败")
    message_tpl = _lazy("源码分析流程初始化失败，请稍后重试")


class SourceAnalysisDefaultRuleConditionsInvalidError(IssueError):
    code = 3327011
    name = _lazy("源码分析默认规则条件无效")
    message_tpl = _lazy("默认规则的匹配条件必须为空")


class SourceAnalysisInvalidStatusTransitionError(IssueError):
    """执行记录状态迁移非法，通常源于并发改写同一条记录。message 携带迁移方向，仅用于排障。"""

    code = 3327012
    status_code = 409  # Conflict 语义，调用方应重新查询最新状态
    name = _lazy("源码分析状态流转非法")
    message_tpl = _lazy("源码分析记录状态已变更，请重新查询后重试")


class SourceAnalysisOperationConflictError(IssueError):
    """前端操作与当前最新执行状态冲突，data.reason 提供稳定的刷新判断依据。"""

    code = 3327013
    status_code = 409
    name = _lazy("源码分析操作冲突")
    message_tpl = "{message}"
