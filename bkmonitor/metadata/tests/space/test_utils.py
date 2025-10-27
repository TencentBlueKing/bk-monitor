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

pytestmark = pytest.mark.django_db(databases="__all__")


@pytest.fixture
def create_or_delete_records(mocker):
    models.Space.objects.all().delete()
    models.SpaceResource.objects.all().delete()

    models.Space.objects.create(id=123456, space_type_id="bkci", space_id="test_space")
    models.Space.objects.create(id=123457, space_type_id="bksaas", space_id="test_saas")
    models.SpaceResource.objects.create(
        space_type_id="bkci",
        space_id="test_space",
        resource_type="bkcc",
        resource_id="2",
    )
    yield
    models.Space.objects.filter(id__in=[-123456, -123457]).delete()
    models.SpaceResource.objects.filter(
        space_type_id="bkci", space_id="test_space", resource_type="bkcc", resource_id="2"
    ).delete()


@pytest.mark.django_db(databases="__all__")
def test_get_negative_space_related_info(create_or_delete_records):
    bkci_info = utils.get_negative_space_related_info(negative_biz_id=-123456)
    assert bkci_info["space_type"] == "bkci"
    assert bkci_info["space_id"] == "test_space"
    assert bkci_info["bk_biz_id"] == "2"
    assert bkci_info["negative_biz_id"] == -123456

    bksaas_info = utils.get_negative_space_related_info(negative_biz_id=-123457)
    assert bksaas_info["space_type"] == "bksaas"
    assert bksaas_info["space_id"] == "test_saas"
    assert bksaas_info["bk_biz_id"] is None
    assert bksaas_info["negative_biz_id"] == -123457

    with pytest.raises(ValueError):
        utils.get_negative_space_related_info(negative_biz_id=-123456789)


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
    models.SpaceResource.objects.filter(space_type_id=DEFAULT_SPACE_TYPE, space_id=DEFAULT_SPACE_ID).delete()
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


def test_filter_space_resource(create_and_delete_record):
    spaces = [(DEFAULT_SPACE_TYPE, DEFAULT_SPACE_ID)]
    space_resource_data = utils._filter_space_resource_by_page(spaces)
    expected_key = (DEFAULT_SPACE_TYPE, DEFAULT_SPACE_ID)
    print(space_resource_data)
    assert set(space_resource_data.keys()) == {expected_key}
    assert isinstance(space_resource_data[expected_key], list)
