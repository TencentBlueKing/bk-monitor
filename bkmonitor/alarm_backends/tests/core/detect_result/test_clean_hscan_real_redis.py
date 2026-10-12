"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import subprocess
import time
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from redis.client import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from alarm_backends.core.detect_result.clean import CleanResult


@pytest.fixture(scope="module")
def real_redis():
    temporary_directory = TemporaryDirectory(prefix="clean-hscan-", dir="/tmp")
    socket_path = Path(temporary_directory.name) / "redis.sock"
    process = subprocess.Popen(
        [
            "redis-server",
            "--save",
            "",
            "--appendonly",
            "no",
            "--port",
            "0",
            "--unixsocket",
            str(socket_path),
            "--unixsocketperm",
            "700",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    client = Redis(unix_socket_path=str(socket_path), decode_responses=True)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            client.ping()
            break
        except RedisConnectionError:
            time.sleep(0.01)
    else:
        stderr = process.stderr.read() if process.stderr else ""
        process.terminate()
        raise RuntimeError(f"redis-server did not start: {stderr}")

    yield client

    client.close()
    process.terminate()
    process.wait(timeout=5)
    temporary_directory.cleanup()


def _scan_all(client, redis_key, *, count=3, max_fields=2048):
    cursor = 0
    fields = set()
    cursors = []
    while True:
        cursor, page = CleanResult.scan_last_checkpoint_page(
            client,
            redis_key,
            cursor=cursor,
            count=count,
            max_fields=max_fields,
        )
        fields.update(page)
        cursors.append(cursor)
        if cursor == 0:
            return fields, cursors


def test_listpack_proves_count_is_only_a_hint_and_hard_limit_still_applies(real_redis):
    redis_key = "clean-hscan:listpack"
    real_redis.delete(redis_key)
    real_redis.hset(redis_key, mapping={f"field-{index}": "1" for index in range(50)})

    assert real_redis.object("encoding", redis_key) in {"listpack", "ziplist"}
    next_cursor, fields = CleanResult.scan_last_checkpoint_page(
        real_redis,
        redis_key,
        cursor=0,
        count=1,
        max_fields=100,
    )
    assert next_cursor == 0
    assert len(fields) == 50

    with pytest.raises(ValueError):
        CleanResult.scan_last_checkpoint_page(real_redis, redis_key, cursor=0, count=1, max_fields=10)


def test_hashtable_scan_preserves_opaque_cursor_until_zero(real_redis):
    redis_key = "clean-hscan:hashtable"
    real_redis.delete(redis_key)
    expected = {f"field-{index}" for index in range(100)}
    real_redis.hset(redis_key, mapping={field: "x" * 100 for field in expected})

    assert real_redis.object("encoding", redis_key) == "hashtable"
    fields, cursors = _scan_all(real_redis, redis_key)

    assert fields == expected
    assert cursors[-1] == 0
    assert any(cursor != 0 for cursor in cursors[:-1])


def test_next_complete_scan_compensates_for_changes_during_previous_scan(real_redis):
    redis_key = "clean-hscan:concurrent-change"
    real_redis.delete(redis_key)
    real_redis.hset(redis_key, mapping={f"field-{index}": "x" * 100 for index in range(100)})

    cursor, _ = CleanResult.scan_last_checkpoint_page(real_redis, redis_key, cursor=0, count=3, max_fields=2048)
    real_redis.hdel(redis_key, "field-0")
    real_redis.hset(redis_key, "field-new", "x" * 100)
    while cursor != 0:
        cursor, _ = CleanResult.scan_last_checkpoint_page(
            real_redis,
            redis_key,
            cursor=cursor,
            count=3,
            max_fields=2048,
        )

    stable_fields, _ = _scan_all(real_redis, redis_key)
    assert stable_fields == {f"field-{index}" for index in range(1, 100)} | {"field-new"}
