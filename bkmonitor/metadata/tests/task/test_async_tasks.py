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
from metadata.task.tasks import _check_and_delete_ds_consul_config
from metadata.tests.common_utils import consul_client


@pytest.fixture
def create_or_delete_records(mocker):
    data_source = models.DataSource.objects.create(
        bk_data_id=50010,
        data_name="data_link_test",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="test",
        is_custom_source=False,
        created_from='bkdata',
    )
    yield
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
    data_source.delete()


@pytest.mark.django_db(databases=["default", "monitor_api"])
def test_check_and_delete_ds_consul_config(create_or_delete_records, mocker):
    """
    测试检查并删除 Consul 配置
    """
    # Mock HashConsul 类
    mock_hash_consul = mocker.patch("metadata.task.tasks.consul_tools.HashConsul", autospec=True)

    # Mock get 和 delete 方法
    mock_get = mock_hash_consul.return_value.get
    mock_delete = mock_hash_consul.return_value.delete

    # 获取测试数据源
    data_source = models.DataSource.objects.get(bk_data_id=50010)

    # 场景 1: Consul 配置存在
    mock_get.return_value = (
        '9605173687',
        {'Key': data_source.consul_config_path, 'Value': b'{"some_key": "some_value"}'},
    )

    _check_and_delete_ds_consul_config(data_source=data_source)

    # 验证 get 和 delete 方法是否被调用
    mock_get.assert_called_once_with(data_source.consul_config_path)
    mock_delete.assert_called_once_with(data_source.consul_config_path)

    # 场景 2: Consul 配置不存在
    mock_get.reset_mock()
    mock_delete.reset_mock()

    mock_get.return_value = ('123456', None)  # 模拟配置不存在

    _check_and_delete_ds_consul_config(data_source=data_source)

    mock_get.assert_called_once_with(data_source.consul_config_path)
    mock_delete.assert_not_called()

    # 场景 3: 非 bkdata 来源
    data_source.created_from = "other_source"
    data_source.save()

    mock_get.reset_mock()
    mock_delete.reset_mock()

    _check_and_delete_ds_consul_config(data_source=data_source)

    mock_get.assert_not_called()
    mock_delete.assert_not_called()
