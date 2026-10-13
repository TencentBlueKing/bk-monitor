import copy
from collections.abc import Callable
from typing import Any, TypeVar

from typing_extensions import deprecated

ExtraFormatterFunc = Callable[[str, "StdError"], str]

T = TypeVar("T", bound="StdError")


class StdError(Exception):
    """API error object with detailed code and description

    :param message: required, Detailed error message, may contains templated variables
    :param code_num: A numeric full error code, when it is not empty, it will be directly used as a complete error code
    :param error_code: A str error code,it return the splicing system code and module code(Only takes effect when code_num does not exist)
    :param extra_formatter: an extra function for formatting message
    :param status_code: desired HTTP status code for representing current Error
    :param data: stores extra data in current Exception object
    :param code_desc: An english identifier (Auto filled by field name in the ErrorCodes class)

    """

    # 系统编码
    SYSTEM_CODE: str = "68"
    # 异常消息分隔符
    DELIMITER: str = ": "
    # 模块编码
    MODULE_CODE: str = "00"
    # 默认的http状态码
    STATUS_CODE: int = 500
    # 一类异常的提示(会加在message前面)  不会被extra_formatter处理
    MESSAGE: str = ""

    # 不推荐使用字段(兼容一些需要以类定义异常的场景，这种用法无法生成异常码文档)
    ERROR_CODE: str = "000"

    def __init__(
        self,
        message: str,
        code_num: int | None = None,
        error_code: str | None = None,
        extra_formatter: ExtraFormatterFunc | None = None,
        status_code: int = STATUS_CODE,
        data: Any | None = None,
        errors: Any | None = None,
        code_desc: str | None = None,
        **kwargs: dict[str, Any],
    ):
        """
        NOTE: 继承了Exception且super().__init__()了,celery worker内会自动pickle序列化且报错，导致降级使用父类进行实例化，堆栈信息__str__出来的异常类丢失部分属性信息，但是堆栈正确。
        :param message: 详细的错误信息，可能包含模板变量
        :param error_code: 字符串类型的错误码，当它不为空且code_num为空时，会被用于完整错误码。例如该字段: "001",完整错误码为"6800001"
        :param code_num: 数字类型的完整错误码，当它不为空时，会被直接作为完整错误码使用。例如: 8801001,强制覆盖完整8位错误码。
        :param extra_formatter: 用于格式化错误信息的额外函数
        :param status_code: 该异常对应的HTTP状态码
        :param data: 存储在异常对象中的额外数据（建议setData来使用），该参数保留仅用于_clone和response_data方法
        :param errors: 存储在异常对象中的额外错误信息（建议setErrors来使用），该参数仅用于_clone和response_data方法
        :param code_desc: 英文标识符（由ErrorCodes类中的字段名自动填充,如果不使用标准用法，使用的类直接实例化，将为None）不推荐手动传入
        """
        super().__init__(message)
        self.code_num: int | None = code_num
        self.error_code: str | None = error_code
        self.extra_formatter: ExtraFormatterFunc | None = extra_formatter
        self.status_code: int = status_code
        # Save message as private field to expose it as an property
        self._message: str = message
        # "code_desc" will be set by field name in the ErrorCodes class(clone it when set)
        self.code_desc: str | None = code_desc
        # extra errors info, usually used to store validation errors
        self.data: Any | None = data
        self.errors: Any | None = errors
        if not self.error_code:
            self.error_code = self.ERROR_CODE

    def set_message(self: T, message: str) -> T:
        """Try to fix the original error message, return a cloned `StdError` object

        :param message: if not given, default message will be used
        """
        # Note: use `f` to join str for compatibility with lazy loaded messages，such as django i18n gettext
        return self._clone(message=message)

    @deprecated(
        "不建议直接使用该方法，建议直接使用 `full_error_code` 属性来获取完整的错误码，该方法名与 `error_code` 字段容易混淆，且 `full_error_code` 更加语义化"
    )
    def get_error_code(self) -> str:
        """Get a complete exception code for return"""
        if self.code_num is not None:
            return str(self.code_num)
        return f"{self.SYSTEM_CODE}{self.MODULE_CODE}{self.error_code}"

    def set_data(self: T, data: Any) -> T:
        """A chain method which set data property"""
        obj = self._clone()
        obj.data = data
        return obj

    def set_errors(self: T, errors: Any) -> T:
        """A chain method which set errors property"""
        obj = self._clone()
        obj.errors = errors
        return obj

    def render_data(self) -> Any:
        """
        返回异常信息
        """
        return self.data

    @property
    def message(self) -> str:
        """Get detailed error message, it the `extra_formatter` was defined, it will be used for formatting"""
        if self.extra_formatter:
            return self.extra_formatter(self._message, self)
        if self.MESSAGE != "":
            # If MESSAGE is defined, prepend it to the message
            return f"{self.MESSAGE}{self.DELIMITER}{self._message}"
        return self._message

    @property
    def full_error_code(self) -> str:
        """Get the full error code, which is a combination of system code, module code and error code"""
        return self.get_error_code()  # pyright: ignore[reportDeprecated]

    def __copy__(self: T) -> T:
        """浅拷贝协议实现，子类可重写以处理特殊属性

        通过 __new__ 创建新实例并复制 __dict__，避免调用 __init__，
        这样可以自动保留所有实例属性，包括子类新增的属性。
        """
        obj = self.__class__.__new__(self.__class__)
        obj.__dict__.update(self.__dict__)
        """
        NOTE: 核心原因：
            1. args 是 C 层面的属性，不在 __dict__ 中
            2. pickle 反序列化时用 args 来重建异常,celery worker 内部会自动 pickle 异常对象
            3. repr() 默认显示 args 内容
            所以必须调用 Exception.__init__(obj, message) 来正确设置 args。
        """
        Exception.__init__(obj, self._message)
        return obj

    def _clone(self: T, message: str | None = None) -> T:
        """Clone a new StdError object

        :param message: if given, the cloned object will use this message instead of current `self._message`
        """
        obj = copy.copy(self)
        if message is not None:
            obj._message = message
            # 同步更新 Exception 的 args
            Exception.__init__(obj, message)
        return obj

    @staticmethod
    def _render(message: str, *args: Any) -> str:
        """Render message template with variables, using standard python string template syntax"""
        if args:
            return message.format(*args)
        return message

    def __str__(self) -> str:  # pyright: ignore[reportImplicitOverride]
        return f"<{self.__class__.__name__}: {self.code_desc}({self.full_error_code})-{self.message}>"

    def __set_name__(self, obj_type: type, name: str) -> None:
        """Set field name as error code object's code"""
        self.code_desc = name

    def response_data(self) -> dict[str, Any]:
        message: str = f"（{self.code_desc}）{self.message}"
        if self.errors:
            message += f"（detail => {self.errors}）"
        return {
            "result": False,
            "code": self.full_error_code,
            "data": self.data,
            "message": message,
            "errors": self.errors,
        }
