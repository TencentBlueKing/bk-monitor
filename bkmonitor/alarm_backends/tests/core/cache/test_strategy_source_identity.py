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

import fakeredis

from alarm_backends.core.cache.strategy import StrategyCacheManager
from bkm_space.api import SpaceApi


def test_add_source_identity_uses_one_cached_space_list(monkeypatch):
    strategies = [
        {"id": 1, "bk_biz_id": 2},
        {"id": 2, "bk_biz_id": 2},
        {"id": 3, "bk_biz_id": -3},
    ]
    calls = 0

    def list_spaces_dict():
        nonlocal calls
        calls += 1
        return [
            {"bk_biz_id": 2, "bk_tenant_id": "tenant-a", "space_uid": "bkcc__2"},
            {"bk_biz_id": -3, "bk_tenant_id": "tenant-b", "space_uid": "bcs__project"},
        ]

    monkeypatch.setattr(SpaceApi, "list_spaces_dict", list_spaces_dict)

    StrategyCacheManager.add_source_identity(strategies)

    assert calls == 1
    assert strategies == [
        {"id": 1, "bk_biz_id": 2, "bk_tenant_id": "tenant-a", "space_uid": "bkcc__2"},
        {"id": 2, "bk_biz_id": 2, "bk_tenant_id": "tenant-a", "space_uid": "bkcc__2"},
        {"id": 3, "bk_biz_id": -3, "bk_tenant_id": "tenant-b", "space_uid": "bcs__project"},
    ]


def test_add_source_identity_isolates_incomplete_business(monkeypatch, caplog):
    strategies = [
        {"id": 1, "bk_biz_id": 2},
        {"id": 2, "bk_biz_id": 3, "bk_tenant_id": "stale", "space_uid": "stale__3"},
        {"id": 3, "bk_biz_id": 4},
    ]
    monkeypatch.setattr(
        SpaceApi,
        "list_spaces_dict",
        lambda: [
            {"bk_biz_id": 2, "bk_tenant_id": "tenant-a", "space_uid": "bkcc__2"},
            {"bk_biz_id": 3, "bk_tenant_id": None, "space_uid": "bkcc__3"},
        ],
    )

    with caplog.at_level(logging.WARNING, logger="cache"):
        StrategyCacheManager.add_source_identity(strategies)

    assert strategies[0]["bk_tenant_id"] == "tenant-a"
    assert strategies[0]["space_uid"] == "bkcc__2"
    assert "bk_tenant_id" not in strategies[1]
    assert "space_uid" not in strategies[1]
    assert "bk_tenant_id" not in strategies[2]
    assert "space_uid" not in strategies[2]
    assert "reason=SPACE_IDENTITY_INVALID, affected=1" in caplog.text
    assert "reason=SPACE_NOT_FOUND, affected=1" in caplog.text


def test_add_source_identity_space_query_failure_is_fail_open(monkeypatch, caplog):
    strategies = [{"id": 1, "bk_biz_id": 2, "bk_tenant_id": "stale", "space_uid": "stale__2"}]

    def raise_space_query_error():
        raise RuntimeError("space query failed")

    monkeypatch.setattr(SpaceApi, "list_spaces_dict", raise_space_query_error)

    with caplog.at_level(logging.ERROR, logger="cache"):
        StrategyCacheManager.add_source_identity(strategies)

    assert strategies == [{"id": 1, "bk_biz_id": 2}]
    assert "reason=SPACE_LIST_FAILED" in caplog.text


def test_refresh_strategy_serializes_source_identity(monkeypatch):
    strategy = {"id": 1, "bk_biz_id": 2, "items": []}
    cache = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(StrategyCacheManager, "cache", cache)
    monkeypatch.setattr(
        SpaceApi,
        "list_spaces_dict",
        lambda: [{"bk_biz_id": 2, "bk_tenant_id": "tenant-a", "space_uid": "bkcc__2"}],
    )

    StrategyCacheManager.refresh_strategy([strategy])

    cached_strategy = json.loads(cache.get(StrategyCacheManager.CACHE_KEY_TEMPLATE.format(strategy_id=1)))
    assert cached_strategy["bk_tenant_id"] == "tenant-a"
    assert cached_strategy["space_uid"] == "bkcc__2"
