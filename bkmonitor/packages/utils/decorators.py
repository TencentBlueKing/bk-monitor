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


import functools

from bkmonitor.iam import Permission
from bkmonitor.iam.action import ActionMeta
from bkmonitor.utils.common_utils import fetch_biz_id_from_dict


def check_perm(action: ActionMeta):
    def outer_wrapper(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            bk_biz_id = fetch_biz_id_from_dict(kwargs) or args[1]
            check_perm_with_raise(bk_biz_id, action)
            return func(*args, **kwargs)

        return wrapper

    return outer_wrapper


def check_perm_with_raise(bk_biz_id, action):
    client = Permission()
    client.is_allowed_by_biz(bk_biz_id=bk_biz_id, action=action, raise_exception=True)


def permission_exempt(view_func):
    """
    登录豁免，被此装饰器修饰的action可以不校验登录态
    """

    def wrapped_view(*args, **kwargs):
        args[0].permission_exempt = True
        return view_func(*args, **kwargs)

    return wrapped_view
