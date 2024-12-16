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
from django.utils.translation import gettext_lazy as _lazy

from core.errors import Error


class ParamsPermissionDeniedError(Error):
    """
    请求参数校验失败
    """

    status_code = 403
    code = 3377401
    name = _lazy("请求参数校验失败")
    message_tpl = _lazy("请求参数{key}校验失败，接收到的参数为：{error_params}, 仅支持：{correct_params}")


class InvalidParamsError(Error):
    """
    缺少必要参数
    """

    status_code = 403
    code = 3377402
    name = _lazy("缺少必要参数")
    message_tpl = _lazy("缺少必要请求参数{key}")


class SearchLockedError(Error):
    """
    查询时间段权限异常
    """

    status_code = 403
    code = 3377403
    name = _lazy("查询时间段校验失败")
    message_tpl = _lazy("查询该时间段数据的权限校验不通过，接收到的参数为：{error_params}，仅支持：{correct_params}")


class TokenValidatedError(Error):
    """
    token校验异常
    """

    status_code = 400
    code = 3377404
    name = _lazy("token校验失败")
    message_tpl = _lazy("当前分享链接不存在")


class TokenExpiredError(Error):
    """
    token校验异常
    """

    status_code = 400
    code = 3377405
    name = _lazy("token已过期")
    message_tpl = _lazy("当前分享链接已过期")


class TokenDeletedError(Error):
    """
    token校验异常
    """

    status_code = 400
    code = 3377406
    name = _lazy("token已被收回")
    message_tpl = _lazy("当前分享链接已被{username}收回")
