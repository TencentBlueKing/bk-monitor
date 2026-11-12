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
import traceback
from contextlib import contextmanager
from typing import Any, Callable, List

from apps.utils.log import logger


def map_if(arr: List, map_func: Callable[[Any], Any] = lambda x: x, if_func: Callable[[Any], bool] = lambda x: bool(x)):
    return [map_func(item) for item in arr if if_func(item)]


@contextmanager
def ignored(*exceptions, **kwargs):
    try:
        yield
    except exceptions:
        if kwargs.get("log_exception", False):
            logger.warning(traceback.format_exc())
        pass


def get_field_value(record: dict, field: str, default: Any = "") -> Any:
    """
    按 field_alias 从日志中取值，同时兼容扁平（dotted key）与嵌套两种结构

    优先直接命中（扁平结构或同名字段），未命中时按点号路径在嵌套结构中逐层导航，
    例如 a.b.c 可同时支持 {"a.b.c": "1"} 与 {"a": {"b": {"c": "1"}}}

    :param record: 单条日志
    :param field: result_schema 中的 field_alias，可能是 a.b.c 这类嵌套路径
    :param default: 路径不存在时的返回值，默认空串（与既有导出行为一致）
    :return: 字段值；路径不存在时返回 default
    """
    if not isinstance(record, dict) or not isinstance(field, str) or not field:
        return default

    if field in record:
        return record[field]

    value = record
    for part in field.split("."):
        if not isinstance(value, dict) or part not in value:
            return default
        value = value[part]

    return value


def project_chart_row(record: dict, fields: list) -> list:
    """
    把单条记录投影成导出的一行

    兼容扁平（dotted key）与嵌套两种字段形态，字段缺失时输出空串

    :param record: 单条记录
    :param fields: result_schema 中的 field_alias 列表
    :return: 按 fields 顺序排列的值列表
    """
    return [get_field_value(record, field) for field in fields]
