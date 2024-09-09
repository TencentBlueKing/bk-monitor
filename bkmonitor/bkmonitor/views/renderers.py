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

import json
from copy import copy

from django.utils.encoding import smart_text
from rest_framework.renderers import BaseRenderer

from bkmonitor.utils.common_utils import DatetimeEncoder
from core.errors.iam import PermissionDeniedError


def is_status_code_ok(code):
    return 200 <= code < 300


class PlainTextRenderer(BaseRenderer):
    media_type = 'text/plain'
    format = 'txt'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return smart_text(data, encoding=self.charset)


class UJSONRenderer(BaseRenderer):
    """
    Renderer which serializes to JSON.
    Applies JSON's backslash-u character escaping for non-ascii characters.
    Uses the blazing-fast ujson library for serialization.
    """

    media_type = "application/json"
    format = "json"
    ensure_ascii = True
    charset = None

    def render(self, data, *args, **kwargs):
        if data is None:
            return bytes()

        ret = json.dumps(data, ensure_ascii=self.ensure_ascii, cls=DatetimeEncoder)

        # force return value to unicode
        if isinstance(ret, str):
            return bytes(ret.encode("utf-8"))
        return ret


class MonitorJSONRenderer(UJSONRenderer):
    def get_result(self, data, renderer_context=None):
        from core.drf_resource.exceptions import CustomException

        if hasattr(self, "rendered_content"):
            return self.rendered_content
        response = renderer_context["response"]

        formatted_data = {
            "result": is_status_code_ok(response.status_code),
            # "code": str(code and "3309%03d" % code),  # ESB 规范错误码
            "code": 200,
            "message": "OK",
        }

        if formatted_data["result"]:
            if isinstance(data, dict) and "data" in data and "result" in data:
                # 如果是字典类型且字典中已经存在键名为'data'的键
                # 说明已经处理过
                formatted_data = data

            else:
                if isinstance(data, dict):
                    if "results" in data:
                        origin_data = copy(data)
                        data = origin_data.pop("results")
                        meta = origin_data
                        formatted_data.update({"data": data, "_meta": meta})

                formatted_data.update({"data": data})
        else:
            exc = getattr(response, "exception_instance", None)
            if isinstance(exc, CustomException):
                formatted_data["message"] = exc.message
                formatted_data["data"] = exc.data
                formatted_data["code"] = exc.code
                formatted_data["error_details"] = data.get("error_details")  # 报错额外信息，适配新版弹框样式
            elif isinstance(exc, PermissionDeniedError):
                extra = exc.__dict__["extra"]
                formatted_data.update(exc.__dict__)
                formatted_data.update(extra)
                formatted_data.pop("extra")
            elif isinstance(data, dict):
                formatted_data["message"] = data.get("detail") or data.get("message") or data
                formatted_data["error_details"] = data.get("error_details")  # 报错额外信息，适配新版弹框样式
            else:
                formatted_data["message"] = data
        return formatted_data

    def render(self, data, accepted_media_type=None, renderer_context=None):
        formatted_data = self.get_result(data, renderer_context)
        return super(MonitorJSONRenderer, self).render(formatted_data, accepted_media_type, renderer_context)
