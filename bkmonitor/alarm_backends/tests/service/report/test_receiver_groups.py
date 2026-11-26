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
from unittest.mock import Mock

import pytest

from alarm_backends.service.new_report.handler import base
from alarm_backends.service.report import handler
from constants.report import StaffChoice


def staff(identifier, kind=StaffChoice.user, enabled=True):
    return {"id": identifier, "type": kind, "is_enabled": enabled}


@pytest.fixture(params=["legacy", "new"])
def report_version(request):
    return request.param


@pytest.fixture
def group_list(monkeypatch):
    lookup = Mock(
        return_value=[
            {"id": "group-a", "children": ["alice", "bob", "admin", "system"]},
            {"id": "group-b", "children": ["carol"]},
        ]
    )
    monkeypatch.setattr(handler.api.monitor, "group_list", lookup)
    monkeypatch.setattr(base.api.monitor, "group_list", lookup)
    return lookup


def fetch(version, subscribers):
    if version == "legacy":
        return handler.ReportHandler.fetch_receivers(SimpleNamespace(), subscribers)
    channel = SimpleNamespace(channel_name=base.ChannelEnum.USER.value, subscribers=subscribers)
    return base.SendChannelHandler.fetch_subscribers(SimpleNamespace(channel=channel), bk_biz_id=2)


@pytest.mark.parametrize(
    "subscribers,expected",
    [
        ([staff("alice"), staff("alice"), staff("admin"), staff("system")], {"alice"}),
        ([staff("alice", enabled=False)], set()),
        ([staff("group-a", StaffChoice.group, False)], set()),
        ([staff("group-a", StaffChoice.group, False), staff("alice")], {"alice"}),
    ],
)
def test_without_enabled_groups_skips_lookup(report_version, group_list, subscribers, expected):
    group_list.side_effect = AssertionError("group lookup must not run")
    assert set(fetch(report_version, subscribers)) == expected
    group_list.assert_not_called()


def test_enabled_groups_are_fetched_once(report_version, group_list):
    result = fetch(report_version, [staff("group-a", StaffChoice.group), staff("group-b", StaffChoice.group)])
    assert set(result) == {"alice", "bob", "carol"}
    if report_version == "legacy":
        group_list.assert_called_once_with()
    else:
        group_list.assert_called_once_with(bk_biz_id=2)


def test_mixed_receivers_keep_disabled_users_and_reserved_user_filtering(report_version, group_list):
    result = fetch(
        report_version,
        [staff("group-a", StaffChoice.group), staff("bob", enabled=False), staff("carol"), staff("alice")],
    )
    assert set(result) == {"alice", "carol"}
    group_list.assert_called_once()


def test_existing_receiver_order_semantics_are_preserved(report_version, group_list):
    # Legacy resolves every group before users; the new report resolves entries in their input order.
    result = fetch(report_version, [staff("bob", enabled=False), staff("group-a", StaffChoice.group)])
    assert set(result) == ({"alice"} if report_version == "legacy" else {"alice", "bob"})


def test_legacy_group_lookup_error_propagates(group_list):
    group_list.side_effect = RuntimeError("lookup failed")
    with pytest.raises(RuntimeError, match="lookup failed"):
        fetch("legacy", [staff("group-a", StaffChoice.group), staff("alice")])


def test_new_group_lookup_error_keeps_individual_receivers(group_list, monkeypatch):
    group_list.side_effect = RuntimeError("lookup failed")
    log_error = Mock()
    monkeypatch.setattr(base.logger, "exception", log_error)
    assert fetch("new", [staff("group-a", StaffChoice.group), staff("alice")]) == ["alice"]
    log_error.assert_called_once()


@pytest.mark.parametrize("channel_name", [base.ChannelEnum.EMAIL.value, base.ChannelEnum.WXBOT.value])
def test_non_user_channel_keeps_ids_and_order_without_lookup(group_list, channel_name):
    subscribers = [{"id": "second"}, {"id": "first"}, {"id": "second"}]
    channel = SimpleNamespace(channel_name=channel_name, subscribers=subscribers)
    result = base.SendChannelHandler.fetch_subscribers(SimpleNamespace(channel=channel), bk_biz_id=2)
    assert result == ["second", "first", "second"]
    group_list.assert_not_called()


@pytest.mark.parametrize("item_receivers", [None, []])
def test_legacy_fallback_loads_tenant_scoped_receivers(group_list, monkeypatch, item_receivers):
    get_item = Mock(return_value=SimpleNamespace(receivers=[staff("alice")]))
    monkeypatch.setattr(handler.ReportItems.objects, "get", get_item)
    report = SimpleNamespace(item_id=7, bk_tenant_id="tenant-a")
    assert handler.ReportHandler.fetch_receivers(report, item_receivers) == ["alice"]
    get_item.assert_called_once_with(pk=7, bk_tenant_id="tenant-a")
    group_list.assert_not_called()


def test_empty_new_subscriber_list_skips_lookup(group_list):
    assert fetch("new", []) == []
    group_list.assert_not_called()
