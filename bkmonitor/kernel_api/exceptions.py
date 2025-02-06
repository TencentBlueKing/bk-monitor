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

import logging

import six
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from bkmonitor.utils.common_utils import failed

logger = logging.getLogger(__name__)


IGNORE_EXCEPTIONS = (ValidationError,)


def api_exception_handler(exc, context):
    """
    针对CustomException返回的错误进行特殊处理，增加了传递数据的特性
    """
    # 有些预期内的错误， 比如ValidationError， 不需要记录日志
    if not isinstance(exc, IGNORE_EXCEPTIONS):
        logger.exception(exc)

    json_data = failed(six.text_type(exc))
    code = getattr(exc, "code", 500)
    if hasattr(exc, "detail"):
        # drf exc
        json_data["detail"] = exc.detail
        code = getattr(exc, "status_code", code)

    json_data["code"] = code
    json_data.pop("msg", None)

    return Response(json_data, content_type="application/json")
