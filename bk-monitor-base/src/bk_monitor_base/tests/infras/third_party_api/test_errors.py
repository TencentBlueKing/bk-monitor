"""测试第三方 API 异常定义。"""

import pytest

from bk_monitor_base.infras.exception import BaseError, ModuleErrorCodes
from bk_monitor_base.infras.third_party_api.errors import ApiError, BkApiError


class TestApiError:
    """测试 ApiError 异常类。"""

    def test_inherits_from_base_error(self) -> None:
        """验证 ApiError 继承自 BaseError。"""
        assert issubclass(ApiError, BaseError)

    def test_module_code(self) -> None:
        """验证第三方 API 异常使用 API 模块错误码。"""
        assert ApiError.MODULE_CODE == ModuleErrorCodes.API

    @pytest.mark.parametrize(
        ("third_api_error_code", "expected"),
        [
            ("1001", "1001"),
            (None, ""),
        ],
    )
    def test_third_api_error_code_property(self, third_api_error_code: str | None, expected: str) -> None:
        """验证 third_api_error_code 属性返回值。"""
        error = ApiError(message="test error", third_api_error_code=third_api_error_code)

        assert error.third_api_error_code == expected

    def test_kwargs_are_forwarded_to_base_error(self) -> None:
        """验证额外关键字参数会透传给 BaseError。"""
        error = ApiError(message="test error", third_api_error_code="1001", status_code=400, error_code="123")

        assert error.status_code == 400
        assert error.get_error_code() == "6801123"
        assert error.third_api_error_code == "1001"

    @pytest.mark.parametrize(
        ("error_code", "third_api_error_code", "expected_error_code", "expected_third_api_error_code"),
        [
            ("123", "E001", "6801123", "E001"),
            (None, None, "6801000", ""),
            ("123", None, "6801123", ""),
            (None, "E001", "6801000", "E001"),
        ],
    )
    def test_error_code_and_third_api_error_code_combinations(
        self,
        error_code: str | None,
        third_api_error_code: str | None,
        expected_error_code: str,
        expected_third_api_error_code: str,
    ) -> None:
        """验证 error_code 与第三方错误码不同组合下的行为。"""
        error = ApiError(
            message="test error",
            error_code=error_code,
            third_api_error_code=third_api_error_code,
        )

        assert error.get_error_code() == expected_error_code
        assert error.third_api_error_code == expected_third_api_error_code


class TestBkApiError:
    """测试 BkApiError 异常类。"""

    def test_inheritance_chain(self) -> None:
        """验证 BkApiError 的继承链正确。"""
        assert issubclass(BkApiError, ApiError)
        assert issubclass(BkApiError, BaseError)

    def test_init_sets_message_and_status_code(self) -> None:
        """验证 BkApiError 会拼装消息并透传状态码。"""
        error = BkApiError(
            module="cmdb",
            action="search_host",
            method="GET",
            url="https://example.com/api",
            message="request failed",
            status_code=404,
            third_api_error_code="E404",
        )

        assert error.message == (
            "module: cmdb, action: search_host, method: GET, url: https://example.com/api, "
            "error message: request failed"
        )
        assert error.status_code == 404
        assert error.third_api_error_code == "E404"
        assert error.get_error_code() == "6801001"

    def test_init_uses_default_third_api_error_code(self) -> None:
        """验证未传第三方错误码时返回空字符串。"""
        error = BkApiError(
            module="cmdb",
            action="search_host",
            method="POST",
            url="https://example.com/api",
            message="request failed",
        )

        assert error.third_api_error_code == ""
        assert error.status_code == 500
