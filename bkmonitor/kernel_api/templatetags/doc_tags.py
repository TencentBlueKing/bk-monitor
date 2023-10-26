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

import datetime
import json
import logging
import random
import urllib.error
import urllib.parse
import urllib.request

from coreschema import schemas
from django import template
from django.db import models
from rest_framework import fields as rest_fields
from rest_framework import serializers

logger = logging.getLogger(__name__)
register = template.Library()


SLZ_GROUPS = {
    (serializers.BooleanField, models.BooleanField): "bool",
    (
        serializers.IntegerField,
        serializers.DecimalField,
        models.IntegerField,
        models.BigIntegerField,
        models.DecimalField,
        models.SmallIntegerField,
        schemas.Integer,
        schemas.Number,
    ): "int",
    (
        serializers.FloatField,
        models.FloatField,
    ): "float",
    (
        models.CharField,
        models.TextField,
        models.UUIDField,
        models.EmailField,
        models.IPAddressField,
        serializers.IPAddressField,
        serializers.EmailField,
        serializers.UUIDField,
        serializers.CharField,
        schemas.String,
    ): "string",
    (
        serializers.ListField,
        schemas.Array,
    ): "list",
    (
        serializers.DictField,
        serializers.ModelSerializer,
        schemas.Object,
        schemas.Anything,
    ): "object",
    (
        models.DateField,
        models.DateTimeField,
        serializers.DateField,
        serializers.DateTimeField,
    ): "time",
}


@register.filter("field_type")
def field_type(field):
    for k, v in list(SLZ_GROUPS.items()):
        if isinstance(field, k):
            return v
    return "any"


class Faker(object):
    def __init__(self):
        from faker import Faker as F

        self.faker = F()

    def __getattr__(self, item):
        return getattr(self.faker, item)

    def bool(self, name=None):
        return random.choice([True, False])

    def int(self, name=None):
        return random.randint(0, 100)

    def string(self, name=None):
        return "<%s>" % name.upper() if name else ""

    def float(self, name=None):
        return random.random()

    def list(self, name=None):
        return []

    def time(self, time=None):
        return datetime.datetime.now().isoformat()

    def object(self, name=None):
        return None


SLZ_TYPES = {
    (
        models.UUIDField,
        serializers.UUIDField,
    ): "uuid4",
    (
        models.EmailField,
        serializers.EmailField,
    ): "email",
    (
        models.IPAddressField,
        serializers.IPAddressField,
    ): "ipv4_private",
}


@register.filter("fake_data")
def fake_data(field, name=""):
    faker = Faker()
    if hasattr(field, "default"):
        value = field.default
    elif hasattr(field, "example"):
        value = field.example
    else:
        value = None
    for k, v in list(SLZ_TYPES.items()) + list(SLZ_GROUPS.items()):
        if isinstance(field, k) or isinstance(getattr(field, "schema", None), k):
            method = getattr(faker, v, faker.object)
            value = method(name)
            break

    empty_values = (rest_fields.empty, models.Empty, type(None))
    if isinstance(value, empty_values) or value in empty_values:
        return ""

    return value


@register.filter("fake_json")
def fake_json(slz, required_only=True):
    data = {}
    if slz:
        for name, f in list(slz.fields.items()):
            if required_only and not f.required:
                continue
            data[name] = fake_data(f, name)
    return data


@register.filter("fake_request")
def fake_request(api):
    method = api.action.lower()
    action = "{} {}".format(method.upper(), api.url)
    params = fake_json(api.request_serializer, True)
    if method == "get":
        example = "{}?{}".format(action, urllib.parse.urlencode(params)) if params else action
    else:
        example = "{}\n{}".format(action, json.dumps(params, indent=4))
    return example


@register.filter("fake_response")
def fake_response(api):
    response = fake_json(api.response_serializer, False)
    return json.dumps(response, indent=4)


@register.filter("slz_fields")
def slz_fields(slz):
    if not slz or getattr(slz, "many", False):
        return []
    return list(slz.fields.items())


@register.filter("mdnewline")
def markdown_newline(value):
    return value.replace("\r", "").replace("\n", "  \n")
