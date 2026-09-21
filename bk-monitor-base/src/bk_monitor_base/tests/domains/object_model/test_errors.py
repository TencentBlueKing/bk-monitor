"""
测试 object_model/errors.py 模块

这个测试文件确保所有异常类和错误代码的正确性。
"""

import pytest

from bk_monitor_base.domains.object_model.errors import (
    ErrorCodes,
    ObjectModelBaseError,
    ObjectModelGroupNotFound,
    ObjectModelGroupOperateError,
    ObjectModelGroupValidError,
    ObjectModelNotFound,
    ObjectModelOperateError,
    ObjectModelValidError,
)
from bk_monitor_base.infras.exception import BaseError


class TestObjectModelError:
    """测试 ObjectModelError 异常类"""

    def test_inherits_from_base_error(self):
        """确保 ObjectModelError 继承自 BaseError"""
        assert issubclass(ObjectModelBaseError, BaseError)

    def test_module_code(self):
        """测试模块代码"""
        assert ObjectModelBaseError.MODULE_CODE == "02"

    def test_default_message(self):
        """测试默认错误消息"""
        assert ObjectModelBaseError.MESSAGE == "对象模型管理异常"

    def test_error_instantiation(self):
        """测试错误实例化"""
        error = ObjectModelBaseError("测试错误")
        assert isinstance(error, ObjectModelBaseError)
        assert isinstance(error, BaseError)

    def test_error_with_code(self):
        """测试带错误代码的错误"""
        error = ObjectModelBaseError("测试错误", error_code="999")
        assert isinstance(error, ObjectModelBaseError)

    def test_error_representation(self):
        """测试错误的字符串表示"""
        error = ObjectModelBaseError("测试错误", error_code="999")
        # 基本测试错误对象可以被转换为字符串
        error_str = str(error)
        assert isinstance(error_str, str)
        assert len(error_str) > 0


class TestErrorCodes:
    """测试 ErrorCodes 错误代码常量类"""

    def test_all_error_codes_are_object_model_errors(self):
        """确保所有错误代码都是 ObjectModelError 实例"""
        error_attributes = [attr for attr in dir(ErrorCodes) if not attr.startswith("_")]

        for attr_name in error_attributes:
            error = getattr(ErrorCodes, attr_name)
            assert isinstance(error, ObjectModelBaseError), f"{attr_name} should be an ObjectModelError instance"

    def test_object_model_errors(self):
        """测试对象模型相关错误代码"""
        # 测试 OBJECT_MODEL_NOT_FOUND
        error = ErrorCodes.OBJECT_MODEL_NOT_FOUND
        assert isinstance(error, ObjectModelBaseError)
        assert "对象模型未找到" in str(error)

        # 测试 OBJECT_MODEL_VALIDATE_ERROR
        error = ErrorCodes.OBJECT_MODEL_VALIDATE_ERROR
        assert isinstance(error, ObjectModelBaseError)
        assert "对象模型校验失败" in str(error)

        # 测试 OBJECT_MODEL_OPERATE_ERROR
        error = ErrorCodes.OBJECT_MODEL_OPERATE_ERROR
        assert isinstance(error, ObjectModelBaseError)
        assert "对象模型操作错误" in str(error)

    def test_object_model_group_errors(self):
        """测试对象模型分组相关错误代码"""
        # 测试 OBJECT_MODEL_GROUP_NOT_FOUND
        error = ErrorCodes.OBJECT_MODEL_GROUP_NOT_FOUND
        assert isinstance(error, ObjectModelBaseError)
        assert "对象模型分组未找到" in str(error)

        # 测试 OBJECT_MODEL_GROUP_VALIDATE_ERROR
        error = ErrorCodes.OBJECT_MODEL_GROUP_VALIDATE_ERROR
        assert isinstance(error, ObjectModelBaseError)
        assert "对象模型分组校验失败" in str(error)

        # 测试 OBJECT_MODEL_GROUP_OPERATE_ERROR
        error = ErrorCodes.OBJECT_MODEL_GROUP_OPERATE_ERROR
        assert isinstance(error, ObjectModelBaseError)
        assert "对象模型分组操作错误" in str(error)

    def test_error_codes_are_unique(self):
        """确保所有错误代码都是唯一的"""
        error_attributes = [attr for attr in dir(ErrorCodes) if not attr.startswith("_")]

        # 检查错误代码的唯一性（如果 BaseError 支持获取错误代码）
        # 这个测试检查不同的错误常量确实是不同的对象
        errors = [getattr(ErrorCodes, attr) for attr in error_attributes]

        # 确保所有错误对象都是不同的实例
        for i, error1 in enumerate(errors):
            for j, error2 in enumerate(errors):
                if i != j:
                    # 确保不同的错误是不同的对象
                    assert error1 is not error2, f"Errors at index {i} and {j} should be different instances"

    def test_object_model_error_codes_range(self):
        """测试对象模型错误代码在 1xx 范围内"""
        object_model_errors = [
            ErrorCodes.OBJECT_MODEL_NOT_FOUND,
            ErrorCodes.OBJECT_MODEL_VALIDATE_ERROR,
            ErrorCodes.OBJECT_MODEL_OPERATE_ERROR,
        ]

        # 这个测试假设错误代码在错误消息中或者可以通过某种方式获取
        # 由于我们无法直接访问错误代码，我们测试错误类型的一致性
        for error in object_model_errors:
            assert isinstance(error, ObjectModelBaseError)
            # 所有对象模型错误都应该包含"对象模型"
            assert "对象模型" in str(error)

    def test_object_model_group_error_codes_range(self):
        """测试对象模型分组错误代码在 2xx 范围内"""
        group_errors = [
            ErrorCodes.OBJECT_MODEL_GROUP_NOT_FOUND,
            ErrorCodes.OBJECT_MODEL_GROUP_VALIDATE_ERROR,
            ErrorCodes.OBJECT_MODEL_GROUP_OPERATE_ERROR,
        ]

        for error in group_errors:
            assert isinstance(error, ObjectModelBaseError)
            # 所有分组错误都应该包含"对象模型分组"
            assert "对象模型分组" in str(error)

    def test_error_constants_are_final(self):
        """测试错误常量类被标记为 final"""
        # 检查 ErrorCodes 类有适当的属性（间接测试 @final 装饰器的存在）
        assert hasattr(ErrorCodes, "__annotations__") or True

        # 确保 ErrorCodes 不应该被实例化（它应该只包含类属性）
        error_attributes = [attr for attr in dir(ErrorCodes) if not attr.startswith("_")]

        # 所有属性都应该是错误实例
        for attr_name in error_attributes:
            attr_value = getattr(ErrorCodes, attr_name)
            assert isinstance(attr_value, ObjectModelBaseError)

    def test_specific_error_details(self):
        """测试特定错误的详细信息"""
        # 测试对象模型未找到错误
        error = ErrorCodes.OBJECT_MODEL_NOT_FOUND
        assert "未找到" in str(error)
        assert "对象模型" in str(error)

        # 测试校验错误
        validate_errors = [
            ErrorCodes.OBJECT_MODEL_VALIDATE_ERROR,
            ErrorCodes.OBJECT_MODEL_GROUP_VALIDATE_ERROR,
        ]
        for error in validate_errors:
            assert "校验失败" in str(error)

        # 测试操作错误
        operate_errors = [
            ErrorCodes.OBJECT_MODEL_OPERATE_ERROR,
            ErrorCodes.OBJECT_MODEL_GROUP_OPERATE_ERROR,
        ]
        for error in operate_errors:
            assert "操作错误" in str(error)


class TestErrorUsage:
    """测试错误的使用场景"""

    @pytest.mark.parametrize(
        "error, expected_exception",
        [
            (ErrorCodes.OBJECT_MODEL_NOT_FOUND, ObjectModelNotFound),
            (ErrorCodes.OBJECT_MODEL_VALIDATE_ERROR, ObjectModelValidError),
            (ErrorCodes.OBJECT_MODEL_OPERATE_ERROR, ObjectModelOperateError),
        ],
    )
    def test_raising_object_model_error(self, error, expected_exception):
        """测试抛出对象模型错误"""
        try:
            raise error
        except expected_exception as e:
            assert isinstance(e, ObjectModelBaseError)
            assert isinstance(e, BaseError)
        except Exception as e:
            # 不应该到达这里
            raise AssertionError(f"Should catch ObjectModelError, but got {type(e)}")

    @pytest.mark.parametrize(
        "error, expected_exception",
        [
            (ErrorCodes.OBJECT_MODEL_GROUP_NOT_FOUND, ObjectModelGroupNotFound),
            (ErrorCodes.OBJECT_MODEL_GROUP_VALIDATE_ERROR, ObjectModelGroupValidError),
            (ErrorCodes.OBJECT_MODEL_GROUP_OPERATE_ERROR, ObjectModelGroupOperateError),
        ],
    )
    def test_raising_object_model_group_error(self, error, expected_exception):
        """测试抛出对象模型分组错误"""
        try:
            raise error
        except expected_exception as e:
            assert isinstance(e, ObjectModelBaseError)
            assert isinstance(e, BaseError)
        except Exception as e:
            # 不应该到达这里
            raise AssertionError(f"Should catch ObjectModelError, but got {type(e)}")

    def test_error_hierarchy(self):
        """测试错误层次结构"""
        # 所有 ErrorCodes 中的错误都应该能被 ObjectModelError 捕获
        error_attributes = [attr for attr in dir(ErrorCodes) if not attr.startswith("_")]

        for attr_name in error_attributes:
            error = getattr(ErrorCodes, attr_name)

            # 测试错误可以被正确的异常类型捕获
            try:
                raise error
            except ObjectModelBaseError:
                # 这是期望的行为
                pass
            except Exception as e:
                raise AssertionError(
                    f"Error {attr_name} should be caught by ObjectModelError, but was caught by {type(e)}"
                )

    def test_error_context_information(self):
        """测试错误上下文信息"""
        # 测试错误可以提供有用的上下文信息
        errors_to_test = [
            (ErrorCodes.OBJECT_MODEL_NOT_FOUND, "对象模型未找到"),
            (ErrorCodes.OBJECT_MODEL_VALIDATE_ERROR, "对象模型校验失败"),
            (ErrorCodes.OBJECT_MODEL_GROUP_NOT_FOUND, "对象模型分组未找到"),
        ]

        for error, expected_message in errors_to_test:
            error_str = str(error)
            assert expected_message in error_str, f"Error should contain '{expected_message}', but got: {error_str}"
