from typing import final

from django.utils.translation import gettext as _

from bk_monitor_base.infras.exception import BaseError, ModuleErrorCodes


class ObjectModelBaseError(BaseError):
    MODULE_CODE: str = ModuleErrorCodes.OBJECT_MODEL
    MESSAGE: str = _("对象模型管理异常")


# 对象模型相关异常
class ObjectModelNotFound(ObjectModelBaseError):
    """对象模型未找到"""


class ObjectModelValidError(ObjectModelBaseError):
    """对象模型校验失败"""


class ObjectModelOperateError(ObjectModelBaseError):
    """对象模型操作错误"""


# 对象模型分组相关异常
class ObjectModelGroupNotFound(ObjectModelBaseError):
    """对象模型分组未找到"""


class ObjectModelGroupValidError(ObjectModelBaseError):
    """对象模型分组校验失败"""


class ObjectModelGroupOperateError(ObjectModelBaseError):
    """对象模型分组操作错误"""


@final
class ErrorCodes:
    OBJECT_MODEL_NOT_FOUND = ObjectModelNotFound(_("对象模型未找到"), error_code="101")
    OBJECT_MODEL_VALIDATE_ERROR = ObjectModelValidError(_("对象模型校验失败"), error_code="102")
    OBJECT_MODEL_OPERATE_ERROR = ObjectModelOperateError(_("对象模型操作错误"), error_code="103")
    OBJECT_MODEL_GROUP_NOT_FOUND = ObjectModelGroupNotFound(_("对象模型分组未找到"), error_code="201")
    OBJECT_MODEL_GROUP_VALIDATE_ERROR = ObjectModelGroupValidError(_("对象模型分组校验失败"), error_code="202")
    OBJECT_MODEL_GROUP_OPERATE_ERROR = ObjectModelGroupOperateError(_("对象模型分组操作错误"), error_code="203")
