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

import datetime
from unittest.mock import patch

from django.test import TestCase

from apps.log_clustering.models import ClusteringConfig
from apps.log_esquery.serializers import EsQuerySearchAttrSerializer
from apps.log_search.models import LogIndexSet, LogIndexSetData

INDEX_INFO = {
    "indices": "2_bklog_1_clustered",
    "scenario_id": "bkdata",
    "storage_cluster_id": 6,
    "time_field": "dtEventTimeStamp",
}

ESQUERY_PARAMS = {
    "aggs": {},
    "collapse": None,
    "end_time": "2025-04-29 14:24:48.780000",
    "filter": [],
    "highlight": {
        "fields": {"*": {"number_of_fragments": 0}},
        "post_tags": ["</mark>"],
        "pre_tags": ["<mark>"],
        "require_field_match": False,
    },
    "include_nested_fields": False,
    "indices": "2_bklog.dataname1",
    "query_string": "aa__dist_051321",
    "scenario_id": "log",
    "scroll": None,
    "size": 50,
    "sort_list": [["dtEventTimeStamp", "desc"], ["gseIndex", "desc"], ["iterationIndex", "desc"]],
    "start": 0,
    "start_time": "2025-04-29 14:09:48.780000",
    "storage_cluster_id": 6,
    "time_field": "dtEventTimeStamp",
    "time_field_type": "date",
    "time_field_unit": "second",
    "time_range": None,
    "time_zone": "Asia/Shanghai",
    "track_total_hits": False,
    "use_time_range": True,
}
ATTRS_PARAMS = {
    "index_set_id": 1,
    "indices": "2_bklog.dataname1",
    "scenario_id": "log",
    "storage_cluster_id": 6,
    "time_field": "dtEventTimeStamp",
    "time_field_type": "date",
    "time_field_unit": "second",
    "use_time_range": True,
    "include_start_time": True,
    "include_end_time": True,
    "start_time": "2025-04-29 14:09:48.780000",
    "end_time": "2025-04-29 14:24:48.780000",
    "time_range": None,
    "time_zone": "Asia/Shanghai",
    "query_string": "aa__dist_051321",
    "filter": [],
    "sort_list": [["dtEventTimeStamp", "desc"], ["gseIndex", "desc"], ["iterationIndex", "desc"]],
    "start": 0,
    "size": 50,
    "dtEventTimeStamp": None,
    "search_type_tag": "search",
    "aggs": {},
    "highlight": {
        "pre_tags": ["<mark>"],
        "post_tags": ["</mark>"],
        "fields": {"*": {"number_of_fragments": 0}},
        "require_field_match": False,
    },
    "collapse": None,
    "search_after": [],
    "track_total_hits": False,
    "scroll": None,
    "include_nested_fields": False,
    "slice_search": False,
    "slice_id": 0,
    "slice_max": 0,
}

INITIAL_DATA = {
    "indices": "2_bklog.dataname1",
    "scenario_id": "log",
    "storage_cluster_id": 6,
    "start_time": "2025-04-29 14:09:48.780000",
    "end_time": "2025-04-29 14:24:48.780000",
    "filter": [],
    "query_string": "aa__dist_051321",
    "sort_list": [["dtEventTimeStamp", "desc"], ["gseIndex", "desc"], ["iterationIndex", "desc"]],
    "start": 0,
    "size": 50,
    "aggs": {},
    "highlight": {
        "pre_tags": ["<mark>"],
        "post_tags": ["</mark>"],
        "fields": {"*": {"number_of_fragments": 0}},
        "require_field_match": False,
    },
    "use_time_range": True,
    "time_zone": "Asia/Shanghai",
    "time_range": None,
    "time_field": "dtEventTimeStamp",
    "time_field_type": "date",
    "time_field_unit": "second",
    "scroll": None,
    "collapse": None,
    "include_nested_fields": False,
    "track_total_hits": False,
}
CREATE_SET_PARAMS = {
    "created_by": "admin",
    "updated_by": "admin",
    "is_deleted": False,
    "deleted_at": None,
    "deleted_by": None,
    "index_set_id": 1,
    "index_set_name": "[采集项]采集名1",
    "space_uid": "bkcc__2",
    "project_id": 0,
    "category_id": "os",
    "bkdata_project_id": None,
    "collector_config_id": 13,
    "scenario_id": "log",
    "storage_cluster_id": 6,
    "source_id": None,
    "orders": 0,
    "view_roles": [],
    "pre_check_tag": True,
    "pre_check_msg": None,
    "is_active": True,
    "fields_snapshot": {},
    "is_trace_log": False,
    "source_app_code": "bk_log_search",
    "time_field": "dtEventTimeStamp",
    "time_field_type": "date",
    "time_field_unit": "millisecond",
    "tag_ids": [],
    "bcs_project_id": "",
    "is_editable": True,
    "target_fields": [],
    "sort_fields": [],
    "result_window": 10000,
    "max_analyzed_offset": 0,
    "max_async_count": 0,
    "support_doris": False,
    "doris_table_id": None,
}
CREATE_SET_DATA_PARAMS = {
    "created_by": "admin",
    "updated_by": "admin",
    "is_deleted": False,
    "deleted_at": None,
    "deleted_by": None,
    "index_id": 1,
    "index_set_id": 1,
    "bk_biz_id": 2,
    "result_table_id": "2_bklog.dataname1",
    "result_table_name": None,
    "time_field": "dtEventTimeStamp",
    "apply_status": "normal",
}
CREATE_CLUSTERING_CONFIG_PARAMS = {
    "id": 1,
    "created_at": datetime.datetime(2024, 5, 13, 7, 15, 18, 886508, tzinfo=datetime.timezone.utc),
    "created_by": "admin",
    "updated_at": datetime.datetime(2024, 9, 10, 8, 18, 42, 310037, tzinfo=datetime.timezone.utc),
    "updated_by": "admin",
    "is_deleted": False,
    "deleted_at": None,
    "deleted_by": None,
    "group_fields": [],
    "collector_config_id": 202,
    "collector_config_name_en": "demodemo102300001",
    "index_set_id": 1,
    "sample_set_id": None,
    "model_id": "datamodeling_model_2cd50d5c",
    "min_members": 1,
    "max_dist_list": "0.1,0.3,0.5,0.7,0.9",
    "predefined_varibles": "",
    "delimeter": "",
    "max_log_length": 1000,
    "is_case_sensitive": 0,
    "depth": 5,
    "max_child": 100,
    "clustering_fields": "log",
    "filter_rules": [],
    "bk_biz_id": 2,
    "related_space_pre_bk_biz_id": 2,
    "pre_treat_flow": None,
    "new_cls_pattern_rt": "",
    "new_cls_index_set_id": None,
    "bkdata_data_id": 1573533,
    "bkdata_etl_result_table_id": "2_demodemo102300001",
    "bkdata_etl_processing_id": "2_demodemo102300001",
    "log_bk_data_id": None,
    "signature_enable": True,
    "pre_treat_flow_id": None,
    "after_treat_flow": None,
    "after_treat_flow_id": None,
    "source_rt_name": "2_bklog.demodemo102300001",
    "category_id": "kubernetes",
    "python_backend": None,
    "es_storage": "es-default",
    "modify_flow": None,
    "options": None,
    "task_records": [{"time": 1715765644, "operate": "create", "task_id": "b8bd2553228736218ed87c02de649948"}],
    "task_details": {},
    "model_output_rt": "2_bklog_1_clustering_output",
    "clustered_rt": "2_bklog_1_clustered",
    "signature_pattern_rt": "",
    "predict_flow": {
        "es": {
            "expires": "1",
            "has_replica": '"false"',
            "json_fields": "[]",
            "analyzed_fields": '["log"]',
            "doc_values_fields": "",
        },
        "bk_biz_id": 2,
        "es_cluster": "es-default",
        "is_flink_env": True,
        "result_table_id": "2_demodemo102300001",
        "format_signature": {
            "fields": "",
            "groups": "",
            "table_name": "bklog_1_clustered",
            "filter_rule": "",
            "result_table_id": "2_bklog_1_clustered",
        },
        "table_name_no_id": "demodemo102300001",
        "clustering_predict": {
            "model_id": "datamodeling_model_2cd50d5c",
            "table_name": "bklog_1_clustering_output",
            "input_fields": "",
            "output_fields": "",
            "result_table_id": "2_bklog_1_clustering_output",
            "model_release_id": 101,
            "clustering_training_params": {
                "depth": 5,
                "st_list": "0.9,0.8875,0.875,0.8625,0.85",
                "delimeter": "",
                "max_child": 100,
                "min_members": 1,
                "max_dist_list": "0.1,0.3,0.5,0.7,0.9",
                "max_log_length": 1000,
                "is_case_sensitive": 0,
                "use_offline_model": 0,
                "predefined_variables": "",
            },
        },
        "clustering_stream_source": {
            "fields": "",
            "groups": "",
            "table_name": "bklog_1_clustering",
            "filter_rule": "where `data` is not null and length(`data`) > 1 ",
            "result_table_id": "2_bklog_1_clustering",
        },
    },
    "predict_flow_id": 120,
    "online_task_id": None,
    "log_count_aggregation_flow": None,
    "log_count_aggregation_flow_id": None,
    "new_cls_strategy_enable": False,
    "new_cls_strategy_output": "test20240725_64172_plan_14",
    "normal_strategy_enable": False,
    "normal_strategy_output": "",
    "access_finished": True,
    "regex_rule_type": "customize",
    "regex_template_id": 0,
}
TARGET_ATTRS = {
    "index_set_id": 1,
    "indices": "2_bklog_1_clustered",
    "scenario_id": "bkdata",
    "storage_cluster_id": 6,
    "time_field": "dtEventTimeStamp",
    "time_field_type": "date",
    "time_field_unit": "second",
    "use_time_range": True,
    "include_start_time": True,
    "include_end_time": True,
    "start_time": "2025-04-29 14:09:48.780000",
    "end_time": "2025-04-29 14:24:48.780000",
    "time_range": None,
    "time_zone": "Asia/Shanghai",
    "query_string": "aa__dist_051321",
    "filter": [],
    "sort_list": [["dtEventTimeStamp", "desc"], ["gseIndex", "desc"], ["iterationIndex", "desc"]],
    "start": 0,
    "size": 50,
    "dtEventTimeStamp": None,
    "search_type_tag": "search",
    "aggs": {},
    "highlight": {
        "pre_tags": ["<mark>"],
        "post_tags": ["</mark>"],
        "fields": {"*": {"number_of_fragments": 0}},
        "require_field_match": False,
    },
    "collapse": None,
    "search_after": [],
    "track_total_hits": False,
    "scroll": None,
    "include_nested_fields": False,
    "slice_search": False,
    "slice_id": 0,
    "slice_max": 0,
}


class TestEsQuerySearchAttrSerializer(TestCase):
    @patch(
        "apps.log_esquery.serializers._get_index_info",
        lambda index_set_id, is_clustered_fields: INDEX_INFO,
    )
    def test_validate(self):
        LogIndexSet.objects.create(**CREATE_SET_PARAMS)
        LogIndexSetData.objects.create(**CREATE_SET_DATA_PARAMS)
        ClusteringConfig.objects.create(**CREATE_CLUSTERING_CONFIG_PARAMS)

        self._serializer = EsQuerySearchAttrSerializer(ESQUERY_PARAMS)
        self._serializer.initial_data = INITIAL_DATA
        attrs = self._serializer.validate(ATTRS_PARAMS)
        self.assertEqual(attrs, TARGET_ATTRS)
