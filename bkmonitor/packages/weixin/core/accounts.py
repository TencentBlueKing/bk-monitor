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


import random
import time
from urllib.parse import urlparse

from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect
from django.utils.translation import ugettext as _
from six.moves import range, urllib

from common.log import logger

from . import settings as weixin_settings
from .api import QyWeiXinApi, WeiXinApi
from .models import BkWeixinUser


class WeixinAccountSingleton(object):
    """
    单例基类
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        """
        @param class_:
        """
        if not isinstance(cls._instance, cls):
            cls._instance = object.__new__(cls, *args, **kwargs)
        return cls._instance


class WeixinAccount(WeixinAccountSingleton):
    """
    微信账号体系相关的基类Account
    提供通用的账号功能
    """

    # 跳转到微信重定向链接
    WEIXIN_OAUTH_URL = f"{weixin_settings.WEIXIN_QY_OPEN_DOMAIN}/connect/oauth2/authorize"

    def __init__(self):
        if weixin_settings.IS_QY_WEIXIN:
            self.weixin_api = QyWeiXinApi()
        else:
            self.weixin_api = WeiXinApi()

    def is_weixin_visit(self, request):
        """
        是否来自微信访问
        """
        if not weixin_settings.USE_WEIXIN:
            return False

        # 如果有HTTP_X_ORIGINAL_URI，则取HTTP_X_ORIGINAL_URI的值，否则，使用当前请求的路径
        request_path = request.META.get("HTTP_X_ORIGINAL_URI") or request.path
        host = request.META.get(weixin_settings.X_FORWARDED_WEIXIN_HOST) or request.get_host()
        if (
            request_path.startswith(weixin_settings.WEIXIN_SITE_URL)
            and host == weixin_settings.WEIXIN_APP_EXTERNAL_HOST
        ):
            return True
        return False

    def set_weixin_oauth_state(self, request, length=32):
        """
        生成随机的state，并存储到session中
        """
        allowed_chars = "abcdefghijkmnpqrstuvwxyzABCDEFGHIJKLMNPQRSTUVWXYZ0123456789"
        state = "".join(random.choice(allowed_chars) for _ in range(length))
        request.session["WEIXIN_OAUTH_STATE"] = state
        request.session["WEIXIN_OAUTH_STATE_TIMESTAMP"] = time.time()
        return state

    def get_oauth_redirect_url(self, callback_url, state="authenticated"):
        """
        获取oauth访问链接
        """
        params = {
            "appid": weixin_settings.WEIXIN_APP_ID,
            "redirect_uri": callback_url,
            "response_type": "code",
            "scope": weixin_settings.WEIXIN_SCOPE,
            "state": state,
            "agentid": weixin_settings.WEIXIN_AGENT_ID,
        }
        params = urllib.parse.urlencode(params)
        redirect_uri = "{}?{}#wechat_redirect".format(self.WEIXIN_OAUTH_URL, params)
        return redirect_uri

    def redirect_weixin_login(self, request):
        """
        跳转到微信登录
        """
        url = urllib.parse.urlparse(request.build_absolute_uri())
        path = weixin_settings.WEIXIN_LOGIN_URL
        # 将重定向地址改为外部访问地址
        full_path = request.get_full_path().replace(settings.SITE_URL + "weixin/", weixin_settings.WEIXIN_SITE_URL)
        query = urllib.parse.urlencode({"c_url": full_path})
        scheme = weixin_settings.WEIXIN_APP_EXTERNAL_SCHEME or url.scheme
        callback_url = urllib.parse.urlunsplit(
            (scheme, weixin_settings.WEIXIN_APP_EXTERNAL_HOST, path, query, url.fragment)
        )
        state = self.set_weixin_oauth_state(request)
        redirect_uri = self.get_oauth_redirect_url(callback_url, state)
        return HttpResponseRedirect(redirect_uri)

    def verify_weixin_oauth_state(self, request, expires_in=60):
        """
        验证state是否正确，防止csrf攻击
        """
        try:
            state = request.GET.get("state")
            raw_state = request.session.get("WEIXIN_OAUTH_STATE")
            raw_timestamp = request.session.get("WEIXIN_OAUTH_STATE_TIMESTAMP")
            # 验证state
            if not raw_state or raw_state != state:
                return False
            # 验证时间戳
            if not raw_timestamp or time.time() - raw_timestamp > expires_in:
                return False
            # 验证成功后清空session
            request.session["WEIXIN_OAUTH_STATE"] = None
            request.session["WEIXIN_OAUTH_STATE_TIMESTAMP"] = None
            return True
        except Exception as e:
            logger.exception("验证请求weixin code的 state参数出错： %s" % e)
            return False

    def verfiy_weixin_oauth_code(self, request):
        """
        验证Code有效性
        """
        code = request.GET.get("code")
        is_ok, data = self.weixin_api.check_login_code(code)
        return is_ok, data

    def get_user_info(self, base_data):
        """
        根据access_token获取用户信息
        """
        openid = base_data.get("openid")
        userinfo = {"openid": openid}
        if weixin_settings.WEIXIN_SCOPE != "snsapi_userinfo":
            return userinfo
        access_token = base_data.get("access_token")
        data = self.weixin_api.get_user_info(access_token, openid)

        # nickname乱码问题 https://www.zhihu.com/question/30298730
        userinfo.update(
            {
                "nickname": data.get("nickname") or "",
                "gender": data.get("sex") or "",
                "country": data.get("country") or "",
                "province": data.get("province") or "",
                "city": data.get("city") or "",
                "avatar_url": data.get("headimgurl") or "",
                "userid": openid,
            }
        )
        return userinfo

    def get_qy_user_info(self, base_data):
        """
        企业微信：根据access_token获取用户信息
        """
        data = self.weixin_api.get_user_info(base_data.get("access_token"), base_data.get("userid"))

        return {
            "openid": base_data.get("userid" if weixin_settings.IS_QY_WEIXIN else "openid"),
            "userid": base_data.get("userid"),
            "nickname": data.get("name", ""),
            "gender": data.get("gender", ""),
            "country": data.get("country", ""),
            "province": data.get("province", ""),
            "city": data.get("city", ""),
            "avatar_url": data.get("avatar", ""),
            # 'telephone': data.get('telephone', ''),
            # 'mobile': data.get('mobile', ''),
            # 'alias': data.get('alias', ''),
            # 'qr_code': data.get('qr_code', ''),
            # 'email': data.get('email', ''),
        }

    def get_callback_url(self, request):
        """
        获取实际访问的URL
        """
        callback_url = request.GET.get("c_url")
        if not callback_url or not callback_url.startswith("/"):
            callback_url = weixin_settings.WEIXIN_SITE_URL
        return callback_url

    def login(self, request):
        """
        微信登录后回调
        """
        if not self.is_weixin_visit(request):
            # TODO 改造为友好页面
            return HttpResponse(_("非微信访问，或应用未启动微信访问"))
        # 验证回调state
        if not self.verify_weixin_oauth_state(request):
            # TODO 改造为友好页面
            return HttpResponse(_("State验证失败"))
        # 验证code有效性
        is_code_vaild, base_data = self.verfiy_weixin_oauth_code(request)
        if not is_code_vaild:
            # TODO 改造为友好页面
            return HttpResponse(_("登录失败"))

        # 设置登录
        # 对于授权为snsapi_userinfo的，需获取用户信息
        if weixin_settings.IS_QY_WEIXIN:
            userinfo = self.get_qy_user_info(base_data)
        else:
            userinfo = self.get_user_info(base_data)

        openid = userinfo.pop("openid")
        user = BkWeixinUser.objects.get_update_or_create_user(openid, **userinfo)

        # 设置session
        request.session["weixin_user_id"] = user.id
        setattr(request, "weixin_user", user)

        # 跳转到用户实际访问URL
        callback_url = self.get_callback_url(request)
        path = urlparse(callback_url).path
        return HttpResponseRedirect(path)
