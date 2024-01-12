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

import os

from django.conf import settings

# 解决多级nginx代理下遇到的最外层nginx的`X-Forwarded-Host`设置失效问题
X_FORWARDED_WEIXIN_HOST = "HTTP_X_FORWARDED_WEIXIN_HOST"

# 是否开启使用
USE_WEIXIN = os.environ.get("BKAPP_USE_WEIXIN", None) == "1"
# 是否为企业微信
IS_QY_WEIXIN = os.environ.get("BKAPP_IS_QY_WEIXIN", None) == "1"
# 微信公众号的app id/企业微信corp id
WEIXIN_APP_ID = os.environ.get("BKAPP_WEIXIN_APP_ID", "")
# 微信公众号的app secret/企业微信应用的secret
WEIXIN_APP_SECRET = os.environ.get("BKAPP_WEIXIN_APP_SECRET", "")
# 该蓝鲸应用对外暴露的外网域名，即配置的微信能回调或访问的域名，如：test.bking.com
WEIXIN_APP_EXTERNAL_HOST = os.environ.get("BKAPP_WEIXIN_APP_EXTERNAL_HOST", "")

# 应用授权作用域
# snsapi_base （不弹出授权页面，直接跳转，只能获取用户openid），
# snsapi_userinfo （弹出授权页面，可通过openid拿到昵称、性别、所在地。并且， 即使在未关注的情况下，只要用户授权，也能获取其信息 ）
WEIXIN_SCOPE = "snsapi_userinfo"

# 蓝鲸微信请求URL前缀
WEIXIN_SITE_URL = os.environ.get("BKAPP_WEIXIN_SITE_URL", settings.SITE_URL + "weixin/")
# 蓝鲸微信本地静态文件请求URL前缀
WEIXIN_STATIC_URL = os.environ.get("BKAPP_WEIXIN_STATIC_URL", settings.STATIC_URL + "weixin/")
# 蓝鲸微信登录的URL
WEIXIN_LOGIN_URL = WEIXIN_SITE_URL.rstrip("/") + "/login/"

# 微信 Agent id
WEIXIN_AGENT_ID = os.environ.get("BKAPP_WEIXIN_AGENT_ID", "")
# 应用于重定向 scheme 与访问 scheme 不一致的情况
WEIXIN_APP_EXTERNAL_SCHEME = os.environ.get("BKAPP_WEIXIN_APP_EXTERNAL_SCHEME", "")
# 企业微信的 api domain，用于 api调用
WEIXIN_QY_API_DOMAIN = os.environ.get("BKAPP_WEIXIN_QY_API_DOMAIN", "https://qyapi.weixin.qq.com").rstrip("/")
# 企业微信的 web domain，用于 oauth2
WEIXIN_QY_OPEN_DOMAIN = os.environ.get("BKAPP_WEIXIN_QY_OPEN_DOMAIN", "https://open.weixin.qq.com").rstrip("/")
