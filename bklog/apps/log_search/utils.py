# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""
import functools
import operator

from typing import List, Dict, Any


def sort_func(data: List[Dict[str, Any]], sort_list: List[List[str]], key_func=lambda x: x) -> List[Dict[str, Any]]:
    """
    排序函数 提供复杂嵌套的数据结构排序能力
    params data 源数据  [{"a": {"b": 3}}, {"a": {"b": 7}}, {"a": {"b": 2}}]
    params sort_list 排序规则 [["a.b", "desc"]]
    params key_func 排序字段值获取函数
    """

    def _sort_compare(x: Dict[str, Any], y: Dict[str, Any]) -> int:

        x = key_func(x)
        y = key_func(y)

        def _get_value(keys: str, _data: Dict[str, Any]) -> Any:

            try:
                _value = functools.reduce(operator.getitem, keys.split("."), _data)
            except (KeyError, TypeError):
                _value = None
            return _value

        for sort_info in sort_list:
            field_name, order = sort_info

            if "." in field_name:
                _x_value = _get_value(field_name, x)
                _y_value = _get_value(field_name, y)
            else:
                _x_value = x.get(field_name, None)
                _y_value = y.get(field_name, None)

            if _x_value is None or _y_value is None:
                continue

            try:
                if _x_value != _y_value:
                    if order == "desc":
                        return (_x_value < _y_value) - (_x_value > _y_value)
                    else:
                        return (_x_value > _y_value) - (_x_value < _y_value)
            except TypeError:
                continue

        return 0

    return sorted(data, key=functools.cmp_to_key(_sort_compare))
