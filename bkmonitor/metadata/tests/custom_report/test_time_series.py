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
import datetime

import pytest

from metadata import models

pytestmark = pytest.mark.django_db
from metadata.models import AccessVMRecord

DEFAULT_GROUP_ID = 1
DEFAULT_TABLE_ID = "test_demo.__default__"


@pytest.fixture
def create_and_delete_records():
    models.TimeSeriesGroup.objects.create(
        bk_data_id=1,
        bk_biz_id=1,
        table_id=DEFAULT_TABLE_ID,
        is_split_measurement=True,
        time_series_group_id=DEFAULT_GROUP_ID,
    )
    models.TimeSeriesMetric.objects.bulk_create(
        [
            models.TimeSeriesMetric(
                **{
                    'group_id': DEFAULT_GROUP_ID,
                    'table_id': "test_demo.disk_usage",
                    'field_id': 1,
                    'field_name': 'disk_usage',
                    'tag_list': [
                        'disk_name',
                        'bk_target_ip',
                    ],
                }
            ),
            models.TimeSeriesMetric(
                **{
                    'group_id': DEFAULT_GROUP_ID,
                    'table_id': "test_demo.disk_usage1",
                    'field_id': 2,
                    'field_name': 'disk_usage1',
                    'tag_list': [
                        'disk_name',
                        'bk_target_ip',
                    ],
                }
            ),
            models.TimeSeriesMetric(
                **{
                    'group_id': DEFAULT_GROUP_ID,
                    'table_id': "test_demo.disk_usage2",
                    'field_id': 3,
                    'field_name': 'disk_usage2',
                    'tag_list': [
                        'disk_name',
                        'bk_target_ip',
                    ],
                }
            ),
        ]
    )
    access_vm_records = [
        AccessVMRecord(
            data_type=AccessVMRecord.BCS_CLUSTER_K8S,
            result_table_id="rt1",
            bcs_cluster_id="cluster1",
            storage_cluster_id=1,
            vm_cluster_id=1,
            bk_base_data_id=1,
            bk_base_data_name="data1",
            vm_result_table_id="rt1",
            remark="remark1"
        ),
        AccessVMRecord(
            data_type=AccessVMRecord.BCS_CLUSTER_K8S,
            result_table_id="rt1",
            bcs_cluster_id="cluster2",
            storage_cluster_id=2,
            vm_cluster_id=2,
            bk_base_data_id=2,
            bk_base_data_name="data2",
            vm_result_table_id="rt2",
            remark="remark2"
        ),
        AccessVMRecord(
            data_type=AccessVMRecord.ACCESS_VM,
            result_table_id="rt3",
            vm_cluster_id=3,
            bk_base_data_id=3,
            bk_base_data_name="data3",
            vm_result_table_id="rt3",
            remark="remark3"
        )
    ]
    AccessVMRecord.objects.bulk_create(access_vm_records)
    yield
    models.TimeSeriesGroup.objects.filter(table_id="test_demo.__default__").delete()
    models.TimeSeriesMetric.objects.filter(
        group_id=DEFAULT_GROUP_ID, field_name__in=["disk_usage", "disk_usage1", "disk_usage2"]
    ).delete()
    AccessVMRecord.objects.filter(id__in=[r.id for r in access_vm_records]).delete()


@pytest.mark.django_db(databases=["default", "monitor_api"])
def test_create_ts_metrics(create_and_delete_records):
    metric_info_list = [
        {
            "field_name": "disk_usage4",
            "tag_value_list": {
                "endpoint": {"last_update_time": 1701506528, "values": None},
            },
            "last_modify_time": 1701506528,
        }
    ]
    models.TimeSeriesMetric.bulk_refresh_ts_metrics(
        group_id=DEFAULT_GROUP_ID, table_id=DEFAULT_TABLE_ID, metric_info_list=metric_info_list, is_auto_discovery=True
    )
    assert models.TimeSeriesMetric.objects.filter(group_id=DEFAULT_GROUP_ID).count() == 4

    objs = models.TimeSeriesMetric.objects.filter(group_id=DEFAULT_GROUP_ID, field_name="disk_usage4")
    assert objs.exists()
    assert objs.get().last_modify_time.strftime("%Y-%m-%d") == datetime.datetime.now().strftime("%Y-%m-%d")


@pytest.mark.django_db(databases=["default", "monitor_api"])
def test_update_ts_metrics(create_and_delete_records):
    dt = datetime.datetime.now() + datetime.timedelta(days=2)
    curr_time = int(dt.timestamp())
    metric_info_list = [
        {
            "field_name": "disk_usage1",
            "tag_value_list": {
                "endpoint": {"last_update_time": curr_time, "values": None},
            },
            "last_modify_time": curr_time,
        }
    ]
    last_modify_time = models.TimeSeriesMetric.objects.get(
        group_id=DEFAULT_GROUP_ID, field_name="disk_usage1"
    ).last_modify_time
    assert last_modify_time.strftime("%Y-%m-%d") == datetime.datetime.now().strftime("%Y-%m-%d")
    models.TimeSeriesMetric.bulk_refresh_ts_metrics(
        group_id=DEFAULT_GROUP_ID, table_id=DEFAULT_TABLE_ID, metric_info_list=metric_info_list, is_auto_discovery=True
    )
    assert models.TimeSeriesMetric.objects.filter(group_id=DEFAULT_GROUP_ID).count() == 3

    objs = models.TimeSeriesMetric.objects.filter(group_id=DEFAULT_GROUP_ID, field_name="disk_usage1")
    assert objs.exists()
    assert objs.get().last_modify_time.strftime("%Y-%m-%d") == dt.strftime("%Y-%m-%d")


@pytest.mark.django_db(databases=["default", "monitor_api"])
def test_disable_ts_metrics(create_and_delete_records):
    dt = datetime.datetime.now() + datetime.timedelta(days=2)
    curr_time = int(dt.timestamp())
    metric_info_list = [
        {
            "field_name": "disk_usage1",
            "tag_value_list": {
                "endpoint": {"last_update_time": curr_time, "values": None},
            },
            "last_modify_time": curr_time,
            "is_active": False,
        }
    ]
    last_modify_time = models.TimeSeriesMetric.objects.get(
        group_id=DEFAULT_GROUP_ID, field_name="disk_usage1"
    ).last_modify_time
    assert last_modify_time.strftime("%Y-%m-%d") == datetime.datetime.now().strftime("%Y-%m-%d")
    models.TimeSeriesMetric.bulk_refresh_ts_metrics(
        group_id=DEFAULT_GROUP_ID, table_id=DEFAULT_TABLE_ID, metric_info_list=metric_info_list, is_auto_discovery=True
    )
    assert models.TimeSeriesMetric.objects.filter(group_id=DEFAULT_GROUP_ID).count() == 3

    objs = models.TimeSeriesMetric.objects.filter(group_id=DEFAULT_GROUP_ID, field_name="disk_usage1")
    assert objs.exists()
    assert objs.get().last_modify_time.strftime("%Y") == "1969"


@pytest.mark.django_db(databases=["default", "monitor_api"])
def test_delete_ts_metrics(create_and_delete_records):
    dt = datetime.datetime.now() + datetime.timedelta(days=2)
    curr_time = int(dt.timestamp())
    metric_info_list = [
        {
            "field_name": "disk_usage1",
            "tag_value_list": {
                "endpoint": {"last_update_time": curr_time, "values": None},
            },
            "last_modify_time": curr_time,
            "is_active": False,
        }
    ]
    last_modify_time = models.TimeSeriesMetric.objects.get(
        group_id=DEFAULT_GROUP_ID, field_name="disk_usage1"
    ).last_modify_time
    assert last_modify_time.strftime("%Y-%m-%d") == datetime.datetime.now().strftime("%Y-%m-%d")
    assert models.TimeSeriesMetric.objects.filter(group_id=DEFAULT_GROUP_ID).count() == 3
    models.TimeSeriesMetric.bulk_refresh_ts_metrics(
        group_id=DEFAULT_GROUP_ID, table_id=DEFAULT_TABLE_ID, metric_info_list=metric_info_list, is_auto_discovery=False
    )
    assert models.TimeSeriesMetric.objects.filter(group_id=DEFAULT_GROUP_ID).count() == 2

    objs = models.TimeSeriesMetric.objects.filter(group_id=DEFAULT_GROUP_ID, field_name="disk_usage1")
    assert not objs.exists()



@pytest.mark.django_db(databases=["default", "monitor_api"])
def test_return_more_than_one():
    from django.core.exceptions import MultipleObjectsReturned

    # Query the database to retrieve the test data
    records = AccessVMRecord.objects.filter(result_table_id="rt1")

    # Assert that there are more than one records
    assert records
    with pytest.raises(MultipleObjectsReturned):
        records = AccessVMRecord.objects.get(result_table_id="rt1")
        # 如果 相同 table id 没有抛出 MultipleObjectsReturned 失败
        assert records
