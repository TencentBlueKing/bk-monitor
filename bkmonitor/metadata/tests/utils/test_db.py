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
from metadata.utils import db

DEFAULT_BCS_CLUSTER_ID_ONE = "BCS-K8S-10001"
DEFAULT_BCS_CLUSTER_ID_TWO = "BCS-K8S-10002"
DEFAULT_BIZ_ID = 1
DEFAULT_K8S_METRIC_DATA_ID_ONE = 101010
DEFAULT_K8S_METRIC_DATA_ID_TWO = 101011

pytestmark = pytest.mark.django_db


@pytest.fixture
def create_and_delete_record():
    models.BCSClusterInfo.objects.create(
        cluster_id=DEFAULT_BCS_CLUSTER_ID_ONE,
        bcs_api_cluster_id=DEFAULT_BCS_CLUSTER_ID_ONE,
        bk_biz_id=DEFAULT_BIZ_ID,
        project_id="test",
        domain_name="test",
        port=1001,
        server_address_path="test",
        api_key_content="test",
        K8sMetricDataID=DEFAULT_K8S_METRIC_DATA_ID_ONE,
    )
    models.BCSClusterInfo.objects.create(
        cluster_id=DEFAULT_BCS_CLUSTER_ID_TWO,
        bcs_api_cluster_id=DEFAULT_BCS_CLUSTER_ID_TWO,
        bk_biz_id=DEFAULT_BIZ_ID,
        project_id="test",
        domain_name="test",
        port=1001,
        server_address_path="test",
        api_key_content="test",
        K8sMetricDataID=DEFAULT_K8S_METRIC_DATA_ID_TWO,
    )
    yield
    models.BCSClusterInfo.objects.filter(
        cluster_id__in=[DEFAULT_BCS_CLUSTER_ID_ONE, DEFAULT_BCS_CLUSTER_ID_TWO]
    ).delete()


@pytest.mark.django_db(databases=["default", "monitor_api"])
def test_filter_model_by_page(create_and_delete_record):
    expect_cluster_id = [DEFAULT_BCS_CLUSTER_ID_ONE, DEFAULT_BCS_CLUSTER_ID_TWO]
    data = db.filter_model_by_in_page(
        models.BCSClusterInfo, "cluster_id__in", expect_cluster_id, page_size=1, value_func="values"
    )
    assert len(data) == 2
    assert {d["cluster_id"] for d in data} == set(expect_cluster_id)

    data = db.filter_model_by_in_page(
        models.BCSClusterInfo,
        "cluster_id__in",
        expect_cluster_id,
        page_size=1,
        value_func="values",
        value_field_list=["cluster_id"],
    )
    assert len(data) == 2
    keys = set()
    for d in data:
        keys = keys.union(set(d.keys()))

    assert keys == {"cluster_id"}

    data = db.filter_model_by_in_page(
        models.BCSClusterInfo,
        "cluster_id__in",
        expect_cluster_id,
        page_size=1,
        value_func="values_list",
        value_field_list=["cluster_id"],
    )
    assert set(data) == set(expect_cluster_id)

    data = db.filter_model_by_in_page(
        models.BCSClusterInfo,
        "cluster_id__in",
        expect_cluster_id,
    )
    assert len(data) == 2
    assert {d.cluster_id for d in data} == set(expect_cluster_id)
