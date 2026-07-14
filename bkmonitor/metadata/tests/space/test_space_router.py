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
import logging
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from metadata import models
from metadata.models.space import ds_rt
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis
from metadata.task.tasks import push_and_publish_space_router

from .conftest import (
    DEFAULT_DATA_ID,
    DEFAULT_EVENT_ES_TABLE_ID,
    DEFAULT_LOG_ES_TABLE_ID,
    DEFAULT_TABLE_ID,
)

pytestmark = pytest.mark.django_db(databases="__all__")


def test_push_and_publish_space_router_returns_when_space_not_found(caplog):
    with (
        patch("metadata.task.tasks.models.Space.objects.get", side_effect=models.Space.DoesNotExist),
        patch("metadata.models.space.space_table_id_redis.SpaceTableIDRedis") as space_redis,
        caplog.at_level(logging.WARNING),
    ):
        push_and_publish_space_router(space_type="bkcc", space_id="not-exist")

    space_redis.assert_not_called()
    assert "space not found, space_type->[bkcc], space_id->[not-exist], skip" in caplog.text


def test_push_and_publish_space_router_does_not_fallback_empty_tenant():
    target_space = SimpleNamespace(bk_tenant_id="")
    with (
        patch("metadata.task.tasks.models.Space.objects.get", return_value=target_space),
        patch.object(SpaceTableIDRedis, "push_space_table_ids"),
        patch.object(SpaceTableIDRedis, "push_data_label_table_ids"),
        pytest.raises(ValueError, match="bk_tenant_id is required"),
    ):
        push_and_publish_space_router(
            space_type="bkcc",
            space_id="empty-tenant",
            table_id_list=["empty.tenant"],
        )


@pytest.mark.parametrize(
    "data_id_list, table_id_list, expected_data",
    [
        (None, None, {DEFAULT_TABLE_ID: DEFAULT_DATA_ID}),
        ([123], None, {}),
        (None, ["test.not_exist"], {}),
        ([DEFAULT_DATA_ID], None, {DEFAULT_TABLE_ID: DEFAULT_DATA_ID}),
        (None, [DEFAULT_TABLE_ID], {DEFAULT_TABLE_ID: DEFAULT_DATA_ID}),
        ([123], [DEFAULT_TABLE_ID], {}),
        ([DEFAULT_DATA_ID], ["test.not_exist"], {}),
        ([DEFAULT_DATA_ID], [DEFAULT_TABLE_ID], {DEFAULT_TABLE_ID: DEFAULT_DATA_ID}),
    ],
)
def test_get_result_tables_by_data_ids(create_and_delete_record, data_id_list, table_id_list, expected_data):
    assert ds_rt.get_result_tables_by_data_ids(data_id_list, table_id_list) == expected_data


def test_get_table_info_for_influxdb_and_vm(create_and_delete_record):
    data = ds_rt.get_table_info_for_influxdb_and_vm(bk_tenant_id="system", table_id_list=[DEFAULT_TABLE_ID])
    keys = ["cluster_name", "db", "measurement", "storage_id", "vm_rt", "tags_key", "storage_name", "storage_type"]
    assert set(keys) == set(data[DEFAULT_TABLE_ID].keys())

    data = ds_rt.get_table_info_for_influxdb_and_vm(bk_tenant_id="system", table_id_list=["test.not_exist"])
    assert not data


def test_compose_es_table_id_detail(create_and_delete_record):
    models.ClusterInfo.objects.update_or_create(
        cluster_id=1,
        defaults={
            "bk_tenant_id": "system",
            "cluster_name": "test_es",
            "cluster_type": models.ClusterInfo.TYPE_ES,
            "domain_name": "es.example.com",
            "port": 9200,
            "description": "",
            "is_default_cluster": False,
        },
    )
    with (
        patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis") as mock_hmset,
        patch("metadata.utils.redis_tools.RedisTools.publish"),
    ):
        SpaceTableIDRedis().push_table_id_detail(
            bk_tenant_id="system",
            table_id_list=[DEFAULT_LOG_ES_TABLE_ID, DEFAULT_EVENT_ES_TABLE_ID],
            is_publish=False,
        )

    data = {key: json.loads(value) for key, value in mock_hmset.call_args.args[1].items()}

    log_data = data[DEFAULT_LOG_ES_TABLE_ID]
    assert log_data["db"] == DEFAULT_LOG_ES_TABLE_ID.split(".")[0]

    event_table_id = f"{DEFAULT_EVENT_ES_TABLE_ID}.__default__"
    assert event_table_id in data
    event_data = data[event_table_id]
    assert event_data["db"] == DEFAULT_EVENT_ES_TABLE_ID

    # 校验必要 key 存在
    for key in ["db", "measurement", "storage_id"]:
        assert key in data[DEFAULT_LOG_ES_TABLE_ID]
        assert key in data[event_table_id]
