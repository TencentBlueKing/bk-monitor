"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
"""

import copy
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings

from apps.log_search.models import LogIndexSet, LogIndexSetData
from apps.log_search.permission import Permission
from apps.log_unifyquery.handler.base import UnifyQueryHandler

INDEX_SET_IDS = [1]

# 白名单内应用
WHITELISTED_APP = "bk_log_search"
# 白名单外第三方应用
NON_WHITELIST_APP = "third_party_app"

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

SEARCH_PARAMS = {
    "addition": [],
    "aggs": {},
    "begin": 0,
    "bk_biz_id": 2,
    "custom_indices": "",
    "end_time": "2025-04-29 14:24:48.780000",
    "index_set_ids": ["1"],
    "is_desensitize": True,
    "keyword": "aa__dist_051321",
    "scenario_id": "log",
    "search_mode": "sql",
    "size": 50,
    "sort_list": [],
    "start_time": "2025-04-29 14:09:48.780000",
    "time_field": "dtEventTimeStamp",
    "time_field_type": "date",
    "time_field_unit": "second",
    "track_total_hits": False,
}


class TestUnifyQueryHandlerDesensitize(TestCase):
    """校验 UnifyQueryHandler 的脱敏初始化逻辑, 尤其是 original_search 的短路语义."""

    def setUp(self):
        LogIndexSet.objects.create(**CREATE_SET_PARAMS)
        LogIndexSetData.objects.create(**CREATE_SET_DATA_PARAMS)

    @override_settings(ESQUERY_WHITE_LIST=[WHITELISTED_APP])
    @patch.object(UnifyQueryHandler, "init_base_dict", return_value={})
    def test_original_search_short_circuit_for_non_whitelist_caller(self, mock_init_base_dict):
        """原始日志查询(original_search=True)时, 即使调用方不在白名单也应强制不脱敏."""
        search_params = copy.deepcopy(SEARCH_PARAMS)
        search_params["original_search"] = True
        search_params["is_desensitize"] = False

        with (
            patch("apps.log_unifyquery.handler.base.get_request", return_value=Mock()),
            patch.object(Permission, "get_auth_info", return_value={"bk_app_code": NON_WHITELIST_APP}),
        ):
            handler = UnifyQueryHandler(search_params)
            self.assertFalse(handler.is_desensitize)

    @override_settings(ESQUERY_WHITE_LIST=[WHITELISTED_APP])
    @patch.object(UnifyQueryHandler, "init_base_dict", return_value={})
    def test_non_whitelist_caller_without_original_search_is_desensitized(self, mock_init_base_dict):
        """无 original_search 时, 白名单外的调用方仍会被强制脱敏(作为对照, 证明短路逻辑确实改变了结果)."""
        search_params = copy.deepcopy(SEARCH_PARAMS)
        search_params["is_desensitize"] = False

        with (
            patch("apps.log_unifyquery.handler.base.get_request", return_value=Mock()),
            patch.object(Permission, "get_auth_info", return_value={"bk_app_code": NON_WHITELIST_APP}),
            patch("apps.log_unifyquery.handler.base.FeatureToggleObject.toggle", return_value=None),
            patch("apps.log_unifyquery.handler.base.get_request_username", return_value="someone"),
        ):
            handler = UnifyQueryHandler(search_params)
            self.assertTrue(handler.is_desensitize)
