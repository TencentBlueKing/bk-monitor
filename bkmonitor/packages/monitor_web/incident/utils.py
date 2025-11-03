"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import re

PASCAL_TO_SNAKE_PATTERN_1 = re.compile(r"([A-Z]+)([A-Z][a-z])")
PASCAL_TO_SNAKE_PATTERN_2 = re.compile(r"([a-z\d])([A-Z])")


def pascal_to_snake(name):
    """
    将大驼峰（PascalCase）转换为下划线命名法（snake_case）

    Args:
        name (str): 大驼峰格式的字符串

    Returns:
        str: 下划线命名法格式的字符串

    Examples:
        >>> pascal_to_snake("EventSource")
        'event_source'
        >>> pascal_to_snake("HTTPSConnection")
        'https_connection'
        >>> pascal_to_snake("XMLHttpRequest")
        'xml_http_request'
        >>> pascal_to_snake("IOError")
        'io_error'
        >>> pascal_to_snake("MyAPIClient")
        'my_api_client'
    """
    # 处理连续大写字母的情况，如 HTTPSConnection -> HTTPS_Connection
    # 在连续大写字母中，除了最后一个字母外，其他字母后面都加下划线
    name = PASCAL_TO_SNAKE_PATTERN_1.sub(r"\1_\2", name)

    # 处理大写字母前面添加下划线的情况，如 EventSource -> Event_Source
    name = PASCAL_TO_SNAKE_PATTERN_2.sub(r"\1_\2", name)

    # 转换为小写
    return name.lower()
