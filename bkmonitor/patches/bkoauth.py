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

LOG = logging.getLogger('component')


# 重写bkoauth.update_user_access_token,消除原bkoauth产生的大量MissingSchema异常堆栈
def update_user_access_token(sender, request, user, *args, **kwargs):
    """自动刷新access_token"""
    from bkoauth.client import oauth_client
    from bkoauth.exceptions import TokenAPIError

    try:
        access_token = oauth_client.get_access_token(request)
        LOG.info('user logged in get access_token success: %s' % access_token)
    except TokenAPIError as error:
        LOG.error('user logged in get access_token failed: %s' % error)  # 改用error级别记录，消除MissingSchema异常堆栈


def patch_bkoauth_update_user_access_token(*args, **kwargs):
    from bkoauth.signals import (
        update_user_access_token as original_update_user_access_token,
    )
    from django.contrib.auth.signals import user_logged_in

    user_logged_in.disconnect(original_update_user_access_token)  # 断开原先的信号连接
    user_logged_in.connect(update_user_access_token)  # 连接至自定义实现的update_user_access_token
