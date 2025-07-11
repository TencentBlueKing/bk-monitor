"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from functools import lru_cache
from django.conf import settings
from django.utils.translation import gettext as _

from bkmonitor.utils.local import local
from bkmonitor.utils.request import get_request, get_request_tenant_id
from constants.common import DEFAULT_TENANT_ID
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
