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
from django.core.cache.backends.locmem import LocMemCache

from bk_dataview.permissions import GrafanaRole
from iam_engine.core.config import AuthMode
from monitor_web.grafana import permissions as grafana


@pytest.fixture
def env(monkeypatch):
    state = SimpleNamespace(
        mode=AuthMode.V3,
        tenant="system",
        check=Mock(return_value=(True, GrafanaRole.Viewer, {})),
        cache=LocMemCache("grafana-read-permission-test", {}),
    )
    state.cache.clear()
    monkeypatch.setattr(grafana, "cache", state.cache)
    monkeypatch.setattr(grafana, "get_mode_provider", lambda: SimpleNamespace(get_mode=lambda: state.mode))
    monkeypatch.setattr(grafana, "get_request_tenant_id", lambda: state.tenant)
    monkeypatch.setattr(grafana.DashboardPermission, "has_permission", state.check)
    return state


def request(username="alice", biz_id=20, **extra):
    return SimpleNamespace(biz_id=biz_id, user=SimpleNamespace(username=username, is_superuser=False), **extra)


def allowed(req, fallback=None):
    return grafana.GrafanaReadPermission(fallback).has_permission(req, None)


def test_grant_is_reused_across_requests_for_ttl(env, monkeypatch):
    monkeypatch.setattr(env.cache, "set", Mock(wraps=env.cache.set))
    assert allowed(request()) and allowed(request())
    assert env.check.call_count == 1
    env.cache.set.assert_called_once()
    assert env.cache.set.call_args.args[1:] == (True, grafana.GrafanaReadPermission.ALLOW_CACHE_SECONDS)


def test_grant_from_dashboard_acl_is_reused(env):
    env.check.return_value = (True, GrafanaRole.Anonymous, {"uid": "View"})
    assert allowed(request()) and allowed(request())
    assert env.check.call_count == 1


def test_denial_and_fallback_grant_are_never_cached(env):
    env.check.return_value = (True, GrafanaRole.Anonymous, {})
    assert not allowed(request()) and not allowed(request())
    fallback = Mock(has_permission=Mock(return_value=True))
    assert allowed(request(), fallback) and allowed(request(), fallback)
    assert env.check.call_count == 4
    assert fallback.has_permission.call_count == 2


@pytest.mark.parametrize(
    "change",
    [
        lambda env: setattr(env, "mode", AuthMode.V4),
        lambda env: setattr(env, "mode", AuthMode.UNION),
        lambda env: setattr(env, "tenant", "other"),
    ],
)
def test_grant_is_isolated_by_mode_and_tenant(env, change):
    assert allowed(request())
    change(env)
    env.check.return_value = (True, GrafanaRole.Anonymous, {})
    assert not allowed(request())
    assert env.check.call_count == 2


@pytest.mark.parametrize("other", [request(username="bob"), request(biz_id=21)])
def test_grant_is_isolated_by_user_and_business(env, other):
    assert allowed(request())
    env.check.return_value = (True, GrafanaRole.Anonymous, {})
    assert not allowed(other)


@pytest.mark.parametrize(
    "elevated",
    [
        request(skip_check=True),
        request(token="share-token"),
        request(external_user="partner"),
        SimpleNamespace(biz_id=20, user=SimpleNamespace(username="alice", is_superuser=True)),
    ],
)
def test_request_scoped_grants_are_not_shared(env, elevated):
    assert allowed(elevated)
    env.check.return_value = (True, GrafanaRole.Anonymous, {})
    assert not allowed(request())
    assert env.check.call_count == 2
