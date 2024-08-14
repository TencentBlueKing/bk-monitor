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
from typing import Any, Dict, List

from bkm_space.api import SpaceApi
from bkmonitor.iam import ActionEnum, Permission
from bkmonitor.utils.user import get_global_user


def get_bk_biz_ids_by_user(user=None, use_cache=True) -> [int]:
    spaces = get_space_dict_by_user(user, use_cache)
    return [biz["bk_biz_id"] for biz in spaces]


def get_space_map(use_cache=True) -> Dict[int, Dict[str, Any]]:
    space_map = {}
    spaces = SpaceApi.list_spaces_dict(use_cache)
    for space in spaces:
        space_map[space["bk_biz_id"]] = space
    return space_map


def get_space_dict_by_user(user=None, use_cache=True) -> List[Dict[str, Any]]:
    """
    获取用户拥有的空间列表
    """
    if user is None:
        username = get_global_user()
    elif isinstance(user, str):
        username = user
    else:
        username = user.username

    perm_client = Permission(username)
    return perm_client.filter_space_list_by_action(ActionEnum.VIEW_BUSINESS, use_cache)
