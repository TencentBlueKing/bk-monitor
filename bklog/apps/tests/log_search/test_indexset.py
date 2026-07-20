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
from unittest.mock import MagicMock, patch

import arrow
from blueapps.account.models import User
from django.conf import settings
from django.test import TestCase, override_settings

from apps.log_databus.constants import DORIS_CLUSTER_TYPE, STORAGE_CLUSTER_TYPE
from apps.log_databus.models import CollectorConfig, DataLinkConfig
from apps.log_search.handlers.index_set import BaseIndexSetHandler
from apps.log_search.models import IndexSetTag, LogIndexSet, LogIndexSetData, Scenario, TAG_TYPE_INNER
from apps.tests.utils import FakeRedis
from bkm_space.define import Space

BK_BIZ_ID = 1
SPACE_UID = "bkcc__2"
STORAGE_CLUSTER_ID = 1
SUCCESS_STATUS_CODE = 200
SOURCE_APP_CODE = "log-search-4"
SCENARIO_ID_ES = "es"
SCENARIO_ID_BKDATA = "bkdata"

OVERRIDE_MIDDLEWARE = "apps.tests.middlewares.OverrideMiddleware"

CLUSTER_INFO = [
    {
        "cluster_config": {
            "cluster_id": 1,
            "cluster_name": "",
            "display_name": "",
            "port": 123,
            "domain_name": "",
            "version": "7.x",
        }
    }
]
CLUSTER_INFO_WITH_AUTH = [
    {
        "cluster_config": {"cluster_id": 1, "cluster_name": "", "display_name": "", "version": "7.x"},
        "auth_info": {"username": "", "password": ""},
        "cluster_type": "elasticsearch",
    }
]
CLUSTER_INFOS = {"2_bklog.test3333": {"cluster_config": {"cluster_id": 1, "cluster_name": ""}}}

MAPPING_LIST = [
    {"properties": {"date": {"type": "timestamp"}, "log": {"type": "string"}, "server_id": {"type": "long"}}}
]

QUERY_ALIAS_SETTINGS = {
    "alias_settings": [
        {
            "field_name": "a",
            "query_alias": "a_alias",
            "path_type": "string",
        }
    ]
}

ALIAS_SETTINGS_RESULT = {"result": True, "data": {"index_set_id": "1"}, "code": 0, "message": ""}

CREATE_SUCCESS = {
    "result": True,
    "data": {
        "bcs_project_id": "",
        "index_set_id": 5,
        "view_roles": [],
        "bkdata_project_id": None,
        "indexes": [],
        "is_trace_log": False,
        "time_field": "abc",
        "time_field_type": "date",
        "time_field_unit": "millisecond",
        "index_set_name": "登陆日志",
        "storage_cluster_id": 1,
        "category_id": "other_rt",
        "scenario_id": "es",
        "project_id": 0,
        "query_alias_settings": None,
        "space_uid": "bkcc__2",
        "bkdata_auth_url": "",
        "created_at": "2021-06-26 16:06:18+0800",
        "created_by": "admin",
        "updated_at": "2021-06-26 16:06:18+0800",
        "updated_by": "admin",
        "is_deleted": False,
        "deleted_at": None,
        "deleted_by": None,
        "collector_config_id": None,
        "source_id": None,
        "orders": 0,
        "pre_check_tag": True,
        "pre_check_msg": None,
        "is_active": True,
        "fields_snapshot": None,
        "source_app_code": settings.APP_CODE,
        "tag_ids": [],
        "is_editable": True,
        "is_group": False,
        "parent_index_set_ids": None,
        "parent_index_set_names": None,
        "sort_fields": [],
        "target_fields": [],
        "result_window": 10000,
        "max_analyzed_offset": 0,
        "max_async_count": 0,
        "doris_table_id": None,
        "support_doris": False,
        "is_platform_index": False,
        "platform_index_filter": None,
        "platform_index_visibility": None,
    },
    "code": 0,
    "message": "",
}

DELETE_SUCCESS = {"message": "", "code": 0, "data": None, "result": True}

UPDATE_INDEX_SET = {
    "bcs_project_id": "",
    "index_set_id": 102,
    "view_roles": [],
    "bkdata_project_id": None,
    "indexes": [
        {
            "index_id": 204,
            "index_set_id": 102,
            "bk_biz_id": None,
            "source_id": None,
            "source_name": "--",
            "result_table_id": "log_xxx",
            "scenario_id": "es",
            "storage_cluster_id": 3,
            "time_field": "timestamp",
            "result_table_name": None,
            "apply_status": "normal",
            "apply_status_name": "正常",
        },
        {
            "index_id": 203,
            "index_set_id": 102,
            "bk_biz_id": 1,
            "source_id": None,
            "source_name": "--",
            "result_table_id": "591_xx",
            "scenario_id": "log",
            "storage_cluster_id": 6,
            "time_field": "timestamp",
            "result_table_name": None,
            "apply_status": "normal",
            "apply_status_name": "正常",
        },
    ],
    "is_trace_log": False,
    "time_field": "abc",
    "time_field_type": "date",
    "time_field_unit": "millisecond",
    "created_at": "2021-06-26 16:19:32+0800",
    "created_by": "admin",
    "updated_at": "2021-06-26 16:19:32+0800",
    "updated_by": "admin",
    "is_deleted": False,
    "deleted_at": None,
    "deleted_by": None,
    "index_set_name": "登陆日志",
    "project_id": 0,
    "query_alias_settings": None,
    "space_uid": "bkcc__2",
    "category_id": "host",
    "collector_config_id": None,
    "scenario_id": "es",
    "storage_cluster_id": 1,
    "source_id": None,
    "orders": 0,
    "pre_check_tag": True,
    "pre_check_msg": None,
    "is_active": True,
    "fields_snapshot": "{}",
    "source_app_code": settings.APP_CODE,
    "tag_ids": [],
    "is_editable": True,
    "is_group": False,
    "sort_fields": [],
    "target_fields": [],
    "result_window": 10000,
    "max_analyzed_offset": 0,
    "max_async_count": 0,
    "doris_table_id": None,
    "support_doris": False,
    "is_platform_index": False,
    "platform_index_filter": None,
    "platform_index_visibility": None,
}

NOT_EDITABLE_RETURN = {
    "result": False,
    "code": "3600001",
    "data": None,
    "message": "索引集登陆日志禁止编辑（3600001）",
    "errors": None,
}

INDEX_SET_LISTS = {
    "total": 1,
    "list": [
        {
            "index_set_id": 31,
            "view_roles": [],
            "bkdata_project_id": None,
            "bcs_project_id": "",
            "indexes": [
                {
                    "index_id": 62,
                    "index_set_id": 31,
                    "bk_biz_id": None,
                    "source_id": None,
                    "source_name": "--",
                    "result_table_id": "log_xxx",
                    "scenario_id": "es",
                    "storage_cluster_id": 3,
                    "time_field": "timestamp",
                    "result_table_name": None,
                    "apply_status": "normal",
                    "apply_status_name": "正常",
                },
                {
                    "index_id": 61,
                    "index_set_id": 31,
                    "bk_biz_id": 1,
                    "source_id": None,
                    "source_name": "--",
                    "result_table_id": "591_xx",
                    "scenario_id": "log",
                    "storage_cluster_id": 6,
                    "time_field": "timestamp",
                    "result_table_name": None,
                    "apply_status": "normal",
                    "apply_status_name": "正常",
                },
            ],
            "is_trace_log": False,
            "time_field": "abc",
            "time_field_type": "date",
            "time_field_unit": "millisecond",
            "created_at": "2021-06-26 16:11:58+0800",
            "created_by": "admin",
            "updated_at": "2021-06-26 16:11:58+0800",
            "updated_by": "admin",
            "is_deleted": False,
            "deleted_at": None,
            "deleted_by": None,
            "index_set_name": "登陆日志",
            "project_id": 0,
            "query_alias_settings": None,
            "space_uid": "bkcc__2",
            "category_id": "other_rt",
            "collector_config_id": None,
            "scenario_id": "es",
            "storage_cluster_id": 1,
            "source_id": None,
            "orders": 0,
            "pre_check_tag": True,
            "pre_check_msg": None,
            "is_active": True,
            "fields_snapshot": "{}",
            "source_app_code": settings.APP_CODE,
            "tags": [],
            "category_name": "其他",
            "scenario_name": "第三方ES",
            "storage_cluster_name": "",
            "apply_status": "normal",
            "apply_status_name": "正常",
            "bk_biz_id": 2,
            "permission": {},
            "is_editable": True,
            "is_group": False,
            "sort_fields": [],
            "target_fields": [],
            "result_window": 10000,
            "storage_cluster_domain_name": "",
            "storage_cluster_port": 123,
            "max_analyzed_offset": 0,
            "max_async_count": 0,
            "doris_table_id": None,
            "support_doris": False,
            "is_platform_index": False,
            "platform_index_filter": None,
            "platform_index_visibility": None,
        }
    ],
}

TOKEN_PERMISSIONS = {
    "permissions": [
        {
            "status": "active",
            "data_token_id": 592,
            "scope_id_key": "result_table_id",
            "updated_by": "admin",
            "created_at": "2020-04-26 17:35:50",
            "description": None,
            "scope_name_key": "result_table_name",
            "updated_at": "2020-04-26 17:35:50",
            "created_by": "admin",
            "scope_display": {"result_table_name": "2_test_table_1"},
            "scope": {
                "result_table_name": "2_test_table_1",
                "result_table_id": "2_test_table_1",
                "description": "测试表1",
            },
            "object_class": "result_table",
            "id": 4297,
            "scope_object_class": "result_table",
            "action_id": "result_table.query_data",
        }
    ]
}

SYSC_AUTH_STATUS_RESULT = [
    {
        "index_id": 154,
        "index_set_id": 135,
        "bk_biz_id": None,
        "source_id": None,
        "source_name": "--",
        "result_table_id": "log_xxx",
        "scenario_id": "es",
        "storage_cluster_id": 6,
        "time_field": "timestamp",
        "result_table_name": None,
        "apply_status": "normal",
        "apply_status_name": "正常",
    },
    {
        "index_id": 153,
        "index_set_id": 135,
        "bk_biz_id": 1,
        "source_id": None,
        "source_name": "--",
        "result_table_id": "591_xx",
        "scenario_id": "log",
        "storage_cluster_id": 6,
        "time_field": "timestamp",
        "result_table_name": None,
        "apply_status": "normal",
        "apply_status_name": "正常",
    },
]

RETRIEVE_LIST = {
    "bcs_project_id": "",
    "index_set_id": 63,
    "view_roles": [],
    "bkdata_project_id": None,
    "bk_biz_id": 2,
    "apply_status": "normal",
    "apply_status_name": "正常",
    "storage_cluster_name": "",
    "tags": [],
    "storage_cluster_domain_name": "",
    "storage_cluster_port": 123,
    "scenario_name": "第三方ES",
    "category_name": "其他",
    "indexes": [
        {
            "index_id": 126,
            "index_set_id": 63,
            "bk_biz_id": None,
            "source_id": None,
            "source_name": "--",
            "result_table_id": "log_xxx",
            "scenario_id": "es",
            "storage_cluster_id": 3,
            "time_field": "timestamp",
            "result_table_name": None,
            "apply_status": "normal",
            "apply_status_name": "正常",
        },
        {
            "index_id": 125,
            "index_set_id": 63,
            "bk_biz_id": 1,
            "source_id": None,
            "source_name": "--",
            "result_table_id": "591_xx",
            "scenario_id": "log",
            "storage_cluster_id": 6,
            "time_field": "timestamp",
            "result_table_name": None,
            "apply_status": "normal",
            "apply_status_name": "正常",
        },
    ],
    "is_trace_log": False,
    "time_field": "abc",
    "time_field_type": "date",
    "time_field_unit": "millisecond",
    "source_name": "--",
    "created_at": "2021-06-26 16:15:41+0800",
    "created_by": "admin",
    "updated_at": "2021-06-26 16:15:41+0800",
    "updated_by": "admin",
    "is_deleted": False,
    "deleted_at": None,
    "deleted_by": None,
    "index_set_name": "登陆日志",
    "project_id": 0,
    "query_alias_settings": None,
    "space_uid": "bkcc__2",
    "category_id": "other_rt",
    "collector_config_id": None,
    "scenario_id": "es",
    "storage_cluster_id": 1,
    "source_id": None,
    "orders": 0,
    "parent_index_set_ids": [],
    "pre_check_tag": True,
    "pre_check_msg": None,
    "is_active": True,
    "fields_snapshot": "{}",
    "source_app_code": settings.APP_CODE,
    "is_editable": True,
    "is_group": False,
    "sort_fields": [],
    "target_fields": [],
    "result_window": 10000,
    "max_analyzed_offset": 0,
    "max_async_count": 0,
    "doris_table_id": None,
    "support_doris": False,
    "is_platform_index": False,
    "platform_index_filter": None,
    "platform_index_visibility": None,
}
MULTI_RESULT = {}
FIELDS_LIST = [
    {
        "field_type": "keyword",
        "field_name": "a",
        "field_alias": "",
        "is_display": False,
        "is_editable": True,
        "tag": "dimension",
        "origin_field": "",
        "es_doc_values": True,
        "is_analyzed": False,
        "field_operator": [
            {"operator": "=", "label": "=", "placeholder": "请选择或直接输入，Enter分隔", "wildcard_operator": "=~"},
        ],
        "is_built_in": False,
        "is_case_sensitive": False,
        "tokenize_on_chars": "",
        "description": "",
    }
]


class Dummy(dict):
    def __getitem__(self, item):
        return {}


@patch("apps.iam.handlers.drf.BusinessActionPermission.has_permission", return_value=True)
@patch("apps.log_search.tasks.mapping.sync_single_index_set_mapping_snapshot.delay", return_value=None)
@patch("apps.log_databus.tasks.bkdata.async_create_bkdata_data_id", return_value=None)
@patch("apps.iam.handlers.drf.InstanceActionPermission.has_permission", return_value=True)
@patch("apps.iam.handlers.drf.ViewBusinessPermission.has_permission", return_value=True)
@patch("apps.iam.handlers.permission.Permission.batch_is_allowed", return_value=Dummy())
@patch("apps.decorators.user_operation_record.delay", return_value=None)
class TestIndexSet(TestCase):
    def setUp(self) -> None:
        if User.objects.filter(username="admin").exists():
            return
        User.objects.create_superuser(username="admin")

    @staticmethod
    def sync_index_id(index_sets, ids):
        for index, i_s in enumerate(index_sets["indexes"]):
            i_s["index_id"] = ids[index]

    @staticmethod
    def sync_indexes(index_sets, **kwargs):
        for i_s in index_sets["indexes"]:
            for key, value in kwargs.items():
                i_s[key] = value

    @staticmethod
    def sync_params(index_set, **kwargs):
        for key, value in kwargs.items():
            index_set[key] = value

    @patch("apps.log_search.tasks.mapping.sync_index_set_mapping_snapshot.delay", return_value=None)
    @patch("apps.utils.bk_data_auth.BkDataAuthHandler.filter_unauthorized_rt_by_user", return_value=[])
    @patch(
        "apps.utils.bk_data_auth.BkDataAuthHandler.list_authorized_rt_by_token",
        return_value=["591_xx", "log_xxx"],
    )
    @patch("apps.api.TransferApi.get_cluster_info", return_value=CLUSTER_INFO_WITH_AUTH)
    @patch("apps.api.BkLogApi.mapping", return_value=MAPPING_LIST)
    @patch("apps.api.TransferApi.get_result_table_storage", lambda _: CLUSTER_INFOS)
    @patch("apps.api.BkDataAuthApi.get_auth_token", return_value=TOKEN_PERMISSIONS)
    @override_settings(MIDDLEWARE=(OVERRIDE_MIDDLEWARE,))
    def test_sync_auth_status(self, *args, **kwargs):
        """
        测试API [POST] sync_auth_status
        """
        data = {
            "index_set_name": "登陆日志",
            "space_uid": SPACE_UID,
            "storage_cluster_id": STORAGE_CLUSTER_ID,
            "result_table_id": "591_xx",
            "category_id": "other_rt",
            "scenario_id": SCENARIO_ID_BKDATA,
            "view_roles": [],
            "indexes": [
                {
                    "bk_biz_id": BK_BIZ_ID,
                    "result_table_id": "591_xx",
                    "time_field": "timestamp",
                    "scenario_id": "log",
                    "storage_cluster_id": 6,
                },
                {
                    "bk_biz_id": None,
                    "result_table_id": "log_xxx",
                    "time_field": "timestamp",
                    "scenario_id": "es",
                    "storage_cluster_id": 6,
                },
            ],
            "is_trace_log": "0",
            "time_field": "abc",
            "time_field_type": "date",
            "time_field_unit": "millisecond",
        }

        path = "/api/v1/index_set/"

        self.client.post(path=path, data=json.dumps(data), content_type="application/json")

        index_set = LogIndexSet.objects.all().first()
        index_set_id = index_set.index_set_id
        index_ids = [i["index_id"] for i in index_set.indexes]

        path = "/api/v1/index_set/" + str(index_set_id) + "/sync_auth_status/"

        response = self.client.post(path=path)
        content = json.loads(response.content)

        for index, item in enumerate(SYSC_AUTH_STATUS_RESULT):
            item["index_set_id"] = index_set_id
            item["index_id"] = index_ids[index]

        self.assertEqual(response.status_code, SUCCESS_STATUS_CODE)
        self.assertEqual(content["data"], SYSC_AUTH_STATUS_RESULT)

    @patch("apps.api.TransferApi.get_cluster_info", return_value=CLUSTER_INFO)
    @override_settings(MIDDLEWARE=(OVERRIDE_MIDDLEWARE,))
    def test_list_index_set(self, *args, **kwargs):
        """
        测试 索引集-列表 api.v1.index_set
        """
        # 插入一条索引集记录
        self.do_create_index_set(self)

        # 取到插入数据的一些字段
        index_set = LogIndexSet.objects.all().first()

        index_set_id = index_set.index_set_id
        created_at = arrow.get(index_set.created_at).to(settings.TIME_ZONE).strftime(settings.BKDATA_DATETIME_FORMAT)
        updated_at = arrow.get(index_set.updated_at).to(settings.TIME_ZONE).strftime(settings.BKDATA_DATETIME_FORMAT)
        index_ids = [i["index_id"] for i in index_set.indexes]

        path = "/api/v1/index_set/"
        data = {"space_uid": SPACE_UID, "page": 1, "pagesize": 2}
        response = self.client.get(path=path, data=data)
        content = json.loads(response.content)

        # 同步测试数据库中一些实时和自增的字段
        self.sync_index_id(INDEX_SET_LISTS["list"][0], index_ids)
        self.sync_indexes(INDEX_SET_LISTS["list"][0], index_set_id=index_set_id)
        self.sync_params(
            INDEX_SET_LISTS["list"][0],
            index_set_id=index_set_id,
            created_at=created_at,
            updated_at=updated_at,
        )

        self.assertEqual(response.status_code, SUCCESS_STATUS_CODE)
        data = content["data"]
        self.maxDiff = 100000

        self.assertEqual(data, INDEX_SET_LISTS)

    @patch("apps.log_search.tasks.mapping.sync_index_set_mapping_snapshot.delay", return_value=None)
    # @patch("apps.log_search.handlers.index_set.LogIndexSetDataHandler.post_add_log.delay", return_value=True)
    @patch("apps.api.TransferApi.get_cluster_info", return_value=CLUSTER_INFO_WITH_AUTH)
    @patch("apps.log_search.models.LogIndexSetData.objects.filter", return_value=LogIndexSetData.objects.none())
    @patch("apps.api.BkLogApi.mapping", return_value=MAPPING_LIST)
    @patch("apps.api.TransferApi.get_result_table_storage", lambda _: CLUSTER_INFOS)
    @patch("apps.api.TransferApi.create_or_update_log_router", return_value=None)
    @override_settings(MIDDLEWARE=(OVERRIDE_MIDDLEWARE,))
    def do_create_index_set(self, *args, **kwargs):
        """
        添加一条索引集数据
        """
        data = {
            "index_set_name": "登陆日志",
            "space_uid": SPACE_UID,
            "storage_cluster_id": STORAGE_CLUSTER_ID,
            "result_table_id": "591_xx",
            "category_id": "other_rt",
            "scenario_id": SCENARIO_ID_ES,
            "view_roles": [],
            "indexes": [
                {
                    "bk_biz_id": BK_BIZ_ID,
                    "result_table_id": "591_xx",
                    "time_field": "timestamp",
                    "scenario_id": "log",
                    "storage_cluster_id": 6,
                },
                {
                    "bk_biz_id": None,
                    "result_table_id": "log_xxx",
                    "time_field": "timestamp",
                    "scenario_id": "es",
                    "storage_cluster_id": 3,
                },
            ],
            "is_trace_log": "0",
            "time_field": "abc",
            "time_field_type": "date",
            "time_field_unit": "millisecond",
        }

        path = "/api/v1/index_set/"

        response = self.client.post(path=path, data=json.dumps(data), content_type="application/json")
        return response

    @patch(
        "apps.log_search.handlers.search.search_handlers_esquery.SearchHandler.get_all_fields_by_index_id",
        return_value=MULTI_RESULT,
    )
    @patch(
        "apps.log_search.handlers.search.search_handlers_esquery.SearchHandler._set_time_filed_type", return_value=""
    )
    @patch("apps.api.BkLogApi.mapping", return_value=[])
    @patch("apps.api.TransferApi.create_or_update_log_router", return_value=None)
    @override_settings(MIDDLEWARE=(OVERRIDE_MIDDLEWARE,))
    @FakeRedis("apps.utils.cache.cache")
    def do_update_alias_settings(self, *args, **kwargs):
        """
        更新别名配置
        """
        path = f"/api/v1/search/index_set/{kwargs['index_set_id']}/alias_settings/"
        response = self.client.post(path=path, data=json.dumps(QUERY_ALIAS_SETTINGS), content_type="application/json")
        return response

    @override_settings(MIDDLEWARE=(OVERRIDE_MIDDLEWARE,))
    def test_create_index_set(self, *args, **kwargs):
        """
        测试API [POST] create_index_set
        """

        response = self.do_create_index_set(self)

        content = json.loads(response.content)

        index_set_id = content["data"]["index_set_id"]
        created_at = content["data"]["created_at"]
        updated_at = content["data"]["updated_at"]

        CREATE_SUCCESS["data"].update(
            {"index_set_id": index_set_id, "created_at": created_at, "updated_at": updated_at}
        )
        self.maxDiff = 100000
        self.assertEqual(response.status_code, SUCCESS_STATUS_CODE)
        self.assertEqual(content, CREATE_SUCCESS)

        # 验证别名配置
        MULTI_RESULT.update({index_set_id: (FIELDS_LIST, [])})
        response = self.do_update_alias_settings(index_set_id=index_set_id)
        self.assertEqual(response.status_code, SUCCESS_STATUS_CODE)
        ALIAS_SETTINGS_RESULT["data"].update({"index_set_id": str(index_set_id)})
        content = json.loads(response.content)
        index_set = LogIndexSet.objects.get(index_set_id=index_set_id)
        self.assertEqual(index_set.query_alias_settings, QUERY_ALIAS_SETTINGS["alias_settings"])
        self.assertEqual(content, ALIAS_SETTINGS_RESULT)

    @patch("apps.log_search.tasks.mapping.sync_index_set_mapping_snapshot.delay", return_value=None)
    @patch("apps.api.BkLogApi.mapping", return_value=MAPPING_LIST)
    @patch("apps.log_search.handlers.index_set.sync_index_set_archive.delay", return_value=None)
    @patch("apps.api.TransferApi.create_or_update_log_router", return_value=None)
    @override_settings(MIDDLEWARE=(OVERRIDE_MIDDLEWARE,))
    def test_update_index_set(self, *args, **kwargs):
        """
        测试API [POST] update_index_set
        """
        # 插入一条索引集记录
        self.do_create_index_set(self)

        # 获取插入索引集的一些信息
        index_set = LogIndexSet.objects.all().first()
        index_set_id = index_set.index_set_id
        space_uid = index_set.space_uid
        storage_cluster_id = index_set.storage_cluster_id
        scenario_id = index_set.scenario_id
        index_ids = [i["index_id"] for i in index_set.indexes]

        data = {
            "space_uid": space_uid,
            "scenario_id": scenario_id,
            "index_set_name": "登陆日志",
            "view_roles": [],
            "storage_cluster_id": storage_cluster_id,
            "category_id": "host",
            "indexes": [
                {"bk_biz_id": BK_BIZ_ID, "result_table_id": "591_xx", "time_field": "timestamp"},
                {"bk_biz_id": None, "result_table_id": "log_xxx", "time_field": "timestamp"},
            ],
            "time_field": "abc",
            "time_field_type": "date",
            "time_field_unit": "millisecond",
        }

        path = "/api/v1/index_set/" + str(index_set_id) + "/"

        response = self.client.patch(path=path, data=json.dumps(data), content_type="application/json")

        content = json.loads(response.content)

        created_at = content["data"]["created_at"]
        updated_at = content["data"]["updated_at"]

        # 同步测试数据库中一些实时和自增的字段
        self.sync_indexes(UPDATE_INDEX_SET, index_set_id=index_set_id)
        self.sync_index_id(UPDATE_INDEX_SET, index_ids)
        self.sync_params(UPDATE_INDEX_SET, index_set_id=index_set_id, created_at=created_at, updated_at=updated_at)

        self.assertEqual(response.status_code, SUCCESS_STATUS_CODE)
        self.maxDiff = 1000000
        self.assertEqual(content["data"], UPDATE_INDEX_SET)

        # 测试不可编辑字段 为True下仍可以编辑
        index_set.is_editable = False
        index_set.save()
        response = self.client.patch(path=path, data=json.dumps(data), content_type="application/json")
        content = json.loads(response.content)
        created_at = content["data"]["created_at"]
        updated_at = content["data"]["updated_at"]

        check_data = copy.deepcopy(UPDATE_INDEX_SET)
        self.sync_params(
            check_data, index_set_id=index_set_id, created_at=created_at, updated_at=updated_at, is_editable=False
        )
        self.assertEqual(json.loads(response.content)["data"], check_data)

    @override_settings(MIDDLEWARE=(OVERRIDE_MIDDLEWARE,))
    def test_delete_index_set(self, *args):
        """
        测试API [DELETE] delete_index_set
        """

        # 插入一条索引集记录
        self.do_create_index_set(self)

        # 获取插入索引集的id
        index_set = LogIndexSet.objects.all().first()
        index_set_id = index_set.index_set_id

        path = "/api/v1/index_set/"
        path += str(index_set_id) + "/"

        response = self.client.delete(path=path)
        content = json.loads(response.content)

        self.assertEqual(response.status_code, SUCCESS_STATUS_CODE)
        self.assertEqual(content, DELETE_SUCCESS)

    @patch("apps.api.TransferApi.get_cluster_info", return_value=CLUSTER_INFO)
    @override_settings(MIDDLEWARE=(OVERRIDE_MIDDLEWARE,))
    def test_retrieve_index_set(self, *args):
        """
        测试API [GET] retrieve_index_set
        """
        # 插入一条索引集记录
        self.do_create_index_set(self)

        # 获取一些自增的字段，以更新到验证数据中
        index_set = LogIndexSet.objects.all().first()
        index_set_id = index_set.index_set_id
        index_ids = [i["index_id"] for i in index_set.indexes]
        created_at = arrow.get(index_set.created_at).to(settings.TIME_ZONE).strftime(settings.BKDATA_DATETIME_FORMAT)
        updated_at = arrow.get(index_set.updated_at).to(settings.TIME_ZONE).strftime(settings.BKDATA_DATETIME_FORMAT)

        path = "/api/v1/index_set/" + str(index_set_id) + "/"

        response = self.client.get(path=path)
        content = json.loads(response.content)

        # 同步测试数据库中一些实时和自增的字段
        self.sync_index_id(RETRIEVE_LIST, index_ids)
        self.sync_indexes(RETRIEVE_LIST, index_set_id=index_set_id)
        self.sync_params(RETRIEVE_LIST, index_set_id=index_set_id, created_at=created_at, updated_at=updated_at)

        self.assertEqual(response.status_code, SUCCESS_STATUS_CODE)
        self.maxDiff = 100000
        self.assertEqual(content["data"], RETRIEVE_LIST)


@patch("apps.iam.handlers.drf.BusinessActionPermission.has_permission", return_value=True)
@patch("apps.iam.handlers.drf.InstanceActionPermission.has_permission", return_value=True)
@patch("apps.iam.handlers.drf.ViewBusinessPermission.has_permission", return_value=True)
@patch("apps.iam.handlers.permission.Permission.batch_is_allowed", return_value=Dummy())
class IndexGroupViewSetTestCase(TestCase):
    def setUp(self):
        self.do_create_index_group()

    @override_settings(MIDDLEWARE=(OVERRIDE_MIDDLEWARE,))
    def do_create_index_group(self, *args, **kwargs):
        path = "/api/v1/index_group/"
        data = {"space_uid": SPACE_UID, "index_set_name": "new_group"}
        response = self.client.post(path, data)
        content = json.loads(response.content)

        self.assertEqual(response.status_code, SUCCESS_STATUS_CODE)
        self.assertIn("index_set_id", content["data"])

        # 验证数据库
        new_group = LogIndexSet.objects.get(index_set_id=content["data"]["index_set_id"])
        self.assertEqual(new_group.index_set_name, "new_group")
        self.assertEqual(new_group.space_uid, SPACE_UID)
        self.assertTrue(new_group.is_group)
        self.index_group = new_group

    @override_settings(MIDDLEWARE=(OVERRIDE_MIDDLEWARE,))
    @patch("apps.log_search.models.SpaceApi.get_space_detail")
    def test_list_index_groups(self, mock_get_space_detail, *args, **kwargs):
        mock_space = Space(
            id=2,
            space_type_id="bkcc",
            space_id="2",
            space_name="蓝鲸",
            status="normal",
            space_code="2",
            space_uid="bkcc__2",
            type_name="业务",
            bk_biz_id=2,
            extend={
                "status": "normal",
                "language": "zh-hans",
                "resources": [{"resource_id": "blueking", "resource_type": "bkci"}],
                "time_zone": "Asia/Shanghai",
                "display_name": "[业务] 蓝鲸",
                "is_bcs_valid": False,
            },
            bk_tenant_id="system",
        )

        mock_get_space_detail.return_value = mock_space

        path = "/api/v1/index_group/"
        data = {"space_uid": SPACE_UID}

        response = self.client.get(path, data)
        content = json.loads(response.content)

        self.assertEqual(response.status_code, SUCCESS_STATUS_CODE)
        index_groups = content["data"]["list"]
        self.assertEqual(len(index_groups), 1)
        self.assertEqual(index_groups[0]["index_set_id"], self.index_group.index_set_id)
        self.assertEqual(index_groups[0]["index_set_name"], "new_group")
        self.assertEqual(index_groups[0]["index_count"], 0)

    @override_settings(MIDDLEWARE=(OVERRIDE_MIDDLEWARE,))
    def test_update_index_group(self, *args, **kwargs):
        path = f"/api/v1/index_group/{self.index_group.index_set_id}/"
        data = {"index_set_name": "updated_group"}
        response = self.client.put(path, data, content_type="application/json")

        self.assertEqual(response.status_code, SUCCESS_STATUS_CODE)

        # 验证数据库
        updated_group = LogIndexSet.objects.get(index_set_id=self.index_group.index_set_id)
        self.assertEqual(updated_group.index_set_name, "updated_group")

    @override_settings(MIDDLEWARE=(OVERRIDE_MIDDLEWARE,))
    def test_delete_index_group(self, *args, **kwargs):
        path = f"/api/v1/index_group/{self.index_group.index_set_id}/"
        response = self.client.delete(path)

        self.assertEqual(response.status_code, SUCCESS_STATUS_CODE)
        # 验证数据库
        self.assertFalse(LogIndexSet.objects.filter(index_set_id=self.index_group.index_set_id).exists())


class TestPlatformIndexSerializer(TestCase):
    """
    测试平台级索引集有关序列化器的校验行为
    """

    def test_is_platform_index_true_but_visibility_and_filter_empty(self):
        """
        is_platform_index=True 但 visibility/filter 为空 → 拒绝
        """
        from apps.log_databus.serializers import PlatformIndexFieldsSerializer

        ser = PlatformIndexFieldsSerializer(data={"is_platform_index": True})
        self.assertFalse(ser.is_valid())

        ser = PlatformIndexFieldsSerializer(
            data={
                "is_platform_index": True,
                "platform_index_visibility": {"type": "multi_biz", "bk_biz_ids": [1, 2]},
                # 缺 platform_index_filter
            }
        )
        self.assertFalse(ser.is_valid())

        ser = PlatformIndexFieldsSerializer(
            data={
                "is_platform_index": True,
                # 缺 platform_index_visibility
                "platform_index_filter": {"field": "bk_biz_id", "value_ref": "bk_biz_id"},
            }
        )
        self.assertFalse(ser.is_valid())

    def test_is_platform_index_true_with_full_fields(self):
        """
        is_platform_index=True 且 visibility/filter 完整 → 通过
        """
        from apps.log_databus.serializers import PlatformIndexFieldsSerializer

        ser = PlatformIndexFieldsSerializer(
            data={
                "is_platform_index": True,
                "platform_index_visibility": {"type": "multi_biz", "bk_biz_ids": [1, 2]},
                "platform_index_filter": {"field": "bk_biz_id", "value_ref": "bk_biz_id"},
            }
        )
        self.assertTrue(ser.is_valid(), msg=ser.errors)

    def test_is_platform_index_false_or_missing_does_not_require_others(self):
        """
        is_platform_index=False/未传 → 即使 visibility/filter 缺失也通过
        """
        from apps.log_databus.serializers import PlatformIndexFieldsSerializer

        ser = PlatformIndexFieldsSerializer(data={"is_platform_index": False})
        self.assertTrue(ser.is_valid(), msg=ser.errors)

        ser = PlatformIndexFieldsSerializer(data={})
        self.assertTrue(ser.is_valid(), msg=ser.errors)

    def test_visibility_multi_biz_without_bk_biz_ids(self):
        """
        multi_biz 模式下 bk_biz_ids 为空 → 拒绝
        """
        from apps.log_databus.serializers import PlatformIndexVisibilitySerializer

        ser = PlatformIndexVisibilitySerializer(data={"type": "multi_biz"})
        self.assertFalse(ser.is_valid())

        ser = PlatformIndexVisibilitySerializer(data={"type": "multi_biz", "bk_biz_ids": []})
        self.assertFalse(ser.is_valid())

    def test_visibility_biz_attr_without_bk_biz_labels(self):
        """
        biz_attr 模式下 bk_biz_labels 为空 → 拒绝
        """
        from apps.log_databus.serializers import PlatformIndexVisibilitySerializer

        ser = PlatformIndexVisibilitySerializer(data={"type": "biz_attr"})
        self.assertFalse(ser.is_valid())

        ser = PlatformIndexVisibilitySerializer(data={"type": "biz_attr", "bk_biz_labels": {}})
        self.assertFalse(ser.is_valid())

    def test_visibility_valid_cases(self):
        """
        visibility 正确填充 → 通过
        """
        from apps.log_databus.serializers import PlatformIndexVisibilitySerializer

        ser = PlatformIndexVisibilitySerializer(data={"type": "multi_biz", "bk_biz_ids": [1, 2, 3]})
        self.assertTrue(ser.is_valid(), msg=ser.errors)

        ser = PlatformIndexVisibilitySerializer(data={"type": "biz_attr", "bk_biz_labels": {"env": "prod"}})
        self.assertTrue(ser.is_valid(), msg=ser.errors)


PLATFORM_VISIBILITY = {"type": "multi_biz", "bk_biz_ids": [1, 2]}
PLATFORM_FILTER = {"field": "bk_biz_id", "value_ref": "bk_biz_id"}


@patch("apps.iam.handlers.drf.BusinessActionPermission.has_permission", return_value=True)
@patch("apps.log_search.tasks.mapping.sync_single_index_set_mapping_snapshot.delay", return_value=None)
@patch("apps.log_databus.tasks.bkdata.async_create_bkdata_data_id", return_value=None)
@patch("apps.iam.handlers.drf.InstanceActionPermission.has_permission", return_value=True)
@patch("apps.iam.handlers.drf.ViewBusinessPermission.has_permission", return_value=True)
@patch("apps.iam.handlers.permission.Permission.batch_is_allowed", return_value=Dummy())
@patch("apps.decorators.user_operation_record.delay", return_value=None)
class TestPlatformIndexHandler(TestCase):
    """
    通过 HTTP 接口走 IndexSetHandler.create / update，
    端到端验证 is_platform_index / platform_index_visibility / platform_index_filter
    三个字段的落库行为
    """

    def setUp(self) -> None:
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser(username="admin")

    @staticmethod
    def _build_create_payload(**overrides):
        data = {
            "index_set_name": "平台日志",
            "space_uid": SPACE_UID,
            "storage_cluster_id": STORAGE_CLUSTER_ID,
            "category_id": "other_rt",
            "scenario_id": SCENARIO_ID_ES,
            "view_roles": [],
            "indexes": [
                {
                    "bk_biz_id": BK_BIZ_ID,
                    "result_table_id": "591_xx",
                    "time_field": "timestamp",
                    "scenario_id": "log",
                    "storage_cluster_id": 6,
                },
                {
                    "bk_biz_id": None,
                    "result_table_id": "log_xxx",
                    "time_field": "timestamp",
                    "scenario_id": "es",
                    "storage_cluster_id": 3,
                },
            ],
            "is_trace_log": "0",
            "time_field": "abc",
            "time_field_type": "date",
            "time_field_unit": "millisecond",
        }
        data.update(overrides)
        return data

    @patch("apps.log_search.tasks.mapping.sync_index_set_mapping_snapshot.delay", return_value=None)
    @patch("apps.api.TransferApi.get_cluster_info", return_value=CLUSTER_INFO_WITH_AUTH)
    @patch("apps.log_search.models.LogIndexSetData.objects.filter", return_value=LogIndexSetData.objects.none())
    @patch("apps.api.BkLogApi.mapping", return_value=MAPPING_LIST)
    @patch("apps.api.TransferApi.get_result_table_storage", lambda _: CLUSTER_INFOS)
    @patch("apps.api.TransferApi.create_or_update_log_router", return_value=None)
    @override_settings(MIDDLEWARE=(OVERRIDE_MIDDLEWARE,))
    def test_create_with_platform_fields(self, *args, **kwargs):
        """
        IndexSetHandler.create + 平台字段 → LogIndexSet 正确写入 3 个字段
        """
        payload = self._build_create_payload(
            is_platform_index=True,
            platform_index_visibility=PLATFORM_VISIBILITY,
            platform_index_filter=PLATFORM_FILTER,
        )
        response = self.client.post(
            path="/api/v1/index_set/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, SUCCESS_STATUS_CODE)

        index_set = LogIndexSet.objects.all().order_by("-index_set_id").first()
        self.assertTrue(index_set.is_platform_index)
        self.assertEqual(index_set.platform_index_visibility, PLATFORM_VISIBILITY)
        self.assertEqual(index_set.platform_index_filter, PLATFORM_FILTER)

    @patch("apps.log_search.tasks.mapping.sync_index_set_mapping_snapshot.delay", return_value=None)
    @patch("apps.api.TransferApi.get_cluster_info", return_value=CLUSTER_INFO_WITH_AUTH)
    @patch("apps.log_search.models.LogIndexSetData.objects.filter", return_value=LogIndexSetData.objects.none())
    @patch("apps.api.BkLogApi.mapping", return_value=MAPPING_LIST)
    @patch("apps.api.TransferApi.get_result_table_storage", lambda _: CLUSTER_INFOS)
    @patch("apps.api.TransferApi.create_or_update_log_router", return_value=None)
    @patch("apps.log_search.handlers.index_set.sync_index_set_archive.delay", return_value=None)
    @override_settings(MIDDLEWARE=(OVERRIDE_MIDDLEWARE,))
    def test_update_switch_off_platform_index_clears_related_fields(self, *args, **kwargs):
        """
        IndexSetHandler.update 从 is_platform_index=True 切回 False → visibility/filter 被清空
        """
        # 先创建一个开启平台级的索引集
        create_payload = self._build_create_payload(
            is_platform_index=True,
            platform_index_visibility=PLATFORM_VISIBILITY,
            platform_index_filter=PLATFORM_FILTER,
        )
        response = self.client.post(
            path="/api/v1/index_set/",
            data=json.dumps(create_payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, SUCCESS_STATUS_CODE)

        index_set = LogIndexSet.objects.all().order_by("-index_set_id").first()
        index_set_id = index_set.index_set_id
        # 确认初始状态
        self.assertTrue(index_set.is_platform_index)
        self.assertEqual(index_set.platform_index_visibility, PLATFORM_VISIBILITY)
        self.assertEqual(index_set.platform_index_filter, PLATFORM_FILTER)

        # 切回 False
        update_payload = {
            "space_uid": index_set.space_uid,
            "scenario_id": index_set.scenario_id,
            "index_set_name": index_set.index_set_name,
            "view_roles": [],
            "storage_cluster_id": index_set.storage_cluster_id,
            "category_id": "host",
            "indexes": [
                {"bk_biz_id": BK_BIZ_ID, "result_table_id": "591_xx", "time_field": "timestamp"},
                {"bk_biz_id": None, "result_table_id": "log_xxx", "time_field": "timestamp"},
            ],
            "time_field": "abc",
            "time_field_type": "date",
            "time_field_unit": "millisecond",
            "is_platform_index": False,
            # visibility 与 filter 即使还传着，切回 False 后也应被清空
            "platform_index_visibility": PLATFORM_VISIBILITY,
            "platform_index_filter": PLATFORM_FILTER,
        }
        response = self.client.patch(
            path=f"/api/v1/index_set/{index_set_id}/",
            data=json.dumps(update_payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, SUCCESS_STATUS_CODE)

        index_set.refresh_from_db()
        self.assertFalse(index_set.is_platform_index)
        self.assertIsNone(index_set.platform_index_visibility)
        self.assertIsNone(index_set.platform_index_filter)

    @patch("apps.log_search.tasks.mapping.sync_index_set_mapping_snapshot.delay", return_value=None)
    @patch("apps.api.TransferApi.get_cluster_info", return_value=CLUSTER_INFO_WITH_AUTH)
    @patch("apps.log_search.models.LogIndexSetData.objects.filter", return_value=LogIndexSetData.objects.none())
    @patch("apps.api.BkLogApi.mapping", return_value=MAPPING_LIST)
    @patch("apps.api.TransferApi.get_result_table_storage", lambda _: CLUSTER_INFOS)
    @patch("apps.api.TransferApi.create_or_update_log_router", return_value=None)
    @patch("apps.log_search.handlers.index_set.sync_index_set_archive.delay", return_value=None)
    @override_settings(MIDDLEWARE=(OVERRIDE_MIDDLEWARE,))
    def test_update_without_is_platform_index_keeps_existing_fields(self, *args, **kwargs):
        """
        IndexSetHandler.update 不传 is_platform_index (None) → 保留现有 visibility/filter 不被清空
        """
        # 先创建一个开启平台级的索引集
        create_payload = self._build_create_payload(
            is_platform_index=True,
            platform_index_visibility=PLATFORM_VISIBILITY,
            platform_index_filter=PLATFORM_FILTER,
        )
        response = self.client.post(
            path="/api/v1/index_set/",
            data=json.dumps(create_payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, SUCCESS_STATUS_CODE)

        index_set = LogIndexSet.objects.all().order_by("-index_set_id").first()
        index_set_id = index_set.index_set_id

        # 更新时不传 is_platform_index（走 None 分支），仅改其他字段
        update_payload = {
            "space_uid": index_set.space_uid,
            "scenario_id": index_set.scenario_id,
            "index_set_name": "平台日志-改名",
            "view_roles": [],
            "storage_cluster_id": index_set.storage_cluster_id,
            "category_id": "host",
            "indexes": [
                {"bk_biz_id": BK_BIZ_ID, "result_table_id": "591_xx", "time_field": "timestamp"},
                {"bk_biz_id": None, "result_table_id": "log_xxx", "time_field": "timestamp"},
            ],
            "time_field": "abc",
            "time_field_type": "date",
            "time_field_unit": "millisecond",
        }
        response = self.client.patch(
            path=f"/api/v1/index_set/{index_set_id}/",
            data=json.dumps(update_payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, SUCCESS_STATUS_CODE)

        index_set.refresh_from_db()
        # 未传 is_platform_index 时，三个字段应保持原有值
        self.assertEqual(index_set.index_set_name, "平台日志-改名")
        self.assertTrue(index_set.is_platform_index)
        self.assertEqual(index_set.platform_index_visibility, PLATFORM_VISIBILITY)
        self.assertEqual(index_set.platform_index_filter, PLATFORM_FILTER)

    @patch("apps.log_search.tasks.mapping.sync_index_set_mapping_snapshot.delay", return_value=None)
    @patch("apps.api.TransferApi.get_cluster_info", return_value=CLUSTER_INFO_WITH_AUTH)
    @patch("apps.log_search.models.LogIndexSetData.objects.filter", return_value=LogIndexSetData.objects.none())
    @patch("apps.api.BkLogApi.mapping", return_value=MAPPING_LIST)
    @patch("apps.api.TransferApi.get_result_table_storage", lambda _: CLUSTER_INFOS)
    @patch("apps.api.TransferApi.create_or_update_log_router", return_value=None)
    @patch("apps.log_search.handlers.index_set.sync_index_set_archive.delay", return_value=None)
    @override_settings(MIDDLEWARE=(OVERRIDE_MIDDLEWARE,))
    def test_update_only_visibility_without_touching_is_platform_index(self, *args, **kwargs):
        """
        IndexSetHandler.update 仅改 visibility（is_platform_index 保持原值）
        → visibility 更新成功
        """
        # 先创建一个开启平台级的索引集（初始 visibility = multi_biz）
        create_payload = self._build_create_payload(
            is_platform_index=True,
            platform_index_visibility=PLATFORM_VISIBILITY,
            platform_index_filter=PLATFORM_FILTER,
        )
        response = self.client.post(
            path="/api/v1/index_set/",
            data=json.dumps(create_payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, SUCCESS_STATUS_CODE)

        index_set = LogIndexSet.objects.all().order_by("-index_set_id").first()
        index_set_id = index_set.index_set_id
        original_storage_cluster_id = index_set.storage_cluster_id

        new_visibility = {"type": "biz_attr", "bk_biz_labels": {"env": "prod"}}
        update_payload = {
            "space_uid": index_set.space_uid,
            "scenario_id": index_set.scenario_id,
            "index_set_name": index_set.index_set_name,
            "view_roles": [],
            "storage_cluster_id": original_storage_cluster_id,
            "category_id": "host",
            "indexes": [
                {"bk_biz_id": BK_BIZ_ID, "result_table_id": "591_xx", "time_field": "timestamp"},
                {"bk_biz_id": None, "result_table_id": "log_xxx", "time_field": "timestamp"},
            ],
            "time_field": "abc",
            "time_field_type": "date",
            "time_field_unit": "millisecond",
            "is_platform_index": True,
            # 仅仅改动 visibility
            "platform_index_visibility": new_visibility,
            "platform_index_filter": PLATFORM_FILTER,
        }
        response = self.client.patch(
            path=f"/api/v1/index_set/{index_set_id}/",
            data=json.dumps(update_payload),
            content_type="application/json",
        )
        # 不报错
        self.assertEqual(response.status_code, SUCCESS_STATUS_CODE)

        index_set.refresh_from_db()
        # storage 保持不变
        self.assertEqual(index_set.storage_cluster_id, original_storage_cluster_id)
        self.assertTrue(index_set.is_platform_index)
        # 验证更新
        self.assertEqual(index_set.platform_index_visibility, new_visibility)
        self.assertEqual(index_set.platform_index_filter, PLATFORM_FILTER)


class TestCustomCreateIdempotent(TestCase):
    """
    验证 CollectorHandler.custom_create 在命中已存在 EN 名时的两条分支：
    - ignore_exists=True  → 返回已有记录信息且 created=False
    - ignore_exists=False → 抛 CollectorConfigNameENDuplicateException
    """

    def _build_params(self, **overrides):
        params = {
            "bk_biz_id": 2,
            "collector_config_name": "自定义采集",
            "collector_config_name_en": "custom_collector_en",
            "custom_type": "log",
            "category_id": "other_rt",
            "description": "desc",
            "etl_config": "",
            "etl_params": {},
            "fields": [],
        }
        params.update(overrides)
        return params

    @patch(
        "apps.log_databus.handlers.collector.base.CollectorHandler._pre_check_collector_config_en",
        return_value=True,
    )
    @patch("apps.log_databus.handlers.collector.base.CollectorConfig.objects.get")
    def test_custom_create_ignore_exists_true_returns_existing(self, mock_get, mock_pre_check):
        """
        ignore_exists=True 命中已存在 → 返回 created=False 且 ids 正确
        """
        from apps.log_databus.handlers.collector.base import CollectorHandler

        existing = MagicMock()
        existing.collector_config_id = 100
        existing.index_set_id = 200
        existing.bk_data_id = 300
        mock_get.return_value = existing

        result = CollectorHandler().custom_create(ignore_exists=True, **self._build_params())

        self.assertEqual(
            result,
            {
                "collector_config_id": 100,
                "index_set_id": 200,
                "bk_data_id": 300,
                "created": False,
            },
        )
        # 确认短路：没有进入实际创建流程
        mock_pre_check.assert_called_once()
        mock_get.assert_called_once()

    @patch(
        "apps.log_databus.handlers.collector.base.CollectorHandler._pre_check_collector_config_en",
        return_value=True,
    )
    def test_custom_create_ignore_exists_false_raises(self, mock_pre_check):
        """
        ignore_exists=False 命中已存在 → 抛 CollectorConfigNameENDuplicateException
        """
        from apps.log_databus.exceptions import CollectorConfigNameENDuplicateException
        from apps.log_databus.handlers.collector.base import CollectorHandler

        with self.assertRaises(CollectorConfigNameENDuplicateException):
            CollectorHandler().custom_create(ignore_exists=False, **self._build_params())

        mock_pre_check.assert_called_once()

    @patch("apps.log_databus.tasks.bkdata.async_create_bkdata_data_id.delay", return_value=None)
    @patch("apps.api.TransferApi.get_result_table", return_value={})
    @patch("apps.api.TransferApi.get_data_id", return_value={})
    @patch("apps.api.TransferApi.create_result_table", return_value={"table_id": "test_table_id"})
    @patch("apps.api.TransferApi.get_cluster_info", return_value=CLUSTER_INFO_WITH_AUTH)
    @patch("apps.utils.thread.MultiExecuteFunc.append", return_value="")
    @patch("apps.utils.thread.MultiExecuteFunc.run", return_value={})
    @patch("apps.log_databus.handlers.collector.base.CollectorHandler._send_create_notify", return_value=None)
    @patch("apps.log_databus.handlers.collector.base.CollectorHandler._authorization_collector", return_value=None)
    @patch(
        "apps.log_databus.handlers.collector_scenario.base.CollectorScenario.update_or_create_data_id",
        return_value=300,
    )
    @patch("apps.log_search.handlers.index_set.sync_index_set_archive.delay", return_value=None)
    @patch("apps.log_search.tasks.mapping.sync_single_index_set_mapping_snapshot.delay", return_value=None)
    @patch("apps.decorators.user_operation_record.delay", return_value=None)
    def test_custom_create_resolves_default_data_link(self, *args):
        from apps.log_databus.handlers.collector.base import CollectorHandler

        data_link = DataLinkConfig.objects.create(
            link_group_name="public link",
            bk_biz_id=0,
            bk_tenant_id=settings.BK_APP_TENANT_ID,
            kafka_cluster_id=162858,
            transfer_cluster_id="bkte-bklog-gz-1",
            es_cluster_ids=[3],
            is_active=True,
        )

        result = CollectorHandler().custom_create(data_link_id=0, **self._build_params())

        collector = CollectorConfig.objects.get(collector_config_id=result["collector_config_id"])
        self.assertEqual(collector.data_link_id, data_link.data_link_id)


class TestSyncRouter(TestCase):
    """
    回归测试：sync_router / get_index_set_table_info_list 的路由创建逻辑。

    三种采集项类型：
      1. 原生 Doris 采集项
         —— ES 一样的接入流程，storage_cluster_type="doris"，没有 Doris 标签
         —— doris_table_id 为空（在采集项创建阶段不设置）
         —— 默认路由走 ES（__default__），analysis 路由不创建（__default__ 已支持 sql/grep）
      2. 存量 ES + Doris 采集项（更新后启用 Doris）
         —— 无 Doris 标签，但 doris_table_id 有值
         —— 默认路由走 ES（__default__），analysis 路由走 Doris（__analysis__）
      3. 手动接入 Doris 集群的采集项
         —— 有 Doris 标签，doris_table_id 有值
         —— 默认路由走 Doris（__doris__），analysis 路由走 Doris（__analysis__）
    """

    def _ensure_doris_tag(self) -> str:
        """确保 Doris 标签存在，返回其 tag_id 字符串。
        Doris 标签的 tag_type 默认为 TAG_TYPE_USER。
        """
        return str(IndexSetTag.get_tag_id("Doris", tag_type=TAG_TYPE_INNER))

    def _build_native_doris_index_set(self, **extra) -> LogIndexSet:
        """创建一个原生 Doris 采集项：
        - 无 Doris 标签
        - doris_table_id 为空，support_doris=False（原生 Doris 自带 sql/grep，不需要额外标识）
        - storage_cluster_type="doris"（原生 Doris 采集项标识）
        - 有 LogIndexSetData（走 ES 接入流程）
        """
        params = dict(
            index_set_name="native_doris",
            space_uid="bkcc__2",
            scenario_id=Scenario.LOG,
            doris_table_id=None,
            support_doris=False,
        )
        params.update(extra)
        index_set = LogIndexSet.objects.create(**params)
        # 原生 Doris 同样有 ES 层面的 LogIndexSetData
        LogIndexSetData.objects.create(
            index_set_id=index_set.index_set_id,
            result_table_id="591_native",
            scenario_id=Scenario.LOG,
            bk_biz_id=2,
        )
        # CollectorConfig 记录，避免 ES 路由中 collector_config.is_nanos 报错
        CollectorConfig.objects.create(
            table_id="591_native",
            bk_biz_id=2,
            collector_config_name="native_doris_cc",
            collector_scenario_id="log",
            category_id="other_rt",
            storage_cluster_type=DORIS_CLUSTER_TYPE,
        )
        return index_set

    def _build_es_doris_index_set(self, **extra) -> LogIndexSet:
        """创建一个存量 ES + Doris 采集项（开启了 sql/grep）：
        - 无 Doris 标签
        - doris_table_id 有值，support_doris=True（开启了 sql/grep 能力）
        - storage_cluster_type="elasticsearch"（普通采集项标识）
        - 有 LogIndexSetData（ES 历史数据）
        """
        params = dict(
            index_set_name="es_doris",
            space_uid="bkcc__2",
            scenario_id=Scenario.LOG,
            doris_table_id="db.doris_table_1",
            support_doris=True,
        )
        params.update(extra)
        index_set = LogIndexSet.objects.create(**params)
        LogIndexSetData.objects.create(
            index_set_id=index_set.index_set_id,
            result_table_id="591_xx",
            scenario_id=Scenario.LOG,
            bk_biz_id=2,
        )
        CollectorConfig.objects.create(
            table_id="591_xx",
            bk_biz_id=2,
            collector_config_name="es_doris_cc",
            collector_scenario_id="log",
            category_id="other_rt",
            storage_cluster_type=STORAGE_CLUSTER_TYPE,
        )
        return index_set

    def _build_manual_doris_index_set(self, **extra) -> LogIndexSet:
        """创建一个手动接入 Doris 集群的采集项（开启了 sql/grep）：
        - 有 Doris 标签
        - doris_table_id 有值，support_doris=True（开启了 sql/grep 能力）
        - storage_cluster_type="elasticsearch"（跟 ES 采集项一样，手动接入 Doris 集群）
        - 有 CollectorConfig 记录（采集项）

        注意：tag_ids 必须传列表而非字符串，防止 tag_id 值拼接导致的匹配失败。
        """
        doris_tag_id = self._ensure_doris_tag()
        # 手动接入 Doris 也有采集项，storage_cluster_type 为 elasticsearch
        collector_config_obj = CollectorConfig.objects.create(
            table_id="591_manual",
            bk_biz_id=2,
            collector_config_name="manual_doris_cc",
            collector_scenario_id="log",
            category_id="other_rt",
            storage_cluster_type=STORAGE_CLUSTER_TYPE,
        )
        params = dict(
            index_set_name="manual_doris",
            space_uid="bkcc__2",
            scenario_id=Scenario.BKDATA,
            tag_ids=[doris_tag_id],
            doris_table_id="db.doris_table_1,db.doris_table_2",
            support_doris=True,
            collector_config_id=collector_config_obj.collector_config_id,
        )
        params.update(extra)
        index_set_obj = LogIndexSet.objects.create(**params)
        # refresh_from_db 确保 tag_ids 经过 from_db_value 转换（避免 list("14") 拆字问题）
        index_set_obj.refresh_from_db()

        collector_config_obj.index_set_id = index_set_obj.index_set_id
        collector_config_obj.save()

        return index_set_obj

    # ==================================================================
    # 场景 1：原生 Doris 采集项
    # ==================================================================

    def test_native_doris_default(self):
        """
        原生 Doris —— get_index_set_table_info_list(is_analysis=False)
        期望：走 ES 路由分支，返回 __default__ 后缀条目
        """
        index_set = self._build_native_doris_index_set()
        result = BaseIndexSetHandler.get_index_set_table_info_list(index_set, is_analysis=False)
        self.assertEqual(len(result), 1)
        info = result[0]
        self.assertEqual(
            info["table_id"],
            f"bklog_index_set_{index_set.index_set_id}_591_native.__default__",
        )
        self.assertEqual(info["source_type"], Scenario.LOG)

    def test_native_doris_analysis_empty(self):
        """
        原生 Doris —— get_index_set_table_info_list(is_analysis=True)
        期望：doris_table_id 为空 → 返回空列表（不创建 analysis 路由）
        """
        index_set = self._build_native_doris_index_set()
        result = BaseIndexSetHandler.get_index_set_table_info_list(index_set, is_analysis=True)
        self.assertEqual(result, [])

    def test_native_doris_sync_router_only_default(self):
        """
        原生 Doris —— sync_router 只注册一次（默认路由），不注册 analysis 路由
        """
        index_set = self._build_native_doris_index_set()
        append_calls = []

        def _capture_append(result_key, func, params=None, use_request=True, multi_func_params=False):
            append_calls.append((result_key, func, params))

        with patch("apps.utils.thread.MultiExecuteFunc.append", side_effect=_capture_append):
            with patch("apps.utils.thread.MultiExecuteFunc.run", return_value={}):
                BaseIndexSetHandler.sync_router(index_set)

        self.assertEqual(len(append_calls), 1)
        key, func, params = append_calls[0]
        self.assertEqual(key, f"bklog_index_set_{index_set.index_set_id}")
        self.assertTrue(callable(func))
        self.assertEqual(params["data_label"], f"bklog_index_set_{index_set.index_set_id}")
        for info in params["table_info"]:
            self.assertTrue(info["table_id"].endswith(".__default__"))
            self.assertTrue(info["is_enable"])

    # ==================================================================
    # 场景 2：存量 ES + Doris 采集项
    # ==================================================================

    def test_es_doris_default(self):
        """
        存量 ES + Doris —— get_index_set_table_info_list(is_analysis=False)
        期望：走 ES 路由分支，返回 __default__ 后缀条目
        """
        index_set = self._build_es_doris_index_set()
        result = BaseIndexSetHandler.get_index_set_table_info_list(index_set, is_analysis=False)
        self.assertEqual(len(result), 1)
        info = result[0]
        self.assertEqual(
            info["table_id"],
            f"bklog_index_set_{index_set.index_set_id}_591_xx.__default__",
        )
        self.assertEqual(info["source_type"], Scenario.LOG)

    def test_es_doris_analysis(self):
        """
        存量 ES + Doris —— get_index_set_table_info_list(is_analysis=True)
        期望：is_analysis=True 且 doris_table_id 有值 → 返回 Doris 条目，后缀 __analysis__
        """
        index_set = self._build_es_doris_index_set()
        result = BaseIndexSetHandler.get_index_set_table_info_list(index_set, is_analysis=True)
        self.assertEqual(len(result), 1)
        info = result[0]
        self.assertEqual(info["storage_type"], "doris")
        self.assertEqual(info["source_type"], "bkdata")
        self.assertTrue(info["table_id"].endswith(".__analysis__"))

    def test_es_doris_sync_router_both(self):
        """
        存量 ES + Doris —— sync_router 注册两次路由：
          - data_label=bklog_index_set_{id}           → ES 条目（__default__）
          - data_label=bklog_index_set_{id}_analysis   → Doris 条目（__analysis__）
        """
        index_set = self._build_es_doris_index_set()
        append_calls = []

        def _capture_append(result_key, func, params=None, use_request=True, multi_func_params=False):
            append_calls.append((result_key, func, params))

        with patch("apps.utils.thread.MultiExecuteFunc.append", side_effect=_capture_append):
            with patch("apps.utils.thread.MultiExecuteFunc.run", return_value={}):
                BaseIndexSetHandler.sync_router(index_set)

        self.assertEqual(len(append_calls), 2)

        # 默认路由 → ES
        key0, _, params0 = append_calls[0]
        self.assertEqual(key0, f"bklog_index_set_{index_set.index_set_id}")
        for info in params0["table_info"]:
            self.assertTrue(info["table_id"].endswith(".__default__"))
            self.assertEqual(info["source_type"], Scenario.LOG)
            self.assertTrue(info["is_enable"])

        # Analysis 路由 → Doris
        key1, _, params1 = append_calls[1]
        self.assertEqual(key1, f"bklog_index_set_{index_set.index_set_id}_analysis")
        for info in params1["table_info"]:
            self.assertTrue(info["table_id"].endswith(".__analysis__"))
            self.assertEqual(info["storage_type"], "doris")
            self.assertEqual(info["source_type"], "bkdata")
            self.assertTrue(info["is_enable"])

    # ==================================================================
    # 场景 3：手动接入 Doris 集群的采集项
    # ==================================================================

    def test_manual_doris_default(self):
        """
        手动接入 Doris —— get_index_set_table_info_list(is_analysis=False)
        期望：返回 Doris 条目，后缀 __doris__
        """
        index_set = self._build_manual_doris_index_set()
        result = BaseIndexSetHandler.get_index_set_table_info_list(index_set, is_analysis=False)
        self.assertEqual(len(result), 2)
        for info in result:
            self.assertEqual(info["storage_type"], "doris")
            self.assertEqual(info["source_type"], "bkdata")
            self.assertTrue(info["table_id"].endswith(".__doris__"))

    def test_manual_doris_analysis(self):
        """
        手动接入 Doris —— get_index_set_table_info_list(is_analysis=True)
        期望：is_doris=True + doris_table_id 有值 → 返回 Doris 条目，后缀 __analysis__
        """
        index_set = self._build_manual_doris_index_set()
        result = BaseIndexSetHandler.get_index_set_table_info_list(index_set, is_analysis=True)
        self.assertEqual(len(result), 2)
        for info in result:
            self.assertEqual(info["storage_type"], "doris")
            self.assertEqual(info["source_type"], "bkdata")
            self.assertTrue(info["table_id"].endswith(".__analysis__"))

    def test_manual_doris_sync_router_both(self):
        """
        手动接入 Doris —— sync_router 注册两次路由：
          - data_label=bklog_index_set_{id}           → Doris 条目（__doris__）
          - data_label=bklog_index_set_{id}_analysis   → Doris 条目（__analysis__）
        """
        index_set = self._build_manual_doris_index_set()
        append_calls = []

        def _capture_append(result_key, func, params=None, use_request=True, multi_func_params=False):
            append_calls.append((result_key, func, params))

        with patch("apps.utils.thread.MultiExecuteFunc.append", side_effect=_capture_append):
            with patch("apps.utils.thread.MultiExecuteFunc.run", return_value={}):
                BaseIndexSetHandler.sync_router(index_set)

        self.assertEqual(len(append_calls), 2)

        # 默认路由 → Doris（__doris__）
        key0, _, params0 = append_calls[0]
        self.assertEqual(key0, f"bklog_index_set_{index_set.index_set_id}")
        for info in params0["table_info"]:
            self.assertTrue(info["table_id"].endswith(".__doris__"))
            self.assertEqual(info["storage_type"], "doris")
            self.assertTrue(info["is_enable"])

        # Analysis 路由 → Doris（__analysis__）
        key1, _, params1 = append_calls[1]
        self.assertEqual(key1, f"bklog_index_set_{index_set.index_set_id}_analysis")
        for info in params1["table_info"]:
            self.assertTrue(info["table_id"].endswith(".__analysis__"))
            self.assertEqual(info["storage_type"], "doris")
            self.assertEqual(info["source_type"], "bkdata")
            self.assertTrue(info["is_enable"])

    # ==================================================================
    # 边界情况
    # ==================================================================

    def test_doris_table_info_no_doris_table_id(self):
        """
        有 Doris 标签但 doris_table_id 为空 —— 无论是否 analysis
        期望：返回空列表（不创建路由）
        """
        doris_tag_id = self._ensure_doris_tag()
        index_set = LogIndexSet.objects.create(
            index_set_name="doris_no_table",
            space_uid="bkcc__2",
            scenario_id=Scenario.BKDATA,
            tag_ids=[doris_tag_id],
            doris_table_id=None,
        )

        self.assertEqual(BaseIndexSetHandler.get_index_set_table_info_list(index_set, is_analysis=False), [])
        self.assertEqual(BaseIndexSetHandler.get_index_set_table_info_list(index_set, is_analysis=True), [])
