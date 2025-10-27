"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json

import pytest

from metadata import models
from metadata.management.commands.sync_bklog_es_router import Command

pytestmark = pytest.mark.django_db(databases="__all__")


def test_query_bklog_es_router(mocker):
    space_type, space_id = "bkcc", "2"
    es_router = {
        "total": 2100,
        "list": [
            {
                "cluster_id": 4,
                "index_set": "2_bklog.test20240611,2_bklog.test_nginx_stdout",
                "source_type": "log",
                "data_label": "log_index_set_290",
                "table_id": "2_bklog.test20240611,2_bklog.test_nginx_stdout",
                "space_uid": f"{space_type}__{space_id}",
            },
            {
                "cluster_id": 22,
                "index_set": "2_bkapm_trace_test_*",
                "source_type": "es",
                "data_label": "es_index_set_285",
                "table_id": "bklog_index_set_285.__default__",
                "space_uid": f"{space_type}__{space_id}",
            },
        ],
    }
    mocker.patch("core.drf_resource.api.log_search.list_es_router", return_value=es_router)

    cmd = Command()
    data_queue = cmd._list_es_router()
    assert data_queue.qsize() == 3

    all_data = []
    while not data_queue.empty():
        data = data_queue.get()
        all_data.extend(data)

    assert len(all_data) == 6
    assert {d["space_uid"] for d in all_data} == {f"{space_type}__{space_id}"}


def test_update_or_create_es_router():
    space_type, space_id = "bkcc", "2"
    es_router = [
        {
            "cluster_id": 4,
            "index_set": "2_bklog.test20240611,2_bklog.test_nginx_stdout",
            "source_type": "log",
            "data_label": "log_index_set_290",
            "table_id": "2_bklog.test20240611",
            "space_uid": f"{space_type}__{space_id}",
            "options": [
                {
                    "name": "demo",
                    "value_type": "dict",
                    "value": json.dumps({"name": "test1", "type": "time", "unit": "millisecond"}),
                }
            ],
        },
        {
            "cluster_id": 22,
            "index_set": "2_bkapm_trace_test_*",
            "source_type": "es",
            "data_label": "es_index_set_285",
            "table_id": "bklog_index_set_285.__default__",
            "space_uid": f"{space_type}__{space_id}",
        },
    ]
    cmd = Command()
    cmd._update_or_create_es_data(es_router)

    # 比对数量
    assert (
        models.ResultTable.objects.filter(
            table_id__in=["bklog_index_set_285.__default__", "2_bklog.test20240611"]
        ).count()
        == 2
    )
    assert (
        models.ESStorage.objects.filter(
            table_id__in=["bklog_index_set_285.__default__", "2_bklog.test20240611"]
        ).count()
        == 2
    )
    assert (
        models.ResultTableOption.objects.filter(
            table_id__in=[["bklog_index_set_285.__default__", "2_bklog.test20240611"]]
        ).count()
        == 1
    )
