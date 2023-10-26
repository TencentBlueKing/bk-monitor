from apps.exceptions import BaseException, ErrorCode
from django.utils.translation import ugettext_lazy as _

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
