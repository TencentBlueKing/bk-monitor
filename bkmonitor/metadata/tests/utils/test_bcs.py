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
from metadata.models import BCSClusterInfo, SpaceDataSource
from metadata.utils.bcs import get_bcs_space_by_biz, get_bcs_dataids

pytestmark = pytest.mark.django_db

FAKE_PROJECT_ID = "testbcs"


@pytest.fixture
def create_or_delete_records():
    # 创建模拟数据
    space_records = [
        models.Space(id=1, space_type_id="bkcc", space_name="bkccname", space_id="1", space_code=""),
        models.Space(id=2, space_type_id="bkci", space_name="testbkci", space_id="testbkci", space_code=""),
        models.Space(id=3, space_type_id="bkci", space_name="testbcs1", space_id="testbcs1",
                     space_code=FAKE_PROJECT_ID),
    ]
    models.Space.objects.bulk_create(space_records)

    bcs_cluster_infos = [
        models.BCSClusterInfo(cluster_id="BCS-K8S-00000",port=1,bk_biz_id=1,CustomMetricDataID=1001,K8sMetricDataID=1002),
        models.BCSClusterInfo(cluster_id="BCS-K8S-00001",port=1,bk_biz_id=2,CustomMetricDataID=1003,K8sMetricDataID=1004),
        models.BCSClusterInfo(cluster_id="BCS-K8S-00002",port=1,bk_biz_id=3,CustomMetricDataID=1005,K8sMetricDataID=1006),
    ]
    models.BCSClusterInfo.objects.bulk_create(bcs_cluster_infos)

    space_data_sources = [
        models.SpaceDataSource(space_type_id='bkcc', space_id=1,bk_data_id=1001),
        models.SpaceDataSource(space_type_id='bkcc', space_id=1, bk_data_id=1002),
        models.SpaceDataSource(space_type_id='bkcc', space_id=1, bk_data_id=1009),
        models.SpaceDataSource(space_type_id='bkcc', space_id=1, bk_data_id=1010),
        models.SpaceDataSource(space_type_id='bkcc', space_id=1, bk_data_id=1003),
    ]
    models.SpaceDataSource.objects.bulk_create(space_data_sources)

    yield

    # 清理数据
    models.Space.objects.all().delete()
    models.BCSClusterInfo.objects.all().delete()
    models.SpaceDataSource.objects.all().delete()


@pytest.mark.parametrize(
    "bk_biz_ids, expected_list",
    [
        ([], []),
        (None, []),
        ([-2, -3], [{"space_type_id": "bkci", "space_id": "testbcs1", "space_code": FAKE_PROJECT_ID}]),
        ([0, 1], []),
        ([-2, 0, 1], []),
        ([-3, 0, 1], [{"space_type_id": "bkci", "space_id": "testbcs1", "space_code": FAKE_PROJECT_ID}]),
    ],
)
@pytest.mark.django_db(databases=['default', 'monitor_api'])
def test_get_project_ids(create_or_delete_records, bk_biz_ids, expected_list):
    space = get_bcs_space_by_biz(bk_biz_ids)
    assert space == expected_list


@pytest.mark.django_db(databases=['default', 'monitor_api'])
def test_get_bcs_dataids(create_or_delete_records):
    bk_biz_ids = [1]
    mode = 'custom'
    data_ids, data_id_cluster_map = get_bcs_dataids(bk_biz_ids=bk_biz_ids, mode=mode)
    assert data_ids == {1001,1003}
    assert data_id_cluster_map == {1001: "BCS-K8S-00000", 1003: "BCS-K8S-00001",'built_in_metric_data_id_list': []}

    mode = 'k8s'
    data_ids, data_id_cluster_map = get_bcs_dataids(bk_biz_ids=bk_biz_ids, mode=mode)
    assert data_ids == {1002}
    assert data_id_cluster_map == {1002: "BCS-K8S-00000",'built_in_metric_data_id_list': [1002]}

    mode = 'both'
    data_ids, data_id_cluster_map = get_bcs_dataids(bk_biz_ids=bk_biz_ids, mode=mode)
    assert data_ids == {1001,1002,1003}
    assert data_id_cluster_map == {1001: "BCS-K8S-00000", 1002: "BCS-K8S-00000", 1003: "BCS-K8S-00001",'built_in_metric_data_id_list': [1002]}
