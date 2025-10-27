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
from django.core.management import call_command

from api.cmdb.define import Business
from metadata.models import DataSource, DataSourceResultTable, ResultTable
from metadata.models.space import Space, SpaceDataSource
from metadata.tests.commands.conftest import consul_client

pytestmark = pytest.mark.django_db(databases="__all__")
fake_creator = "system"
fake_biz_id = 123
fake_data_id = 2
fake_platform_data_id = 1001


@pytest.fixture
def create_and_delete_resource(mocker):
    mocker.patch("metadata.models.data_source.DataSource.delete_consul_config", return_value=True)
    # 创建结果表
    ResultTable.objects.create(
        table_id="rtdb.rtmeasurement",
        table_name_zh="test",
        is_custom_table=True,
        schema_type="fix",
        default_storage="influxDB",
        creator=fake_creator,
        last_modify_user=fake_creator,
        bk_biz_id=fake_biz_id,
    )
    # 平台级 0 业务
    ResultTable.objects.create(
        table_id="rtdb.rtmeasurement1",
        table_name_zh="test1",
        is_custom_table=True,
        schema_type="fix",
        default_storage="influxDB",
        creator=fake_creator,
        last_modify_user=fake_creator,
        bk_biz_id=0,
    )

    # 数据源信息
    all_ds = list(DataSource.objects.all())
    DataSource.objects.all().delete()
    DataSource.objects.create(
        bk_data_id=fake_data_id,
        data_name="t_test",
        mq_cluster_id=1,
        mq_config_id=1,
        is_custom_source=True,
        etl_config="bk_system_basereport",
    )
    DataSource.objects.create(
        bk_data_id=fake_platform_data_id,
        data_name="test_snapshot",
        mq_cluster_id=1,
        mq_config_id=1,
        is_custom_source=True,
        etl_config="bk_system_basereport",
    )

    # 数据源和结果表的关系
    DataSourceResultTable.objects.create(bk_data_id=fake_data_id, table_id="rtdb.rtmeasurement", creator=fake_creator)
    DataSourceResultTable.objects.create(
        bk_data_id=fake_platform_data_id, table_id="rtdb.rtmeasurement1", creator=fake_creator
    )
    yield
    DataSourceResultTable.objects.filter(table_id__in=["rtdb.rtmeasurement", "rtdb.rtmeasurement1"]).delete()
    ResultTable.objects.filter(table_id__in=["rtdb.rtmeasurement", "rtdb.rtmeasurement1"]).delete()
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
    DataSource.objects.all().delete()
    DataSource.objects.bulk_create(all_ds)
    Space.objects.all().delete()
    SpaceDataSource.objects.all().delete()


def test_sync_cmdb_space(mocker, create_and_delete_resource):
    # mocker cmdb biz
    mocker.patch(
        "core.drf_resource.api.cmdb.get_business", return_value=[Business(bk_biz_id=fake_biz_id, bk_biz_name="test")]
    )

    call_command("sync_cmdb_space")

    space_objs = Space.objects.all()
    # 校验有 123 业务空间
    assert len(space_objs) == 1
    assert {s.space_id for s in space_objs} == {str(fake_biz_id)}

    # 校验数据源中没有全业务的授权ID
    sd_objs = SpaceDataSource.objects.filter(space_id=fake_biz_id)
    assert not sd_objs.filter(from_authorization=True).exists()
    assert sd_objs.first().bk_data_id == 2

    # 校验平台级 data id
    ds_objs = DataSource.objects.filter(is_platform_data_id=True)
    assert ds_objs.exists()
    assert ds_objs.first().bk_data_id == fake_platform_data_id
