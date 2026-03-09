from django.utils.translation import gettext_lazy as _

from apps.exceptions import BaseException, ErrorCode


class BaseTGPAException(BaseException):
    MODULE_CODE = ErrorCode.BKLOG_TGPA
    MESSAGE = _("客户端日志模块异常")


class FileSizeExceedLimitException(BaseTGPAException):
    ERROR_CODE = "001"
    MESSAGE = _("文件大小超过最大下载限制")
