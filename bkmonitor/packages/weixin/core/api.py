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


import abc

import requests
import six

from common.log import logger

from . import settings as weixin_settings


class API(object, six.with_metaclass(abc.ABCMeta)):
    """API请求工具"""

    timeout = 10
    ssl_verify = False

    def http_get(self, _http_url, **kwargs):
        """
        http 请求GET方法
        """
        try:
            resp = requests.get(_http_url, params=kwargs, timeout=self.timeout, verify=self.ssl_verify)
            # https://www.zhihu.com/question/30298730 乱码问题
            resp.encoding = "utf-8"
            resp = resp.json()
            return resp
        except Exception as error:
            logger.error("requests get url:{} error: {}".format(_http_url, error))
            return {}

    def http_post(self, _http_url, params=None, data=None, json=None, **kwargs):
        """
        http 请求POST方法
        """
        try:
            resp = requests.post(
                _http_url, params=params, data=data, json=json, timeout=self.timeout, verify=self.ssl_verify
            )
            resp = resp.json()
            return resp
        except Exception as error:
            logger.error("requests post url:{} data: {} params: {} error {}".format(_http_url, data, params, error))
            return {}


class ApiMixin(API):
    """公共方法"""

    def http_get(self, _http_url, **kwargs):
        data = super(ApiMixin, self).http_get(_http_url, **kwargs)
        # 企业微信和微信的接口返回格式不一致，这里做兼容处理
        if data.get("errcode") and data.get("errcode") != 0:
            logger.error("weixin api (url: {}) return error: {}".format(_http_url, data))
            return {}
        return data

    def http_post(self, _http_url, **kwargs):
        data = super(ApiMixin, self).http_post(_http_url, **kwargs)
        # 企业微信和微信的接口返回格式不一致，这里做兼容处理
        if data.get("errcode") and data.get("errcode") != 0:
            logger.error("weixin api (url: {}) return error: {}".format(_http_url, data))
            return {}
        return data


class WeiXinApi(ApiMixin):
    """微信公众号登录认证"""

    # 登录票据CODE验证URL
    WEIXIN_CHECK_CODE_URL = "https://api.weixin.qq.com/sns/oauth2/access_token"
    # 获取微信信息API
    WEIXIN_GET_USER_INFO_URL = "https://api.weixin.qq.com/sns/userinfo"

    def __init__(self):
        super(WeiXinApi, self).__init__()
        self.app_id = weixin_settings.WEIXIN_APP_ID
        self.secret = weixin_settings.WEIXIN_APP_SECRET

    def check_login_code(self, code):
        """
        校验登录回调code
        """
        query_param = {"appid": self.app_id, "secret": self.secret, "code": code, "grant_type": "authorization_code"}
        data = self.http_get(self.WEIXIN_CHECK_CODE_URL, **query_param)
        access_token = data.get("access_token")
        openid = data.get("openid")
        if access_token is None or openid is None:
            logger.error("登录票据CODE接口返回无access_token或openid")
            return False, {}
        return True, {"access_token": access_token, "openid": openid}

    def get_user_info(self, access_token, openid):
        """
        获取用户授权的用户信息
        """
        query_param = {"access_token": access_token, "openid": openid}
        data = self.http_get(self.WEIXIN_GET_USER_INFO_URL, **query_param)
        return data


class QyWeiXinApi(ApiMixin):
    """企业微信应用登录认证"""

    # 企业微信：获取access_token
    QY_WEIXIN_GET_ACCESS_TOKEN_URL = f"{weixin_settings.WEIXIN_QY_API_DOMAIN}/cgi-bin/gettoken"
    # 企业微信：获取访问用户身份
    QY_WEIXIN_GET_USER_INFO_URL = f"{weixin_settings.WEIXIN_QY_API_DOMAIN}/cgi-bin/user/getuserinfo"
    # 企业微信：读取成员
    QY_WEIXIN_GET_USER_URL = f"{weixin_settings.WEIXIN_QY_API_DOMAIN}/cgi-bin/user/get"
    # 企业微信userid -> 微信openid
    QY_WEIXIN_CONVERT_TO_OPENID = f"{weixin_settings.WEIXIN_QY_API_DOMAIN}/cgi-bin/user/convert_to_openid"

    def __init__(self):
        super(QyWeiXinApi, self).__init__()
        self.app_id = weixin_settings.WEIXIN_APP_ID
        self.secret = weixin_settings.WEIXIN_APP_SECRET

    def _get_qy_user_id(self, access_token, code):
        """
        企业微信：获取用户授权的用户信息
        企业成员 {
           "errcode": 0,
           "errmsg": "ok",
           "UserId":"USERID",
           "DeviceId":"DEVICEID"
        } or 非企业成员
        {
           "errcode": 0,
           "errmsg": "ok",
           "OpenId":"OPENID",
           "DeviceId":"DEVICEID"
        }
        """
        query_param = {"access_token": access_token, "code": code}
        data = self.http_get(self.QY_WEIXIN_GET_USER_INFO_URL, **query_param)
        return data

    def _convert_userid_to_openid(self, access_token, userid):
        """
        企业微信：转换userid为openid
        """
        kwargs = {
            "params": {"access_token": access_token},
            "json": {"userid": userid},
        }

        data = self.http_post(self.QY_WEIXIN_CONVERT_TO_OPENID, **kwargs)
        return data

    def _get_access_token(self):
        """
        企业微信：获取access_token
        {
           "errcode": 0，
           "errmsg": "ok"，
           "access_token": "accesstoken000001",
           "expires_in": 7200
        }
        """
        query_param = {"corpid": self.app_id, "corpsecret": self.secret}
        data = self.http_get(self.QY_WEIXIN_GET_ACCESS_TOKEN_URL, **query_param)
        return data

    def check_login_code(self, code):
        # def check_qy_login_code(self, code):
        """
        企业微信：校验用户登录回调code
        返回内容比普通微信多了一个userid
        """

        access_token = self._get_access_token().get("access_token")
        user_info = self._get_qy_user_id(access_token, code)

        userid = user_info.get("UserId")
        openid = user_info.get("OpenId")

        # 转换企业成员的userid为openid
        if not openid and userid:
            openid = self._convert_userid_to_openid(access_token, userid).get("openid")

        if not (access_token and userid):
            logger.error("企业微信：登录票据CODE接口返回无access_token或openid")
            return False, {}

        return True, {"access_token": access_token, "openid": openid, "userid": userid, "code": code}

    def get_user_info(self, access_token, userid):
        """
        企业微信：获取成员信息
        https://work.weixin.qq.com/api/doc#90000/90135/90196
        """
        query_param = {"access_token": access_token, "userid": userid}
        data = self.http_get(self.QY_WEIXIN_GET_USER_URL, **query_param)
        return data
