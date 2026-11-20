# -*- coding: utf-8 -*-
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

from django.test import TestCase
from unittest.mock import patch

from apps.log_search.handlers.search.mapping_handlers import MappingHandlers
from apps.log_search.models import Scenario

INDICES = ""
INDEX_SET_ID = 0
SCENARIO_ID = ""
STORAGE_CLUSTER_ID = 1
TIME_FIELD = ""
START_TIME = ""
END_TIME = ""

BKDATA_ASYNC_FIELDS_LIST = [
    {"field_name": "dtEventTimeStamp", "es_doc_values": True},
    {"field_name": "ip", "es_doc_values": True},
    {"field_name": "gseindex", "es_doc_values": True},
    {"field_name": "_iteration_idx", "es_doc_values": True},
]

BKDATA_CONTAINER_ASYNC_FIELDS_LIST = [
    {"field_name": "dtEventTimeStamp", "es_doc_values": True},
    {"field_name": "container_id", "es_doc_values": True},
    {"field_name": "gseindex", "es_doc_values": True},
    {"field_name": "_iteration_idx", "es_doc_values": True},
]

LOG_ASYNC_FIELDS_LIST = [
    {"field_name": "dtEventTimeStamp", "es_doc_values": True},
    {"field_name": "serverIp", "es_doc_values": True},
    {"field_name": "gseIndex", "es_doc_values": True},
    {"field_name": "iterationIndex", "es_doc_values": True},
]

FAILED_LOG_ASYNC_FIELDS = [
    {"field_name": "dtEventTimeStamp", "es_doc_values": True},
    {"field_name": "serverIp", "es_doc_values": True},
    {"field_name": "gseindex", "es_doc_values": True},
]

CUSTOM_SORT_FIELDS = ["dtEventTimeStamp", "gseindex"]


class TestMappingHandler(TestCase):
    def setUp(self) -> None:
        self.mapping_handlers = MappingHandlers(
            indices=INDICES,
            index_set_id=INDEX_SET_ID,
            scenario_id=SCENARIO_ID,
            storage_cluster_id=STORAGE_CLUSTER_ID,
            time_field=TIME_FIELD,
            start_time=START_TIME,
            end_time=END_TIME,
        )

    def test_generate_async_export_reason(self):
        self.assertEqual(
            "缺少必备字段: dtEventTimeStamp, ip, gseindex, _iteration_idx or dtEventTimeStamp,"
            + " container_id, gseindex, _iteration_idx",
            MappingHandlers._generate_async_export_reason(Scenario.BKDATA, {})["async_export_usable_reason"],
        )
        self.assertEqual(
            "缺少必备字段: dtEventTimeStamp, serverIp, gseIndex, iterationIndex",
            MappingHandlers._generate_async_export_reason(Scenario.LOG, {})["async_export_usable_reason"],
        )

    @patch("apps.feature_toggle.handlers.toggle.FeatureToggleObject.switch", lambda _: True)
    def test_async_export_fields(self):
        self.assertTrue(
            MappingHandlers.async_export_fields(BKDATA_ASYNC_FIELDS_LIST, Scenario.BKDATA, [])["async_export_usable"]
        )
        self.assertTrue(
            MappingHandlers.async_export_fields(BKDATA_CONTAINER_ASYNC_FIELDS_LIST, Scenario.BKDATA, [])[
                "async_export_usable"
            ]
        )
        self.assertTrue(MappingHandlers.async_export_fields(LOG_ASYNC_FIELDS_LIST, Scenario.LOG, [])["async_export_usable"])
        self.assertTrue(MappingHandlers.async_export_fields([], Scenario.ES, [])["async_export_usable"])

        self.assertTrue(
            MappingHandlers.async_export_fields(FAILED_LOG_ASYNC_FIELDS, Scenario.LOG, CUSTOM_SORT_FIELDS)["async_export_usable"]
        )

        self.assertFalse(
            MappingHandlers.async_export_fields(FAILED_LOG_ASYNC_FIELDS, Scenario.LOG, [])["async_export_usable"]
        )


class TestMappingMatchOnlyTextCompat(TestCase):
    def test_operators_and_is_analyzed(self):
        from apps.log_search.constants import OPERATORS, TEXT_FIELD_TYPES
        from apps.log_search.handlers.search.mapping_handlers import MappingHandlers

        self.assertIn("match_only_text", TEXT_FIELD_TYPES)
        self.assertEqual(OPERATORS["match_only_text"], OPERATORS["text"])
        self.assertTrue(MappingHandlers._is_analyzed("match_only_text"))
        self.assertTrue(MappingHandlers._is_analyzed("text"))
        self.assertFalse(MappingHandlers._is_analyzed("keyword"))

    def test_mapping_handlers_extracts_match_only_text(self):
        from apps.log_search.handlers.search.mapping_handlers import MappingHandlers

        properties_dict = {
            "raw_message": {"type": "match_only_text", "latest_field_type": "match_only_text"},
            "status": {"type": "keyword", "latest_field_type": "keyword"},
        }
        fields = MappingHandlers.get_all_index_fields_by_mapping(properties_dict)
        fields_by_name = {item["field_name"]: item for item in fields}
        self.assertEqual(fields_by_name["raw_message"]["field_type"], "match_only_text")
        self.assertTrue(fields_by_name["raw_message"]["is_analyzed"])
        self.assertFalse(fields_by_name["raw_message"]["es_doc_values"])
        self.assertFalse(fields_by_name["status"]["is_analyzed"])
        self.assertTrue(fields_by_name["status"]["es_doc_values"])

        nested_fields = MappingHandlers.get_fields_recursively(
            "nested_info",
            {"type": "nested", "properties": {"sub_message": {"type": "match_only_text"}}},
        )
        self.assertEqual(len(nested_fields), 1)
        self.assertEqual(nested_fields[0]["field_name"], "nested_info.sub_message")
        self.assertEqual(nested_fields[0]["field_type"], "match_only_text")
        self.assertTrue(nested_fields[0]["is_analyzed"])
        self.assertFalse(nested_fields[0]["es_doc_values"])

        handler = MappingHandlers.__new__(MappingHandlers)
        text_fields = handler._get_text_fields(
            [
                {"field_name": "status", "field_type": "keyword"},
                {"field_name": "raw_message", "field_type": "match_only_text"},
            ]
        )
        self.assertEqual(text_fields, ["raw_message"])

