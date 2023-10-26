# -*- coding: utf-8 -*-
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
from django.core.management import call_command

from metadata import models
from metadata.tests.commands.conftest import (
    DEFAULT_DATA_ID,
    DEFAULT_INFLUXDB_CLUSTER_ID,
    DEFAULT_NAME,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def clean_records():
    yield
    models.DataSourceResultTable.objects.filter(table_id__startswith="dbm").delete()
    models.ResultTable.objects.filter(table_id__startswith="dbm").delete()
    models.ResultTableField.objects.filter(table_id__startswith="dbm").delete()
    models.ResultTableFieldOption.objects.filter(table_id__startswith="dbm").delete()
    models.ResultTableOption.objects.filter(table_id__startswith="dbm").delete()
    models.InfluxDBStorage.objects.filter(table_id__startswith="dbm").delete()
    models.SpaceDataSource.objects.filter(space_type_id="bkcc").delete()


def test_add_extend_dimensions(create_and_delete_record, mocker, clean_records):
    assert models.ResultTable.objects.filter(table_id=DEFAULT_NAME).exists()

    class ReturnResult:
        @property
        def status_code(self):
            return 204

    mocker.patch("requests.post", return_value=ReturnResult())
    mocker.patch("metadata.models.data_source.DataSource.refresh_outer_config", return_value=None)
    mocker.patch("metadata.models.storage.InfluxDBStorage.push_redis_data", return_value=None)
    mocker.patch("celery.app.task.Task.delay", return_value=True)
    call_command(
        "add_extend_dimensions",
        bk_data_id=DEFAULT_DATA_ID,
        proxy_cluster_id=DEFAULT_INFLUXDB_CLUSTER_ID,
        cluster_name=DEFAULT_NAME,
    )

    # 判断新的结果表存在
    assert models.ResultTable.objects.filter(table_id=f"dbm_{DEFAULT_NAME}").exists()
    # 判断添加的字段存在
    check_field_name = ["app", "appid"]
    for f in check_field_name:
        assert models.ResultTableField.objects.filter(field_name=f).exists()
    # 判断 option 存在
    check_option_name = ["enable_dbm_meta", "must_include_dimensions", "mapping_result_table"]
    for o in check_option_name:
        assert models.ResultTableOption.objects.filter(name=o).exists()
    # 判断 option 的映射
    assert models.ResultTableOption.objects.get(name="mapping_result_table").value == DEFAULT_NAME
