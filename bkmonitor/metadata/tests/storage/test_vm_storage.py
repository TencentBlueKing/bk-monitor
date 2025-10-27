"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import pytest

from metadata import models
from metadata.service.vm_storage import query_vm_datalink_all
from metadata.tests.common_utils import consul_client

pytestmark = pytest.mark.django_db(databases="__all__")


@pytest.fixture
def create_or_delete_records(mocker):
    data_source = models.DataSource.objects.create(
        bk_data_id=50010,
        data_name="data_link_test",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="test",
        is_custom_source=False,
        bk_tenant_id="system",
    )
    result_table = models.ResultTable.objects.create(
        table_id="1001_bkmonitor_time_series_50010.__default__",
        bk_biz_id=1001,
        is_custom_table=False,
        bk_tenant_id="system",
    )
    models.DataSourceResultTable.objects.create(
        bk_tenant_id="system",
        table_id="1001_bkmonitor_time_series_50010.__default__",
        bk_data_id=50010,
    )
    models.AccessVMRecord.objects.create(
        result_table_id="1001_bkmonitor_time_series_50010.__default__",
        vm_result_table_id="1001_vm_test_50010",
        bk_tenant_id="system",
        bk_base_data_id=50010,
        vm_cluster_id=111,
    )
    yield
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
    data_source.delete()
    result_table.delete()


def test_query_vm_datalink_all(create_or_delete_records):
    """
    测试查询VM数据链路
    """
    res = query_vm_datalink_all(bk_data_id=50010)
    expected = {
        "bk_data_id": 50010,
        "etl_config": "test",
        "is_enabled": True,
        "option": {},
        "result_table_list": [
            {
                "bk_base_data_id": 50010,
                "field_list": [],
                "option": {},
                "result_table": "1001_bkmonitor_time_series_50010.__default__",
                "schema_type": "",
            }
        ],
    }
    assert res == expected
