from bk_monitor_base.infras.exception import BaseError


class TestBaseError:
    """Test cases for BaseError class"""

    def test_system_code(self) -> None:
        """Test system code is correct"""
        error = BaseError(message="test error", error_code="001")
        assert error.SYSTEM_CODE == "68"
        assert error.get_error_code() == "6800001"
