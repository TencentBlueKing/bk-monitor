"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest.mock import Mock

import fakeredis
import pytest
from redis.exceptions import ConnectionError

from alarm_backends.core.cache.mail_report import MailReportCacheManager
from alarm_backends.service.report import handler
from bkmonitor.utils import extended_json
from constants.report import BuildInBizType


@pytest.fixture
def group_cache(monkeypatch):
    cache = fakeredis.FakeRedis()
    monkeypatch.setattr(MailReportCacheManager, "cache", cache)
    api_call = Mock(side_effect=AssertionError("group lookup must not call monitor API"))
    monkeypatch.setattr(handler.api.monitor, "get_setting_and_notify_group", api_call)
    yield cache
    api_call.assert_not_called()


def set_groups(cache, controller=None, notify=None):
    cache.set(
        MailReportCacheManager.MAIL_REPORT_CACHE_KEY,
        extended_json.dumps(
            {
                "controller_group": {"users": [], "users_biz": controller or {}},
                "alert_group": {"users": [], "users_biz": notify or {}},
            }
        ),
    )


def graph_types(*enabled):
    return {kind: kind in enabled for kind in (BuildInBizType.ALL, BuildInBizType.SETTINGS, BuildInBizType.NOTIFY)}


def parse_groups(graphs, receivers, superusers=()):
    return handler.ReportHandler.parse_users_group(None, "tenant-a", graphs, receivers, superusers)


def test_cached_groups_preserve_business_sorting_and_receiver_filtering(group_cache):
    set_groups(
        group_cache,
        controller={"alice": {3, 2}, "bob": [2, 3]},
        notify={"alice": [4], "bob": {4}},
    )

    result = parse_groups(
        graph_types(BuildInBizType.SETTINGS, BuildInBizType.NOTIFY),
        ["alice", "bob", "admin-user", "", "x" * 32, "webhook(example.test)"],
        superusers=["admin-user"],
    )

    assert result == {
        f"{BuildInBizType.SETTINGS}-2,3,{BuildInBizType.NOTIFY}-4": {"alice", "bob"},
        f"{BuildInBizType.SETTINGS}-superuser,{BuildInBizType.NOTIFY}-superuser": {"admin-user"},
    }


def test_local_cache_does_not_bypass_business_permission(group_cache, monkeypatch):
    set_groups(group_cache, controller={"alice": [3], "admin-user": [3]})
    clients = []

    def make_permission(username, bk_tenant_id):
        assert bk_tenant_id == "tenant-a"
        client = Mock(skip_check=True)

        def visible_businesses(action):
            assert action == handler.ActionEnum.VIEW_BUSINESS
            assert client.skip_check is False
            return [{"bk_biz_id": 5}, {"bk_biz_id": 2}]

        client.filter_space_list_by_action.side_effect = visible_businesses
        clients.append((username, client))
        return client

    monkeypatch.setattr(handler, "Permission", make_permission)
    result = parse_groups(
        graph_types(BuildInBizType.ALL, BuildInBizType.SETTINGS), ["alice", "admin-user"], ["admin-user"]
    )

    assert result == {
        f"{BuildInBizType.ALL}-2,5,{BuildInBizType.SETTINGS}-3,": {"alice"},
        f"{BuildInBizType.ALL}-superuser,{BuildInBizType.SETTINGS}-superuser,": {"admin-user"},
    }
    assert [username for username, _ in clients] == ["alice", "admin-user"]
    for _, client in clients:
        client.filter_space_list_by_action.assert_called_once()


def test_empty_cached_groups_keep_users_without_businesses(group_cache):
    set_groups(group_cache)
    assert parse_groups(graph_types(BuildInBizType.SETTINGS, BuildInBizType.NOTIFY), ["alice"]) == {
        f"{BuildInBizType.SETTINGS}-,{BuildInBizType.NOTIFY}-": {"alice"}
    }


def test_missing_cache_keeps_existing_missing_snapshot_behavior(group_cache):
    assert parse_groups(graph_types(), ["alice"]) == {"": {"alice"}}
    # The existing missing-snapshot contract uses a list instead of a user map.
    with pytest.raises(AttributeError):
        parse_groups(graph_types(BuildInBizType.SETTINGS), ["alice"])


def test_cache_read_failure_is_not_converted_to_empty_groups(group_cache, monkeypatch):
    monkeypatch.setattr(group_cache, "get", Mock(side_effect=ConnectionError("cache unavailable")))
    with pytest.raises(ConnectionError):
        parse_groups(graph_types(BuildInBizType.SETTINGS), ["alice"])
