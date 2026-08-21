"""bkm-cli 管理操作的最小公共请求门禁。"""

import re
from typing import Any

from core.drf_resource.exceptions import CustomException


OPERATOR_PLACEHOLDER_PATTERN = re.compile(
    r"^(?:<[^<>]+>|\$\{[^{}]+\}|your[-_ ](?:operator|username|account))$",
    flags=re.IGNORECASE,
)


def validate_management_request(
    params: Any,
    *,
    allowed_fields: set[str],
    max_operator_length: int,
) -> str:
    """校验管理请求的公共信封，并返回本次人工授权声明的实际执行人。"""
    if not isinstance(params, dict):
        raise CustomException(message="params 必须是对象")

    unknown_fields = sorted(set(params) - allowed_fields)
    if unknown_fields:
        raise CustomException(message=f"不支持的参数: {unknown_fields}")

    if params.get("confirmed") is not True:
        raise CustomException(message="写操作必须先取得人工确认，并传入 confirmed=true")

    operator = params.get("operator")
    if not isinstance(operator, str) or not operator.strip():
        raise CustomException(message="operator 为必填项，必须填写当前人工授权中的实际执行人")
    operator = operator.strip()
    if OPERATOR_PLACEHOLDER_PATTERN.fullmatch(operator):
        raise CustomException(message="operator 必须填写当前人工授权中的实际执行人，不能使用占位符")
    if len(operator) > max_operator_length:
        raise CustomException(message=f"operator 长度不能超过 {max_operator_length}")
    return operator
