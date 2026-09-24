# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnusedParameter=false
# pyright: reportUnannotatedClassAttribute=false
# pyright: reportPrivateUsage=false
import pickle

import pytest
from pydantic import BaseModel

from bk_monitor_base.infras.exception import StdError


class TestStdError:
    """Test cases for StdError class"""

    def test_init_with_code_num(self) -> None:
        """Test initialization with code_num"""
        error = StdError(message="test error", code_num=6801001)
        assert error.get_error_code() == "6801001"
        assert error.message == "test error"

    def test_init_with_error_code(self) -> None:
        """Test initialization with error_code"""
        error = StdError(message="test error", error_code="001")
        assert error.get_error_code() == "6800001"
        assert error.message == "test error"

    def test_set_message(self) -> None:
        """Test set_message method"""
        error = StdError(message="test error", error_code="001")
        new_error = error.set_message("new error")
        assert new_error.message == "new error"
        assert error.message == "test error"  # Original error should not be modified

    def test_set_data(self) -> None:
        """Test set_data method"""

        class ErrorData(BaseModel):
            field: str

        error = StdError(message="test error", error_code="001")
        data = ErrorData(field="test data")
        new_error = error.set_data(data)
        assert new_error.data == data
        assert error.data is None  # Original error should not be modified

    def test_set_errors(self) -> None:
        """Test set_errors method"""
        error = StdError(message="test error", error_code="001")
        errors = {"field": ["error message"]}
        new_error = error.set_errors(errors)
        assert new_error.errors == errors
        assert error.errors is None  # Original error should not be modified

    def test_extra_formatter(self) -> None:
        """Test extra_formatter functionality"""

        def formatter(message: str, error: StdError) -> str:
            return f"Formatted: {message}"

        error = StdError(message="test error", error_code="001", extra_formatter=formatter)
        assert error.message == "Formatted: test error"

    def test_response_data(self) -> None:
        """Test response_data method"""
        errors = (
            StdError(message="test error", error_code="001").set_data({"key": "value"}).set_errors({"field": ["error"]})
        )
        response = errors.response_data()
        assert isinstance(response, dict)
        assert response["result"] is False
        assert response["message"] == "（None）test error（detail => {'field': ['error']}）"
        assert response["code"] == "6800001"
        assert response["data"] == {"key": "value"}
        assert response["errors"] == {"field": ["error"]}

    def test_response_data_with_code_desc(self) -> None:
        """Test response_data includes code_desc in message"""

        class ErrorCodes:
            TEST_ERROR = StdError(message="test error", error_code="001")

        error_codes = ErrorCodes()
        response = error_codes.TEST_ERROR.response_data()
        assert response["message"].startswith("（TEST_ERROR）")

    def test_render_method(self) -> None:
        """Test _render static method with and without arguments"""
        # Test without arguments
        result = StdError._render("test message")
        assert result == "test message"

        # Test with arguments
        result = StdError._render("test message: {}, {}", "arg1", "arg2")
        assert result == "test message: arg1, arg2"

    def test_str_representation(self) -> None:
        """Test string representation of StdError"""

        class ErrorCodes:
            TEST_ERROR = StdError(message="test error", code_num=6801001)

        error_codes = ErrorCodes()
        expected = "<StdError: TEST_ERROR(6801001)-test error>"
        assert str(error_codes.TEST_ERROR) == expected

    def test_set_message_str_representation(self) -> None:
        """Test string representation after using set_message"""

        class ErrorCodes:
            TEST_ERROR_Z = StdError(message="test error", code_num=6801001)

        error_codes = ErrorCodes()
        expected = "<StdError: TEST_ERROR_Z(6801001)-test error>"
        assert str(error_codes.TEST_ERROR_Z) == expected
        new_error = error_codes.TEST_ERROR_Z.set_message("new error message")
        expected = "<StdError: TEST_ERROR_Z(6801001)-new error message>"
        assert str(new_error) == expected

    def test_descriptor_protocol(self) -> None:
        """Test __set_name__ descriptor protocol"""

        class ErrorCodes:
            error = StdError(message="test error", error_code="001")

        error_codes = ErrorCodes()
        assert error_codes.error.code_desc == "error"

    def test_message_with_prefix(self) -> None:
        """Test message property with MESSAGE prefix"""

        class PrefixError(StdError):
            MESSAGE = "Error Prefix"
            DELIMITER = " -> "

        error = PrefixError(message="test error")
        assert error.message == "Error Prefix -> test error"

    def test_message_without_prefix(self) -> None:
        """Test message property without MESSAGE prefix"""
        error = StdError(message="test error")
        assert error.message == "test error"  # No prefix when MESSAGE is empty

    def test_message_with_different_delimiter(self) -> None:
        """Test message property with custom delimiter"""

        class CustomDelimiterError(StdError):
            MESSAGE = "Custom Error"
            DELIMITER = " >>> "

        error = CustomDelimiterError(message="test error")
        assert error.message == "Custom Error >>> test error"

    def test_message_priority(self) -> None:
        """Test message formatting priority (extra_formatter > MESSAGE prefix)"""

        class PriorityError(StdError):
            MESSAGE = "Error Prefix"

        def formatter(message: str, error: StdError) -> str:
            return f"Formatted: {message}"

        error = PriorityError(message="test error", extra_formatter=formatter)
        # extra_formatter should take precedence over MESSAGE
        assert error.message == "Formatted: test error"


class CustomError(StdError):
    """Custom error class for testing"""

    SYSTEM_CODE = "77"
    MODULE_CODE = "99"


class TestCustomError:
    """Test cases for custom error inheritance"""

    def test_custom_module_code(self) -> None:
        """Test custom module code works correctly"""
        error = CustomError(message="test error", error_code="001")
        assert error.get_error_code() == "7799001"

    def test_inheritance_chain(self) -> None:
        """Test error inheritance and properties"""
        error = CustomError(message="test error", error_code="001")
        assert isinstance(error, CustomError)
        assert isinstance(error, StdError)
        assert isinstance(error, Exception)


@pytest.mark.parametrize(
    "code_num,error_code,expected",
    [
        (6801001, None, "6801001"),
        (None, "001", "6800001"),
        (6899999, "001", "6899999"),  # code_num takes precedence
    ],
)
def test_error_code_generation(code_num: int | None, error_code: str | None, expected: str) -> None:
    """Test error code generation with different inputs"""
    error = StdError(message="test", code_num=code_num, error_code=error_code)
    assert error.get_error_code() == expected


@pytest.mark.parametrize(
    "code_num,error_code,expected",
    [
        (6801001, None, "6801001"),
        (None, "001", "6800001"),
        (6899999, "001", "6899999"),
    ],
)
def test_full_error_code_property(code_num: int | None, error_code: str | None, expected: str) -> None:
    """测试 full_error_code 属性返回完整错误码"""
    error = StdError(message="test", code_num=code_num, error_code=error_code)

    assert error.full_error_code == expected
    assert error.full_error_code == error.get_error_code()


class ExtendedError(StdError):
    """子类扩展了额外属性，用于测试 _clone 是否保留子类属性"""

    def __init__(
        self,
        message: str,
        request_id: str | None = None,
        trace_id: str | None = None,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.request_id = request_id
        self.trace_id = trace_id


class TestClonePreservesSubclassAttributes:
    """测试 _clone 方法是否正确保留子类扩展的属性"""

    def test_clone_preserves_extra_attributes_via_set_message(self) -> None:
        """set_message 应保留子类的 request_id 和 trace_id"""
        error = ExtendedError(
            message="original",
            request_id="req-123",
            trace_id="trace-456",
            error_code="001",
        )

        cloned = error.set_message("new message")

        assert cloned.message == "new message"
        assert cloned.request_id == "req-123"
        assert cloned.trace_id == "trace-456"
        assert cloned.get_error_code() == "6800001"

    def test_clone_preserves_extra_attributes_via_set_data(self) -> None:
        """set_data 应保留子类的 request_id 和 trace_id"""
        error = ExtendedError(
            message="test",
            request_id="req-789",
            trace_id="trace-012",
            error_code="002",
        )

        cloned = error.set_data({"key": "value"})

        assert cloned.data == {"key": "value"}
        assert cloned.request_id == "req-789"
        assert cloned.trace_id == "trace-012"

    def test_clone_preserves_extra_attributes_via_set_errors(self) -> None:
        """set_errors 应保留子类的 request_id 和 trace_id"""
        error = ExtendedError(
            message="test",
            request_id="req-abc",
            trace_id="trace-def",
            error_code="003",
        )

        cloned = error.set_errors({"field": ["error"]})

        assert cloned.errors == {"field": ["error"]}
        assert cloned.request_id == "req-abc"
        assert cloned.trace_id == "trace-def"

    def test_clone_does_not_mutate_original(self) -> None:
        """克隆不应修改原始对象"""
        error = ExtendedError(
            message="original",
            request_id="req-original",
            error_code="001",
        )

        cloned = error.set_message("modified")

        assert error.message == "original"
        assert error.request_id == "req-original"
        assert cloned.message == "modified"
        assert cloned.request_id == "req-original"

    def test_clone_preserves_class_type(self) -> None:
        """克隆应保持正确的类型"""
        error = ExtendedError(message="test", request_id="req-123")

        cloned = error.set_message("new")

        assert type(cloned) is ExtendedError
        assert isinstance(cloned, StdError)

    def test_chained_clone_preserves_attributes(self) -> None:
        """链式调用克隆方法应保留所有属性"""
        error = ExtendedError(
            message="original",
            request_id="req-chain",
            trace_id="trace-chain",
            error_code="001",
        )

        cloned = error.set_message("step1").set_data({"a": 1}).set_errors({"b": ["c"]})

        assert cloned.message == "step1"
        assert cloned.data == {"a": 1}
        assert cloned.errors == {"b": ["c"]}
        assert cloned.request_id == "req-chain"
        assert cloned.trace_id == "trace-chain"


class TestPickleSerialization:
    """测试 pickle 序列化/反序列化，模拟 Celery worker 环境"""

    def test_pickle_std_error(self) -> None:
        """基类 StdError pickle 序列化和反序列化"""
        error = StdError(
            message="test error",
            code_num=6801001,
            error_code="001",
            status_code=400,
            data={"key": "value"},
            errors={"field": ["error"]},
        )

        pickled = pickle.dumps(error)
        restored: StdError = pickle.loads(pickled)

        assert restored.message == "test error"
        assert restored.code_num == 6801001
        assert restored.error_code == "001"
        assert restored.status_code == 400
        assert restored.data == {"key": "value"}
        assert restored.errors == {"field": ["error"]}
        assert restored.get_error_code() == "6801001"

    def test_pickle_subclass_with_extra_attributes(self) -> None:
        """子类扩展属性在 pickle 后应保留"""
        error = ExtendedError(
            message="extended error",
            request_id="req-pickle-123",
            trace_id="trace-pickle-456",
            error_code="001",
            data={"context": "test"},
        )

        pickled = pickle.dumps(error)
        restored: ExtendedError = pickle.loads(pickled)

        assert type(restored) is ExtendedError
        assert restored.message == "extended error"
        assert restored.request_id == "req-pickle-123"
        assert restored.trace_id == "trace-pickle-456"
        assert restored.data == {"context": "test"}
        assert restored.get_error_code() == "6800001"

    def test_pickle_cloned_subclass(self) -> None:
        """克隆后的子类对象 pickle 序列化应保留所有属性"""
        original = ExtendedError(
            message="original",
            request_id="req-clone-pickle",
            trace_id="trace-clone-pickle",
            error_code="002",
        )
        cloned = original.set_message("cloned message").set_data({"cloned": True})

        pickled = pickle.dumps(cloned)
        restored: ExtendedError = pickle.loads(pickled)

        assert type(restored) is ExtendedError
        assert restored.message == "cloned message"
        assert restored.request_id == "req-clone-pickle"
        assert restored.trace_id == "trace-clone-pickle"
        assert restored.data == {"cloned": True}

    def test_pickle_preserves_class_attributes(self) -> None:
        """pickle 应保留类级别的属性（SYSTEM_CODE, MODULE_CODE 等）"""
        error = CustomError(message="custom", error_code="001")

        pickled = pickle.dumps(error)
        restored: CustomError = pickle.loads(pickled)

        assert type(restored) is CustomError
        assert restored.SYSTEM_CODE == "77"
        assert restored.MODULE_CODE == "99"
        assert restored.get_error_code() == "7799001"

    def test_pickle_multiple_rounds(self) -> None:
        """多次序列化/反序列化后属性应保持一致"""
        error = ExtendedError(
            message="multi-round",
            request_id="req-multi",
            trace_id="trace-multi",
            error_code="003",
        )

        for _ in range(3):
            pickled = pickle.dumps(error)
            error = pickle.loads(pickled)

        assert error.message == "multi-round"
        assert error.request_id == "req-multi"
        assert error.trace_id == "trace-multi"

    def test_pickle_after_chained_operations(self) -> None:
        """链式操作后的对象 pickle 应正常工作"""
        error = (
            ExtendedError(message="chain", request_id="req-chain", error_code="001")
            .set_message("modified")
            .set_data({"step": 1})
            .set_errors({"validation": ["failed"]})
        )

        pickled = pickle.dumps(error)
        restored: ExtendedError = pickle.loads(pickled)

        assert restored.message == "modified"
        assert restored.request_id == "req-chain"
        assert restored.data == {"step": 1}
        assert restored.errors == {"validation": ["failed"]}
