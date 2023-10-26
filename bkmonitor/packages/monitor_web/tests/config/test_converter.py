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


from rest_framework import serializers

from bkmonitor.models import GlobalConfig
from monitor_web.config.converter import convert_field


class TestConverter(object):
    def create_global_config(self, config_key, serializer):
        data_type = serializer.__class__.__name__.replace("Field", "")
        return GlobalConfig(
            key=config_key,
            value=serializer.default,
            description=serializer.label,
            data_type=data_type,
            options=serializer._kwargs,
        )

    def test_integer_field(self):
        config = self.create_global_config(
            "INT_FIELD", serializers.IntegerField(label="异常记录保留天数", default=30, min_value=1, help_text="数值调小会导致历史数据丢失")
        )
        assert convert_field(config) == {
            "formChildProps": {"type": "number", "placeholder": "数值调小会导致历史数据丢失", "min": 1},
            "formItemProps": {
                "property": "INT_FIELD",
                "help_text": "数值调小会导致历史数据丢失",
                "required": True,
                "label": "异常记录保留天数",
            },
            "rules": [{"message": "必填项", "required": True, "trigger": "blur"}],
            "value": 30,
            "key": "INT_FIELD",
            "type": "input",
        }

    def test_char_field(self):
        config = self.create_global_config(
            "CHAR_FIELD", serializers.CharField(label="测试文本类型", default="", allow_blank=True)
        )

        assert convert_field(config) == {
            "formChildProps": {"placeholder": ""},
            "formItemProps": {"property": "CHAR_FIELD", "help_text": "", "required": False, "label": "测试文本类型"},
            "rules": [],
            "value": "",
            "key": "CHAR_FIELD",
            "type": "input",
        }

    def test_boolean_field(self):
        config = self.create_global_config("BOOL_FIELD", serializers.BooleanField(label="全局 Ping 告警开关", default=True))
        assert convert_field(config) == {
            "formChildProps": {
                "placeholder": "",
                "size": "min",
                "theme": "primary",
            },
            "formItemProps": {"property": "BOOL_FIELD", "help_text": "", "required": False, "label": "全局 Ping 告警开关"},
            "rules": [],
            "value": True,
            "key": "BOOL_FIELD",
            "type": "switcher",
        }

    def test_json_field(self):
        config = self.create_global_config("JSON_FIELD", serializers.JSONField(label="JSON字段测试", default={"a": "b"}))
        assert convert_field(config) == {
            "formChildProps": {"type": "textarea", "placeholder": ""},
            "formItemProps": {"property": "JSON_FIELD", "help_text": "", "required": False, "label": "JSON字段测试"},
            "rules": [],
            "value": {"a": "b"},
            "key": "JSON_FIELD",
            "type": "input",
        }

    def test_list_field(self):
        config = self.create_global_config("LIST_FIELD", serializers.ListField(label="列表字段测试", default=["a", "b", "c"]))
        assert convert_field(config) == {
            "formChildProps": {"allowCreate": True, "list": [], "hasDeleteIcon": True, "placeholder": ""},
            "formItemProps": {"property": "LIST_FIELD", "help_text": "", "required": False, "label": "列表字段测试"},
            "rules": [],
            "value": ["a", "b", "c"],
            "key": "LIST_FIELD",
            "type": "tag-input",
        }

    def test_choice_field(self):
        config = self.create_global_config(
            "CHOICE_FIELD",
            serializers.ChoiceField(
                label="测试单选", help_text="测试单选说明", default="sh", choices=(("gz", "广州"), ("sh", "上海"), ("sz", "深圳"))
            ),
        )
        assert convert_field(config) == {
            "formChildProps": {
                "placeholder": "测试单选说明",
                "options": [{"id": "gz", "name": "广州"}, {"id": "sh", "name": "上海"}, {"id": "sz", "name": "深圳"}],
            },
            "formItemProps": {"property": "CHOICE_FIELD", "help_text": "测试单选说明", "required": False, "label": "测试单选"},
            "rules": [],
            "value": "sh",
            "key": "CHOICE_FIELD",
            "type": "radio-group",
        }

    def test_multi_choice_field(self):
        config = self.create_global_config(
            "MULTI_CHOICE_FIELD",
            serializers.MultipleChoiceField(
                label="测试多选",
                help_text="测试多选说明",
                default=["gz", "sz"],
                choices=(("gz", "广州"), ("sh", "上海"), ("sz", "深圳")),
            ),
        )
        assert convert_field(config) == {
            "formChildProps": {
                "placeholder": "测试多选说明",
                "options": [{"id": "gz", "name": "广州"}, {"id": "sh", "name": "上海"}, {"id": "sz", "name": "深圳"}],
            },
            "formItemProps": {
                "property": "MULTI_CHOICE_FIELD",
                "help_text": "测试多选说明",
                "required": False,
                "label": "测试多选",
            },
            "rules": [],
            "value": ["gz", "sz"],
            "key": "MULTI_CHOICE_FIELD",
            "type": "checkbox-group",
        }
