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

from bkmonitor.models import base


def format_managers(managers):
    return base.ReportItems.format_managers.fget(SimpleNamespace(managers=managers))


@pytest.mark.parametrize(
    "managers,expected",
    [
        ([], set()),
        ([{"type": "user", "id": "alice"}], {"alice"}),
        (
            [
                {"type": "user", "id": "alice"},
                {"type": "user", "id": "alice"},
                {"type": "user", "id": "admin"},
                {"type": "user", "id": "system"},
                {"type": "user"},
                {"type": "user", "id": ""},
            ],
            {"alice", "admin", "system"},
        ),
    ],
)
def test_individual_managers_do_not_query_groups(monkeypatch, managers, expected):
    group_list = Mock(side_effect=AssertionError("individual managers must not query groups"))
    monkeypatch.setattr(base.api.monitor, "group_list", group_list)
    assert set(format_managers(managers)) == expected
    group_list.assert_not_called()


@pytest.mark.parametrize(
    "groups,expected",
    [
        ({"group-a": ["alice", "bob"], "group-b": ["bob"]}, {"alice", "bob"}),
        ([{"id": "group-a", "children": ["bob"]}], {"alice"}),
    ],
)
def test_group_managers_keep_existing_response_handling(monkeypatch, groups, expected):
    group_list = Mock(return_value=groups)
    monkeypatch.setattr(base.api.monitor, "group_list", group_list)
    managers = [
        {"type": "group", "id": "group-a"},
        {"type": "group", "id": "group-b"},
        {"type": "user", "id": "alice"},
    ]
    assert set(format_managers(managers)) == expected
    group_list.assert_called_once_with()


@pytest.mark.parametrize("manager", [{"type": "group", "id": "group-a"}, {"type": "group"}])
def test_group_lookup_errors_still_propagate(monkeypatch, manager):
    group_list = Mock(side_effect=RuntimeError("group lookup failed"))
    monkeypatch.setattr(base.api.monitor, "group_list", group_list)
    with pytest.raises(RuntimeError, match="group lookup failed"):
        format_managers([manager])
    group_list.assert_called_once_with()
