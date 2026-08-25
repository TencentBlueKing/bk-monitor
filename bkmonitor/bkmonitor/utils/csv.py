"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import csv
from urllib import parse
from typing import Any
from collections.abc import Iterable

from django.http import HttpResponse


def generate_csv_file_download_response(file_name: str, file_content: Iterable[Iterable[Any]]) -> HttpResponse:
    """生成一个带有文件内容和文件名的 HTTP 响应"""

    # 确保文件名以 .csv 结尾
    if file_name[-4:].lower() != ".csv":
        file_name += ".csv"
    # ISO8859_1 是 ASCII 的超集（一种8位的字符编码），实现最大兼容性
    # 部分浏览器不支持解析参数值的 %，所以这里直接不做 URL 编码，然后用双引号包裹起来
    iso8859_1_file_name = file_name.encode("utf-8").decode("ISO8859_1")

    # 需要替换掉不符合操作系统文件名要求和会影响请求头读取的字符
    prohibited_chars = "\\/?:*\"<>|';="
    for char in prohibited_chars:
        iso8859_1_file_name = iso8859_1_file_name.replace(char, "_")

    # 使用 parse.quote 进行 URL 编码，确保文件名中的特殊字符被正确编码
    # 现代浏览器会自动将不符合操作系统文件名要求的字符替换为下划线，这里 utf8_file_name 不做处理
    utf8_file_name = parse.quote(file_name, encoding="utf8")

    # 现代浏览器会自动将文件名截取到符合操作系统文件名要求的长度，这里只返回最多 240 个字符
    iso8859_1_file_name = iso8859_1_file_name[-240:]
    utf8_file_name = utf8_file_name[-240:]

    # filename* 优先级更高，用于支持现代浏览器和系统，可以正确显示Unicode文件名
    response = HttpResponse(
        content_type="text/csv",
        headers={
            "Content-Disposition": f"attachment;filename=\"{iso8859_1_file_name}\";filename*=UTF-8''{utf8_file_name}"
        },
    )

    writer = csv.writer(response)
    for row_list in file_content:
        # 例子：row_list => ["a", "b", "c"]
        writer.writerow(row_list)
    return response
