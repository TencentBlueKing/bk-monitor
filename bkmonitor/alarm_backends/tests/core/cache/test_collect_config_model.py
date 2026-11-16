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
from types import SimpleNamespace
from unittest.mock import patch

import fakeredis
import pytest
from bk_monitor_base.domains.metric_plugin.old_models import (
    CollectConfigMeta,
    CollectorPluginConfig,
    CollectorPluginInfo,
    DeploymentConfigVersion,
    PluginVersionHistory,
)
from bk_monitor_base.infras.constant import OLD_MONITOR_SAAS_DB_NAME
from django.db import DatabaseError

from alarm_backends.core.cache import mail_report
from alarm_backends.core.cache.models.collect_config import CollectConfigCacheManager
from alarm_backends.service.alert.enricher.translator.collect_config import CollectingConfigTranslator

pytestmark = pytest.mark.django_db(databases="__all__")


@pytest.fixture
def cache(monkeypatch):
    redis = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(CollectConfigCacheManager, "cache", redis)
    monkeypatch.setattr(mail_report.MailReportCacheManager, "cache", redis)
    return redis


@pytest.fixture
def deployment():
    version = PluginVersionHistory.objects.create(
        plugin_id="test-plugin",
        config=CollectorPluginConfig.objects.create(),
        info=CollectorPluginInfo.objects.create(),
    )
    return DeploymentConfigVersion.objects.create(plugin_version=version, config_meta_id=1, params="{}")


def create_config(deployment, **kwargs):
    return CollectConfigMeta.objects.create(
        **{"deployment_config": deployment, "bk_biz_id": 2, "name": "collect", **kwargs}
    )


def test_snapshot_reads_all_tenants_and_only_needed_fields(cache, deployment):
    configs = [
        create_config(deployment, bk_tenant_id=tenant, bk_biz_id=biz, name=tenant, cache_data="not-json")
        for tenant, biz in (("tenant-a", 2), ("tenant-b", 3))
    ]
    deleted = create_config(deployment, is_deleted=True)
    assert CollectConfigMeta.objects.all().db == OLD_MONITOR_SAAS_DB_NAME

    CollectConfigCacheManager.refresh()

    for config in configs:
        assert CollectConfigCacheManager.get(config.id) == {"id": config.id, "name": config.name}
        assert 0 < cache.ttl(CollectConfigCacheManager.format_key(config.id)) <= CollectConfigCacheManager.CACHE_TIMEOUT
    assert CollectConfigCacheManager.get(deleted.id) is None


@pytest.mark.parametrize("extra", [{}, {"cache_data": {"old": True}, "create_user": "old-user"}])
def test_translator_accepts_old_and_new_cache_shapes(cache, extra):
    cache.set(CollectConfigCacheManager.format_key(1), json.dumps({"id": 1, "name": "collect", **extra}))
    translator = CollectingConfigTranslator.__new__(CollectingConfigTranslator)
    field = SimpleNamespace(value=1, display_name="", display_value="")
    data = {"bk_collect_config_id": field}
    assert translator.translate(data) is data
    assert field.display_value == "collect"


def test_empty_snapshot_keeps_existing_expiry_behavior(cache):
    key = CollectConfigCacheManager.format_key(1)
    cache.set(key, json.dumps({"id": 1, "name": "old"}), 100)
    CollectConfigCacheManager.refresh()
    assert CollectConfigCacheManager.get(1)["name"] == "old"
    assert 0 < cache.ttl(key) <= 100
    assert CollectConfigCacheManager.get(-1) is None


def test_partial_database_failure_preserves_cache(cache):
    key = CollectConfigCacheManager.format_key(1)
    cache.set(key, json.dumps({"id": 1, "name": "old"}))

    def rows():
        yield {"id": 1, "name": "partial"}
        raise DatabaseError("read failed")

    with patch.object(CollectConfigMeta.objects, "filter") as query:
        query.return_value.values.return_value = rows()
        with pytest.raises(DatabaseError):
            CollectConfigCacheManager.refresh()
    assert CollectConfigCacheManager.get(1)["name"] == "old"


@pytest.fixture
def empty_other_controller_sources(monkeypatch):
    for model in (mail_report.EventGroup, mail_report.Shield, mail_report.Strategy, mail_report.NoticeGroup):
        monkeypatch.setattr(model.objects, "filter", lambda **kwargs: SimpleNamespace(values=lambda *fields: []))


def test_controller_group_reads_creators_across_tenants(deployment, empty_other_controller_sources):
    create_config(deployment, bk_tenant_id="tenant-a", create_user="alice", update_user="bob", cache_data="not-json")
    create_config(deployment, bk_tenant_id="tenant-b", bk_biz_id=3, create_user="bob", update_user="carol")
    create_config(deployment, create_user="deleted-user", update_user="deleted-user", is_deleted=True)

    users, businesses = mail_report.MailReportCacheManager.fetch_controller_group()

    assert set(users) == {"alice", "bob", "carol"}
    assert dict(businesses) == {"alice": {2}, "bob": {2, 3}, "carol": {3}}


def test_empty_controller_group(empty_other_controller_sources):
    users, businesses = mail_report.MailReportCacheManager.fetch_controller_group()
    assert users == []
    assert dict(businesses) == {}


def test_controller_query_failure_preserves_report_cache(cache):
    manager = mail_report.MailReportCacheManager
    cache.set(manager.MAIL_REPORT_CACHE_KEY, "old-report")
    with patch.object(CollectConfigMeta.objects, "filter", side_effect=DatabaseError("read failed")):
        with pytest.raises(DatabaseError):
            manager.refresh_mail_report_group()
    assert cache.get(manager.MAIL_REPORT_CACHE_KEY) == "old-report"
