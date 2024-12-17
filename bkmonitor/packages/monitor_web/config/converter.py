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


import abc
import logging

import six
from django.utils.translation import gettext as _
from rest_framework import serializers

logger = logging.getLogger(__name__)


def convert_field(config):
    """
    :param bkmonitor.models.GlobalConfig config: 全局配置对象
    """
    try:
        serializer = config.get_serializer()
    except Exception as e:
        serializer = serializers.CharField()
        logger.exception("全局配置 [{}] 加载异常: {}".format(config.key, e))

    converter_cls = globals().get("{}FieldConverter".format(config.data_type), CharFieldConverter)
    converter = converter_cls(config, serializer)
    return converter.convert()


class BaseFieldConverter(six.with_metaclass(abc.ABCMeta, object)):
    """
    将后台的全局配置转换为前端全局配置格式
    """

    FRONTEND_FORM_TYPE = ""

    def __init__(self, config, serializer):
        self.config = config
        self.serializer = serializer

    def get_form_item_props(self):
        return {
            "label": _(self.serializer.label or self.config.description)
            if self.serializer.label or self.config.description
            else "",
            "required": self.serializer.required,
            "property": self.config.key,
            "help_text": _(self.serializer.help_text) if self.serializer.help_text else "",
        }

    def get_form_child_props(self):
        return {
            "placeholder": _(self.serializer.help_text) if self.serializer.help_text else "",
        }

    def get_rules(self):
        rules = []
        if self.get_form_item_props().get("required"):
            rules.append(
                {
                    "required": True,
                    "message": _("必填项"),
                    "trigger": "blur",
                }
            )
        return rules

    def convert(self):
        return {
            "formItemProps": self.get_form_item_props(),
            "type": self.FRONTEND_FORM_TYPE,
            "key": self.config.key,
            "value": self.config.value,
            "formChildProps": self.get_form_child_props(),
            "rules": self.get_rules(),
        }


class IntegerFieldConverter(BaseFieldConverter):
    FRONTEND_FORM_TYPE = "input"

    # def get_rules(self):
    #     rules = super(IntegerFieldConverter, self).get_rules()
    #     rules.append()

    def get_form_child_props(self):
        form_child_props = super(IntegerFieldConverter, self).get_form_child_props()
        form_child_props["type"] = "number"
        if self.serializer.min_value is not None:
            form_child_props["min"] = self.serializer.min_value
        if self.serializer.max_value is not None:
            form_child_props["max"] = self.serializer.max_value
        return form_child_props

    def get_form_item_props(self):
        form_item_props = super(IntegerFieldConverter, self).get_form_item_props()
        form_item_props["required"] = True
        return form_item_props


class CharFieldConverter(BaseFieldConverter):
    FRONTEND_FORM_TYPE = "input"


class BooleanFieldConverter(BaseFieldConverter):
    FRONTEND_FORM_TYPE = "switcher"

    def get_form_child_props(self):
        form_child_props = super(BooleanFieldConverter, self).get_form_child_props()
        form_child_props["size"] = "min"
        form_child_props["theme"] = "primary"
        return form_child_props


class JSONFieldConverter(BaseFieldConverter):
    FRONTEND_FORM_TYPE = "input"

    def get_form_child_props(self):
        form_child_props = super(JSONFieldConverter, self).get_form_child_props()
        form_child_props["type"] = "textarea"
        return form_child_props


class ListFieldConverter(BaseFieldConverter):
    FRONTEND_FORM_TYPE = "tag-input"

    def get_form_child_props(self):
        form_child_props = super(ListFieldConverter, self).get_form_child_props()
        form_child_props["allowCreate"] = True
        form_child_props["hasDeleteIcon"] = True
        form_child_props["list"] = []
        return form_child_props


class ChoiceFieldConverter(BaseFieldConverter):
    FRONTEND_FORM_TYPE = "radio-group"

    def get_form_child_props(self):
        form_child_props = super(ChoiceFieldConverter, self).get_form_child_props()
        form_child_props["options"] = [
            {
                "id": choice[0],
                "name": choice[1],
            }
            for choice in list(self.serializer.choices.items())
        ]
        return form_child_props


class MultipleChoiceFieldConverter(BaseFieldConverter):
    FRONTEND_FORM_TYPE = "checkbox-group"

    def get_form_child_props(self):
        form_child_props = super(MultipleChoiceFieldConverter, self).get_form_child_props()
        form_child_props["options"] = [
            {
                "id": choice[0],
                "name": choice[1],
            }
            for choice in list(self.serializer.choices.items())
        ]
        return form_child_props
