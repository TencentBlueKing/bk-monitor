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
import six
from six.moves import range

_escape_table = [six.chr(x) for x in range(128)]
_escape_table[0] = "\\0"
_escape_table[ord("\\")] = "\\\\"
_escape_table[ord("\n")] = "\\n"
_escape_table[ord("\r")] = "\\r"
_escape_table[ord("\032")] = "\\Z"
_escape_table[ord('"')] = '\\"'
_escape_table[ord("'")] = "\\'"


def _escape_unicode(value, mapping=None):
    """escapes *value* without adding quote.

    Value should be unicode
    """
    return value.translate(_escape_table)


def escape_string(value, mapping=None):
    """escape_string escapes *value* but not surround it with quotes.

    Value should be bytes or unicode.
    """
    if isinstance(value, six.string_types):
        return _escape_unicode(value)
    assert isinstance(value, (bytes, bytearray))
    value = value.replace("\\", "\\\\")
    value = value.replace("\0", "\\0")
    value = value.replace("\n", "\\n")
    value = value.replace("\r", "\\r")
    value = value.replace("\032", "\\Z")
    value = value.replace("'", "\\'")
    value = value.replace('"', '\\"')
    return value


def escape_bytes_prefixed(value, mapping=None):
    assert isinstance(value, (bytes, bytearray))
    return b"_binary'%s'" % escape_string(value)


def escape_bytes(value, mapping=None):
    assert isinstance(value, (bytes, bytearray))
    return b"'%s'" % escape_string(value)
