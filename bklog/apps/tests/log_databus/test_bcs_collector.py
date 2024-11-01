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
import copy
import json
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.log_databus.handlers.collector import CollectorHandler
from apps.log_databus.handlers.collector_scenario.base import CollectorScenario
from apps.log_databus.serializers import BCSCollectorSerializer
from apps.utils.drf import custom_params_valid

PATH_STD_PARAMS = {
    "bk_biz_id": 3,
    "project_id": "3e11f4212ca2444d92a869c26fcbd4a9",
    "collector_config_name": "bcs_create1",
    "collector_config_name_en": "bcs_create1",
    "description": "",
    "bcs_cluster_id": "BCS-K8S-15641",
    "add_pod_label": False,
    "config": [
        {
            "namespaces": ["default"],
            "paths": ["/error"],
            "data_encoding": "UTF-8",
            "enable_stdout": True,
            "conditions": {
                "type": "match",
                "separator": "|",
                "match_content": None,
                "separator_filters": [{"op": "=", "word": "error", "logic_op": "and", "fieldindex": "-1"}],
            },
            "label_selector": {},
            "annotation_selector": {},
            "container": {"workload_type": "", "workload_name": "", "container_name": ""},
            "multiline": {"multiline_pattern": "", "multiline_max_lines": 50, "multiline_timeout": 2},
        }
    ],
}
PATH_STD_RESULT = {
    "add_pod_label": False,
    "bcs_cluster_id": "BCS-K8S-15641",
    "bk_biz_id": 3,
    "collector_config_name": "create1",
    "collector_config_name_en": "bcs_create1",
    "container_config": [
        {
            "all_container": True,
            "annotation_selector": {"match_annotations": []},
            "any_namespace": False,
            "bk_data_id": 100,
            "bkdata_data_id": None,
            "container": {"container_name": "", "workload_name": "", "workload_type": ""},
            "data_encoding": "UTF-8",
            "enable_stdout": True,
            "id": 1,
            "label_selector": {"match_expressions": [], "match_labels": []},
            "namespaces": ["default"],
            "params": {
                "conditions": {
                    "match_content": None,
                    "separator": "|",
                    "separator_filters": [{"fieldindex": "-1", "logic_op": "and", "op": "=", "word": "error"}],
                    "type": "match",
                },
                "multiline_max_lines": 50,
                "multiline_pattern": "",
                "multiline_timeout": "2",
                "paths": ["/error"],
            },
            "status": "FAILED",
            "status_detail": "配置下发失败: expected string or " "bytes-like object",
            "stdout_conf": {"bk_data_id": 101, "bkdata_data_id": None},
        }
    ],
    "description": "",
    "environment": "container",
    "extra_labels": [],
    "file_index_set_id": 1,
    "is_file_deleted": False,
    "is_std_deleted": False,
    "rule_file_index_set_id": 1,
    "rule_id": 1,
    "rule_std_index_set_id": 2,
    "std_index_set_id": 2,
}

PATH_PARAMS = {
    "bk_biz_id": 3,
    "project_id": "3e11f4212ca2444d92a869c26fcbd4a9",
    "collector_config_name": "bcs_create1",
    "collector_config_name_en": "bcs_create1",
    "description": "",
    "bcs_cluster_id": "BCS-K8S-15641",
    "add_pod_label": False,
    "config": [
        {
            "namespaces": ["default"],
            "paths": ["/path1"],
            "data_encoding": "UTF-8",
            "enable_stdout": False,
            "conditions": {
                "type": "match",
                "separator": "|",
                "match_content": None,
                "separator_filters": [{"op": "=", "word": "path1", "logic_op": "and", "fieldindex": "-1"}],
            },
            "label_selector": {},
            "annotation_selector": {},
            "container": {"workload_type": "", "workload_name": "", "container_name": ""},
            "multiline": {"multiline_pattern": "", "multiline_max_lines": 50, "multiline_timeout": 2},
        },
        {
            "namespaces": ["default"],
            "paths": ["/path2"],
            "data_encoding": "UTF-8",
            "enable_stdout": False,
            "conditions": {
                "type": "match",
                "separator": "|",
                "match_content": None,
                "separator_filters": [{"op": "=", "word": "path2", "logic_op": "and", "fieldindex": "-1"}],
            },
            "label_selector": {},
            "annotation_selector": {},
            "container": {"workload_type": "", "workload_name": "", "container_name": ""},
            "multiline": {"multiline_pattern": "", "multiline_max_lines": 50, "multiline_timeout": 2},
        },
    ],
}

PATH_RESULT = {
    "add_pod_label": False,
    "bcs_cluster_id": "BCS-K8S-15641",
    "bk_biz_id": 3,
    "collector_config_name": "create1",
    "collector_config_name_en": "bcs_create1",
    "container_config": [
        {
            "all_container": True,
            "annotation_selector": {"match_annotations": []},
            "any_namespace": False,
            "bk_data_id": 100,
            "bkdata_data_id": None,
            "container": {"container_name": "", "workload_name": "", "workload_type": ""},
            "data_encoding": "UTF-8",
            "enable_stdout": False,
            "id": 1,
            "label_selector": {"match_expressions": [], "match_labels": []},
            "namespaces": ["default"],
            "params": {
                "conditions": {
                    "match_content": None,
                    "separator": "|",
                    "separator_filters": [{"fieldindex": "-1", "logic_op": "and", "op": "=", "word": "path1"}],
                    "type": "match",
                },
                "multiline_max_lines": 50,
                "multiline_pattern": "",
                "multiline_timeout": "2",
                "paths": ["/path1"],
            },
            "status": "FAILED",
            "status_detail": "配置下发失败: expected string or " "bytes-like object",
            "stdout_conf": {"bk_data_id": 101, "bkdata_data_id": None},
        },
        {
            "all_container": True,
            "annotation_selector": {"match_annotations": []},
            "any_namespace": False,
            "bk_data_id": 100,
            "bkdata_data_id": None,
            "container": {"container_name": "", "workload_name": "", "workload_type": ""},
            "data_encoding": "UTF-8",
            "enable_stdout": False,
            "id": 5,
            "label_selector": {"match_expressions": [], "match_labels": []},
            "namespaces": ["default"],
            "params": {
                "conditions": {
                    "match_content": None,
                    "separator": "|",
                    "separator_filters": [{"fieldindex": "-1", "logic_op": "and", "op": "=", "word": "path2"}],
                    "type": "match",
                },
                "multiline_max_lines": 50,
                "multiline_pattern": "",
                "multiline_timeout": "2",
                "paths": ["/path2"],
            },
            "status": "FAILED",
            "status_detail": "配置下发失败: expected string or " "bytes-like object",
            "stdout_conf": {"bk_data_id": 101, "bkdata_data_id": None},
        },
    ],
    "description": "",
    "environment": "container",
    "extra_labels": [],
    "file_index_set_id": 1,
    "is_file_deleted": False,
    "is_std_deleted": False,
    "rule_file_index_set_id": 1,
    "rule_id": 1,
    "rule_std_index_set_id": 2,
    "std_index_set_id": 2,
}

STD_PARAMS = {
    "bk_biz_id": 3,
    "project_id": "3e11f4212ca2444d92a869c26fcbd4a9",
    "collector_config_name": "bcs_create1",
    "collector_config_name_en": "bcs_create1",
    "description": "",
    "bcs_cluster_id": "BCS-K8S-15641",
    "add_pod_label": False,
    "config": [
        {
            "namespaces": ["default"],
            "paths": [],
            "data_encoding": "UTF-8",
            "enable_stdout": True,
            "conditions": {"type": "none", "separator": None, "match_content": None},
            "label_selector": {},
            "annotation_selector": {},
            "container": {"workload_type": "", "workload_name": "", "container_name": ""},
            "multiline": {"multiline_pattern": "", "multiline_max_lines": 40, "multiline_timeout": 1},
        },
        {
            "namespaces": ["default"],
            "paths": [],
            "data_encoding": "UTF-8",
            "enable_stdout": True,
            "conditions": {"type": "none", "separator": None, "match_content": None},
            "label_selector": {},
            "container": {"workload_type": "", "workload_name": "", "container_name": ""},
            "multiline": {"multiline_pattern": "", "multiline_max_lines": 50, "multiline_timeout": 2},
        },
    ],
}

STD_RESULT = {
    "add_pod_label": False,
    "bcs_cluster_id": "BCS-K8S-15641",
    "bk_biz_id": 3,
    "collector_config_name": "create1",
    "collector_config_name_en": "bcs_create1",
    "container_config": [
        {
            "all_container": True,
            "annotation_selector": {"match_annotations": []},
            "any_namespace": False,
            "bk_data_id": 100,
            "bkdata_data_id": None,
            "container": {"container_name": "", "workload_name": "", "workload_type": ""},
            "data_encoding": "UTF-8",
            "enable_stdout": True,
            "id": 6,
            "label_selector": {"match_expressions": [], "match_labels": []},
            "namespaces": ["default"],
            "params": {
                "conditions": {"match_content": None, "separator": None, "type": "none"},
                "multiline_max_lines": 40,
                "multiline_pattern": "",
                "multiline_timeout": "1",
                "paths": [],
            },
            "status": "FAILED",
            "status_detail": "配置下发失败: expected string or " "bytes-like object",
            "stdout_conf": {"bk_data_id": 101, "bkdata_data_id": None},
        },
        {
            "all_container": True,
            "annotation_selector": {"match_annotations": []},
            "any_namespace": False,
            "bk_data_id": 100,
            "bkdata_data_id": None,
            "container": {"container_name": "", "workload_name": "", "workload_type": ""},
            "data_encoding": "UTF-8",
            "enable_stdout": True,
            "id": 7,
            "label_selector": {"match_expressions": [], "match_labels": []},
            "namespaces": ["default"],
            "params": {
                "conditions": {"match_content": None, "separator": None, "type": "none"},
                "multiline_max_lines": 50,
                "multiline_pattern": "",
                "multiline_timeout": "2",
                "paths": [],
            },
            "status": "FAILED",
            "status_detail": "配置下发失败: expected string or " "bytes-like object",
            "stdout_conf": {"bk_data_id": 101, "bkdata_data_id": None},
        },
    ],
    "description": "",
    "environment": "container",
    "extra_labels": [],
    "file_index_set_id": 1,
    "is_file_deleted": False,
    "is_std_deleted": False,
    "rule_file_index_set_id": 1,
    "rule_id": 1,
    "rule_std_index_set_id": 2,
    "std_index_set_id": 2,
}

NOT_PATH_STD_PARAMS = {
    "bk_biz_id": 3,
    "project_id": "3e11f4212ca2444d92a869c26fcbd4a9",
    "collector_config_name": "bcs_create1",
    "collector_config_name_en": "bcs_create1",
    "description": "",
    "bcs_cluster_id": "BCS-K8S-15641",
    "add_pod_label": False,
    "config": [
        {
            "namespaces": ["default"],
            "paths": [],
            "data_encoding": "UTF-8",
            "enable_stdout": False,
            "conditions": {"type": "none", "separator": None, "match_content": None},
            "label_selector": {},
            "container": {"workload_type": "", "workload_name": "", "container_name": ""},
            "multiline": {"multiline_pattern": "", "multiline_max_lines": 50, "multiline_timeout": 2},
        }
    ],
}
NOT_PATH_STD_RESULT = {
    "add_pod_label": False,
    "bcs_cluster_id": "BCS-K8S-15641",
    "bk_biz_id": 3,
    "collector_config_name": "create1",
    "collector_config_name_en": "bcs_create1",
    "container_config": [],
    "description": "",
    "environment": "container",
    "extra_labels": [],
    "file_index_set_id": 1,
    "is_file_deleted": False,
    "is_std_deleted": False,
    "rule_file_index_set_id": 1,
    "rule_id": 1,
    "rule_std_index_set_id": 2,
    "std_index_set_id": 2,
}

PARAMS = {
    "bk_biz_id": 3,
    "project_id": "3e11f4212ca2444d92a869c26fcbd4a9",
    "collector_config_name": "bcs_create1",
    "collector_config_name_en": "bcs_create1",
    "description": "",
    "bcs_cluster_id": "BCS-K8S-15641",
    "add_pod_label": False,
    "config": [
        {
            "namespaces": ["default"],
            "paths": ["/var/log/messages"],
            "data_encoding": "UTF-8",
            "enable_stdout": True,
            "conditions": {
                "type": "match",
                "separator": "|",
                "match_content": None,
                "separator_filters": [{"op": "=", "word": "aa", "logic_op": "and", "fieldindex": "-1"}],
            },
            "label_selector": {},
            "annotation_selector": {},
            "container": {"workload_type": "", "workload_name": "", "container_name": ""},
            "multiline": {"multiline_pattern": "", "multiline_max_lines": 50, "multiline_timeout": 2},
        },
        {
            "namespaces": ["default"],
            "paths": [],
            "data_encoding": "UTF-8",
            "enable_stdout": True,
            "conditions": {
                "type": "match",
                "separator": " ",
                "match_content": None,
                "separator_filters": [{"op": "=", "word": "bb", "logic_op": "and", "fieldindex": "1"}],
            },
            "label_selector": {},
            "container": {"workload_type": "", "workload_name": "", "container_name": ""},
            "multiline": {"multiline_pattern": "", "multiline_max_lines": 40, "multiline_timeout": 2},
        },
        {
            "namespaces": ["default"],
            "paths": ["/apps/messages"],
            "data_encoding": "UTF-8",
            "enable_stdout": False,
            "conditions": {
                "type": "match",
                "separator": "|",
                "match_content": None,
                "separator_filters": [{"op": "=", "word": "error", "logic_op": "and", "fieldindex": "-1"}],
            },
            "label_selector": {},
            "annotation_selector": {},
            "container": {"workload_type": "", "workload_name": "", "container_name": ""},
            "multiline": {"multiline_pattern": "", "multiline_max_lines": 30, "multiline_timeout": 2},
        },
    ],
}

MULTIPLE_RESULT = {
    "add_pod_label": False,
    "bcs_cluster_id": "BCS-K8S-15641",
    "bk_biz_id": 3,
    "collector_config_name": "create1",
    "collector_config_name_en": "bcs_create1",
    "container_config": [
        {
            "all_container": True,
            "annotation_selector": {"match_annotations": []},
            "any_namespace": False,
            "bk_data_id": 100,
            "bkdata_data_id": None,
            "container": {"container_name": "", "workload_name": "", "workload_type": ""},
            "data_encoding": "UTF-8",
            "enable_stdout": True,
            "id": 8,
            "label_selector": {"match_expressions": [], "match_labels": []},
            "namespaces": ["default"],
            "params": {
                "conditions": {
                    "match_content": None,
                    "separator": "|",
                    "separator_filters": [{"fieldindex": "-1", "logic_op": "and", "op": "=", "word": "aa"}],
                    "type": "match",
                },
                "multiline_max_lines": 50,
                "multiline_pattern": "",
                "multiline_timeout": "2",
                "paths": ["/var/log/messages"],
            },
            "status": "FAILED",
            "status_detail": "配置下发失败: expected string or " "bytes-like object",
            "stdout_conf": {"bk_data_id": 101, "bkdata_data_id": None},
        },
        {
            "all_container": True,
            "annotation_selector": {"match_annotations": []},
            "any_namespace": False,
            "bk_data_id": 100,
            "bkdata_data_id": None,
            "container": {"container_name": "", "workload_name": "", "workload_type": ""},
            "data_encoding": "UTF-8",
            "enable_stdout": True,
            "id": 11,
            "label_selector": {"match_expressions": [], "match_labels": []},
            "namespaces": ["default"],
            "params": {
                "conditions": {
                    "match_content": None,
                    "separator": " ",
                    "separator_filters": [{"fieldindex": "1", "logic_op": "and", "op": "=", "word": "bb"}],
                    "type": "match",
                },
                "multiline_max_lines": 40,
                "multiline_pattern": "",
                "multiline_timeout": "2",
                "paths": [],
            },
            "status": "FAILED",
            "status_detail": "配置下发失败: expected string or " "bytes-like object",
            "stdout_conf": {"bk_data_id": 101, "bkdata_data_id": None},
        },
        {
            "all_container": True,
            "annotation_selector": {"match_annotations": []},
            "any_namespace": False,
            "bk_data_id": 100,
            "bkdata_data_id": None,
            "container": {"container_name": "", "workload_name": "", "workload_type": ""},
            "data_encoding": "UTF-8",
            "enable_stdout": False,
            "id": 9,
            "label_selector": {"match_expressions": [], "match_labels": []},
            "namespaces": ["default"],
            "params": {
                "conditions": {
                    "match_content": None,
                    "separator": "|",
                    "separator_filters": [{"fieldindex": "-1", "logic_op": "and", "op": "=", "word": "error"}],
                    "type": "match",
                },
                "multiline_max_lines": 30,
                "multiline_pattern": "",
                "multiline_timeout": "2",
                "paths": ["/apps/messages"],
            },
            "status": "FAILED",
            "status_detail": "配置下发失败: expected string or " "bytes-like object",
            "stdout_conf": {"bk_data_id": 101, "bkdata_data_id": None},
        },
    ],
    "description": "",
    "environment": "container",
    "extra_labels": [],
    "file_index_set_id": 1,
    "is_file_deleted": False,
    "is_std_deleted": False,
    "rule_file_index_set_id": 1,
    "rule_id": 1,
    "rule_std_index_set_id": 2,
    "std_index_set_id": 2,
}

RESULT_DICT = {
    "add_pod_label": False,
    "bcs_cluster_id": "BCS-K8S-15641",
    "bk_biz_id": 3,
    "collector_config_name": "create1",
    "collector_config_name_en": "bcs_create1",
    "container_config": [
        {
            "all_container": True,
            "annotation_selector": {"match_annotations": []},
            "any_namespace": False,
            "bk_data_id": 100,
            "bkdata_data_id": None,
            "container": {"container_name": "", "workload_name": "", "workload_type": ""},
            "data_encoding": "UTF-8",
            "enable_stdout": True,
            "id": 1,
            "label_selector": {"match_expressions": [], "match_labels": []},
            "namespaces": ["default"],
            "params": {
                "conditions": {
                    "match_content": None,
                    "separator": "|",
                    "separator_filters": [{"fieldindex": "-1", "logic_op": "and", "op": "=", "word": "aa"}],
                    "type": "match",
                },
                "multiline_max_lines": 50,
                "multiline_pattern": "",
                "multiline_timeout": "2",
                "paths": ["/var/log/messages"],
            },
            "status": "FAILED",
            "status_detail": "配置下发失败: expected string or " "bytes-like object",
            "stdout_conf": {"bk_data_id": 101, "bkdata_data_id": None},
        },
        {
            "all_container": True,
            "annotation_selector": {"match_annotations": []},
            "any_namespace": False,
            "bk_data_id": 100,
            "bkdata_data_id": None,
            "container": {"container_name": "", "workload_name": "", "workload_type": ""},
            "data_encoding": "UTF-8",
            "enable_stdout": True,
            "id": 3,
            "label_selector": {"match_expressions": [], "match_labels": []},
            "namespaces": ["default"],
            "params": {
                "conditions": {
                    "match_content": None,
                    "separator": " ",
                    "separator_filters": [{"fieldindex": "1", "logic_op": "and", "op": "=", "word": "bb"}],
                    "type": "match",
                },
                "multiline_max_lines": 40,
                "multiline_pattern": "",
                "multiline_timeout": "2",
                "paths": [],
            },
            "status": None,
            "status_detail": "",
            "stdout_conf": {"bk_data_id": 101, "bkdata_data_id": None},
        },
        {
            "all_container": True,
            "annotation_selector": {"match_annotations": []},
            "any_namespace": False,
            "bk_data_id": 100,
            "bkdata_data_id": None,
            "container": {"container_name": "", "workload_name": "", "workload_type": ""},
            "data_encoding": "UTF-8",
            "enable_stdout": False,
            "id": 4,
            "label_selector": {"match_expressions": [], "match_labels": []},
            "namespaces": ["default"],
            "params": {
                "conditions": {
                    "match_content": None,
                    "separator": "|",
                    "separator_filters": [{"fieldindex": "-1", "logic_op": "and", "op": "=", "word": "error"}],
                    "type": "match",
                },
                "multiline_max_lines": 30,
                "multiline_pattern": "",
                "multiline_timeout": "2",
                "paths": ["/apps/messages"],
            },
            "status": None,
            "status_detail": "",
            "stdout_conf": {"bk_data_id": 101, "bkdata_data_id": None},
        },
    ],
    "description": "",
    "environment": "container",
    "extra_labels": [],
    "file_index_set_id": 1,
    "is_file_deleted": False,
    "is_std_deleted": False,
    "rule_file_index_set_id": 1,
    "rule_id": 1,
    "rule_std_index_set_id": 2,
    "std_index_set_id": 2,
}

TABLE_ID = "space_240026_bklog.BCS-K8S-15641_bcs_create_path"
OVERRIDE_MIDDLEWARE = "apps.tests.middlewares.OverrideMiddleware"

BK_APP_CODE = "bk_bcs"

ES_CLUSTERS = [
    {
        "cluster_config": {
            "domain_name": "127.0.0.1",
            "port": 9200,
            "extranet_domain_name": "",
            "extranet_port": 0,
            "schema": "http",
            "is_ssl_verify": False,
            "ssl_verification_mode": "none",
            "ssl_insecure_skip_verify": False,
            "ssl_certificate_authorities": "",
            "ssl_certificate": "",
            "ssl_certificate_key": "",
            "raw_ssl_certificate_authorities": "",
            "raw_ssl_certificate": "",
            "raw_ssl_certificate_key": "",
            "cluster_id": 3,
            "cluster_name": "es7_cluster",
            "version": "7.2",
            "custom_option": {
                "bk_biz_id": 3,
                "hot_warm_config": {
                    "is_enabled": False,
                    "hot_attr_name": "",
                    "hot_attr_value": "",
                    "warm_attr_name": "",
                    "warm_attr_value": "",
                },
                "source_type": "other",
                "visible_config": {"visible_type": "all_biz", "visible_bk_biz": [], "bk_biz_labels": {}},
                "setup_config": {
                    "retention_days_max": 3,
                    "retention_days_default": 1,
                    "number_of_replicas_max": 1,
                    "number_of_replicas_default": 0,
                    "es_shards_default": 1,
                    "es_shards_max": 3,
                },
                "admin": ["system"],
                "description": "",
                "enable_archive": False,
                "enable_assessment": True,
            },
            "registered_system": "_default",
            "creator": "system",
            "create_time": 1684943948,
            "last_modify_user": "admin",
            "last_modify_time": 1715674078,
            "is_default_cluster": True,
        },
        "cluster_type": "elasticsearch",
        "auth_info": {"password": "8E6", "username": "elastic"},
    }
]


@patch("apps.log_search.permission.Permission.get_auth_info", return_value={"bk_app_code": BK_APP_CODE})
@patch.multiple(
    "apps.api.TransferApi",
    get_result_table=lambda _: {},
    create_result_table=lambda _: {"table_id": TABLE_ID},
    get_cluster_info=lambda _: ES_CLUSTERS,
    get_data_id=lambda _: None,
)
@override_settings(MIDDLEWARE=(OVERRIDE_MIDDLEWARE,))
class TestBcsCollector(TestCase):
    @patch.multiple(
        "apps.api.TransferApi",
        get_result_table=lambda _: {},
        create_result_table=lambda _: {"table_id": TABLE_ID},
        get_cluster_info=lambda _: ES_CLUSTERS,
        get_data_id=lambda _: None,
    )
    @patch.object(CollectorScenario, "update_or_create_data_id")
    def setUp(self, mock_bk_data_id, *args, **kwargs):
        mock_bk_data_id.side_effect = [100, 101]

        # 调用create_bcs_collector接口,初始化数据
        params = copy.deepcopy(PARAMS)
        data = custom_params_valid(serializer=BCSCollectorSerializer, params=params)
        handler = CollectorHandler()
        result = handler.create_bcs_container_config(data=data, bk_app_code=BK_APP_CODE)
        handler.sync_bcs_container_bkdata_id(result)
        handler.sync_bcs_container_task(result)
        RESULT_DICT.update(
            {
                "file_index_set_id": result["file_index_set_id"],
                "rule_file_index_set_id": result["rule_file_index_set_id"],
                "rule_std_index_set_id": result["rule_std_index_set_id"],
                "rule_id": result["rule_id"],
                "std_index_set_id": result["std_index_set_id"],
            }
        )

    @patch("apps.api.TransferApi.get_result_table", lambda _: {})
    @patch("apps.api.TransferApi.create_result_table", lambda _: {"table_id": "TABLE_ID"})
    def test_bcs_collector(self, *args, **kwargs):
        rule_id = RESULT_DICT["rule_id"]
        update_path = f"/api/v1/databus/collectors/{rule_id}/update_bcs_collector/"
        list_params = {"bk_biz_id": PARAMS["bk_biz_id"], "bcs_cluster_id": PARAMS["bcs_cluster_id"]}
        list_path = f"/api/v1/databus/collectors/list_bcs_collector/"

        # 验证create的结果
        response = self.client.get(path=list_path, data=list_params)
        content = json.loads(response.content)
        self.assertEqual(content["data"][0], RESULT_DICT)

        # update-> path+std
        self.client.post(path=update_path, data=json.dumps(PATH_STD_PARAMS), content_type="application/json")
        response = self.client.get(path=list_path, data=list_params)
        content = json.loads(response.content)
        self.assertEqual(content["data"][0], PATH_STD_RESULT)

        # update-> 多条path
        self.client.post(path=update_path, data=json.dumps(PATH_PARAMS), content_type="application/json")
        response = self.client.get(path=list_path, data=list_params)
        content = json.loads(response.content)
        self.assertEqual(content["data"][0], PATH_RESULT)

        # update-> 多条std
        self.client.post(path=update_path, data=json.dumps(STD_PARAMS), content_type="application/json")
        response = self.client.get(path=list_path, data=list_params)
        content = json.loads(response.content)
        self.assertEqual(content["data"][0], STD_RESULT)

        # update-> path和std都不存在的情况
        self.client.post(path=update_path, data=json.dumps(NOT_PATH_STD_PARAMS), content_type="application/json")
        response = self.client.get(path=list_path, data=list_params)
        content = json.loads(response.content)
        self.assertEqual(content["data"][0], NOT_PATH_STD_RESULT)

        # update-> path+std, path, std
        self.client.post(path=update_path, data=json.dumps(PARAMS), content_type="application/json")
        response = self.client.get(path=list_path, data=list_params)
        content = json.loads(response.content)
        self.assertEqual(content["data"][0], MULTIPLE_RESULT)

    @patch("apps.api.TransferApi.modify_data_id", lambda _: _)
    def test_delete_bcs_collector(self, *args, **kwargs):
        rule_id = RESULT_DICT["rule_id"]
        path = f"/api/v1/databus/collectors/{rule_id}/delete_bcs_collector/"
        response = self.client.delete(path=path)
        content = json.loads(response.content)
        self.assertEqual(content["result"], True)
