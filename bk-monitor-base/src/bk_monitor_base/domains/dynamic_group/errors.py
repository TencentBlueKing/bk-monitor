from typing import final

from django.utils.translation import gettext_lazy as _

from bk_monitor_base.infras.exception import BaseError, ModuleErrorCodes


class DynamicGroupBaseError(BaseError):
    MODULE_CODE: str = ModuleErrorCodes.DYNAMIC_GROUP
    MESSAGE: str = _("动态分组管理异常")


# 动态分组相关异常
class DynamicGroupNotFound(DynamicGroupBaseError):
    """动态分组未找到"""


class DynamicGroupValidError(DynamicGroupBaseError):
    """动态分组校验失败"""


class DynamicGroupOperateError(DynamicGroupBaseError):
    """动态分组操作错误"""


# 动态分组成员相关异常
class DynamicGroupMemberNotFound(DynamicGroupBaseError):
    """动态分组成员未找到"""


class DynamicGroupMemberOperateError(DynamicGroupBaseError):
    """动态分组成员操作错误"""


@final
class ErrorCodes:
    DYNAMIC_GROUP_NOT_FOUND = DynamicGroupNotFound(_("动态分组未找到"), error_code="101")
    DYNAMIC_GROUP_VALIDATE_ERROR = DynamicGroupValidError(_("动态分组校验失败"), error_code="102")
    DYNAMIC_GROUP_OPERATE_ERROR = DynamicGroupOperateError(_("动态分组操作错误"), error_code="103")
    DYNAMIC_GROUP_MEMBER_NOT_FOUND = DynamicGroupMemberNotFound(_("动态分组成员未找到"), error_code="201")
    DYNAMIC_GROUP_MEMBER_OPERATE_ERROR = DynamicGroupMemberOperateError(_("动态分组成员操作错误"), error_code="202")
