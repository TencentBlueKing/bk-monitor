"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from types import SimpleNamespace
from typing import Any

import pytest

from apm.core.handlers.profile.active_profiling import CONSUL_PATH_PREFIX, ActiveProfilingConsulHandler
from apm.models import ProfileDataSource
from apm.resources import EnableActiveProfilingResource
from constants.apm import BUILTIN_EVENT_GROUP_LABEL, BUILTIN_EVENT_GROUP_NAME, BUILTIN_PROFILING_APP_NAME
from metadata.models import DataSource

HANDLER_MODULE = "apm.core.handlers.profile.active_profiling"


@pytest.fixture
def enable_apis(mocker):
    mocker.patch("apm.resources.get_request_username", return_value="admin")
    mocks = {
        name: mocker.patch(f"core.drf_resource.resource.metadata.{name}", return_value=return_value)
        for name, return_value in [
            ("query_event_group", []),
            ("query_data_source", {"bk_data_id": 1001}),
            ("create_data_id", {"bk_data_id": 1002}),
            ("create_event_group", {"event_group_id": 555}),
        ]
    }
    mocks["apply_datasource"] = mocker.patch.object(ProfileDataSource, "apply_datasource")
    mocks["refresh_consul"] = mocker.patch("apm.resources.refresh_active_profiling_consul_config.delay")
    return mocks


def test_enable_creates_builtin_profiling_datasource_and_event_group(enable_apis):
    enable_apis["query_data_source"].side_effect = DataSource.DoesNotExist

    assert EnableActiveProfilingResource().request({"bk_biz_id": 2}) is None

    enable_apis["apply_datasource"].assert_called_once_with(
        bk_biz_id=2, app_name=BUILTIN_PROFILING_APP_NAME, option=True
    )
    assert enable_apis["create_data_id"].call_args.kwargs["data_name"] == f"2_{BUILTIN_EVENT_GROUP_NAME}"
    enable_apis["create_event_group"].assert_called_once_with(
        operator="admin",
        bk_data_id=1002,
        bk_biz_id=2,
        event_group_name=BUILTIN_EVENT_GROUP_NAME,
        label=BUILTIN_EVENT_GROUP_LABEL,
        data_label=BUILTIN_EVENT_GROUP_NAME,
    )
    enable_apis["refresh_consul"].assert_called_once_with(2)


def test_enable_skips_existing_event_group(enable_apis):
    enable_apis["query_event_group"].return_value = [{"event_group_id": 555}]

    assert EnableActiveProfilingResource().request({"bk_biz_id": 2}) is None

    enable_apis["query_data_source"].assert_not_called()
    enable_apis["create_data_id"].assert_not_called()
    enable_apis["create_event_group"].assert_not_called()
    enable_apis["refresh_consul"].assert_called_once_with(2)


def test_enable_reuses_existing_event_data_id(enable_apis):
    EnableActiveProfilingResource().request({"bk_biz_id": 2})

    enable_apis["create_data_id"].assert_not_called()
    assert enable_apis["create_event_group"].call_args.kwargs["bk_data_id"] == 1001


class FakeQuerySet(list):
    def values(self, *fields: str) -> "FakeQuerySet":
        return FakeQuerySet({field: row[field] for field in fields} for row in self)

    def values_list(self, *fields: str, flat: bool = False) -> "FakeQuerySet":
        if flat:
            return FakeQuerySet(row[fields[0]] for row in self)
        return FakeQuerySet(tuple(row[field] for field in fields) for row in self)


@pytest.fixture
def consul_rows(mocker):
    """业务 2 已开通且 DataID 启用；业务 3 的事件分组 DataID 已停用"""
    rows: dict[str, list[Any]] = {
        "profiles": [{"bk_biz_id": 2}, {"bk_biz_id": 3}],
        "event_groups": [
            {"bk_tenant_id": "system", "bk_biz_id": 2, "bk_data_id": 1001},
            {"bk_tenant_id": "system", "bk_biz_id": 3, "bk_data_id": 1002},
        ],
        "data_sources": [{"bk_data_id": 1001, "mq_cluster_id": 9}],
        "topics": [{"bk_data_id": 1001, "topic": "topic_1001"}],
        "clusters": [SimpleNamespace(cluster_id=9, domain_name="kafka.local", port=9092, username="u", password="p")],
    }
    filters = {
        "profiles": mocker.patch.object(ProfileDataSource.objects, "filter"),
        "event_groups": mocker.patch(f"{HANDLER_MODULE}.EventGroup.objects.filter"),
        "data_sources": mocker.patch(f"{HANDLER_MODULE}.DataSource.objects.filter"),
        "topics": mocker.patch(f"{HANDLER_MODULE}.KafkaTopicInfo.objects.filter"),
        "clusters": mocker.patch(f"{HANDLER_MODULE}.ClusterInfo.objects.filter"),
    }
    for name, patched in filters.items():
        patched.side_effect = lambda *args, _name=name, **kwargs: FakeQuerySet(rows[_name])

    hash_consul = mocker.patch(f"{HANDLER_MODULE}.consul_tools.HashConsul").return_value
    hash_consul.list_keys.return_value = (1, [])
    return SimpleNamespace(rows=rows, filters=filters, consul=hash_consul)


def test_check_update_puts_enabled_data_ids_and_deletes_stale_keys(consul_rows):
    consul_rows.consul.list_keys.return_value = (
        1,
        [f"{CONSUL_PATH_PREFIX}1001", f"{CONSUL_PATH_PREFIX}1002", f"{CONSUL_PATH_PREFIX}1003"],
    )

    ActiveProfilingConsulHandler.check_update()

    consul_rows.filters["profiles"].assert_called_once_with(app_name=BUILTIN_PROFILING_APP_NAME)
    consul_rows.filters["event_groups"].assert_called_once_with(
        bk_biz_id__in=[2, 3], event_group_name=BUILTIN_EVENT_GROUP_NAME, is_delete=False, is_enable=True
    )
    consul_rows.filters["data_sources"].assert_called_once_with(bk_data_id__in=[1001, 1002], is_enable=True)
    consul_rows.consul.put.assert_called_once_with(
        key=f"{CONSUL_PATH_PREFIX}1001",
        value={
            "bk_tenant_id": "system",
            "bk_biz_id": 2,
            "bk_data_id": 1001,
            "kafka_info": {"host": "kafka.local:9092", "username": "u", "password": "p", "topic": "topic_1001"},
        },
        bk_data_id=1001,
    )
    deleted = [call.args[0] for call in consul_rows.consul.delete.call_args_list]
    assert deleted == [f"{CONSUL_PATH_PREFIX}1002", f"{CONSUL_PATH_PREFIX}1003"]


def test_check_update_keeps_old_value_when_kafka_info_incomplete(consul_rows):
    consul_rows.rows["topics"] = []
    consul_rows.consul.list_keys.return_value = (1, [f"{CONSUL_PATH_PREFIX}1001"])

    ActiveProfilingConsulHandler.check_update()

    consul_rows.consul.put.assert_not_called()
    consul_rows.consul.delete.assert_not_called()


def test_check_update_isolates_consul_put_failure(consul_rows):
    consul_rows.rows["data_sources"].append({"bk_data_id": 1002, "mq_cluster_id": 9})
    consul_rows.rows["topics"].append({"bk_data_id": 1002, "topic": "topic_1002"})
    consul_rows.consul.put.side_effect = [RuntimeError("consul unavailable"), True]

    ActiveProfilingConsulHandler.check_update()

    assert consul_rows.consul.put.call_count == 2
    consul_rows.consul.delete.assert_not_called()


def test_refresh_only_puts_target_biz(consul_rows):
    ActiveProfilingConsulHandler.refresh(2)

    consul_rows.filters["event_groups"].assert_called_once_with(
        bk_biz_id__in=[2], event_group_name=BUILTIN_EVENT_GROUP_NAME, is_delete=False, is_enable=True
    )
    consul_rows.consul.put.assert_called_once()
    consul_rows.consul.list_keys.assert_not_called()
    consul_rows.consul.delete.assert_not_called()
