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


import json
from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

import arrow
from django.utils.encoding import force_str
from django.utils.functional import Promise
from elasticsearch_dsl import AttrDict, AttrList

STD_DT_FORMAT = "%Y-%m-%d %H:%M:%S"
SUPPORTED_TYPES = {datetime, date, time, Decimal, UUID, set}
assert len(SUPPORTED_TYPES) == len({c.__name__ for c in SUPPORTED_TYPES})
SUPPORTED_TYPES_NAME2CLASS = {c.__name__: c for c in SUPPORTED_TYPES}


class ESJSONEncoder(json.JSONEncoder):

    """
    extended json encoder
    enable to es AttrDict, AttrList
    """

    def default(self, obj):
        type_ = type(obj)
        if issubclass(type_, AttrList):
            return list(obj)
        if issubclass(type_, AttrDict):
            return obj.to_dict()
        return json.JSONEncoder.default(self, obj)


class CustomJSONEncoder(json.JSONEncoder):

    """
    extended json encoder
    enable to encode datetime, date, time, decimal, uuid
    """

    def default(self, obj):
        type_ = type(obj)
        if type_ in SUPPORTED_TYPES:
            if issubclass(type_, (datetime, date, time)):
                return {"__type__": type_.__name__, "__value__": obj.strftime(STD_DT_FORMAT)}
            if issubclass(type_, Decimal):
                return {"__type__": type_.__name__, "__value__": obj.as_tuple()}
            if issubclass(type_, UUID):
                return {"__type__": type_.__name__, "__value__": obj.hex}
            if issubclass(type_, set):
                return list(obj)
            if issubclass(type_, Promise):
                return force_str(object)
        return json.JSONEncoder.default(self, obj)


class CustomJSONDecoder(json.JSONDecoder):

    """
    extended json decoder
    enable to decode datetime, date, time, decimal, uuid
    """

    def __init__(self, **kw):
        json.JSONDecoder.__init__(self, object_hook=self.dict_to_object, **kw)

    def dict_to_object(self, d):
        type_ = SUPPORTED_TYPES_NAME2CLASS.get(d.get("__type__"))
        if type_ in SUPPORTED_TYPES:
            if issubclass(type_, (datetime, date, time)):
                dt = arrow.get(d.get("__value__")).replace(tzinfo="local").naive
                if type_ is datetime:
                    return dt
                elif type_ is date:
                    return dt.date()
                else:
                    return dt.timetz()
            if issubclass(type_, Decimal):
                return Decimal(d.get("__value__"))
            if issubclass(type_, UUID):
                return UUID(d.get("__value__"))
        return d


class JSONEncoderDT(json.JSONEncoder):

    """
    extended json encoder
    enable to encode datetime
    """

    def default(self, o):
        if isinstance(o, datetime):
            return o.strftime(STD_DT_FORMAT)
        else:
            return super(JSONEncoderDT, self).default(o)


class JSONDecoderDT(json.JSONDecoder):

    """
    extended json decoder
    enable to decode datetime, date, time
    """

    def __init__(self, **kw):
        json.JSONDecoder.__init__(self, object_hook=self.dict_to_object, **kw)

    def dict_to_object(self, d):
        type_ = SUPPORTED_TYPES_NAME2CLASS.get(d.get("__type__"))
        if type_ in SUPPORTED_TYPES:
            if issubclass(type_, (datetime, date, time)):
                return d.get("__value__")
        return d


def dumps(obj, **kwargs):
    return json.dumps(obj, cls=CustomJSONEncoder, **kwargs)


def loads(s, **kwargs):
    return json.loads(s, cls=CustomJSONDecoder, **kwargs)
