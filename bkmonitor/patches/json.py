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

from json import JSONEncoder
from json import dump as json_dump
from json import dumps as json_dumps
from json import load as json_load
from json import loads as json_loads
from logging import getLogger

from django.utils.functional import Promise

try:
    from django.core.files import File
except ImportError:
    File = None

try:
    from elasticsearch_dsl import AttrDict, AttrList
except ImportError:
    AttrList = AttrDict = None

try:
    import ujson
except ImportError:
    __implements__ = []
else:
    __implements__ = ["load", "dump", "loads", "dumps"]


logger = getLogger("bkmonitor")


SAFE_OPTIONS = {
    "encode_html_chars",
    "ensure_ascii",
    "escape_forward_slashes",
    "indent",
}


class CustomJSONEncoder(JSONEncoder):

    """
    extended json encoder
    enable to encode datetime, date, time, decimal, uuid
    """

    def default(self, obj):
        type_ = type(obj)
        if issubclass(type_, set):
            return list(obj)
        if issubclass(type_, bytes):
            return obj.decode()
        if AttrList and issubclass(type_, AttrList):
            return list(obj)
        if AttrDict and issubclass(type_, AttrDict):
            return obj.to_dict()
        if issubclass(type_, Promise):
            return str(obj)
        return JSONEncoder.default(self, obj)


def load(*args, **kwargs):
    # 只允许通过位置参数传递文件对象，不支持关键字参数
    if not args:
        raise TypeError("load() missing 1 required positional argument")

    # ujson的load方法不支持任何关键字参数
    if not kwargs:
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
        except TypeError:
            kwargs.pop("escape_forward_slashes")
            return json_dump(*args, cls=CustomJSONEncoder, **kwargs)
    return json_dump(*args, **kwargs)


def loads(*args, **kwargs):
    # 只允许通过位置参数传递字符串，不支持关键字参数
    if not args:
        raise TypeError("loads() missing 1 required positional argument")

    # ujson的loads方法不支持任何关键字参数
    if not kwargs:
        try:
            return ujson.loads(*args, **kwargs)
        except ValueError:
            pass
    return json_loads(*args, **kwargs)


def dumps(*args, **kwargs):
    if args and isinstance(args[0], set):
        args = (list(args[0]),) + args[1:]

    # 当前文件为django的File对象时，不进行转换，避免segmentation fault错误
    if args and File and isinstance(args[0], File):
        return json_dumps(*args, **kwargs)

    if SAFE_OPTIONS.issuperset(kwargs.keys()):
        try:
            kwargs.setdefault("escape_forward_slashes", False)
            return ujson.dumps(*args, **kwargs)
        except OverflowError:
            kwargs.pop("escape_forward_slashes")
        except TypeError:
            kwargs.pop("escape_forward_slashes")
            return json_dumps(*args, cls=CustomJSONEncoder, **kwargs)
    return json_dumps(*args, **kwargs)
