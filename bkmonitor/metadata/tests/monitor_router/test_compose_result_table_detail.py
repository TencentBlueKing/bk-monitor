"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import pytest

from metadata import models
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis


@pytest.fixture
def create_or_delete_records(mocker):
    models.ESStorage.objects.create(table_id="1001_bklog.stdout", storage_cluster_id=11)
    models.ResultTable.objects.create(
        table_id="1001_bklog.stdout",
        table_name_zh="stdout",
        data_label="bklog_index_set_1001",
        is_custom_table=False,
    )

    # 日志链路必备的两个查询Option： need_add_time & time_field
    models.ResultTableOption.objects.create(
        table_id="1001_bklog.stdout", name="need_add_time", value_type="bool", value="true"
    )
    models.ResultTableOption.objects.create(
        table_id="1001_bklog.stdout",
        name="time_field",
        value_type="dict",
        value='{"name": "dtEventTimeStamp", "type": "date", "unit": "millisecond"}',
    )

    # 创建一些字段查询别名
    models.ESFieldQueryAliasOption.objects.create(
        table_id="1001_bklog.stdout", field_path="__ext.pod_name", query_alias="pod_name", is_deleted=False
    )
    models.ESFieldQueryAliasOption.objects.create(
        table_id="1001_bklog.stdout", field_path="__ext.pod_ip", query_alias="pod_ip", is_deleted=False
    )
    models.ESFieldQueryAliasOption.objects.create(
        table_id="1001_bklog.stdout",
        field_path="__ext.container_name",
        query_alias="container_name",
        is_deleted=True,  # 软删除的别名不会出现
    )
    yield
    models.ESStorage.objects.filter(table_id="1001_bklog.stdout").delete()
    models.ResultTable.objects.filter(table_id="1001_bklog.stdout").delete()
    models.ResultTableOption.objects.filter(table_id="1001_bklog.stdout").delete()
    models.ESFieldQueryAliasOption.objects.filter(table_id="1001_bklog.stdout").delete()


@pytest.mark.django_db(databases="__all__")
def test_compose_es_table_detail(create_or_delete_records):
    """
    测试生成ES结果表详情路由
    """
    client = SpaceTableIDRedis()
    res = client._compose_es_table_id_detail(table_id_list=["1001_bklog.stdout"])
    expected = {
        "1001_bklog.stdout": {
            "storage_id": 11,
            "db": None,
            "measurement": "__default__",
            "source_type": "log",
            "options": {
                "need_add_time": True,
                "time_field": {"name": "dtEventTimeStamp", "type": "date", "unit": "millisecond"},
            },
            "storage_type": "elasticsearch",
            "storage_cluster_records": [],
            "data_label": "bklog_index_set_1001",
            "field_alias": {
                "pod_name": "__ext.pod_name",
                "pod_ip": "__ext.pod_ip",
            },
        }
    }

    assert res == expected
