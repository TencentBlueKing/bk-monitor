"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
import math
import threading
import time
import uuid
from contextlib import contextmanager


logger = logging.getLogger("access.event")

PULL_EVENT_RECORDS_SCRIPT = """
local total = redis.call('LLEN', KEYS[1])
local max_records = tonumber(ARGV[1])
local max_length = tonumber(ARGV[2])
local dropped = 0
if max_length > 0 and total > max_length then
    dropped = total - max_length
    redis.call('LTRIM', KEYS[1], 0, max_length - 1)
    total = max_length
end
local offset = math.min(total, max_records)
if offset == 0 then
    return {dropped, {}}
end
local records = redis.call('LRANGE', KEYS[1], -offset, -1)
redis.call('LTRIM', KEYS[1], 0, -offset - 1)
return {dropped, records}
"""

START_PARTITION_TASK_SCRIPT = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then
    return 0
end
redis.call('SET', KEYS[1], ARGV[2], 'EX', ARGV[3])
return 1
"""

REFRESH_PARTITION_TASK_SCRIPT = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then
    return 0
end
redis.call('EXPIRE', KEYS[1], ARGV[2])
return 1
"""

FINISH_PARTITION_TASK_SCRIPT = """
local current_token = redis.call('GET', KEYS[3])
if current_token ~= ARGV[2] then
    return -1
end
if redis.call('LLEN', KEYS[1]) == 0 then
    redis.call('SREM', KEYS[2], ARGV[1])
    redis.call('DEL', KEYS[3])
    return 0
end
redis.call('EXPIRE', KEYS[3], ARGV[3])
return 1
"""


def build_partition_signal(data_id, partition):
    return f"{data_id}:{partition}"


def parse_partition_signal(signal):
    data_id, separator, partition = signal.rpartition(":")
    if not separator or not data_id or not partition:
        raise ValueError(f"invalid access event partition signal: {signal!r}")
    try:
        partition_number = int(partition)
    except ValueError as exc:
        raise ValueError(f"invalid access event partition signal: {signal!r}") from exc
    if partition_number < 0:
        raise ValueError(f"invalid access event partition signal: {signal!r}")
    return data_id, partition_number


def get_partition_queue_max_length(total_max_length, partition_count):
    if total_max_length <= 0:
        raise ValueError("total_max_length must be greater than zero")
    if partition_count <= 0:
        raise ValueError("partition_count must be greater than zero")
    return math.ceil(total_max_length / partition_count)


def get_event_lock_id(data_id, partition=None):
    if partition is None:
        return f"{data_id}-[redis]"
    return f"{data_id}-partition-{partition}-[redis]"


def get_event_queue_key(data_id, partition, legacy_key, partition_key):
    if partition is None:
        return legacy_key.get_key(data_id=data_id)
    return partition_key.get_key(data_id=data_id, partition=partition)


def pull_event_records(client, queue_key, max_records, max_length=0):
    if max_records <= 0:
        raise ValueError("max_records must be greater than zero")
    if max_length < 0:
        raise ValueError("max_length must not be negative")
    dropped_count, records = client.eval(
        PULL_EVENT_RECORDS_SCRIPT,
        1,
        queue_key,
        max_records,
        max_length,
    )
    return records, int(dropped_count)


def acquire_partition_task(client, task_key, ttl):
    task_token = uuid.uuid4().hex
    if client.set(task_key, task_token, nx=True, ex=ttl):
        return task_token
    return None


def start_partition_task(client, task_key, expected_token, ttl):
    active_token = uuid.uuid4().hex
    started = client.eval(
        START_PARTITION_TASK_SCRIPT,
        1,
        task_key,
        expected_token,
        active_token,
        ttl,
    )
    return active_token if started else None


def refresh_partition_task(client, task_key, active_token, ttl):
    return bool(
        client.eval(
            REFRESH_PARTITION_TASK_SCRIPT,
            1,
            task_key,
            active_token,
            ttl,
        )
    )


@contextmanager
def keep_partition_task_alive(client, task_key, active_token, ttl, max_lease):
    if max_lease <= 0:
        raise ValueError("max_lease must be greater than zero")

    stop_event = threading.Event()
    refresh_interval = max(ttl / 3, 0.1)
    lease_deadline = time.monotonic() + max_lease

    def refresh_loop():
        while True:
            remaining_lease = lease_deadline - time.monotonic()
            if remaining_lease <= 0:
                logger.warning("[access event] partition task reached max lease: %s", task_key)
                return
            if stop_event.wait(min(refresh_interval, remaining_lease)):
                return
            try:
                if not refresh_partition_task(client, task_key, active_token, ttl):
                    return
            except Exception as e:
                logger.warning("[access event] refresh partition task lease failed: %s", e)

    refresh_thread = threading.Thread(target=refresh_loop, name="access-event-partition-lease", daemon=True)
    refresh_thread.start()
    try:
        yield
    finally:
        stop_event.set()
        refresh_thread.join()


def enqueue_partition_messages(
    client,
    queue_key,
    signal_key,
    signal_member,
    task_key,
    messages,
    max_length,
    queue_ttl,
    task_ttl,
):
    if max_length <= 0:
        raise ValueError("max_length must be greater than zero")
    if not messages:
        return 0, None

    task_token = uuid.uuid4().hex
    pipeline = client.pipeline()
    pipeline.lpush(queue_key, *messages)
    pipeline.ltrim(queue_key, 0, max_length - 1)
    pipeline.expire(queue_key, queue_ttl)
    pipeline.sadd(signal_key, signal_member)
    pipeline.expire(signal_key, queue_ttl)
    pipeline.set(task_key, task_token, nx=True, ex=task_ttl)
    length_before_trim, _, _, _, _, task_acquired = pipeline.execute()
    dropped_count = max(length_before_trim - max_length, 0)
    return dropped_count, task_token if task_acquired else None


def finish_partition_task(
    client,
    queue_key,
    signal_key,
    signal_member,
    task_key,
    task_token,
    task_ttl,
):
    result = client.eval(
        FINISH_PARTITION_TASK_SCRIPT,
        3,
        queue_key,
        signal_key,
        task_key,
        signal_member,
        task_token,
        task_ttl,
    )
    if result < 0:
        return None
    return bool(result)
