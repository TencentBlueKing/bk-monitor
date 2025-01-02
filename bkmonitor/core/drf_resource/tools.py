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
import logging
from collections import OrderedDict

from django.utils.encoding import force_str
from rest_framework import serializers
from rest_framework.fields import empty

from bkmonitor.utils.text import camel_to_underscore

logger = logging.getLogger(__name__)


class FieldType(object):
    BOOLEAN = "Boolean"
    NUMBER = "Number"
    STRING = "String"
    INTEGER = "Integer"
    OBJECT = "Object"
    ARRAY = "Array"
    ENUM = "Enum"


def get_serializer_fields(serializer_class):
    """
    遍历serializer所有field，生成关于该serializer的schema列表
    """

    if not serializer_class:
        return []

    serializer = serializer_class()

    if isinstance(serializer, serializers.ListSerializer):
        return []

    if not isinstance(serializer, serializers.Serializer):
        return []

    fields = []
    for field in list(serializer.fields.values()):
        if field.read_only or isinstance(field, serializers.HiddenField):
            continue

        fields.append(field_to_schema(field))

    return fields


def field_to_schema(field):
    """
    根据serializer field生成关于该field数据结构的schema
    """
    description = force_str(field.label) if field.label else ""

    type_params = {
        "type": FieldType.STRING,
    }

    if isinstance(field, (serializers.ListSerializer, serializers.ListField)):
        child_schema = field_to_schema(field.child)
        type_params = {"type": FieldType.ARRAY, "items": child_schema}
    elif isinstance(field, serializers.Serializer):
        type_params = {
            "type": FieldType.OBJECT,
            "properties": OrderedDict([(key, field_to_schema(value)) for key, value in list(field.fields.items())]),
        }
    # elif isinstance(field, serializers.ManyRelatedField):
    #     type_params = {
    #         "type": FieldType.ARRAY,
    #         "items": FieldType.STRING,
    #     }
    elif isinstance(field, serializers.RelatedField):
        type_params = {
            "type": FieldType.STRING,
        }
    elif isinstance(field, (serializers.MultipleChoiceField, serializers.ChoiceField)):
        type_params = {
            "type": FieldType.ENUM,
            "choices": list(field.choices.keys()),
        }
    elif isinstance(field, serializers.BooleanField):
        type_params = {
            "type": FieldType.BOOLEAN,
        }
    elif isinstance(field, (serializers.DecimalField, serializers.FloatField)):
        type_params = {
            "type": FieldType.NUMBER,
        }
    elif isinstance(field, serializers.IntegerField):
        type_params = {
            "type": FieldType.INTEGER,
        }

    type_params.update(
        {
            "required": field.required,
            "name": field.field_name,
            "source_name": field.source,
            "description": description,
            "default": field.default,
        }
    )
    return type_params


def render_schema(fields, parent="", using_source=False):
    """
    将field schema渲染成apidoc的格式
    :param fields: schema list
    :param parent: field name of parent
    :param using_source: using source name of the field
    :return: list
    """
    print_list = []
    for field in fields:
        real_type = field["type"]
        field_name = field["source_name"] if using_source else field["name"]
        origin_name = "{}.{}".format(parent, field_name) if parent else field_name
        real_name = origin_name
        if field["type"] == FieldType.ARRAY:
            real_type = "%s[]" % field["items"]["type"]
        elif field["type"] == FieldType.ENUM:
            choices = ",".join(['"%s"' % c for c in field["choices"]])
            real_type = "{}={}".format(FieldType.STRING, choices)
        if field["default"] is not empty:
            real_name = "{}={}".format(real_name, field["default"])
        if not field["required"]:
            real_name = "[%s]" % real_name
        print_list.append("{{{}}} {} {}".format(real_type, real_name, field["description"]))

        if field["type"] == FieldType.ARRAY and field["items"]["type"] == FieldType.OBJECT:
            print_list += render_schema(
                fields=list(field["items"]["properties"].values()), parent=origin_name, using_source=using_source
            )
        elif field["type"] == FieldType.OBJECT:
            print_list += render_schema(
                fields=list(field["properties"].values()), parent=origin_name, using_source=using_source
            )
    return print_list


def get_underscore_viewset_name(viewset):
    return camel_to_underscore(viewset.__name__.replace("ViewSet", ""))


def _format_serializer_errors_core(errors, fields, params):
    """序列化器错误信息格式化"""
    for key, field_errors in list(errors.items()):
        label, sub_message = key, ""

        if key not in fields:
            sub_message = json.dumps(field_errors)
        else:
            field = fields[key]
            label = field.field_name
            if isinstance(field_errors, dict):
                if hasattr(field, "child"):
                    sub_format = _format_serializer_errors_core(field_errors, field.child.fields, params)
                else:
                    sub_format = _format_serializer_errors_core(field_errors, field.fields, params)
                sub_message += sub_format
            elif isinstance(field_errors, list):
                for error in field_errors:
                    # 若错误信息中有%s可将错误值加入其中
                    sub_message = error.format(**{key: params.get(key, "")})

        message = "({}) {}".format(label, sub_message)
        return message
    return ""


def format_serializer_errors(serializer):
    try:
        message = _format_serializer_errors_core(serializer.errors, serializer.fields, serializer.get_initial())
    except Exception as e:
        logger.warning("序列化器错误信息格式化失败，原因: {}".format(e))
        return serializer.errors
    else:
        return message
