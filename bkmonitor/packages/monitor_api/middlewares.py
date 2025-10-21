# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import json
import traceback

import six
from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin
from django.utils.text import compress_sequence, compress_string

from bkmonitor.utils.common_utils import DatetimeEncoder, failed
from bkmonitor.utils.request import is_ajax_request
from common.log import logger
from core.drf_resource.exceptions import CustomException
from core.errors import Error
from core.errors.common import CustomError, UnknownError

METHOD_OVERRIDE_HEADER = "HTTP_X_HTTP_METHOD_OVERRIDE"


def get_message(status_code, data):
    if 200 <= status_code < 300:
        return "OK"
    elif "detail" in data:
        return data["detail"]
    else:
        return str(status_code)


class MonitorAPIMiddleware(MiddlewareMixin):
    """
    异常处理，对于发生500的ajax请求，修改为正常的response，
    避免前端因为没有处理500错误，导致前端默认的异常弹框
    """

    def process_response(self, request, response):
        """
        预期的异常处理，直接将状态码设置为200即可（主要针对DRF）
        """
        if is_ajax_request(request) and (200 <= response.status_code < 300 or response.status_code >= 500):
            response.status_code = 200
            response.reason_phrase = "OK"
        content_encoding = getattr(response, "content_encoding", None)
        if content_encoding == "gzip":
            self.compress(response)
        return response

    def compress(self, response):
        if not response.streaming and len(response.content) < 200:
            return
        if response.streaming:
            # Delete the `Content-Length` header for streaming content, because
            # we won't know the compressed size until we stream it.
            response.streaming_content = compress_sequence(response.streaming_content)
            del response["Content-Length"]
        else:
            # Return the compressed content only if it's actually shorter.
            compressed_content = compress_string(response.content)
            if len(compressed_content) >= len(response.content):
                return response
            response.content = compressed_content
            response["Content-Length"] = str(len(response.content))
        response["Content-Encoding"] = "gzip"

    def process_exception(self, request, exception):
        """
        非预期的异常处理
        """
        exc_info = traceback.format_exc()

        status_code = 200
        # CustomException特殊处理
        if isinstance(exception, CustomException):
            result = failed(exception.message)
            result["code"] = CustomError.code
            result["name"] = CustomError.name
            logger.exception(exception)
        elif isinstance(exception, Error):
            status_code = exception.status_code
            result = {
                "result": False,
                "code": exception.code,
                "name": exception.name,
                "message": exception.message,
                "data": exception.data,
            }
            exception.log()
        else:
            result = failed(six.text_type(exc_info.splitlines()[-1]))
            result["code"] = UnknownError.code
            result["name"] = UnknownError.name
            logger.exception(exception)

        if is_ajax_request(request):
            return HttpResponse(
                json.dumps(result, cls=DatetimeEncoder), content_type="application/json", status=status_code
            )
        raise exception
