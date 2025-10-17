"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any

import abc
from core.drf_resource.base import Resource
from opentelemetry import trace
from opentelemetry.trace.status import Status, StatusCode
from bkmonitor.utils.request import get_request_username

from core.drf_resource.exceptions import record_exception


tracer = trace.get_tracer(__name__)


class FaultTolerantResource(Resource, abc.ABC):
    """
    支持异常容错的 Resource，将异常捕获并记录到调用链，返回默认数据。
    适用于对异常不敏感的场景，例如检索类场景，抛出大部分预期内异常（例如无数据）或者部分后台异常，但用户无需关注。
    """

    DEFAULT_RESPONSE_DATA: Any = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._is_validate_request_data_finished: bool = False

    def validate_request_data(self, request_data: dict[str, Any]) -> dict[str, Any]:
        validated_data: dict[str, Any] = super().validate_request_data(request_data)
        self._is_validate_request_data_finished = True
        return validated_data

    @classmethod
    def is_return_default_early(cls, validated_request_data: dict[str, Any]) -> bool:
        """判断是否提前返回默认数据"""
        return False

    def request(self, request_data=None, **kwargs):
        """
        执行请求，并对请求数据和返回数据进行数据校验
        """
        with tracer.start_as_current_span(self.get_resource_name(), record_exception=False) as span:
            try:
                request_data = request_data or kwargs
                validated_request_data = self.validate_request_data(request_data)
                if self.is_return_default_early(validated_request_data):
                    # 判断是否可以提前返回默认数据。
                    return self.handle_response_data(validated_request_data)

                response_data = self.perform_request(validated_request_data)
                validated_response_data = self.validate_response_data(response_data)
                return validated_response_data
            except Exception as exc:  # pylint: disable=broad-except
                # 内部调用 xx.perform_request 时，需要补充上 user.username & http.response.message，便于快速定位触发用户及异常。
                exc_desc: str = f"{type(exc).__name__}: {exc}"
                span.set_status(Status(status_code=StatusCode.ERROR, description=exc_desc))
                span.set_attributes({"user.username": get_request_username(), "http.response.message": exc_desc})

                # Record the exception as an event
                record_exception(span, exc, out_limit=10)

                # Set status in case exception was raised
                span.set_status(Status(status_code=StatusCode.ERROR, description=exc_desc))

                if self._is_validate_request_data_finished:
                    # 非参数校验环节抛出的异常，均视为可容忍异常，返回默认数据。
                    return self.handle_response_data(validated_request_data)

                raise

    def handle_response_data(self, validated_request_data: dict[str, Any]) -> Any:
        return self.DEFAULT_RESPONSE_DATA
