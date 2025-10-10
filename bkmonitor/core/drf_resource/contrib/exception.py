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


class FaultTolerantResource(Resource, abc.ABC):
    """
    支持异常容错的 Resource，将异常捕获并记录到调用链，返回默认数据。
    适用于对异常不敏感的场景，例如检索类场景，抛出大部分预期内异常（例如无数据）或者部分后台异常，但用户无需关注。
    """

    DEFAULT_RESPONSE_DATA: Any = None

    @abc.abstractmethod
    def _perform_request(self, validated_request_data: dict[str, Any]):
        raise NotImplementedError

    @classmethod
    def is_return_default_early(cls, validated_request_data: dict[str, Any]) -> bool:
        """判断是否提前返回默认数据"""
        return False

    def perform_request(self, validated_request_data: dict[str, Any]):
        if self.is_return_default_early(validated_request_data):
            return self.DEFAULT_RESPONSE_DATA

        try:
            return self._perform_request(validated_request_data)
        except Exception as exc:  # pylint: disable=broad-except
            # Record the exception and set status in the current span.
            span = trace.get_current_span()
            # 内部调用 xx.perform_request 时，需要补充上 user.username & http.response.message，便于快速定位触发用户及异常。
            exc_desc: str = f"{type(exc).__name__}: {exc}"
            span.set_status(Status(status_code=StatusCode.ERROR, description=exc_desc))
            span.set_attributes({"user.username": get_request_username(), "http.response.message": exc_desc})
            record_exception(span, exc, out_limit=10)
            return self.handle_response_data(validated_request_data)

    def handle_response_data(self, validated_request_data: dict[str, Any]) -> Any:
        return self.DEFAULT_RESPONSE_DATA
