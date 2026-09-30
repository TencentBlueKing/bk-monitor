from typing import Any, final

from bk_monitor_base.infras.exception import BaseError, ModuleErrorCodes


class ApiError(BaseError):
    """
    API错误类

    该类用于表示调用第三方API时发生的错误，包含了第三方API的错误码和错误信息。

    拓展属性:
        - `third_api_error_code`: 存储第三方API返回的错误码，如果没有定义则返回空字符串。
    """

    MODULE_CODE: str = ModuleErrorCodes.API

    def __init__(self, message: str, *args: Any, third_api_error_code: str | None = None, **kwargs: Any) -> None:
        super().__init__(message, *args, **kwargs)
        self._third_api_error_code: str | None = third_api_error_code

    @property
    def third_api_error_code(self) -> str:
        """获取第三方API错误码，如果没有定义则返回空字符串"""
        return self._third_api_error_code or ""


@final
class BkApiError(ApiError):
    """蓝鲸API错误类"""

    ERROR_CODE: str = "001"

    def __init__(
        self,
        module: str,
        action: str,
        method: str,
        url: str,
        message: str,
        status_code: int = 500,
        third_api_error_code: str | None = None,
    ):
        message = f"module: {module}, action: {action}, method: {method}, url: {url}, error message: {message}"
        super().__init__(message=message, third_api_error_code=third_api_error_code, status_code=status_code)
