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

from alarm_backends.core.cache.key import DATA_SIGNAL_KEY
from bkmonitor.models import CacheNode
from core.prometheus import metrics

logger = logging.getLogger("self_monitor")


class RedisMetricCollectReport(object):
    # 默认16个db
    DB_COUNT = 16

    def __init__(self):
        self.client = DATA_SIGNAL_KEY.client

    def get_redis_info(self):
        redis_nodes = CacheNode.objects.filter(is_enable=True)
        nodes_info = []
        for node in redis_nodes:
            try:
                nodes_info.append(self.get_node_redis_info(node))
            except Exception as e:
                logger.exception("[collect redis error]{} detail: {}", node, e)
                continue
        return nodes_info

    def get_node_redis_info(self, node):
        real_client = self.client.get_client(node)
        node_info = real_client.info()
        # 在info命令获取的信息基础上增加额外的信息
        if node.cache_type == "SentinelRedisCache":
            host, port = real_client._instance.connection_pool.get_master_address()
            node_info.update(
                {
                    "mastername": real_client.master_name,
                    "node_type": "sentinel",
                    "host": host,
                    "port": port,
                }
            )
        else:
            connection_kwargs = real_client._instance.connection_pool.connection_kwargs
            node_info.update(
                {
                    "mastername": "",
                    "node_type": "standalone",
                    "host": connection_kwargs["host"],
                    "port": connection_kwargs["port"],
                }
            )

            # 获取指标config_maxclients、config_maxmemory、db的值
            node_info.update(
                {
                    "config_maxclients": int(real_client.config_get("maxclients")["maxclients"]),
                    "config_maxmemory": int(real_client.config_get("maxmemory")["maxmemory"]),
                }
            )
        return node_info

    def set_redis_metric_data(self, node_info: dict):
        labels = {
            "node_type": node_info["node_type"],
            "mastername": node_info["mastername"],
            "role": node_info["role"],
            "host": node_info["host"],
            "port": str(node_info["port"]),
        }

        # redis_exporter 和 redis info指标名不一样
        metrics.AOF_CURRENT_REWRITE_DURATION_SEC.labels(**labels).set(node_info["aof_current_rewrite_time_sec"])
        metrics.AOF_LAST_COW_SIZE_BYTES.labels(**labels).set(node_info["aof_last_cow_size"])
        metrics.AOF_LAST_REWRITE_DURATION_SEC.labels(**labels).set(node_info["aof_last_rewrite_time_sec"])
        metrics.COMMANDS_PROCESSED_TOTAL.labels(**labels).set(node_info["total_commands_processed"])
        metrics.CONNECTIONS_RECEIVED_TOTAL.labels(**labels).set(node_info["total_connections_received"])
        metrics.CPU_SYS_CHILDREN_SECONDS_TOTAL.labels(**labels).set(node_info["used_cpu_sys_children"])
        metrics.CPU_SYS_SECONDS_TOTAL.labels(**labels).set(node_info["used_cpu_sys"])
        metrics.CPU_USER_CHILDREN_SECONDS_TOTAL.labels(**labels).set(node_info["used_cpu_user_children"])
        metrics.CPU_USER_SECONDS_TOTAL.labels(**labels).set(node_info["used_cpu_user"])
        metrics.DEFRAG_HITS.labels(**labels).set(node_info["active_defrag_hits"])
        metrics.DEFRAG_KEY_HITS.labels(**labels).set(node_info["active_defrag_key_hits"])
        metrics.DEFRAG_KEY_MISSES.labels(**labels).set(node_info["active_defrag_key_misses"])
        metrics.DEFRAG_MISSES.labels(**labels).set(node_info["active_defrag_misses"])
        metrics.EVICTED_KEYS_TOTAL.labels(**labels).set(node_info["evicted_keys"])
        metrics.EXPIRED_KEYS_TOTAL.labels(**labels).set(node_info["expired_keys"])
        metrics.EXPIRED_STALE_PERCENTAGE.labels(**labels).set(node_info["expired_stale_perc"])
        metrics.EXPIRED_TIME_CAP_REACHED_TOTAL.labels(**labels).set(node_info["expired_time_cap_reached_count"])
        metrics.KEYSPACE_HITS_TOTAL.labels(**labels).set(node_info["keyspace_hits"])
        metrics.KEYSPACE_MISSES_TOTAL.labels(**labels).set(node_info["keyspace_misses"])
        metrics.LATEST_FORK_SECONDS.labels(**labels).set(node_info["latest_fork_usec"] / 1000000)
        metrics.LOADING_DUMP_FILE.labels(**labels).set(node_info["loading"])
        metrics.MEMORY_MAX_BYTES.labels(**labels).set(node_info["maxmemory"])
        metrics.MEMORY_USED_BYTES.labels(**labels).set(node_info["used_memory"])
        metrics.MEMORY_USED_DATASET_BYTES.labels(**labels).set(node_info["used_memory_dataset"])
        metrics.MEMORY_USED_LUA_BYTES.labels(**labels).set(node_info["used_memory_lua"])
        metrics.MEMORY_USED_OVERHEAD_BYTES.labels(**labels).set(node_info["used_memory_overhead"])
        metrics.MEMORY_USED_PEAK_BYTES.labels(**labels).set(node_info["used_memory_peak"])
        metrics.MEMORY_USED_RSS_BYTES.labels(**labels).set(node_info["used_memory_rss"])
        metrics.MEMORY_USED_STARTUP_BYTES.labels(**labels).set(node_info["used_memory_startup"])
        metrics.MIGRATE_CACHED_SOCKETS_TOTAL.labels(**labels).inc(node_info["migrate_cached_sockets"])
        metrics.NET_INPUT_BYTES_TOTAL.labels(**labels).set(node_info["total_net_input_bytes"])
        metrics.NET_OUTPUT_BYTES_TOTAL.labels(**labels).set(node_info["total_net_output_bytes"])
        metrics.RDB_CURRENT_BGSAVE_DURATION_SEC.labels(**labels).set(node_info["rdb_current_bgsave_time_sec"])
        metrics.RDB_LAST_BGSAVE_DURATION_SEC.labels(**labels).set(node_info["rdb_last_bgsave_time_sec"])
        metrics.RDB_LAST_COW_SIZE_BYTES.labels(**labels).set(node_info["rdb_last_cow_size"])
        metrics.RDB_LAST_SAVE_TIMESTAMP_SECONDS.labels(**labels).set(node_info["rdb_last_save_time"])
        metrics.REJECTED_CONNECTIONS_TOTAL.labels(**labels).set(node_info["rejected_connections"])
        metrics.REPL_BACKLOG_HISTORY_BYTES.labels(**labels).set(node_info["repl_backlog_histlen"])
        metrics.REPL_BACKLOG_IS_ACTIVE.labels(**labels).set(node_info["repl_backlog_active"])
        metrics.REPLICA_PARTIAL_RESYNC_ACCEPTED.labels(**labels).set(node_info["sync_partial_ok"])
        metrics.REPLICA_PARTIAL_RESYNC_DENIED.labels(**labels).set(node_info["sync_partial_err"])
        metrics.REPLICA_RESYNCS_FULL.labels(**labels).set(node_info["sync_full"])
        metrics.REPLICATION_BACKLOG_BYTES.labels(**labels).set(node_info["repl_backlog_size"])
        metrics.START_TIME_SECONDS.labels(**labels).set(node_info["uptime_in_seconds"])
        metrics.CLIENT_BIGGEST_INPUT_BUF.labels(**labels).set(node_info["client_recent_max_input_buffer"])

        # redis_exporter 和 redis info指标名一样的
        metrics.ACTIVE_DEFRAG_RUNNING.labels(**labels).set(node_info["active_defrag_running"])
        metrics.AOF_ENABLED.labels(**labels).set(node_info["aof_enabled"])
        metrics.AOF_LAST_BGREWRITE_STATUS.labels(**labels).set(
            1 if node_info["aof_last_bgrewrite_status"].lower() == "ok" else 0
        )
        metrics.AOF_LAST_WRITE_STATUS.labels(**labels).set(
            1 if node_info["aof_last_write_status"].lower() == "ok" else 0
        )
        metrics.AOF_REWRITE_IN_PROGRESS.labels(**labels).set(node_info["aof_rewrite_in_progress"])
        metrics.AOF_REWRITE_SCHEDULED.labels(**labels).set(node_info["aof_rewrite_scheduled"])
        metrics.CLUSTER_ENABLED.labels(**labels).set(node_info["cluster_enabled"])
        metrics.LAZYFREE_PENDING_OBJECTS.labels(**labels).set(node_info["lazyfree_pending_objects"])
        metrics.PROCESS_ID.labels(**labels).set(node_info["process_id"])
        metrics.RDB_BGSAVE_IN_PROGRESS.labels(**labels).set(node_info["rdb_bgsave_in_progress"])
        metrics.RDB_LAST_BGSAVE_STATUS.labels(**labels).set(
            1 if node_info["rdb_last_bgsave_status"].lower() == "ok" else 0
        )
        metrics.REPL_BACKLOG_FIRST_BYTE_OFFSET.labels(**labels).set(node_info["repl_backlog_first_byte_offset"])
        metrics.SECOND_REPL_OFFSET.labels(**labels).set(node_info["second_repl_offset"])
        metrics.SLAVE_EXPIRES_TRACKED_KEYS.labels(**labels).set(node_info["slave_expires_tracked_keys"])
        metrics.CONNECTED_CLIENTS.labels(**labels).set(node_info["connected_clients"])
        metrics.BLOCKED_CLIENTS.labels(**labels).set(node_info["blocked_clients"])
        metrics.MEM_FRAGMENTATION_RATIO.labels(**labels).set(node_info["mem_fragmentation_ratio"])
        if "aof_buffer_length" in node_info:
            metrics.AOF_BUFFER_LENGTH.labels(**labels).set(node_info["aof_buffer_length"])
            metrics.AOF_CURRENT_SIZE.labels(**labels).set(node_info["aof_current_size"])
        metrics.RDB_CHANGES_SINCE_LAST_SAVE.labels(**labels).set(node_info["rdb_changes_since_last_save"])
        metrics.PUBSUB_CHANNELS.labels(**labels).set(node_info["pubsub_channels"])
        metrics.PUBSUB_PATTERNS.labels(**labels).set(node_info["pubsub_patterns"])
        metrics.CONNECTED_SLAVES.labels(**labels).set(node_info["connected_slaves"])
        metrics.MASTER_REPL_OFFSET.labels(**labels).set(node_info["master_repl_offset"])

        # 不是从info命令获取指标值的
        metrics.CONFIG_MAXCLIENTS.labels(**labels).set(node_info["config_maxclients"])
        metrics.CONFIG_MAXMEMORY.labels(**labels).set(node_info["config_maxmemory"])

        # key
        for i in range(self.DB_COUNT):
            db_key = f"db{i}"
            if db_key not in node_info:
                continue
            key_info = node_info[db_key]
            metrics.DB_AVG_TTL_SECONDS.labels(**labels, db=i).set(key_info["avg_ttl"] / 1000)
            metrics.DB_KEYS.labels(**labels, db=i).set(key_info["keys"])
            metrics.DB_KEYS_EXPIRING.labels(**labels, db=i).set(key_info["expires"])

    def collect_report_redis_metric_data(self):
        nodes_info = self.get_redis_info()
        for node_info in nodes_info:
            self.set_redis_metric_data(node_info)
        metrics.report_all()
