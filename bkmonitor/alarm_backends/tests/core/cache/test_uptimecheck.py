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
from unittest.mock import patch

import fakeredis
import pytest
from bk_monitor_base.domains.uptime_check.models import (
    UptimeCheckGroupModel,
    UptimeCheckNodeModel,
    UptimeCheckTaskModel,
)
from django.db import DatabaseError

from alarm_backends.core.cache.models.uptimecheck import UptimecheckCacheManager

pytestmark = pytest.mark.django_db(databases="__all__")


@pytest.fixture
def cache(monkeypatch):
    redis = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(UptimecheckCacheManager, "cache", redis)
    return UptimecheckCacheManager


def make_task(**kwargs):
    return UptimeCheckTaskModel.objects.create(
        **{"bk_biz_id": 2, "name": "test task", "protocol": "HTTP", "config": {}, **kwargs}
    )


def test_refresh_includes_all_businesses_and_excludes_deleted(cache):
    tasks = [make_task(bk_biz_id=biz) for biz in (2, 3)]
    deleted = make_task(is_deleted=True)
    nodes = [
        UptimeCheckNodeModel.objects.create(
            bk_tenant_id=tenant, bk_biz_id=biz, name=tenant, ip=f"192.0.2.{biz}", plat_id=biz
        )
        for tenant, biz in (("tenant-a", 2), ("tenant-b", 3))
    ]
    deleted_node = UptimeCheckNodeModel.objects.create(name="deleted", is_deleted=True)

    cache.refresh()

    assert set(cache.get_task_id_list()) == {task.id for task in tasks}
    for task in tasks:
        assert cache.get_task(task.id) == {"id": task.id, "name": task.name, "bk_biz_id": task.bk_biz_id}
        assert 0 < cache.cache.ttl(cache.TASK_CACHE_KEY_TEMPLATE.format(task_id=task.id)) <= cache.CACHE_TIMEOUT
    assert cache.get_task(deleted.id) is None
    assert cache.get_node(deleted_node.id) is None
    for node in nodes:
        actual = cache.get_node(node.id)
        assert actual["name"] == node.name
        assert actual["bk_cloud_id"] == node.plat_id
        assert actual["ip"] == node.ip
        assert cache.get_node(f"{node.plat_id}:{node.ip}") == actual


def test_refresh_removes_deleted_tasks_but_keeps_other_business(cache):
    removed, retained = make_task(), make_task(bk_biz_id=3)
    cache.refresh_tasks()
    removed.is_deleted = True
    removed.save(update_fields=["is_deleted"])

    cache.refresh_tasks()

    assert cache.get_task(removed.id) is None
    assert cache.get_task(retained.id)["name"] == retained.name
    assert cache.get_task_id_list() == [retained.id]


def test_successful_empty_snapshot_removes_old_tasks(cache):
    task = make_task()
    cache.refresh_tasks()
    task.is_deleted = True
    task.save(update_fields=["is_deleted"])
    cache.refresh_tasks()
    assert cache.get_task_id_list() == []
    assert cache.get_task(task.id) is None


def test_single_refresh_preserves_config_and_relations(cache):
    task = make_task(config={"response_code": "200", "response": "expected body"})
    node = UptimeCheckNodeModel.objects.create(name="node")
    group = UptimeCheckGroupModel.objects.create(name="group", bk_biz_id=2)
    task.nodes.add(node)
    task.groups.add(group)
    cache.refresh_tasks()
    assert "config" not in cache.get_task(task.id)

    actual = cache.get_task(task.id, refresh=True)

    assert actual == {
        "id": task.id,
        "name": task.name,
        "bk_biz_id": task.bk_biz_id,
        "protocol": task.protocol,
        "status": task.status,
        "config": task.config,
        "node_ids": [node.id],
        "group_ids": [group.id],
    }
    assert cache.get_task(task.id) == actual


def test_single_refresh_handles_deleted_missing_and_null_config(cache):
    deleted = make_task(is_deleted=True)
    task = make_task(config=None)
    assert cache.get_task(deleted.id, refresh=True) is None
    assert cache.get_task(-1, refresh=True) is None
    assert cache.get_task(task.id, refresh=True)["config"] == {}


@pytest.mark.parametrize(
    "method, model", [("refresh_nodes", UptimeCheckNodeModel), ("refresh_tasks", UptimeCheckTaskModel)]
)
def test_failed_snapshot_keeps_previous_cache(cache, method, model):
    task = make_task()
    cache.refresh_tasks()
    node_key = cache.NODE_CACHE_KEY_TEMPLATE.format(node_id="old-node")
    cache.cache.set(node_key, json.dumps({"name": "old node"}))
    before = {key: cache.cache.get(key) for key in cache.cache.scan_iter()}

    def failed_read():
        yield {"id": 999, "name": "partial", "bk_biz_id": 2, "ip": "192.0.2.9", "plat_id": 0}
        raise DatabaseError("database read failed")

    with patch.object(model.objects, "filter") as query:
        query.return_value.values.return_value = failed_read()
        with pytest.raises(DatabaseError):
            getattr(cache, method)()

    assert {key: cache.cache.get(key) for key in cache.cache.scan_iter()} == before
    assert cache.get_task_id_list() == [task.id]
