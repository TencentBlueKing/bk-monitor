"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

"""
记录线程变量
"""
import sys  # noqa
import uuid  # noqa

from apps.api import BKLoginApi  # noqa

from threading import local  # noqa

from django.conf import settings  # noqa

from apps.exceptions import BaseException  # noqa

_local = local()


def activate_request(request, request_id=None):
    """
    激活request线程变量
    """
    if not request_id:
        request_id = str(uuid.uuid4())
    request.request_id = request_id
    _local.request = request
    return request


def get_request(peaceful=False):
    """
    获取线程请求request
    """
    try:
        return _local.request
    except AttributeError:
        if peaceful:
            return None
        raise BaseException("request thread error!")


def get_request_id():
    """
    获取request_id
    """
    try:
        return get_request().request_id
    except BaseException:
        return str(uuid.uuid4())


def get_request_username(default="admin"):
    """
    获取请求的用户名
    """
    from apps.utils.function import ignored

    username = ""
    with ignored(Exception):
        username = get_request().user.username or get_local_param("request.username")
    if not username and "celery" in sys.argv:
        username = default
        if settings.ENABLE_MULTI_TENANT_MODE:
            username = get_backend_username()
    return username


def get_request_external_username():
    from apps.utils.function import ignored

    username = ""
    with ignored(Exception):
        username = get_request().external_user
    return username


def get_request_external_user_email():
    from apps.utils.function import ignored

    email = ""
    with ignored(Exception):
        email = get_request().external_user_info.get("email", "")
    return email


def get_local_username():
    """从local对象中获取用户信息（celery）"""
    for user_key in ["bk_username", "username", "operator"]:
        username = getattr(local, user_key, None)
        if username is not None:
            return username


def set_request_username(username):
    set_local_param("request.username", username)


def get_request_app_code():
    """
    获取线程请求中的 APP_CODE
    """
    try:
        return get_request().META.get("HTTP_BK_APP_CODE", settings.APP_CODE)
    except Exception:  # pylint: disable=broad-except
        return settings.APP_CODE


def set_local_param(key, value):
    """
    设置自定义线程变量
    """
    setattr(_local, key, value)


def del_local_param(key):
    """
    删除自定义线程变量
    """
    if hasattr(_local, key):
        delattr(_local, key)


def get_local_param(key, default=None):
    """
    获取线程变量
    """
    return getattr(_local, key, default)


def get_request_language_code():
    """
    获取线程请求中的language_code
    """
    try:
        return get_request().LANGUAGE_CODE
    except Exception:  # pylint: disable=broad-except
        return settings.LANGUAGE_CODE


def get_external_app_code():
    """
    获取内外部请求的APP_CODE
    """
    is_external = bool(get_request_external_username())
    if is_external:
        try:
            return get_request().META.get("HTTP_BK_APP_CODE", settings.APP_CODE)
        except Exception:  # pylint: disable=broad-except
            return settings.APP_CODE
    else:
        return settings.APP_CODE


def get_request_tenant_id():
    """
    获取请求中的租户ID
    """
    if settings.ENABLE_MULTI_TENANT_MODE:
        request = get_request(peaceful=True)
        if request and request.META.get("HTTP_X_BK_TENANT_ID", ""):
            return request.META.get("HTTP_X_BK_TENANT_ID", "")
        if request and hasattr(request.user, "tenant_id"):
            return request.user.tenant_id
    return settings.BK_APP_TENANT_ID


def get_admin_username(bk_tenant_id: str) -> str | None:
    if not settings.ENABLE_MULTI_TENANT_MODE:
        return getattr(settings, "COMMON_USERNAME", None)

    result = BKLoginApi.batch_lookup_virtual_user(
        {"bk_tenant_id": bk_tenant_id, "lookup_field": "login_name", "lookups": "bk_admin", "bk_username": "admin"},
        bk_tenant_id=bk_tenant_id,
    )
    if result:
        return result[0].get("bk_username")
    else:
        raise BaseException("get_admin_username: 获取管理员用户失败")


def get_backend_username(peaceful=True, bk_tenant_id: str = "") -> str | None:
    """从配置中获取用户信息"""

    if settings.ENABLE_MULTI_TENANT_MODE:
        if not bk_tenant_id:
            bk_tenant_id = get_request_tenant_id()

        if not bk_tenant_id:
            if not peaceful:
                raise BaseException("get_backend_username: 获取租户ID失败")
            return None

        return get_admin_username(bk_tenant_id)
    else:
        return "admin"


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
        raise BaseException("get_global_user: 获取全局用户失败")


def make_userinfo(bk_tenant_id: str = settings.BK_APP_TENANT_ID):
    username = get_global_user(bk_tenant_id=bk_tenant_id)
    if username:
        return {"bk_username": username}

    raise BaseException("make_userinfo: 获取用户信息失败")
