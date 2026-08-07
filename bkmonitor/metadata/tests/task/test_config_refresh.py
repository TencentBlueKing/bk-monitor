"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
from unittest.mock import call

import pytest
from mockredis.redis import mock_redis_client

from metadata import config
from metadata.task.config_refresh import _refresh_storage_config, clean_datasource_from_consul
from metadata.tests.conftest import HashConsulMocker
from metadata.tools.constants import TASK_FINISHED_FAILURE, TASK_FINISHED_SUCCESS, TASK_STARTED

from .conftest import DEFAULT_BK_DATA_ID, DEFAULT_TRANSFER_CLUSTER_ID

pytestmark = pytest.mark.django_db(databases="__all__")


def test_refresh_storage_config_reports_success_for_single_backend(mocker):
    metrics = mocker.patch("metadata.task.config_refresh.metrics")
    refresher = mocker.Mock()
    mocker.patch("metadata.task.config_refresh.time.time", side_effect=[100, 102])

    _refresh_storage_config("refresh_consul_storage", "consul", refresher)

    refresher.assert_called_once_with()
    assert metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels.call_args_list == [
        call(task_name="refresh_consul_storage", status=TASK_STARTED, process_target=None),
        call(task_name="refresh_consul_storage", status=TASK_FINISHED_SUCCESS, process_target=None),
    ]
    metrics.METADATA_CRON_TASK_COST_SECONDS.labels.assert_called_once_with(
        task_name="refresh_consul_storage", process_target=None
    )


def test_refresh_storage_config_reports_failure_for_single_backend(mocker):
    metrics = mocker.patch("metadata.task.config_refresh.metrics")
    refresher = mocker.Mock(side_effect=ValueError("unavailable"))
    mocker.patch("metadata.task.config_refresh.time.time", side_effect=[100, 102])

    with pytest.raises(RuntimeError, match="metadata redis storage config refresh failed"):
        _refresh_storage_config("refresh_redis_storage", "redis", refresher)

    assert metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels.call_args_list == [
        call(task_name="refresh_redis_storage", status=TASK_STARTED, process_target=None),
        call(task_name="refresh_redis_storage", status=TASK_FINISHED_FAILURE, process_target=None),
    ]


def test_clean_datasource(create_and_delete_record, mocker):
    """测试删除 consul 中不存在的数据源信息"""
    mock_hash_consul = HashConsulMocker()
    key_tmpl = f"{config.CONSUL_PATH}/v1/{DEFAULT_TRANSFER_CLUSTER_ID}/data_id/"
    # 创建两条记录
    deleted_path = f"{key_tmpl}110041"
    mock_hash_consul.put(f"{key_tmpl}{DEFAULT_BK_DATA_ID}", json.dumps({"bk_data_id": DEFAULT_BK_DATA_ID}))
    mock_hash_consul.put(deleted_path, json.dumps({"bk_data_id": 110041}))

    mocker.patch("metadata.utils.consul_tools.HashConsul", return_value=mock_hash_consul)
    mocker.patch("alarm_backends.core.storage.redis.Cache.__new__", return_value=mock_redis_client())

    clean_datasource_from_consul()

    # 判断数据是否存在
    assert mock_hash_consul.get(deleted_path)[1] is None
    assert (
        json.loads(mock_hash_consul.get(f"{key_tmpl}{DEFAULT_BK_DATA_ID}")[1]["Value"])["bk_data_id"]
        == DEFAULT_BK_DATA_ID
    )


def test_clean_transfer_cluster(create_and_delete_record, mocker):
    """测试没有使用的 transfer 集群，以便于处理掉其下的数据源"""
    mock_hash_consul = HashConsulMocker()
    key_tmpl = f"{config.CONSUL_PATH}/v1/{DEFAULT_TRANSFER_CLUSTER_ID}/data_id/"
    # 创建两条记录
    deleted_path = f"{config.CONSUL_PATH}/v1/not-used-transfer/data_id/110041"
    mock_hash_consul.put(f"{key_tmpl}{DEFAULT_BK_DATA_ID}", json.dumps({"bk_data_id": DEFAULT_BK_DATA_ID}))
    mock_hash_consul.put(deleted_path, json.dumps({"bk_data_id": 110041}))

    mocker.patch("metadata.utils.consul_tools.HashConsul", return_value=mock_hash_consul)
    mocker.patch("alarm_backends.core.storage.redis.Cache.__new__", return_value=mock_redis_client())

    clean_datasource_from_consul()

    # 判断数据是否存在
    assert mock_hash_consul.list(f"{config.CONSUL_PATH}/v1/not-used-transfer")[1] is None
    assert mock_hash_consul.get(deleted_path)[1] is None
    assert (
        json.loads(mock_hash_consul.get(f"{key_tmpl}{DEFAULT_BK_DATA_ID}")[1]["Value"])["bk_data_id"]
        == DEFAULT_BK_DATA_ID
    )
