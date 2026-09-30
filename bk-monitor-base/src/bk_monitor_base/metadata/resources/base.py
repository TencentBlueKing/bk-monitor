import json
import logging
from abc import ABC, abstractmethod
from http import HTTPStatus
from typing import Any

from django.utils.translation import gettext as _
from rest_framework.serializers import Serializer

from bk_monitor_base.infras.third_party_api.errors import BkApiError

logger = logging.getLogger("metadata_resource")


class Resource(ABC):
    RequestSerializer: type[Serializer[Any]] | None = None
    ResponseSerializer: type[Serializer[Any]] | None = None

    # 数据是否为对象的列表
    many_request_data: bool = False
    many_response_data: bool = False

    def __init__(self, context: Any = None):
        self.context: Any = context
        self._request_serializer: Serializer | None = None
        self._response_serializer: Serializer | None = None

    def __call__(self, *args, **kwargs) -> Any:
        # thread safe
        tmp_resource = self.__class__()
        return tmp_resource.request(*args, **kwargs)

    @classmethod
    def get_resource_name(cls) -> str:
        return f"{cls.__module__}.{cls.__qualname__}"

    @abstractmethod
    def perform_request(self, validated_request_data: dict[str, Any]) -> Any:
        """
        此处为Resource的业务逻辑，由子类实现
        将request_data通过一定的逻辑转化为response_data

        example:
            return validated_request_data
        """
        raise NotImplementedError

    def validate_request_data(self, request_data: dict[str, Any] | None) -> Any:
        """
        校验请求数据
        """
        self._request_serializer = None
        if not self.RequestSerializer:
            return request_data

        request_serializer: Serializer = self.RequestSerializer(data=request_data, many=self.many_request_data)
        self._request_serializer = request_serializer
        is_valid_request = request_serializer.is_valid()
        if not is_valid_request:
            logger.error(
                f"Resource[{self.get_resource_name()}] 请求参数格式错误：%s",
                format_serializer_errors(request_serializer),
            )
            raise Exception(
                _("Resource[{}] 请求参数格式错误：{}").format(
                    self.get_resource_name(), format_serializer_errors(request_serializer)
                )
            )
        return request_serializer.validated_data

    def validate_response_data(self, response_data: Any) -> Any:
        """
        校验返回数据
        """
        self._response_serializer = None
        if not self.ResponseSerializer:
            return response_data

        response_serializer: Serializer = self.ResponseSerializer(data=response_data, many=self.many_response_data)
        self._response_serializer = response_serializer
        is_valid_response = response_serializer.is_valid()
        if not is_valid_response:
            raise Exception(
                _("Resource[{}] 返回参数格式错误：{}").format(
                    self.get_resource_name(), format_serializer_errors(response_serializer)
                )
            )
        return response_serializer.validated_data

    def request(self, request_data: dict[str, Any] | None = None, **kwargs: dict[str, Any]) -> Any:
        """
        执行请求，并对请求数据和返回数据进行数据校验
        """
        try:
            request_data = request_data or kwargs
            validated_request_data = self.validate_request_data(request_data)
            response_data = self.perform_request(validated_request_data)
            validated_response_data = self.validate_response_data(response_data)
        except Exception as e:
            # 捕获所有异常，转换为统一的 BkApiError 异常
            raise BkApiError(
                module="metadata_resource",
                action=self.get_resource_name(),
                method="",
                url=self.get_resource_name(),
                message=str(e),
                status_code=HTTPStatus.BAD_REQUEST,
            ) from e
        return validated_response_data


def _format_serializer_errors_core(errors, fields, params) -> str:
    """序列化器错误信息格式化"""
    for key, field_errors in list(errors.items()):
        label, sub_message = key, ""

        if key not in fields:
            sub_message = json.dumps(field_errors)
        else:
            field = fields[key]
            label = field.field_name
            if isinstance(field_errors, dict):
                if hasattr(field, "child"):
                    sub_format = _format_serializer_errors_core(field_errors, field.child.fields, params)
                else:
                    sub_format = _format_serializer_errors_core(field_errors, field.fields, params)
                sub_message += sub_format
            elif isinstance(field_errors, list):
                for error in field_errors:
                    # 若错误信息中有%s可将错误值加入其中
                    sub_message = error.format(**{key: params.get(key, "")})

        message = f"({label}) {sub_message}"
        return message
    return ""


def format_serializer_errors(slz: Serializer[Any]) -> Any:
    try:
        message = _format_serializer_errors_core(slz.errors, slz.fields, slz.get_initial())
    except Exception as e:
        logger.warning(f"序列化器错误信息格式化失败，原因: {e}")
        return slz.errors
    else:
        return message
