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
from redis.exceptions import ConnectionError, TimeoutError

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


def test_missing_cache_keeps_api_read_only(group_cache, monkeypatch):
    refresh = Mock(side_effect=AssertionError("read-only API must not refresh"))
    monkeypatch.setattr(MailReportCacheManager, "refresh_mail_report_group", refresh)
    assert MailReportCacheManager.fetch_groups_and_user_bizs()["controller_group"]["users_biz"] == []
    assert parse_groups(graph_types(), ["alice"]) == {"": {"alice"}}
    refresh.assert_not_called()


@pytest.mark.parametrize("error", [ConnectionError, TimeoutError])
def test_cache_read_failure_is_not_converted_to_empty_groups(group_cache, monkeypatch, refresh_sources, error):
    monkeypatch.setattr(group_cache, "get", Mock(side_effect=error("cache unavailable")))
    with pytest.raises(error):
        parse_groups(graph_types(BuildInBizType.SETTINGS), ["alice"])
    refresh_sources[0].assert_not_called()


@pytest.fixture
def refresh_sources(monkeypatch):
    controller = Mock(return_value=(["alice"], {"alice": {3, 2}}))
    notify = Mock(return_value=(["alice"], {"alice": {4}}))
    monkeypatch.setattr(MailReportCacheManager, "fetch_controller_group", controller)
    monkeypatch.setattr(MailReportCacheManager, "fetch_notify_receiver_group", notify)
    return controller, notify


def test_missing_cache_rebuilds_once_and_reuses_snapshot(group_cache, refresh_sources):
    graphs = graph_types(BuildInBizType.SETTINGS, BuildInBizType.NOTIFY)
    expected = {f"{BuildInBizType.SETTINGS}-2,3,{BuildInBizType.NOTIFY}-4": {"alice"}}
    assert parse_groups(graphs, ["alice"]) == expected
    assert parse_groups(graphs, ["alice"]) == expected
    for source in refresh_sources:
        source.assert_called_once()
    assert 0 < group_cache.ttl(MailReportCacheManager.MAIL_REPORT_CACHE_KEY) <= MailReportCacheManager.CACHE_TIMEOUT


def test_valid_empty_cache_does_not_rebuild(group_cache, refresh_sources):
    set_groups(group_cache)
    MailReportCacheManager.fetch_groups_and_user_bizs(ensure=True)
    for source in refresh_sources:
        source.assert_not_called()


@pytest.mark.parametrize("data", [b"", b"invalid json"])
def test_invalid_snapshot_propagates_without_rebuild(group_cache, refresh_sources, data):
    group_cache.set(MailReportCacheManager.MAIL_REPORT_CACHE_KEY, data)
    with pytest.raises(ValueError):
        MailReportCacheManager.fetch_groups_and_user_bizs(ensure=True)
    refresh_sources[0].assert_not_called()


def test_failed_rebuild_can_retry_immediately(group_cache, refresh_sources):
    refresh_sources[0].side_effect = ValueError("source failed")
    with pytest.raises(ValueError, match="source failed"):
        MailReportCacheManager.fetch_groups_and_user_bizs(ensure=True)
    assert group_cache.get(MailReportCacheManager.MAIL_REPORT_CACHE_KEY) is None
    refresh_sources[0].side_effect = None
    result = MailReportCacheManager.fetch_groups_and_user_bizs(ensure=True)
    assert set(result["controller_group"]["users_biz"]["alice"]) == {2, 3}
    assert refresh_sources[0].call_count == 2


@pytest.mark.parametrize("kind,expected", [(BuildInBizType.SETTINGS, {2, 3}), (BuildInBizType.NOTIFY, {4})])
def test_graph_rendering_rebuilds_missing_groups(group_cache, refresh_sources, monkeypatch, kind, expected):
    monkeypatch.setattr(handler.settings, "MAIL_REPORT_BIZ", 2)
    biz, businesses = handler.ReportHandler.parse_graph_info(None, [kind], False, [], ["alice"])
    assert biz == 2
    assert set(businesses) == expected


@pytest.mark.parametrize("graph", ["all", "123", "1,2"])
def test_graph_rendering_without_groups_does_not_read_cache(group_cache, monkeypatch, graph):
    monkeypatch.setattr(handler.settings, "MAIL_REPORT_BIZ", 2)
    monkeypatch.setattr(group_cache, "get", Mock(side_effect=AssertionError("cache not needed")))
    handler.ReportHandler.parse_graph_info(None, [graph], False, [2], ["alice"])


def test_failed_scheduled_refresh_preserves_existing_snapshot(group_cache, refresh_sources):
    set_groups(group_cache, controller={"alice": [9]})
    refresh_sources[0].side_effect = ValueError("source failed")
    with pytest.raises(ValueError, match="source failed"):
        MailReportCacheManager.refresh()
    assert MailReportCacheManager.fetch_groups_and_user_bizs(ensure=True)["controller_group"]["users_biz"] == {
        "alice": [9]
    }


def test_scheduled_refresh_replaces_existing_snapshot(group_cache, refresh_sources):
    set_groups(group_cache, controller={"alice": [9]})
    MailReportCacheManager.refresh()
    result = MailReportCacheManager.fetch_groups_and_user_bizs()
    assert set(result["controller_group"]["users_biz"]["alice"]) == {2, 3}
    refresh_sources[0].assert_called_once()


def test_serialization_failure_preserves_existing_snapshot(group_cache, refresh_sources):
    set_groups(group_cache, controller={"alice": [9]})
    refresh_sources[1].return_value = (["alice"], {"alice": object()})
    with pytest.raises(TypeError):
        MailReportCacheManager.refresh()
    assert MailReportCacheManager.fetch_groups_and_user_bizs()["controller_group"]["users_biz"] == {"alice": [9]}
