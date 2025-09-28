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

import io
import os

import six
from six.moves import map, range


def path_to_dotted(path):
    return ".".join([p for p in path.split(os.sep) if p])


def camel_to_underscore(camel_str):
    assert isinstance(camel_str, six.string_types)

    buf = io.StringIO()
    str_len = len(camel_str)

    for i in range(str_len):
        cur_letter = camel_str[i]
        if i and cur_letter == cur_letter.upper():
            prev_letter = camel_str[i - 1]
            next_letter = camel_str[i + 1] if i < str_len - 1 else "A"
            if cur_letter.isalpha():
                if prev_letter != prev_letter.upper() or next_letter != next_letter.upper():
                    buf.write("_")
        buf.write(cur_letter)

    result = buf.getvalue()
    buf.close()

    return result.lower()


def underscore_to_camel(underscore_str):
    assert isinstance(underscore_str, six.string_types)

    return "".join([x.capitalize() for x in underscore_str.split("_")])


invalid_filename_char = ["\\", "/", ":", "*", "?", '"', "<", ">", "|"]


def convert_filename(to_filename_string):
    r"""
    将文件名转换成符合linux文件系统规则的字符串
    需要转换的字符串：\ / : * ? " < > |
    :param to_filename_string:
    :return:
    """
    for index, c in enumerate(invalid_filename_char):
        target_string = "-%s-" % (chr(ord("a") + index))
        to_filename_string = to_filename_string.replace(c, target_string)

    return to_filename_string


output_string = list(map(convert_filename, invalid_filename_char))


def reconvert_filename(to_string_filename):
    """
    将转换过的文件名，重新变成之前的字符串
    :param to_string_filename:
    :return:
    """
    for index, c in enumerate(output_string):
        to_string_filename = to_string_filename.replace(c, invalid_filename_char[index])

    return to_string_filename


def cut_str_by_max_bytes(s: str, max_bytes: int, encoding: str = None):
    """
    字符串按最大字节长度裁剪
    """
    # 没有超过最大长度
    if len(s.encode(encoding=encoding) if encoding else s) <= max_bytes:
        return s

    # 逐字符计算字符串长度，查找截断字符串的位置
    new_s_len = 0
    max_index = -1
    for index, c in enumerate(s):
        c_bytes = c.encode(encoding=encoding) if encoding else c
        if len(c_bytes) + new_s_len > max_bytes:
            break
        new_s_len += len(c_bytes)
        max_index = index

    return s[: max_index + 1]


def cut_line_str_by_max_bytes(s: str, max_bytes: int, encoding: str = None):
    """
    按行和字节数进行分段切割
    """
    # 没有超过最大长度
    if len(s.encode(encoding=encoding) if encoding else s) <= max_bytes:
        return [s]

    # 逐行字符计算字符串长度，查找截断字符串的位置
    last_block_len = 0
    lines = s.split("\n")
    line_blocks = []
    current_line = ""
    for line in lines:
        c_bytes = line.encode(encoding=encoding) if encoding else line
        if len(c_bytes) + 2 + last_block_len > max_bytes:
            # 如果当前这一行相加超过了最大长度，则表示上一段已满足条件
            if not current_line:
                # 如果一行就已经超过了一段的长度，则进行单行裁剪
                line_blocks.append("{}\n".format(cut_str_by_max_bytes(line, max_bytes - 2, encoding=encoding)))
                continue
            line_blocks.append(current_line)
            current_line = ""
            last_block_len = 0
        if current_line:
            current_line += f"\n{line}"
        else:
            current_line = line
        last_block_len += len(c_bytes) + 2

    line_blocks.append(current_line)
    return line_blocks


def get_content_length(content: str, encoding: str = None):
    """
    根据字节编码进行长度获取
    """
    if encoding:
        return len(content.encode(encoding=encoding))
    return len(content)
