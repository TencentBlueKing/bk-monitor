"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import importlib.util
import time
from pathlib import Path
from unittest.mock import Mock

import fakeredis
import pytest


MODULE_PATH = Path(__file__).parents[4] / "service" / "access" / "event" / "queue.py"
SPEC = importlib.util.spec_from_file_location("access_event_queue", MODULE_PATH)
queue = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(queue)

build_partition_signal = queue.build_partition_signal
acquire_partition_task = queue.acquire_partition_task
enqueue_partition_messages = queue.enqueue_partition_messages
finish_partition_task = queue.finish_partition_task
get_event_lock_id = queue.get_event_lock_id
get_event_queue_key = queue.get_event_queue_key
get_partition_queue_max_length = queue.get_partition_queue_max_length
keep_partition_task_alive = queue.keep_partition_task_alive
pull_event_records = queue.pull_event_records
parse_partition_signal = queue.parse_partition_signal
refresh_partition_task = queue.refresh_partition_task
start_partition_task = queue.start_partition_task


class EvalRedis:
    def __init__(self):
        self.redis = fakeredis.FakeRedis(decode_responses=True)

    def __getattr__(self, name):
        return getattr(self.redis, name)

    def eval(self, script, numkeys, *keys_and_args):
        if script == queue.FINISH_PARTITION_TASK_SCRIPT:
            assert numkeys == 3
            queue_key, signal_key, task_key, signal_member, task_token, task_ttl = keys_and_args
            if self.redis.get(task_key) != task_token:
                return -1
            if self.redis.llen(queue_key) == 0:
                self.redis.srem(signal_key, signal_member)
                self.redis.delete(task_key)
                return 0
            self.redis.expire(task_key, task_ttl)
            return 1
        if script == queue.START_PARTITION_TASK_SCRIPT:
            assert numkeys == 1
            task_key, expected_token, active_token, task_ttl = keys_and_args
            if self.redis.get(task_key) != expected_token:
                return 0
            self.redis.set(task_key, active_token, ex=task_ttl)
            return 1
        if script == queue.REFRESH_PARTITION_TASK_SCRIPT:
            assert numkeys == 1
            task_key, active_token, task_ttl = keys_and_args
            if self.redis.get(task_key) != active_token:
                return 0
            self.redis.expire(task_key, task_ttl)
            return 1
        if script == queue.PULL_EVENT_RECORDS_SCRIPT:
            assert numkeys == 1
            queue_key, max_records, max_length = keys_and_args
            total = self.redis.llen(queue_key)
            dropped = max(total - int(max_length), 0) if int(max_length) > 0 else 0
            if dropped:
                self.redis.ltrim(queue_key, 0, int(max_length) - 1)
                total = int(max_length)
            offset = min(total, int(max_records))
            records = self.redis.lrange(queue_key, -offset, -1) if offset else []
            if records:
                self.redis.ltrim(queue_key, 0, -offset - 1)
            return [dropped, records]
        raise AssertionError("unexpected script")


def test_partition_signal_round_trip():
    signal = build_partition_signal(1000, 3)

    assert parse_partition_signal(signal) == ("1000", 3)


@pytest.mark.parametrize("signal", ["", "1000", "1000:", ":1", "1000:-1", "1000:not-an-integer"])
def test_parse_partition_signal_rejects_malformed_value(signal):
    with pytest.raises(ValueError):
        parse_partition_signal(signal)


def test_partition_queue_max_length_keeps_total_limit():
    assert get_partition_queue_max_length(total_max_length=10, partition_count=3) == 4
    assert get_partition_queue_max_length(total_max_length=10, partition_count=1) == 10


def test_partition_queue_max_length_rejects_invalid_values():
    with pytest.raises(ValueError):
        get_partition_queue_max_length(total_max_length=0, partition_count=1)
    with pytest.raises(ValueError):
        get_partition_queue_max_length(total_max_length=10, partition_count=0)


def test_event_lock_id_preserves_legacy_format_and_isolates_partitions():
    assert get_event_lock_id(1000) == "1000-[redis]"
    assert get_event_lock_id(1000, partition=0) == "1000-partition-0-[redis]"
    assert get_event_lock_id(1000, partition=2) == "1000-partition-2-[redis]"
    assert get_event_lock_id(1000, partition=3) != get_event_lock_id(1000, partition=2)


def test_event_queue_key_treats_partition_zero_as_partition():
    class Key:
        def __init__(self, template):
            self.template = template

        def get_key(self, **kwargs):
            return self.template.format(**kwargs)

    legacy_key = Key("access.event.{data_id}")
    partition_key = Key("access.event.{data_id}.partition.{partition}")

    assert get_event_queue_key(1000, None, legacy_key, partition_key) == "access.event.1000"
    assert get_event_queue_key(1000, 0, legacy_key, partition_key) == "access.event.1000.partition.0"


def test_pull_event_records_atomically_caps_and_removes_only_returned_events():
    client = EvalRedis()
    client.rpush("events", "newest", "newer", "older", "oldest")

    records, dropped = pull_event_records(client, "events", max_records=1, max_length=3)

    assert dropped == 1
    assert records == ["older"]
    assert client.lrange("events", 0, -1) == ["newest", "newer"]


def test_partition_producer_trim_and_atomic_pull_do_not_double_delete():
    client = EvalRedis()
    client.rpush("events", *[f"old-{index}" for index in range(10)])
    enqueue_partition_messages(
        client=client,
        queue_key="events",
        signal_key="signals",
        signal_member="1000:0",
        task_key="task",
        messages=[f"new-{index}" for index in range(5)],
        max_length=10,
        queue_ttl=60,
        task_ttl=30,
    )

    records, dropped = pull_event_records(client, "events", max_records=5)

    assert dropped == 0
    assert records == ["old-0", "old-1", "old-2", "old-3", "old-4"]
    assert client.lrange("events", 0, -1) == ["new-4", "new-3", "new-2", "new-1", "new-0"]


def test_enqueue_partition_messages_atomically_signals_and_claims_one_task():
    client = fakeredis.FakeRedis(decode_responses=True)

    dropped, task_token = enqueue_partition_messages(
        client=client,
        queue_key="events",
        signal_key="signals",
        signal_member="1000:0",
        task_key="task",
        messages=["older", "newer"],
        max_length=10,
        queue_ttl=60,
        task_ttl=30,
    )
    _, duplicate_token = enqueue_partition_messages(
        client=client,
        queue_key="events",
        signal_key="signals",
        signal_member="1000:0",
        task_key="task",
        messages=["latest"],
        max_length=10,
        queue_ttl=60,
        task_ttl=30,
    )

    assert dropped == 0
    assert task_token
    assert duplicate_token is None
    assert client.smembers("signals") == {"1000:0"}
    assert client.get("task") == task_token


def test_acquire_partition_task_recovers_only_when_marker_is_absent():
    client = fakeredis.FakeRedis(decode_responses=True)

    first_token = acquire_partition_task(client, "task", ttl=30)
    duplicate_token = acquire_partition_task(client, "task", ttl=30)
    client.delete("task")
    recovered_token = acquire_partition_task(client, "task", ttl=30)

    assert first_token
    assert duplicate_token is None
    assert recovered_token
    assert recovered_token != first_token


def test_start_partition_task_rejects_stale_token_and_rotates_current_token():
    client = EvalRedis()
    scheduled_token = acquire_partition_task(client, "task", ttl=30)

    assert start_partition_task(client, "task", "stale-token", ttl=30) is None
    active_token = start_partition_task(client, "task", scheduled_token, ttl=30)

    assert active_token
    assert active_token != scheduled_token
    assert client.get("task") == active_token


def test_refresh_partition_task_only_extends_current_active_token():
    client = EvalRedis()
    scheduled_token = acquire_partition_task(client, "task", ttl=30)
    active_token = start_partition_task(client, "task", scheduled_token, ttl=30)

    assert refresh_partition_task(client, "task", "stale-token", ttl=30) is False
    assert refresh_partition_task(client, "task", active_token, ttl=30) is True


def test_partition_task_heartbeat_retries_after_transient_refresh_failure(monkeypatch):
    refresh = Mock(side_effect=[RuntimeError("temporary failure"), True])
    monkeypatch.setattr(queue, "refresh_partition_task", refresh)

    with keep_partition_task_alive(Mock(), "task", "token", ttl=0.3, max_lease=1):
        time.sleep(0.25)

    assert refresh.call_count >= 2


def test_partition_task_heartbeat_stops_at_max_lease(monkeypatch):
    refresh = Mock(return_value=True)
    monkeypatch.setattr(queue, "refresh_partition_task", refresh)

    with keep_partition_task_alive(Mock(), "task", "token", ttl=0.3, max_lease=0.15):
        time.sleep(0.25)
    calls_at_exit = refresh.call_count
    time.sleep(0.15)

    assert calls_at_exit >= 1
    assert refresh.call_count == calls_at_exit


def test_finish_partition_task_keeps_single_claim_while_queue_has_data():
    client = EvalRedis()
    client.lpush("events", "event")
    client.sadd("signals", "1000:0")
    token = acquire_partition_task(client, "task", ttl=30)

    should_continue = finish_partition_task(
        client=client,
        queue_key="events",
        signal_key="signals",
        signal_member="1000:0",
        task_key="task",
        task_token=token,
        task_ttl=30,
    )

    assert should_continue is True
    assert client.get("task") == token
    assert client.smembers("signals") == {"1000:0"}


def test_finish_partition_task_cleans_signal_and_claim_after_drain():
    client = EvalRedis()
    client.sadd("signals", "1000:0")
    token = acquire_partition_task(client, "task", ttl=30)

    should_continue = finish_partition_task(
        client=client,
        queue_key="events",
        signal_key="signals",
        signal_member="1000:0",
        task_key="task",
        task_token=token,
        task_ttl=30,
    )

    assert should_continue is False
    assert client.exists("task") == 0
    assert client.smembers("signals") == set()


def test_finish_partition_task_does_not_touch_newer_claim():
    client = EvalRedis()
    client.set("task", "new-token", ex=30)
    client.sadd("signals", "1000:0")

    should_continue = finish_partition_task(
        client=client,
        queue_key="events",
        signal_key="signals",
        signal_member="1000:0",
        task_key="task",
        task_token="stale-token",
        task_ttl=30,
    )

    assert should_continue is None
    assert client.get("task") == "new-token"
    assert client.smembers("signals") == {"1000:0"}


def test_finish_partition_task_uses_single_eval_command_for_redis_proxy_compatibility():
    client = Mock()
    client.eval.return_value = 0

    should_continue = finish_partition_task(
        client=client,
        queue_key="events",
        signal_key="signals",
        signal_member="1000:0",
        task_key="task",
        task_token="token",
        task_ttl=30,
    )

    assert should_continue is False
    client.eval.assert_called_once()
    client.pipeline.assert_not_called()
