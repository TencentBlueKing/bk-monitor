# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
import math
from typing import List, Tuple

from django.conf import settings

from bkmonitor.utils.thread_backend import ThreadPool

logger = logging.getLogger("bkmonitor.cron_report")


def batch_request(
    func, params, get_data=lambda x: x["info"], get_count=lambda x: x["count"], limit=500, app="cmdb", thread_num=20
):
    """
    并发请求接口
    :param func: 请求方法
    :param params: 请求参数
    :param get_data: 获取数据函数
    :param get_count: 获取总数函数
    :param limit: 一次请求数量
    :param app: 请求系统 ["nodeman", "cmdb","metadata", "bcs_cc"]
    :param thread_num: 线程数
    :return: 请求结果
    """
    params = params.copy()
    refresh_params = {
        "cmdb": lambda origin_params, _start, _limit: origin_params.update(
            {"page": {"start": _start, "limit": _limit}}
        ),
        "nodeman": lambda origin_params, _start, _limit: origin_params.update({"page": _start, "pagesize": _limit}),
        "metadata": lambda origin_params, _start, _limit: origin_params.update({"page": _start, "page_size": _limit}),
        "bcs_cc": lambda origin_params, _start, _limit: origin_params.update({"offset": _start, "limit": _limit}),
        "bk_login": lambda origin_params, _start, _limit: origin_params.update({"page": _start, "page_size": _limit}),
        "job": lambda origin_params, _start, _limit: origin_params.update({"start": _start, "length": _limit}),
    }

    # 标识使用偏移量的系统
    use_offset = app in ["cmdb", "bcs_cc", "job"]

    # 第一页同时获取总数
    refresh_params[app](params, 0 if use_offset else 1, limit)
    result = func(params)
    if not result:
        return []

    data = get_data(result)
    count = get_count(result)
    if not count:
        return data
    data = list(data)
    if count <= limit:
        return data

    # 根据请求总数并发请求剩余页
    pool = ThreadPool(thread_num)
    futures = []
    starts = range(limit, count, limit) if use_offset else range(2, math.ceil(count / limit) + 1)
    for start in starts:
        refresh_params[app](params, start, limit)
        futures.append(pool.apply_async(func, args=(params.copy(),)))

    pool.close()
    pool.join()

    # 取值
    for future in futures:
        data.extend(get_data(future.get()))

    return data


def get_host_display_fields(bk_biz_id: int) -> List[str]:
    """
    获取主机展示字段列表
    """
    return settings.HOST_DISPLAY_FIELDS or ["bk_host_innerip", "bk_host_name", "bk_host_innerip_v6"]


def is_ipv6_biz(bk_biz_id) -> bool:
    """
    判断业务是否支持ipv6
    """
    return str(bk_biz_id) in {str(biz) for biz in settings.IPV6_SUPPORT_BIZ_LIST}


def get_host_view_display_fields(bk_biz_id: int) -> Tuple[str, str]:
    """
    获取主机树展示字段
    """
    fields = settings.HOST_VIEW_DISPLAY_FIELDS or ["bk_host_innerip", "bk_host_name"]
    if len(fields) == 1:
        fields.append("")
    return fields[0], fields[1]
