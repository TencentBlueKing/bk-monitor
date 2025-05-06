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
import datetime
from unittest.mock import patch

from django.test import TestCase

from apps.log_clustering.models import ClusteringConfig
from apps.log_search.models import LogIndexSet, LogIndexSetData
from apps.log_unifyquery.handler.base import UnifyQueryHandler

INDEX_SET_IDS = [1]
SCENARIO_ID = "bkdata"
USING_CLUSTERING_PROXY = True
INDICES = "2_bklog_1_clustered"

CREATE_CLUSTERING_CONFIG_PARAMS = {
    'id': 1,
    'created_at': datetime.datetime(2024, 5, 13, 7, 15, 18, 886508, tzinfo=datetime.timezone.utc),
    'created_by': 'admin',
    'updated_at': datetime.datetime(2024, 9, 10, 8, 18, 42, 310037, tzinfo=datetime.timezone.utc),
    'updated_by': 'admin',
    'is_deleted': False,
    'deleted_at': None,
    'deleted_by': None,
    'group_fields': [],
    'collector_config_id': 202,
    'collector_config_name_en': 'demodemo102300001',
    'index_set_id': 1,
    'sample_set_id': None,
    'model_id': 'datamodeling_model_2cd50d5c',
    'min_members': 1,
    'max_dist_list': '0.1,0.3,0.5,0.7,0.9',
    'predefined_varibles': '',
    'delimeter': '',
    'max_log_length': 1000,
    'is_case_sensitive': 0,
    'depth': 5,
    'max_child': 100,
    'clustering_fields': 'log',
    'filter_rules': [],
    'bk_biz_id': 2,
    'related_space_pre_bk_biz_id': 2,
    'pre_treat_flow': None,
    'new_cls_pattern_rt': '',
    'new_cls_index_set_id': None,
    'bkdata_data_id': 1573533,
    'bkdata_etl_result_table_id': '2_demodemo102300001',
    'bkdata_etl_processing_id': '2_demodemo102300001',
    'log_bk_data_id': None,
    'signature_enable': True,
    'pre_treat_flow_id': None,
    'after_treat_flow': None,
    'after_treat_flow_id': None,
    'source_rt_name': '2_bklog.demodemo102300001',
    'category_id': 'kubernetes',
    'python_backend': None,
    'es_storage': 'es-default',
    'modify_flow': None,
    'options': None,
    'task_records': [{'time': 1715765644, 'operate': 'create', 'task_id': 'b8bd2553228736218ed87c02de649948'}],
    'task_details': {},
    'model_output_rt': '2_bklog_1_clustering_output',
    'clustered_rt': '2_bklog_1_clustered',
    'signature_pattern_rt': '',
    'predict_flow': {
        'es': {
            'expires': '1',
            'has_replica': '"false"',
            'json_fields': '[]',
            'analyzed_fields': '["log"]',
            'doc_values_fields': '',
        },
        'bk_biz_id': 2,
        'es_cluster': 'es-default',
        'is_flink_env': True,
        'result_table_id': '2_demodemo102300001',
        'format_signature': {
            'fields': '',
            'groups': '',
            'table_name': 'bklog_1_clustered',
            'filter_rule': '',
            'result_table_id': '2_bklog_1_clustered',
        },
        'table_name_no_id': 'demodemo102300001',
        'clustering_predict': {
            'model_id': 'datamodeling_model_2cd50d5c',
            'table_name': 'bklog_1_clustering_output',
            'input_fields': '',
            'output_fields': '',
            'result_table_id': '2_bklog_1_clustering_output',
            'model_release_id': 101,
            'clustering_training_params': {
                'depth': 5,
                'st_list': '0.9,0.8875,0.875,0.8625,0.85',
                'delimeter': '',
                'max_child': 100,
                'min_members': 1,
                'max_dist_list': '0.1,0.3,0.5,0.7,0.9',
                'max_log_length': 1000,
                'is_case_sensitive': 0,
                'use_offline_model': 0,
                'predefined_variables': '',
            },
        },
        'clustering_stream_source': {
            'fields': '',
            'groups': '',
            'table_name': 'bklog_1_clustering',
            'filter_rule': 'where `data` is not null and length(`data`) > 1 ',
            'result_table_id': '2_bklog_1_clustering',
        },
    },
    'predict_flow_id': 120,
    'online_task_id': None,
    'log_count_aggregation_flow': None,
    'log_count_aggregation_flow_id': None,
    'new_cls_strategy_enable': False,
    'new_cls_strategy_output': 'test20240725_64172_plan_14',
    'normal_strategy_enable': False,
    'normal_strategy_output': '',
    'access_finished': True,
    'regex_rule_type': 'customize',
    'regex_template_id': 0,
}

KEYWORD_DATA = {
    'addition': [],
    'aggs': {},
    'begin': 0,
    'bk_biz_id': 2,
    'custom_indices': '',
    'default_sort_tag': True,
    'end_time': '2025-04-29 14:24:48.780000',
    'fields_from_es': [
        {
            'es_doc_values': False,
            'field': '__ext',
            'field_alias': '',
            'field_name': '__ext',
            'field_type': 'object',
            'is_display': False,
            'is_editable': True,
            'tag': 'metric',
        },
        {
            'es_doc_values': True,
            'field': 'bk_host_id',
            'field_alias': '',
            'field_name': 'bk_host_id',
            'field_type': 'integer',
            'is_display': False,
            'is_editable': True,
            'tag': 'dimension',
        },
        {
            'es_doc_values': True,
            'field': 'cloudId',
            'field_alias': '',
            'field_name': 'cloudId',
            'field_type': 'integer',
            'is_display': False,
            'is_editable': True,
            'tag': 'dimension',
        },
        {
            'es_doc_values': True,
            'field': 'dtEventTimeStamp',
            'field_alias': '',
            'field_name': 'dtEventTimeStamp',
            'field_type': 'date',
            'is_display': False,
            'is_editable': True,
            'tag': 'timestamp',
        },
        {
            'es_doc_values': True,
            'field': 'gseIndex',
            'field_alias': '',
            'field_name': 'gseIndex',
            'field_type': 'long',
            'is_display': False,
            'is_editable': True,
            'tag': 'dimension',
        },
        {
            'es_doc_values': True,
            'field': 'iterationIndex',
            'field_alias': '',
            'field_name': 'iterationIndex',
            'field_type': 'integer',
            'is_display': False,
            'is_editable': True,
            'tag': 'dimension',
        },
        {
            'es_doc_values': False,
            'field': 'log',
            'field_alias': '',
            'field_name': 'log',
            'field_type': 'text',
            'is_display': False,
            'is_editable': True,
            'tag': 'metric',
        },
        {
            'es_doc_values': True,
            'field': 'path',
            'field_alias': '',
            'field_name': 'path',
            'field_type': 'keyword',
            'is_display': False,
            'is_editable': True,
            'tag': 'dimension',
        },
        {
            'es_doc_values': True,
            'field': 'serverIp',
            'field_alias': '',
            'field_name': 'serverIp',
            'field_type': 'keyword',
            'is_display': False,
            'is_editable': True,
            'tag': 'dimension',
        },
        {
            'es_doc_values': True,
            'field': 'time',
            'field_alias': '',
            'field_name': 'time',
            'field_type': 'date',
            'is_display': False,
            'is_editable': True,
            'tag': 'timestamp',
        },
    ],
    'from_favorite_id': 0,
    'include_nested_fields': False,
    'index_set_id': '1',
    'index_set_ids': ['1'],
    'indices': '2_bklog.dataname1',
    'ip_chooser': {},
    'is_desensitize': True,
    'is_return_doc_id': False,
    'is_scroll_search': False,
    'keyword': 'aa__dist_051321',
    'scenario_id': 'log',
    'scroll_id': None,
    'search_mode': 'sql',
    'size': 50,
    'sort_list': [],
    'start_time': '2025-04-29 14:09:48.780000',
    'storage_cluster_id': 6,
    'time_field': 'dtEventTimeStamp',
    'time_field_type': 'date',
    'time_field_unit': 'second',
    'time_range': None,
    'trace_type': None,
    'track_total_hits': False,
}

FIELD_DATA = {
    'addition': [
        {
            'field': '__dist_00',
            'operator': 'contains',
            'value': [
                '11333151',
            ],
        },
    ],
    'aggs': {},
    'begin': 0,
    'bk_biz_id': 2,
    'custom_indices': '',
    'default_sort_tag': True,
    'end_time': '2025-04-29 14:24:48.780000',
    'fields_from_es': [
        {
            'es_doc_values': False,
            'field': '__ext',
            'field_alias': '',
            'field_name': '__ext',
            'field_type': 'object',
            'is_display': False,
            'is_editable': True,
            'tag': 'metric',
        },
        {
            'es_doc_values': True,
            'field': 'bk_host_id',
            'field_alias': '',
            'field_name': 'bk_host_id',
            'field_type': 'integer',
            'is_display': False,
            'is_editable': True,
            'tag': 'dimension',
        },
        {
            'es_doc_values': True,
            'field': 'cloudId',
            'field_alias': '',
            'field_name': 'cloudId',
            'field_type': 'integer',
            'is_display': False,
            'is_editable': True,
            'tag': 'dimension',
        },
        {
            'es_doc_values': True,
            'field': 'dtEventTimeStamp',
            'field_alias': '',
            'field_name': 'dtEventTimeStamp',
            'field_type': 'date',
            'is_display': False,
            'is_editable': True,
            'tag': 'timestamp',
        },
        {
            'es_doc_values': True,
            'field': 'gseIndex',
            'field_alias': '',
            'field_name': 'gseIndex',
            'field_type': 'long',
            'is_display': False,
            'is_editable': True,
            'tag': 'dimension',
        },
        {
            'es_doc_values': True,
            'field': 'iterationIndex',
            'field_alias': '',
            'field_name': 'iterationIndex',
            'field_type': 'integer',
            'is_display': False,
            'is_editable': True,
            'tag': 'dimension',
        },
        {
            'es_doc_values': False,
            'field': 'log',
            'field_alias': '',
            'field_name': 'log',
            'field_type': 'text',
            'is_display': False,
            'is_editable': True,
            'tag': 'metric',
        },
        {
            'es_doc_values': True,
            'field': 'path',
            'field_alias': '',
            'field_name': 'path',
            'field_type': 'keyword',
            'is_display': False,
            'is_editable': True,
            'tag': 'dimension',
        },
        {
            'es_doc_values': True,
            'field': 'serverIp',
            'field_alias': '',
            'field_name': 'serverIp',
            'field_type': 'keyword',
            'is_display': False,
            'is_editable': True,
            'tag': 'dimension',
        },
        {
            'es_doc_values': True,
            'field': 'time',
            'field_alias': '',
            'field_name': 'time',
            'field_type': 'date',
            'is_display': False,
            'is_editable': True,
            'tag': 'timestamp',
        },
    ],
    'from_favorite_id': 0,
    'include_nested_fields': False,
    'index_set_id': '1',
    'index_set_ids': ['1'],
    'indices': '2_bklog.dataname1',
    'ip_chooser': {},
    'is_desensitize': True,
    'is_return_doc_id': False,
    'is_scroll_search': False,
    'keyword': '',
    'scenario_id': 'log',
    'scroll_id': None,
    'search_mode': 'sql',
    'size': 50,
    'sort_list': [],
    'start_time': '2025-04-29 14:09:48.780000',
    'storage_cluster_id': 6,
    'time_field': 'dtEventTimeStamp',
    'time_field_type': 'date',
    'time_field_unit': 'second',
    'time_range': None,
    'trace_type': None,
    'track_total_hits': False,
}

CREATE_SET_DATA_PARAMS = {
    'created_by': 'admin',
    'updated_by': 'admin',
    'is_deleted': False,
    'deleted_at': None,
    'deleted_by': None,
    'index_id': 1,
    'index_set_id': 1,
    'bk_biz_id': 2,
    'result_table_id': '2_bklog.dataname1',
    'result_table_name': None,
    'time_field': 'dtEventTimeStamp',
    'apply_status': 'normal',
}

CREATE_SET_PARAMS = {
    'created_by': 'admin',
    'updated_by': 'admin',
    'is_deleted': False,
    'deleted_at': None,
    'deleted_by': None,
    'index_set_id': 1,
    'index_set_name': '[采集项]采集名1',
    'space_uid': 'bkcc__2',
    'project_id': 0,
    'category_id': 'os',
    'bkdata_project_id': None,
    'collector_config_id': 13,
    'scenario_id': 'log',
    'storage_cluster_id': 6,
    'source_id': None,
    'orders': 0,
    'view_roles': [],
    'pre_check_tag': True,
    'pre_check_msg': None,
    'is_active': True,
    'fields_snapshot': {},
    'is_trace_log': False,
    'source_app_code': 'bk_log_search',
    'time_field': 'dtEventTimeStamp',
    'time_field_type': 'date',
    'time_field_unit': 'millisecond',
    'tag_ids': [],
    'bcs_project_id': '',
    'is_editable': True,
    'target_fields': [],
    'sort_fields': [],
    'result_window': 10000,
    'max_analyzed_offset': 0,
    'max_async_count': 0,
    'support_doris': False,
    'doris_table_id': None,
}


class TestUnifyQueryHandler(TestCase):
    def setUp(self) -> None:
        LogIndexSet.objects.create(**CREATE_SET_PARAMS)
        LogIndexSetData.objects.create(**CREATE_SET_DATA_PARAMS)

    @patch.object(UnifyQueryHandler, "init_base_dict", return_value={})
    def test_init_index_info_list(self, mock_init_base_dict):
        # 查询条件中包含__dist_xx,且无聚类场景
        self.query_handler = UnifyQueryHandler(FIELD_DATA)
        index_info_dict = self.query_handler._init_index_info_list(INDEX_SET_IDS)[0]
        self.assertEqual(index_info_dict["scenario_id"], "log")
        self.assertEqual(index_info_dict.get("using_clustering_proxy", ''), '')
        self.assertEqual(index_info_dict["indices"], "2_bklog.dataname1")

        # 查询条件中keyword字符串包含"__dist_05,且无聚类场景
        self.query_handler = UnifyQueryHandler(KEYWORD_DATA)
        index_info_list = self.query_handler._init_index_info_list(INDEX_SET_IDS)[0]
        self.assertEqual(index_info_list["scenario_id"], "log")
        self.assertEqual(index_info_dict.get("using_clustering_proxy", ''), '')
        self.assertEqual(index_info_dict["indices"], "2_bklog.dataname1")

        # 查询条件中包含__dist_xx,且有聚类场景
        ClusteringConfig.objects.create(**CREATE_CLUSTERING_CONFIG_PARAMS)
        self.query_handler = UnifyQueryHandler(FIELD_DATA)
        index_info_list = self.query_handler._init_index_info_list(INDEX_SET_IDS)[0]
        self.assertEqual(index_info_list["scenario_id"], "bkdata")
        self.assertEqual(index_info_list["using_clustering_proxy"], True)
        self.assertEqual(index_info_list["indices"], "2_bklog_1_clustered")

        # 查询条件中keyword字符串包含"__dist_05,且有聚类场景
        self.query_handler = UnifyQueryHandler(KEYWORD_DATA)
        index_info_list = self.query_handler._init_index_info_list(INDEX_SET_IDS)[0]
        self.assertEqual(index_info_list["scenario_id"], "bkdata")
        self.assertEqual(index_info_list["using_clustering_proxy"], True)
        self.assertEqual(index_info_list["indices"], "2_bklog_1_clustered")
