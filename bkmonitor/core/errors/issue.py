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


class SourceAnalysisError(IssueError):
    """源码分析错误基类，统一保留前端协议使用的稳定 reason。"""

    name = _lazy("源码分析错误")
    message_tpl = _lazy("源码分析操作失败")
    reason = "source_analysis_error"

    def __init__(self, context=None, data=None, extra=None, **kwargs):
        reason_data = {"reason": self.reason}
        if data:
            reason_data.update(data)
        super().__init__(context=context, data=reason_data, extra=extra, **kwargs)


class SourceAnalysisUpstreamUnavailableError(SourceAnalysisError):
    code = 3327002
    name = _lazy("源码分析上游服务不可用")
    message_tpl = _lazy("源码分析依赖的上游服务暂时不可用，请稍后重试")
    reason = "source_analysis_upstream_unavailable"


class SourceAnalysisConfigNotFoundError(SourceAnalysisError):
    code = 3327003
    name = _lazy("源码分析业务配置不存在")
    message_tpl = _lazy("请先配置源码分析使用的蓝盾项目和代码库")
    reason = "source_analysis_config_not_found"


class SourceAnalysisRepositoryInvalidError(SourceAnalysisError):
    code = 3327004
    name = _lazy("源码分析代码库无效")
    message_tpl = _lazy("所选代码库不存在、不属于该蓝盾项目或不是 Git 代码库")
    reason = "source_analysis_repository_invalid"


class SourceAnalysisResourceNotFoundError(SourceAnalysisError):
    code = 3327005
    name = _lazy("源码分析资源不可用")
    message_tpl = _lazy("存在当前用户不可用的源码分析资源")
    reason = "source_analysis_resource_not_found"


class SourceAnalysisRuleIncompleteError(SourceAnalysisError):
    code = 3327006
    name = _lazy("源码分析规则配置不完整")
    message_tpl = _lazy("启用规则必须配置匹配条件和至少一个智能体")
    reason = "source_analysis_rule_incomplete"


class SourceAnalysisRulePriorityConflictError(SourceAnalysisError):
    code = 3327007
    name = _lazy("源码分析规则优先级冲突")
    message_tpl = _lazy("该业务下已存在相同优先级的源码分析规则")
    reason = "source_analysis_rule_priority_conflict"


class SourceAnalysisDefaultRuleCannotDeleteError(SourceAnalysisError):
    code = 3327008
    name = _lazy("源码分析默认规则不可删除")
    message_tpl = _lazy("默认规则不可删除")
    reason = "source_analysis_default_rule_cannot_delete"


class SourceAnalysisDefaultRulePriorityImmutableError(SourceAnalysisError):
    code = 3327009
    name = _lazy("源码分析默认规则优先级不可修改")
    message_tpl = _lazy("默认规则优先级不可修改")
    reason = "source_analysis_default_rule_priority_immutable"


class SourceAnalysisFlowInitializationFailedError(SourceAnalysisError):
    code = 3327010
    name = _lazy("源码分析流程初始化失败")
    message_tpl = _lazy("源码分析流程初始化失败，请稍后重试")
    reason = "source_analysis_flow_initialization_failed"


class SourceAnalysisDefaultRuleConditionsInvalidError(SourceAnalysisError):
    code = 3327011
    name = _lazy("源码分析默认规则条件无效")
    message_tpl = _lazy("默认规则的匹配条件必须为空")
    reason = "source_analysis_rule_incomplete"
