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
from metadata.task.tasks import _refresh_data_link_status


@pytest.fixture
def create_or_delete_records(mocker):
    models.BkBaseResultTable.objects.create(
        data_link_name='bkm_test_data_link',
        bkbase_data_name='bkm_test_data_link',
        storage_type='victoria_metrics',
        monitor_table_id='1001_bkm_time_series_test.__default__',
        storage_cluster_id=11,
        status='creating',
        bkbase_table_id='2_bkm_1001_bkm_time_series_test',
        bkbase_rt_name='bkm_test_rt',
    )

    models.DataLink.objects.create(
        data_link_name='bkm_test_data_link',
        namespace='bkmonitor',
        data_link_strategy='bk_standard_v2_time_series',
    )

    models.DataIdConfig.objects.create(namespace='bkmonitor', name='bkm_test_data_link')
    models.VMResultTableConfig.objects.create(
        namespace='bkmonitor', status='creating', data_link_name='bkm_test_data_link', name='bkm_test_rt'
    )
    models.VMStorageBindingConfig.objects.create(
        namespace='bkmonitor',
        name='bkm_test_rt',
        status='creating',
        data_link_name='bkm_test_data_link',
    )
    models.DataBusConfig.objects.create(
        namespace='bkmonitor',
        name='bkm_test_rt',
        data_link_name='bkm_test_data_link',
        status='creating',
    )
    yield
    models.DataLink.objects.filter(data_link_name='bkm_test_data_link').delete()
    models.DataIdConfig.objects.filter(name='bkm_test_data_link').delete()
    models.VMResultTableConfig.objects.filter(name='bkm_test_rt').delete()
    models.VMStorageBindingConfig.objects.filter(name='bkm_test_rt').delete()
    models.DataBusConfig.objects.filter(name='bkm_test_rt').delete()
    models.BkBaseResultTable.objects.filter(bkbase_rt_name='bkm_test_rt').delete()


@pytest.mark.django_db(databases=["default", "monitor_api"])
def test_refresh_data_link_status(create_or_delete_records):
    bkbase_rt_record = models.BkBaseResultTable.objects.get(data_link_name='bkm_test_data_link')
    data_link_name = bkbase_rt_record.data_link_name
    bkbase_rt_name = bkbase_rt_record.bkbase_rt_name
    _refresh_data_link_status(bkbase_rt_record=bkbase_rt_record)

    assert models.DataIdConfig.objects.get(name=data_link_name).status == 'Failed'
    assert models.VMResultTableConfig.objects.get(name=bkbase_rt_name).status == 'Failed'
    assert models.VMStorageBindingConfig.objects.get(name=bkbase_rt_name).status == 'Failed'
    assert models.DataBusConfig.objects.get(name=bkbase_rt_name).status == 'Failed'
    assert models.BkBaseResultTable.objects.get(data_link_name=data_link_name).status == 'Pending'
