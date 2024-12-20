# -*- coding: utf-8 -*-
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
from django.utils.translation import gettext_lazy as _

from apps.exceptions import BaseException, ErrorCode

# =================================================
# 日志脱敏
# =================================================


class BaseDesensitizeRuleException(BaseException):
    MODULE_CODE = ErrorCode.BKLOG_COLLECTOR_CONFIG
    MESSAGE = _("日志脱敏规则模块异常")


class DesensitizeRuleNotExistException(BaseDesensitizeRuleException):
    ERROR_CODE = "001"
    MESSAGE = _("脱敏规则 [{id}] 不存在")


class DesensitizeRuleNameExistException(BaseDesensitizeRuleException):
    ERROR_CODE = "002"
    MESSAGE = _("脱敏规则名称: [{name}] 已存在")


class DesensitizeRuleRegexCompileException(BaseDesensitizeRuleException):
    ErrorCode = "003"
    MESSAGE = _("脱敏规则(ID [{rule_id}] ): 正则表达式 [{pattern}] 编译失败")


class DesensitizeDataErrorException(BaseDesensitizeRuleException):
    ErrorCode = "004"
    MESSAGE = _("原始日志子对象处理异常: {e}")


class DesensitizeRegexDebugNoMatchException(BaseDesensitizeRuleException):
    ErrorCode = "005"
    MESSAGE = _("正则表达式未匹配目标字符串")
