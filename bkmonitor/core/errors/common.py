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
"""
公共错误
"""


import six
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy as _lazy

from core.errors import Error


class CommonError(Error):
    """
    公共错误基类
    """

    status_code = 500
    code = 3300001


class CustomError(CommonError):
    code = 3300002
    name = _lazy("自定义异常")
    message_tpl = "{message}"


class UnknownError(CommonError):
    code = 3300003
    name = _lazy("未知错误")
    message_tpl = "{message}"


class DrfApiError(CommonError):
    code = 3300004
    name = _lazy("REST API返回错误")
    message_tpl = "{message}"

    @staticmethod
    def drf_error_processor(detail):
        """
        将DRF ValidationError 错误信息转换为字符串
        """
        if isinstance(detail, six.text_type):
            return detail
        elif isinstance(detail, dict):
            for k, v in list(detail.items()):
                if v:
                    # 补充字段字段信息
                    return f"({k}) {DrfApiError.drf_error_processor(v)}"
            else:
                return ""
        elif isinstance(detail, list):
            for item in detail:
                if item:
                    return DrfApiError.drf_error_processor(item)
            else:
                return ""
        else:
            return _("错误消息解析错误")


class HTTP404Error(CommonError):
    code = 3300005
    status_code = 404
    name = _lazy("找不到")
    message_tpl = "{message}"


class UserInfoMissing(CommonError):
    code = 3300007
    name = _lazy("缺少用户信息")
    message_tpl = "{message}"
