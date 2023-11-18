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
from metadata.models.space import utils

from .conftest import (
    DEFAULT_BCS_CLUSTER_ID_ONE,
    DEFAULT_BCS_CLUSTER_ID_TWO,
    DEFAULT_CREATOR,
    DEFAULT_K8S_METRIC_DATA_ID_ONE,
    DEFAULT_K8S_METRIC_DATA_ID_TWO,
    DEFAULT_SPACE_ID,
    DEFAULT_SPACE_TYPE,
)

pytestmark = pytest.mark.django_db


def test_authorize_data_id_list():
    """测试授权数据源"""
    test_data_id = 109011
    utils.authorize_data_id_list(DEFAULT_SPACE_TYPE, DEFAULT_SPACE_ID, [test_data_id])

    # 检测资源授权
    assert models.SpaceDataSource.objects.filter(
        space_type_id=DEFAULT_SPACE_TYPE, space_id=DEFAULT_SPACE_ID, bk_data_id=test_data_id
    ).exists()


def test_create_bksaas_space_resource(create_and_delete_record, mocker):
    """测试创建蓝鲸应用类型关联的空间资源"""
    api_resp = [
        {"bcs_cluster_id": DEFAULT_BCS_CLUSTER_ID_ONE, "namespace": "bkapp-test-m-stag"},
        {"bcs_cluster_id": DEFAULT_BCS_CLUSTER_ID_TWO, "namespace": "bkapp-test-m-prod"},
    ]
    mocker.patch("core.drf_resource.api.bk_paas.get_app_cluster_namespace", return_value=api_resp)
    utils.create_bksaas_space_resource(DEFAULT_SPACE_TYPE, DEFAULT_SPACE_ID, DEFAULT_CREATOR)

    # 检测数据源已经授权
    assert models.SpaceDataSource.objects.filter(
        space_type_id=DEFAULT_SPACE_TYPE,
        space_id=DEFAULT_SPACE_ID,
        bk_data_id__in=[DEFAULT_K8S_METRIC_DATA_ID_ONE, DEFAULT_K8S_METRIC_DATA_ID_TWO],
    ).exists()
    # 检测资源存在
    objs = models.SpaceResource.objects.filter(
        space_type_id=DEFAULT_SPACE_TYPE, space_id=DEFAULT_SPACE_ID, resource_id=DEFAULT_SPACE_ID
    )
    real_clusters = []
    for obj in objs:
        dimension_values = obj.dimension_values
        for dv in dimension_values:
            real_clusters.append(dv["cluster_id"])
            # 测试命名空间必须为列表
            assert isinstance(dv["namespace"], list)

    assert set(real_clusters) == {DEFAULT_BCS_CLUSTER_ID_ONE, DEFAULT_BCS_CLUSTER_ID_TWO}
