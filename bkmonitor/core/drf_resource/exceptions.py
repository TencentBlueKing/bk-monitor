# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import inspect
import logging
from typing import Optional

from django.http import Http404
from django.utils.translation import ugettext_lazy as _lazy
from opentelemetry.trace.span import Span
from opentelemetry.util import types
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response

from bkmonitor.utils.common_utils import failed
from core.errors import Error, ErrorDetails
from core.errors.common import DrfApiError, HTTP404Error, UnknownError

logger = logging.getLogger(__name__)


class CustomException(Error):
    status_code = 500
    code = 3300002
    name = _lazy("自定义异常")
    message_tpl = _lazy("自定义异常：{msg}")

    def __init__(self, message=None, data=None, code=None):
        """
        :param message: 错误信息
        :param data: 错误数据
        :param code: 错误码
        """
        if message is None:
            message = self.name

        self.data = data
        self.code = code or self.code
        super().__init__(context={"msg": message}, data=data, extra={"code": code})


def custom_exception_handler(exc, context):
    """
    针对CustomException返回的错误进行特殊处理，增加了传递数据的特性
    """
    response = None
    if isinstance(exc, Error):
        headers = {}
        if getattr(exc, "auth_header", None):
            headers["WWW-Authenticate"] = exc.auth_header
        if getattr(exc, "wait", None):
            headers["Retry-After"] = "%d" % exc.wait
        result = {
            "result": False,
            "code": exc.code,
            "name": exc.name,
            "message": exc.message,
            "data": exc.data,
            "error_details": exc.error_details,
        }
        result.update(getattr(exc, "extra", {}))
        response = Response(result, status=exc.status_code, headers=headers)
    elif isinstance(exc, APIException):
        headers = {}
        if getattr(exc, "auth_header", None):
            headers["WWW-Authenticate"] = exc.auth_header
        if getattr(exc, "wait", None):
            headers["Retry-After"] = "%d" % exc.wait
        msg = DrfApiError.drf_error_processor(exc.detail)
        error_detail = ErrorDetails(
            exc_type=type(exc).__name__,
            exc_code=DrfApiError.code,
            overview=msg,
            detail=msg,
        ).to_dict()
        result = {
            "result": False,
            "code": DrfApiError.code,
            "name": DrfApiError.name,
            "message": msg,
            "data": exc.detail,
            "error_details": error_detail,
        }

        response = Response(result, status=exc.status_code, headers=headers)
    elif isinstance(exc, Http404):
        msg = "Not found."
        result = {
            "result": False,
            "code": HTTP404Error.code,
            "name": HTTP404Error.name,
            "message": msg,
            "data": None,
            "error_details": ErrorDetails(
                exc_type=type(exc).__name__,
                exc_code=HTTP404Error.code,
                overview=msg,
                detail=msg,
                popup_message="error",  # 红框
            ).to_dict(),
        }

        response = Response(result, status=status.HTTP_404_NOT_FOUND)
    else:
        result = failed(
            exc,
            error_code=UnknownError.code,
            error_name=UnknownError.name,
            exc_type=type(exc).__name__,
            popup_type="danger",
        )
        result["data"] = getattr(exc, "data", None)
        logger.exception(exc)
        response = Response(result, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    if response is not None:
        setattr(response, "exception_instance", exc)

    return response


def record_exception(
    span: Span,
    exception: Exception,
    attributes: types.Attributes = None,
    timestamp: Optional[int] = None,
    escaped: bool = False,
    out_limit: int = None,
) -> None:
    """Records an exception as a span event."""
    try:
        row = [
            "Traceback (most recent call last):\n",
        ]
        tb = exception.__traceback__
        out_frames = inspect.getouterframes(tb.tb_frame)[1:]
        if out_limit and out_limit > 0:
            out_frames = out_frames[:out_limit]
        for item in reversed(out_frames):
            row.append('  File "{}", line {}, in {}\n'.format(item.filename, item.lineno, item.function))
            for line in item.code_context:
                if line:
                    row.append('    {}\n'.format(line.strip()))

        for item in inspect.getinnerframes(tb):
            row.append('  File "{}", line {}, in {}\n'.format(item.filename, item.lineno, item.function))
            for line in item.code_context:
                if line:
                    row.append('    {}\n'.format(line.strip()))

        stacktrace = ''.join(row)
    except Exception:  # pylint: disable=broad-except
        # workaround for python 3.4, format_exc can raise
        # an AttributeError if the __context__ on
        # an exception is None
        stacktrace = "Exception occurred on stacktrace formatting"
    _attributes = {
        "exception.type": exception.__class__.__name__,
        "exception.message": str(exception),
        "exception.stacktrace": stacktrace,
        "exception.escaped": str(escaped),
    }
    if attributes:
        _attributes.update(attributes)
    span.add_event(name="exception", attributes=_attributes, timestamp=timestamp)
