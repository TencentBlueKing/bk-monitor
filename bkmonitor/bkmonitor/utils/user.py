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


from django.conf import settings
from django.utils.translation import gettext as _

from bkmonitor.utils.local import local
from bkmonitor.utils.request import get_request
from core.errors.common import UserInfoMissing


def get_request_user():
    """
    获取请求中的用户对象
    :return:
    """
    request = get_request(peaceful=True)
    if request:
        return request.user


def get_request_username():
    """基于request获取用户信息（web）"""
    user = get_request_user()
    if user:
        return user.username


def get_local_username():
    """从local对象中获取用户信息（celery）"""
    for user_key in ["bk_username", "username", "operator"]:
        username = getattr(local, user_key, None)
        if username is not None:
            return username


def get_backend_username():
    """从配置中获取用户信息"""
    return getattr(settings, "COMMON_USERNAME", None)


def set_local_username(username):
    local.username = username


def get_global_user(peaceful=True):
    # 1. 用户信息： 获取顺序：
    # 1.1 用户访问的request对象中的用户凭证
    # 1.2 local获取用户名
    # 1.3 系统配置的后台用户
    username = get_request_username() or get_local_username() or get_backend_username()

    if username:
        return username

    if not peaceful:
        raise UserInfoMissing


def make_userinfo():
    username = get_global_user()
    if username:
        return {"bk_username": username}

    raise ValueError(_("make_userinfo: 获取用户信息失败"))
