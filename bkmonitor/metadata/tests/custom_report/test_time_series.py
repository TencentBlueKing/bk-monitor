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
    yield
    models.TimeSeriesGroup.objects.filter(table_id="test_demo.__default__").delete()
    models.TimeSeriesMetric.objects.filter(
        group_id=DEFAULT_GROUP_ID, field_name__in=["disk_usage", "disk_usage1", "disk_usage2"]
    ).delete()


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
