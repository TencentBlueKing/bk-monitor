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
import json
import operator
from io import BytesIO
from typing import Any

from django.http import FileResponse
import re

from apps.log_search.constants import DEFAULT_TIME_FIELD, HighlightConfig
from apps.utils.local import get_request_external_username, get_request_username


def sort_func(data: list[dict[str, Any]], sort_list: list[list[str]], key_func=lambda x: x) -> list[dict[str, Any]]:
    """
    排序函数 提供复杂嵌套的数据结构排序能力
    params data 源数据  [{"a": {"b": 3}}, {"a": {"b": 7}}, {"a": {"b": 2}}]
    params sort_list 排序规则 [["a.b", "desc"]]
    params key_func 排序字段值获取函数
    """

    def _sort_compare(x: dict[str, Any], y: dict[str, Any]) -> int:
        x = key_func(x)
        y = key_func(y)

        def _get_value(keys: str, _data: dict[str, Any]) -> Any:
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
                if field_name == DEFAULT_TIME_FIELD:
                    # 转化为相同的数据类型
                    _x_value = str(_x_value)
                    _y_value = str(_y_value)
                if _x_value != _y_value:
                    if order == "desc":
                        return (_x_value < _y_value) - (_x_value > _y_value)
                    else:
                        return (_x_value > _y_value) - (_x_value < _y_value)
            except TypeError:
                continue

        return 0

    return sorted(data, key=functools.cmp_to_key(_sort_compare))


def create_context_should_query(order, body_should_data, sort_fields, sort_fields_value):
    """
    上下文or查询构造
    请求参数
    :param order: 排序方式 -或+
    :param body_should_data: 父级查询参数
    :param sort_fields: 排序字段
    :param sort_fields_value: 排序字段对应的值
    """
    if order not in ["-", "+"]:
        return

    if order == "+":
        sort_fields_num = len(sort_fields)
        range_op = "gt" if sort_fields_num > 1 else "gte"
    else:
        range_op = "lt"

    # 需要进行term查询的字段
    term_fields = []
    # 构造查询语句
    for index, (range_field, range_field_value) in enumerate(zip(sort_fields, sort_fields_value)):
        if index == 0:
            body_should_data.append(
                {
                    "range": {
                        range_field: {
                            range_op: range_field_value,
                        }
                    }
                }
            )
        else:
            body_should_data.append(
                {
                    "bool": {
                        "filter": [
                            {"term": {_term_range_field["range_field"]: _term_range_field["range_field_value"]}}
                            for _term_range_field in term_fields
                        ]
                    }
                }
            )
            # 升序时最后一个字段操作符设置为大于等于
            if order == "+" and index + 1 == sort_fields_num:
                range_op = "gte"

            body_should_data[index]["bool"]["filter"].append(
                {
                    "range": {
                        range_field: {
                            range_op: range_field_value,
                        }
                    }
                }
            )
        term_fields.append({"range_field": range_field, "range_field_value": range_field_value})


def fetch_request_username():
    """
    1.如果存在外部用户,则优先取外部用户名.
    2.如果是外部用户,则加上external_前缀,避免外部用户名和内部用户名相同引起问题
    """
    request_username = get_request_external_username()
    if request_username:
        request_username = f"external_{request_username}"
    else:
        request_username = get_request_username()
    return request_username


def add_highlight_mark(data_list: list[dict], match_field: str, pattern: str, ignore_case: bool = False):
    """
    添加高亮标记
    :param data_list: 数据列表
    :param match_field: data中需要进行高亮的字段
    :param pattern: 高亮内容的正则表达式
    :param ignore_case: 是否忽略大小写
    """
    if not data_list or not match_field or not pattern or ("." not in match_field and match_field not in data_list[0]):
        return data_list

    for data in data_list:
        # 对 grep_field 字段 pattern 内容进行高亮处理
        if "." in match_field:
            json_data = json.loads(data[match_field.split(".")[0]])
            tmp_dic = json_data
            keys = match_field.split(".")
            first_key = keys[0]
            last_key = keys[-1]
            for key in keys[1:]:
                if isinstance(json_data, dict) and key in json_data:
                    if key == last_key:
                        value = json_data[last_key]
                    else:
                        json_data = json_data[key]
                else:
                    continue
            if not isinstance(value, str):
                value = str(value)
            json_data[last_key] = re.sub(
                pattern,
                lambda x: HighlightConfig.PRE_TAG + x.group() + HighlightConfig.POST_TAG,
                value,
                flags=re.I if ignore_case else 0,
            )
            data[first_key] = json.dumps(tmp_dic)
        else:
            value = data[match_field]
            if not isinstance(value, str):
                value = str(value)
            data[match_field] = re.sub(
                pattern,
                lambda x: HighlightConfig.PRE_TAG + x.group() + HighlightConfig.POST_TAG,
                value,
                flags=re.I if ignore_case else 0,
            )

    return data_list


def split_object_fields(fields_list: list[str]):
    """
    把列表中包含逗号的字符串进行分割
    """
    result_list = []
    for field in fields_list:
        result_list.append(field)
        parts = field.split(".")
        for i in range(1, len(parts)):
            result_list.append(".".join(parts[:i]))

    return result_list


def create_download_response(buffer: BytesIO, file_name: str, content_type: str = "text/plain") -> FileResponse:
    """
    创建一个通用的文件下载响应。

    :param buffer: 一个包含文件内容的 BytesIO 对象。
    :param file_name: 文件的名称。
    :param content_type: 文件的 MIME 类型，默认为 "text/plain"。
    :return: 配置完毕的 FileResponse 对象。
    """
    # 重置指针回到流的开始位置
    buffer.seek(0)

    # 创建文件下载响应
    response = FileResponse(
        buffer,
        as_attachment=True,  # 将内容作为附件下载而不是直接打开
        filename=file_name,
        content_type=content_type,
    )

    return response
