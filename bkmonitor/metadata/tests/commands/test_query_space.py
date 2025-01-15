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
import json
from io import StringIO

import pytest
from django.core.management import call_command

from metadata.models.data_source import DataSource
from metadata.models.space import Space, SpaceDataSource, SpaceResource
from metadata.tests.commands.conftest import consul_client

pytestmark = pytest.mark.django_db


@pytest.fixture
def create_and_delete_resource(mocker):
    # 创建资源
    Space.objects.create(space_type_id="bkcc", space_id="1", space_name="test")
    Space.objects.create(space_type_id="bcs", space_id="testproject", space_name="testprojectname")
    SpaceDataSource.objects.create(space_type_id="bkcc", space_id="1", bk_data_id=1)
    SpaceDataSource.objects.create(space_type_id="bcs", space_id="testproject", bk_data_id=1)
    SpaceResource.objects.create(
        space_type_id="bcs",
        space_id="testproject",
        resource_type="bkcc",
        resource_id="1",
        dimension_values=[{"bk_biz_id": "1"}],
    )
    SpaceResource.objects.create(
        space_type_id="bcs",
        space_id="testproject",
        resource_type="bcs",
        resource_id="testproject",
        dimension_values=[
            {"project_id": "testproject", "cluster_id": "test-cluster", "namespace": None},
            {"project_id": "testproject", "cluster_id": "shared-cluster", "namespace": "testns"},
        ],
    )
    DataSource.objects.create(
        bk_data_id=2,
        mq_cluster_id=1,
        mq_config_id=1,
        is_custom_source=True,
        etl_config="bk_system_basereport",
        is_platform_data_id=True,
    )
    yield
    Space.objects.all().delete()
    SpaceDataSource.objects.all().delete()
    SpaceResource.objects.all().delete()
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
    DataSource.objects.filter(bk_data_id=2).delete()


def test_query_space(create_and_delete_resource):
    # 执行到输出
    out = StringIO()
    call_command("query_space", "with_platform_data_id", **{"space_uid": ["bkcc__1"]}, stdout=out)
    output = out.getvalue()
    output = json.loads(output)

    # 校验逻辑
    assert output
    output_item = output[0]
    assert output_item["space_id"] == "1"
    assert "data_sources" in output_item
    # 添加平台级的 data id
    assert output_item["data_sources"]["platform_data_id_list"] == [1, 2]

    out = StringIO()
    call_command("query_space", **{"space_uid": ["bcs__testproject"]}, stdout=out)
    output = out.getvalue()
    output = json.loads(output)

    # 校验逻辑
    assert output
    output_item = output[0]
    assert output_item["space_id"] == "testproject"
    assert "data_sources" in output_item
    assert output_item["data_sources"] == [1, 2]
    assert "resources" in output_item
    assert len(output_item["resources"]) == 2

    # 不存在的资源
    out = StringIO()
    call_command("query_space", **{"space_uid": ["bcs__notfound"]}, stdout=out)
    output = out.getvalue()
    output = json.loads(output)
    assert isinstance(output, str)
