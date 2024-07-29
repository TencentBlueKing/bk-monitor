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

from json import dump as json_dump
from json import dumps as json_dumps
from json import load as json_load
from json import loads as json_loads

try:
    from django.core.files import File
except ImportError:
    File = None

try:
    import ujson
except ImportError:
    __implements__ = []
else:
    __implements__ = ["load", "dump", "loads", "dumps"]


SAFE_OPTIONS = {
    "encode_html_chars",
    "ensure_ascii",
    "double_precision",
    "escape_forward_slashes",
    "indent",
    "precise_float",
}


def load(*args, **kwargs):
    if SAFE_OPTIONS.issuperset(kwargs.keys()):
        try:
            return ujson.load(*args, **kwargs)
        except ValueError:
            pass
    return json_load(*args, **kwargs)


def dump(*args, **kwargs):
    if SAFE_OPTIONS.issuperset(kwargs.keys()):
        try:
            kwargs.setdefault("escape_forward_slashes", False)
            return ujson.dump(*args, **kwargs)
        except OverflowError:
            kwargs.pop("escape_forward_slashes")
    return json_dump(*args, **kwargs)


def loads(*args, **kwargs):
    if SAFE_OPTIONS.issuperset(kwargs.keys()):
        try:
            kwargs.update({"precise_float": True})
            return ujson.loads(*args, **kwargs)
        except ValueError:
            kwargs.pop("precise_float")
            pass
    return json_loads(*args, **kwargs)


def dumps(*args, **kwargs):
    # 当前文件为django的File对象时，不进行转换，避免segmentation fault错误
    if args and File and isinstance(args[0], File):
        return json_dumps(*args, **kwargs)

    if SAFE_OPTIONS.issuperset(kwargs.keys()):
        try:
            kwargs.setdefault("escape_forward_slashes", False)
            return ujson.dumps(*args, **kwargs)
        except OverflowError:
            kwargs.pop("escape_forward_slashes")
    return json_dumps(*args, **kwargs)
