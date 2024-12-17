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

from blueapps.account.models import UserProperty
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.shortcuts import render
from django.utils.functional import SimpleLazyObject
from django.utils.translation import gettext as _

from .accounts import WeixinAccount
from .models import BkWeixinUser

try:
    from django.utils.deprecation import MiddlewareMixin
except Exception:
    MiddlewareMixin = object


logger = logging.getLogger("root")

User = get_user_model()
weixin_account = WeixinAccount()


def get_user(request):
    user = None
    user_id = request.session.get("weixin_user_id")
    if user_id:
        try:
            user = BkWeixinUser.objects.get(pk=user_id)
        except BkWeixinUser.DoesNotExist:
            user = None
    return user or AnonymousUser()


def get_bk_user(request):
    bkuser = None
    if request.weixin_user and not isinstance(request.weixin_user, AnonymousUser):
        user_model = get_user_model()
        try:
            user_property = UserProperty.objects.get(key="wx_userid", value=request.weixin_user.userid)
        except UserProperty.DoesNotExist:
            logger.warning("user[wx_userid=%s] not in UserProperty" % request.weixin_user.userid)
        else:
            bkuser = user_model.objects.get(username=user_property.user.username)
    return bkuser or AnonymousUser()


class WeixinProxyPatchMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # 非微信访问，跳过中间件
        if not weixin_account.is_weixin_visit(request):
            setattr(request, "source", "web")
            setattr(request, "is_weixin", False)
            return None

        setattr(request, "is_weixin", True)
        setattr(request, "source", "mobile")
        return None


class WeixinAuthenticationMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if not getattr(request, "is_weixin", False):
            return None

        assert hasattr(request, "session"), (
            "The Weixin authentication middleware requires session middleware "
            "to be installed. Edit your MIDDLEWARE_CLASSES setting to insert "
            "'django.contrib.sessions.middleware.SessionMiddleware' before "
            "'weixin.core.middleware.WeixinAuthenticationMiddleware'."
        )
        setattr(request, "weixin_user", SimpleLazyObject(lambda: get_user(request)))
        setattr(request, "user", SimpleLazyObject(lambda: get_bk_user(request)))

        # 微信调试豁免
        if settings.WX_USER:
            weixin_user = BkWeixinUser.objects.first()
            if weixin_user:
                request.user = User.objects.first()
                request.weixin_user = weixin_user
                return None

    def process_response(self, request, response):
        """
        将weixin_user_id写入cookies，避免SESSION_COOKIE_AGE时间太短导致session过期
        """

        if not getattr(request, "is_weixin", False):
            return response

        if request.session.get("weixin_user_id"):
            response.set_cookie("weixin_user_id", request.session["weixin_user_id"])
        return response


class WeixinLoginMiddleware(MiddlewareMixin):
    """weixin Login middleware."""

    def process_view(self, request, view, args, kwargs):
        """process_view."""

        if not getattr(request, "is_weixin", False):
            return None

        # 微信路径默认取消蓝鲸登录
        setattr(view, "login_exempt", True)

        # 豁免微信登录装饰器
        if getattr(view, "weixin_login_exempt", False):
            return None

        # 验证OK
        if request.weixin_user.is_authenticated():
            # 必须绑定微信到蓝鲸 - 返回状态码 438
            if isinstance(request.user, AnonymousUser):
                return render(request, "/weixin/438.html", {"CUSTOM_TITLE": _("蓝鲸监控")})

            return None

        # 微信登录失效或者未通过验证，直接重定向到微信登录
        return weixin_account.redirect_weixin_login(request)
