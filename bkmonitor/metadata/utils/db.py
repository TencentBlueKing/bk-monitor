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

from typing import Dict, List, Optional, Set, Union

from django.db.models.base import ModelBase
from django.db.models.query import QuerySet

# 默认分页过滤的数据量的大小
DEFAULT_FILTER_PAGE_SIZE = 500


def array_group(data, key, group=0):
    if not data or len(data) == 0:
        return {}

    result = {}
    for item in data:
        if isinstance(item, dict):
            attr = item.get(key, None)
        else:
            attr = getattr(item, key, None)

        if attr is None:
            return {}

        if group != 0:
            if attr not in result:
                if isinstance(item, dict):
                    item["_nums"] = 1
                else:
                    item._nums = 1
            else:
                if isinstance(item, dict):
                    item["_nums"] = result[attr]["_nums"] + 1
                else:
                    item._nums = result[attr]._nums + 1

            result[attr] = item

        else:
            if attr not in result:
                result[attr] = []
            result[attr].append(item)
    return result


def array_chunk(data, size=100):
    return [data[i : i + size] for i in range(0, len(data), size)]


def _filter_value(
    objs: QuerySet,
    value_func: Optional[str] = None,
    value_field_list: Optional[List] = None,
) -> Optional[QuerySet]:
    if value_func == "values":
        # 过滤返回数据
        if value_field_list:
            objs = objs.values(*value_field_list)
        else:
            objs = objs.values()
        return objs
    elif value_func == "values_list":
        # 限制过滤条件必选为 1 个
        if len(value_field_list) == 1:
            # NOTE: values list 使用的场景一般是带有过滤字段，否则暂不让不生效
            return objs.values_list(*value_field_list, flat=True)
        return None
    # 默认返回源对象
    return objs


def filter_model_by_in_page(
    model: ModelBase,
    field_op: str,
    filter_data: Union[List, Set],
    page_size: Optional[int] = DEFAULT_FILTER_PAGE_SIZE,
    value_func: Optional[str] = None,
    value_field_list: Optional[List] = None,
    other_filter: Optional[Dict] = None,
) -> Optional[List[QuerySet]]:
    """分页查询，避免使用 in 查询，导致数据量太大，导致 db 锁"""
    # 如果为空，则直接返回
    if not filter_data:
        return []

    # 转换为list，方便统一处理
    if not isinstance(filter_data, list):
        filter_data = list(filter_data)
    # 处理对应的请求
    chunk_list = [filter_data[i : i + page_size] for i in range(0, len(filter_data), page_size)]
    # 返回数据
    ret_data = []
    for chunk in chunk_list:
        # 组装过滤条件
        _filter = {field_op: chunk}
        # 添加其它过滤条件
        if other_filter is not None:
            _filter.update(other_filter)

        result = model.objects.filter(**_filter)
        # 根据函数进行过滤
        result = _filter_value(result, value_func, value_field_list)

        if not result:
            continue

        ret_data.extend(list(result))

    return ret_data


def filter_query_set_by_in_page(
    query_set: QuerySet,
    field_op: str,
    filter_data: Union[List, Set],
    page_size: Optional[int] = DEFAULT_FILTER_PAGE_SIZE,
    value_func: Optional[str] = None,
    value_field_list: Optional[List] = None,
    other_filter: Optional[Dict] = None,
) -> Optional[List[QuerySet]]:
    """过滤 queryset 获取到的数据"""
    # 如果为空，则直接返回
    if not filter_data:
        return []

    # 转换为list，方便统一处理
    if not isinstance(filter_data, list):
        filter_data = list(filter_data)
    # 处理对应的请求
    chunk_list = [filter_data[i : i + page_size] for i in range(0, len(filter_data), page_size)]
    # 返回数据
    ret_data = []
    for chunk in chunk_list:
        # 组装过滤条件
        _filter = {field_op: chunk}
        # 添加其它过滤条件
        if other_filter is not None:
            _filter.update(other_filter)
        result = query_set.filter(**_filter)
        # 根据函数进行过滤
        result = _filter_value(result, value_func, value_field_list)
        if not result:
            continue

        ret_data.extend(list(result))

    return ret_data
