# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


import logging
import time
from contextlib import contextmanager

from alarm_backends.core.storage.redis import Cache as _Cache
from bkmonitor.utils.call_cache import CallCache

from .checker import CheckerRegister
from .utils import generate_function

register = CheckerRegister.redis
Cache = CallCache(_Cache)
logger = logging.getLogger("self_monitor")


@register.status()
def cache_status(manager, result, backend="cache", key="uptime_in_seconds"):
    """Redis 状态"""
    try:
        cache = Cache(backend)
        info = cache.info()
        result.ok(info[key])
    except Exception as err:
        logger.exception(err)
        result.fail(str(err))


REDIS_INFO_KEYS = [
    "aof_rewrite_in_progress",
    "total_connections_received",
    "used_cpu_sys_children",
    "repl_backlog_active",
    "run_id",
    "rejected_connections",
    "redis_build_id",
    "used_memory_peak_human",
    "pubsub_patterns",
    "redis_mode",
    "connected_slaves",
    "db2",
    "uptime_in_days",
    "multiplexing_api",
    "lru_clock",
    "redis_version",
    "redis_git_sha1",
    "sync_partial_ok",
    "migrate_cached_sockets",
    "executable",
    "gcc_version",
    "connected_clients",
    "used_memory_lua_human",
    "used_memory",
    "tcp_port",
    "maxmemory",
    "used_cpu_user_children",
    "repl_backlog_first_byte_offset",
    "rdb_current_bgsave_time_sec",
    "pubsub_channels",
    "used_cpu_user",
    "total_system_memory_human",
    "instantaneous_ops_per_sec",
    "rdb_last_save_time",
    "total_commands_processed",
    "aof_last_write_status",
    "role",
    "cluster_enabled",
    "aof_rewrite_scheduled",
    "sync_partial_err",
    "used_memory_rss",
    "hz",
    "sync_full",
    "aof_enabled",
    "config_file",
    "used_cpu_sys",
    "rdb_last_bgsave_status",
    "instantaneous_output_kbps",
    "latest_fork_usec",
    "maxmemory_policy",
    "aof_last_bgrewrite_status",
    "maxmemory_human",
    "aof_last_rewrite_time_sec",
    "used_memory_human",
    "loading",
    "blocked_clients",
    "process_id",
    "rdb_bgsave_in_progress",
    "repl_backlog_histlen",
    "client_biggest_input_buf",
    "aof_current_rewrite_time_sec",
    "arch_bits",
    "master_repl_offset",
    "used_memory_lua",
    "rdb_last_bgsave_time_sec",
    "expired_keys",
    "mem_fragmentation_ratio",
    "total_net_input_bytes",
    "evicted_keys",
    "keyspace_misses",
    "total_system_memory",
    "repl_backlog_size",
    "instantaneous_input_kbps",
    "client_longest_output_list",
    "mem_allocator",
    "total_net_output_bytes",
    "used_memory_peak",
    "uptime_in_seconds",
    "rdb_changes_since_last_save",
    "redis_git_dirty",
    "os",
    "used_memory_rss_human",
    "keyspace_hits",
]

for key in REDIS_INFO_KEYS:
    generate_function(register.stats(key), "Redis %s" % key, cache_status, key=key)


@contextmanager
def with_client_of_fail(result, backend):
    try:
        yield Cache(backend)
    except Exception as err:
        logger.exception(err)
        raise result.fail(str(err))


CACHE_CHECK_KEY = "-- healthz checking key --"


@register.write.status()
def cache_write_status(manager, result, backend, key=None):
    """Redis 可写状态"""
    key = key or CACHE_CHECK_KEY
    with with_client_of_fail(result, backend) as client:
        result.ok(client.set(key, time.time()))


@register.read.status()
def cache_read_status(manager, result, backend, key=None):
    """Redis 可读状态"""
    key = key or CACHE_CHECK_KEY
    with with_client_of_fail(result, backend) as client:
        result.ok(client.get(key))


def cache_methods(manager, result, backend, method_name, method_args=(), **kwargs):
    with with_client_of_fail(result, backend) as client:
        method = getattr(client, method_name)
        result.ok(method(*method_args, **kwargs))


REDIS_METHODS = ["llen", "ttl", "dbsize", "exists", "hexists", "hlen", "hgetall", "scard"]

for i in REDIS_METHODS:
    generate_function(register.method(i), "Redis method %s" % i, cache_methods, method_name=i)
