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
"""
business-related classes and functions.

This module records whether the business is active or not.
"""


import time

from six.moves import map

from core.drf_resource import resource
from utils.redis_client import redis_cli

__all__ = [
    "get_all_business",
    "get_all_activate_business",
    "activate",
    "deactivate",
]

# redis key
ACTIVE_BIZ_LAST_VISIT_TIME = "active_biz_last_visit_time"
ACTIVE_BIZ_LAST_VISITOR = "active_biz_last_visitor"

BIZ_ACTIVE_EXPIRED_TIME_KEY = "biz_active_expired_time"
DEFAULT_EXPIRED_TIME = 7 * 24 * 3600


def activate(biz_id, username=""):
    """
    Set the biz to top of activation list
    """
    biz_id = str(biz_id).strip()
    if not biz_id:
        return

    score = int(time.time())

    redis_cli.zadd(ACTIVE_BIZ_LAST_VISIT_TIME, {biz_id: score})
    if username and str(username).strip():
        redis_cli.hset(ACTIVE_BIZ_LAST_VISITOR, biz_id, username)


def deactivate(biz_id):
    """
    Remove the biz from the activation list
    """
    biz_id = str(biz_id).strip()
    if not biz_id:
        return
    return redis_cli.zrem(ACTIVE_BIZ_LAST_VISIT_TIME, biz_id)


def maintainer(biz_id):
    result = redis_cli.hget(ACTIVE_BIZ_LAST_VISITOR, biz_id)
    return result.decode("utf-8") if result else ""


def get_all_business():
    """
    Get all businesses
    """
    return [
        (int(data[0]), data[1])
        for data in redis_cli.zrange(ACTIVE_BIZ_LAST_VISIT_TIME, 0, -1, withscores=True)
        if data[0]
    ]


def get_business_id_list():
    all_business = get_all_business()
    id_list = []
    for business in all_business:
        if business[0]:
            id_list.append(int(business[0]))
    return id_list


def _get_expired_time(default_expired_time=DEFAULT_EXPIRED_TIME):
    from monitor.models import GlobalConfig

    try:
        expired_time = int(GlobalConfig.objects.get(key=BIZ_ACTIVE_EXPIRED_TIME_KEY).value)
    except GlobalConfig.DoesNotExist:
        expired_time = default_expired_time
    return expired_time


def get_all_activate_business(cmp_func=None):
    """
    Get a list of all active businesses
    """
    if cmp_func:
        all_business = redis_cli.zrange(ACTIVE_BIZ_LAST_VISIT_TIME, 0, -1, withscores=True)
        return [int(b[0]) for b in all_business if cmp_func(b)]
    else:
        max_score = int(time.time())
        min_score = max_score - _get_expired_time(DEFAULT_EXPIRED_TIME)
        return redis_cli.zrevrangebyscore(ACTIVE_BIZ_LAST_VISIT_TIME, max_score, min_score)


def human_readable_biz(biz_id_list):
    """
    return a human readable biz list
    """
    biz_info = resource.space.get_space_map()
    if not isinstance(biz_id_list, list):
        biz_id_list = [biz_id_list]
    biz_id_list = set(map(int, biz_id_list))
    return [biz_info[biz_id]["display_name"] if biz_id in biz_info else str(biz_id) for biz_id in biz_id_list]
