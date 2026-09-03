"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import re
from functools import lru_cache

from django.conf import settings
from django.utils.translation import gettext as _

from bkmonitor.utils.local import local
from bkmonitor.utils.request import get_request, get_request_tenant_id
from constants.common import DEFAULT_TENANT_ID
from core.errors.api import BKAPIError
from core.errors.common import UserInfoMissing


LOGIN_NAME_WITH_DISPLAY_NAME_PATTERN = re.compile(r"^([A-Za-z][A-Za-z0-9._-]*)\(")
LOGIN_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9._-]*$")


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


def set_local_username(username):
    local.username = username


@lru_cache(maxsize=1000)
def get_admin_username(bk_tenant_id: str) -> str | None:
    if not settings.ENABLE_MULTI_TENANT_MODE:
        return getattr(settings, "COMMON_USERNAME", None)

    from core.drf_resource import api

    # 获取管理员用户
    result = api.bk_login.batch_lookup_virtual_user(
        bk_tenant_id=bk_tenant_id, lookup_field="login_name", lookups="bk_admin", bk_username="admin"
    )
    if result:
        return result[0].get("bk_username")
    else:
        raise ValueError(_("get_admin_username: 获取管理员用户失败"))


def get_backend_username(peaceful=True, bk_tenant_id: str = "") -> str | None:
    """从配置中获取用户信息"""

    if settings.ENABLE_MULTI_TENANT_MODE:
        if not bk_tenant_id:
            bk_tenant_id = get_request_tenant_id(peaceful=peaceful)

        if not bk_tenant_id:
            if not peaceful:
                raise ValueError(_("get_backend_username: 获取租户ID失败"))
            return None

        return get_admin_username(bk_tenant_id)
    else:
        return getattr(settings, "COMMON_USERNAME", None)


def get_global_user(peaceful=True, bk_tenant_id: str = ""):
    # 1. 用户信息： 获取顺序：
    # 1.1 用户访问的request对象中的用户凭证
    # 1.2 local获取用户名
    # 1.3 系统配置的后台用户

    username = (
        get_request_username()
        or get_local_username()
        or get_backend_username(peaceful=peaceful, bk_tenant_id=bk_tenant_id)
    )

    if username:
        return username

    if not peaceful:
        raise UserInfoMissing


def make_userinfo(bk_tenant_id: str = DEFAULT_TENANT_ID):
    username = get_global_user(bk_tenant_id=bk_tenant_id)
    if username:
        return {"bk_username": username}

    raise ValueError(_("make_userinfo: 获取用户信息失败"))


def extract_login_name_from_display_name(display_name: str) -> str | None:
    """从用户展示名中提取可用于企业微信提醒的英文登录名。"""

    if not display_name:
        return None

    matched = LOGIN_NAME_WITH_DISPLAY_NAME_PATTERN.match(display_name)
    if matched:
        return matched.group(1)

    if LOGIN_NAME_PATTERN.fullmatch(display_name):
        return display_name

    return None


def get_wxwork_mention_names(usernames: list[str]) -> dict[str, str]:
    """将多租户用户 ID 转换为企业微信提醒使用的英文登录名。"""

    if not settings.ENABLE_MULTI_TENANT_MODE:
        return {username: username for username in usernames}

    unique_usernames = [username for username in dict.fromkeys(usernames) if username and username != "all"]
    if not unique_usernames:
        return {}

    from core.drf_resource import api

    try:
        user_display_info = api.bk_login.batch_query_user_display_info(bk_usernames=unique_usernames)
    except BKAPIError:
        return {}

    mention_names: dict[str, str] = {}
    for user_info in user_display_info or []:
        username = user_info.get("bk_username")
        mention_name = extract_login_name_from_display_name(user_info.get("display_name"))
        if username and mention_name:
            mention_names[username] = mention_name

    return mention_names


def get_user_display_name(username: str):
    """
    获取用户展示名
    """

    if settings.ROLE == "web":
        request = get_request(peaceful=True)
        if request:
            # 仅当查询的是当前请求用户自身时，才使用请求上下文避免额外的数据库查询
            # 若查询其他用户的展示名（如告警日志中的操作人），需走正常查询路径
            if getattr(request.user, "username", None) == username:
                display_name = getattr(request.user, "display_name", None)
                if display_name:
                    return display_name

    if not settings.ENABLE_MULTI_TENANT_MODE:
        return username

    from core.drf_resource import api

    try:
        user_display_info = api.bk_login.batch_query_user_display_info(bk_usernames=[username])
    except BKAPIError:
        user_display_info = None

    if user_display_info:
        username = user_display_info[0]["display_name"]

    return username
