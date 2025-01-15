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

from metadata import models
from metadata.models.space.ds_rt import (
    compose_monitor_table_detail_for_bkbase_type,
    get_table_info_for_influxdb_and_vm,
)
from metadata.tests.common_utils import consul_client


@pytest.fixture
def create_or_delete_records(mocker):
    models.BkBaseResultTable.objects.create(
        monitor_table_id="1001_bkmonitor_time_series_50010.__default__",
        bkbase_data_name="bkm_data_link_test",
        bkbase_table_id="bkm_1001_bkmonitor_time_series_50010",
        storage_type=models.ClusterInfo.TYPE_VM,
        data_link_name="bkm_data_link_test",
        storage_cluster_id=100111,
    )
    models.AccessVMRecord.objects.create(
        result_table_id="1001_bkmonitor_time_series_50010.__default__",
        vm_cluster_id=100111,
        vm_result_table_id="bkm_1001_bkmonitor_time_series_50010",
        bk_base_data_id=50010,
    )

    models.ClusterInfo.objects.create(
        cluster_name="vm-plat",
        cluster_type=models.ClusterInfo.TYPE_VM,
        domain_name="test.domain.vm",
        port=9090,
        description="",
        cluster_id=100111,
        is_default_cluster=False,
        version="5.x",
    )
    yield
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
    models.BkBaseResultTable.objects.all().delete()
    models.ClusterInfo.objects.all().delete()


@pytest.mark.django_db(databases=["default", "monitor_api"])
def test_compose_monitor_table_detail_for_bkbase_type(create_or_delete_records):
    """
    测试新版BkBaseResultTable路由是否能够如期组装
    """

    # 旧版方式
    old_way_table_id_detail_res = get_table_info_for_influxdb_and_vm(
        table_id_list=['1001_bkmonitor_time_series_50010.__default__']
    )

    # 新版方式
    new_way_table_id_detail_res = compose_monitor_table_detail_for_bkbase_type(
        table_id_list=['1001_bkmonitor_time_series_50010.__default__']
    )

    expected = {
        '1001_bkmonitor_time_series_50010.__default__': {
            'vm_rt': 'bkm_1001_bkmonitor_time_series_50010',
            'storage_id': 100111,
            'cluster_name': '',
            'storage_name': 'vm-plat',
            'db': '',
            'measurement': "bk_split_measurement",
            'tags_key': [],
            'storage_type': 'victoria_metrics',
        }
    }
    assert old_way_table_id_detail_res == new_way_table_id_detail_res
    assert new_way_table_id_detail_res == expected
