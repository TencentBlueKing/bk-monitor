"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

import json

from django.test import SimpleTestCase

from apps.log_databus.handlers.etl_storage.bk_log_json import BkLogJsonEtlStorage


class TestBkdataJsonFieldName(SimpleTestCase):
    def test_bkdata_json_field_name_decodes_transfer_quoting(self):
        fields = [
            {
                "field_name": "normal_field",
                "alias_name": "",
                "field_type": "string",
                "option": {"es_type": "keyword"},
            },
            {
                "field_name": json.dumps("a.b.c"),
                "alias_name": "a_b_c",
                "field_type": "string",
                "option": {"es_type": "keyword"},
            },
            {
                "field_name": json.dumps('a"b'),
                "alias_name": "a_quote_b",
                "field_type": "string",
                "option": {"es_type": "keyword"},
            },
            {
                "field_name": json.dumps(r"a\b"),
                "alias_name": "a_backslash_b",
                "field_type": "string",
                "option": {"es_type": "keyword"},
            },
            {
                "field_name": json.dumps("without.alias"),
                "alias_name": "",
                "field_type": "string",
                "option": {"es_type": "keyword"},
            },
            {
                "field_name": '"unterminated',
                "alias_name": "malformed",
                "field_type": "string",
                "option": {"es_type": "keyword"},
            },
            {
                "field_name": r'"invalid\escape"',
                "alias_name": "invalid_escape",
                "field_type": "string",
                "option": {"es_type": "keyword"},
            },
        ]

        fields_config = BkLogJsonEtlStorage().get_bkdata_fields_configs(fields)

        self.assertEqual(
            fields_config[0]["assign"],
            [
                {"key": "normal_field", "assign_to": "normal_field", "type": "string"},
                {"key": "a.b.c", "assign_to": "a_b_c", "type": "string"},
                {"key": 'a"b', "assign_to": "a_quote_b", "type": "string"},
                {"key": r"a\b", "assign_to": "a_backslash_b", "type": "string"},
                {"key": "without.alias", "assign_to": "without.alias", "type": "string"},
                {"key": '"unterminated', "assign_to": "malformed", "type": "string"},
                {"key": r'"invalid\escape"', "assign_to": "invalid_escape", "type": "string"},
            ],
        )
