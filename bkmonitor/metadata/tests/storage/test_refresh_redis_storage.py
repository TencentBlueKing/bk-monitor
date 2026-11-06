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

import fakeredis
import pytest

from metadata.models.storage import ClusterInfo


@pytest.fixture
def storage_sync(mocker):
    client = fakeredis.FakeRedis()
    clusters = []
    mocker.patch("metadata.models.storage.RedisTools", return_value=mocker.Mock(client=client))
    mocker.patch.object(ClusterInfo.objects, "all", return_value=clusters)
    return client, clusters


def make_cluster(cluster_id=1, **kwargs):
    return ClusterInfo(
        cluster_id=cluster_id,
        cluster_type="influxdb",
        domain_name="storage.example.com",
        port=8086,
        username="fixture-user",
        password="fixture-password",
        **kwargs,
    )


def test_publish_update_delete_and_clear_last_cluster(storage_sync, mocker):
    client, clusters = storage_sync
    first, second = make_cluster(1, schema="http"), make_cluster(2, schema="https")
    clusters.extend([first, second])
    key = f"{ClusterInfo.REDIS_PREFIX_KEY}:1"
    other_key = "bkmonitorv3:unify-query:data:feature_flag"
    client.set(other_key, "untouched")
    publish = mocker.spy(client, "publish")

    ClusterInfo.refresh_redis_storage_config()

    assert ClusterInfo.REDIS_PREFIX_KEY == "bkmonitorv3:unify-query:data:storage"
    assert json.loads(client.get(key)) == {
        "address": "http://storage.example.com:8086",
        "username": "fixture-user",
        "password": "fixture-password",
        "type": "influxdb",
    }
    assert client.ttl(key) == -1
    assert publish.call_args.args[0] == f"{ClusterInfo.REDIS_PREFIX_KEY}:storage_channel"
    assert json.loads(publish.call_args.args[1])["storage_ids"] == [1, 2]

    client.expire(key, 60)
    first.password = "updated-fixture-password"
    clusters.remove(second)
    ClusterInfo.refresh_redis_storage_config()

    assert json.loads(client.get(key))["password"] == "updated-fixture-password"
    assert client.ttl(key) == -1
    assert client.get(f"{ClusterInfo.REDIS_PREFIX_KEY}:2") is None

    clusters.clear()
    ClusterInfo.refresh_redis_storage_config()

    assert list(client.scan_iter(match=f"{ClusterInfo.REDIS_PREFIX_KEY}:*")) == []
    assert json.loads(publish.call_args.args[1])["storage_ids"] == []
    assert publish.call_count == 3
    assert client.get(other_key) == b"untouched"


@pytest.mark.parametrize(
    ("schema", "host", "expected"),
    [
        ("https", "storage.example.com", "https://storage.example.com:8086"),
        ("tcp", "192.0.2.1", "http://192.0.2.1:8086"),
        (None, "storage.example.com", "http://storage.example.com:8086"),
        ("", "storage.example.com", "http://storage.example.com:8086"),
        ("http", "2001:db8::1", "http://[2001:db8::1]:8086"),
        ("https", "[2001:db8::1]", "https://[2001:db8::1]:8086"),
    ],
)
def test_storage_address(storage_sync, schema, host, expected):
    client, clusters = storage_sync
    cluster = make_cluster(schema=schema)
    cluster.domain_name = host
    clusters.append(cluster)

    ClusterInfo.refresh_redis_storage_config()

    assert json.loads(client.get(f"{ClusterInfo.REDIS_PREFIX_KEY}:1"))["address"] == expected


@pytest.mark.parametrize("operation", ["set", "scan_iter", "delete", "publish"])
def test_publish_failure_propagates_without_early_notification(storage_sync, mocker, operation):
    client, clusters = storage_sync
    clusters.append(make_cluster(schema="http"))
    stale_key = f"{ClusterInfo.REDIS_PREFIX_KEY}:99"
    client.set(stale_key, "{}")
    publish = mocker.spy(client, "publish") if operation != "publish" else None
    mocker.patch.object(client, operation, side_effect=RuntimeError("redis unavailable"))

    with pytest.raises(RuntimeError, match="redis unavailable"):
        ClusterInfo.refresh_redis_storage_config()

    if publish is not None:
        publish.assert_not_called()
    if operation in ("set", "scan_iter", "delete"):
        assert client.exists(stale_key)


def test_database_failure_keeps_existing_keys(storage_sync, mocker):
    client, _ = storage_sync
    key = f"{ClusterInfo.REDIS_PREFIX_KEY}:1"
    client.set(key, "previous-value")
    publish = mocker.spy(client, "publish")
    mocker.patch.object(ClusterInfo.objects, "all", side_effect=RuntimeError("database unavailable"))

    with pytest.raises(RuntimeError, match="database unavailable"):
        ClusterInfo.refresh_redis_storage_config()

    assert client.get(key) == b"previous-value"
    publish.assert_not_called()


def test_notify_after_writes_and_cleanup(storage_sync, mocker):
    client, clusters = storage_sync
    clusters.extend([make_cluster(1, schema="http"), make_cluster(2, schema="http")])
    stale_key = f"{ClusterInfo.REDIS_PREFIX_KEY}:99"
    client.set(stale_key, "{}")

    def check_snapshot(channel, message):
        assert client.exists(f"{ClusterInfo.REDIS_PREFIX_KEY}:1", f"{ClusterInfo.REDIS_PREFIX_KEY}:2") == 2
        assert not client.exists(stale_key)
        assert json.loads(message)["storage_ids"] == [1, 2]

    publish = mocker.patch.object(client, "publish", side_effect=check_snapshot)

    ClusterInfo.refresh_redis_storage_config()

    publish.assert_called_once()
