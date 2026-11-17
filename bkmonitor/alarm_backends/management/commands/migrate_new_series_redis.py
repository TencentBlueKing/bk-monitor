"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import os
import re

import redis
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from kombu.utils.url import parse_url
from redis.sentinel import Sentinel

from alarm_backends.core.cache.key import PUBLIC_KEY_PREFIX
from alarm_backends.core.cluster import get_cluster
from alarm_backends.core.storage.redis import CACHE_BACKEND_CONF_MAP, gen_resilient_socket_conf
from bkmonitor.models import CacheNode, CacheRouter

# 匹配全部 9 类 NewSeries 键模板中的 strategy_id：`<prefix>.detect.new_series.<sub_type>.<strategy_id>.<item_id>...`
_NEW_SERIES_STRATEGY_RE = re.compile(r"\.detect\.new_series\.[^.]+\.(\d+)\.")


def get_enabled_source_nodes():
    return list(CacheNode.objects.filter(is_enable=True, cluster_name=get_cluster().name).order_by("id"))


def get_cluster_routers():
    return list(CacheRouter.objects.filter(cluster_name=get_cluster().name).order_by("strategy_score", "id"))


def extract_strategy_id_from_key(raw_key: bytes | str) -> int | None:
    key_text = raw_key.decode("utf-8", errors="ignore") if isinstance(raw_key, bytes) else str(raw_key)
    matched = _NEW_SERIES_STRATEGY_RE.search(key_text)
    return int(matched.group(1)) if matched else None


def resolve_owner_node_id(strategy_id: int, routers, owner_cache: dict[int, int | None]) -> int | None:
    """按当前集群 CacheRouter 严格上限匹配（与 RedisProxy._lookup_node_in_routers 口径一致）。"""
    if strategy_id in owner_cache:
        return owner_cache[strategy_id]
    owner_id = None
    for router in routers:
        if router.strategy_score > strategy_id:
            owner_id = router.node_id
            break
    owner_cache[strategy_id] = owner_id
    return owner_id


def _service_db_and_timeout():
    service_conf = CACHE_BACKEND_CONF_MAP["service"]
    return int(service_conf.get("db", 10)), service_conf.get("socket_timeout")


def _connect_sentinel_master(hosts_str, port, master_name, password, sentinel_password, db, socket_timeout):
    sentinel_kwargs = {"socket_connect_timeout": int(getattr(settings, "REDIS_SOCKET_CONNECT_TIMEOUT", 3))}
    if sentinel_password:
        sentinel_kwargs["password"] = sentinel_password
    hosts = [(h, int(port)) for h in str(hosts_str).split(";") if h]
    sentinel = Sentinel(hosts, sentinel_kwargs=sentinel_kwargs)
    data_conf = {"db": db, "decode_responses": False, "password": password or ""}
    data_conf.update(gen_resilient_socket_conf(socket_timeout))
    master = sentinel.master_for(master_name, redis_class=redis.Redis, **data_conf)
    host, actual_port = master.connection_pool.get_master_address()
    return master, (str(host), int(actual_port), db)


def resolve_node_endpoint(node, db):
    if node.cache_type == "SentinelRedisCache":
        return None
    return (str(node.host), int(node.port), int(db))


def build_raw_source_client(node):
    """创建 decode_responses=False 的源分片客户端，供 DUMP 二进制载荷无损读取。"""
    db, socket_timeout = _service_db_and_timeout()
    if node.cache_type == "SentinelRedisCache":
        conn_kwargs = node.connection_kwargs or {}
        master_name = conn_kwargs["master_name"]
        sentinel_password = conn_kwargs.get("sentinel_password") or getattr(settings, "REDIS_SENTINEL_PASS", "")
        password = node.password or getattr(settings, "REDIS_PASSWD", "")
        client, _ = _connect_sentinel_master(
            node.host, node.port, master_name, password, sentinel_password, db, socket_timeout
        )
        return client

    conf = {
        "host": node.host,
        "port": int(node.port),
        "db": db,
        "password": node.password,
        "decode_responses": False,
    }
    conf.update(gen_resilient_socket_conf(socket_timeout))
    return redis.Redis(**conf)


def build_raw_target_client(target_url: str):
    """根据目标 URL 创建 decode_responses=False 的客户端（固定使用 service DB 10）。"""
    db, socket_timeout = _service_db_and_timeout()
    parts = parse_url(target_url)
    transport = parts.get("transport") or "redis"
    host = parts.get("hostname")
    port = int(parts.get("port") or 6379)
    password = parts.get("password")

    if not host:
        raise CommandError("Invalid target Redis URL: missing hostname")

    if transport in ("sentinel", "SentinelRedisCache"):
        master_name = parts.get("userid") or getattr(settings, "REDIS_MASTER_NAME", "mymaster")
        sentinel_password = parts.get("virtual_host") or getattr(settings, "REDIS_SENTINEL_PASS", "")
        eff_password = password if password else getattr(settings, "REDIS_PASSWD", "")
        return _connect_sentinel_master(host, port, master_name, eff_password, sentinel_password, db, socket_timeout)

    conf = {
        "host": host,
        "port": port,
        "db": db,
        "password": password,
        "decode_responses": False,
    }
    conf.update(gen_resilient_socket_conf(socket_timeout))
    return redis.Redis(**conf), (str(host), port, db)


class Command(BaseCommand):
    help = "一次性平滑迁移各分片 Redis DB10 中的 NewSeries 状态键至独立目标实例（按当前路由归属过滤，保留原 TTL，只拷不删）"

    @staticmethod
    def _escape_glob(text: str) -> str:
        # KEY_PREFIX 在非生产环境可能含 `[development]` 等字符类元字符，需转义后用于 SCAN MATCH
        return text.replace("[", r"\[").replace("]", r"\]")

    def add_arguments(self, parser):
        parser.add_argument(
            "--target-url",
            default="",
            help="目标 Redis URL（默认读取环境变量 REDIS_CACHE_NEW_SERIES_URL）",
        )
        parser.add_argument(
            "--pattern",
            default=f"{self._escape_glob(PUBLIC_KEY_PREFIX)}*.detect.new_series.*",
            help="匹配的 NewSeries 状态键 glob 模式",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=200,
            help="单次 SCAN / pipeline 批大小（默认 200；若包含十万级成员大 ZSET 可调小至 20~50 以控制单批 DUMP 内存）",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            default=False,
            help="实际写入目标 Redis（未传时默认 dry-run，只扫描计数不写入）",
        )

    def handle(self, *args, **options):
        target_url = (options["target_url"] or os.getenv("REDIS_CACHE_NEW_SERIES_URL") or "").strip()
        if not target_url:
            raise CommandError("Target Redis URL is required via --target-url or REDIS_CACHE_NEW_SERIES_URL")

        batch_size = max(1, min(int(options["batch_size"]), 1000))
        pattern = options["pattern"]
        dry_run = not bool(options["apply"])
        db, _ = _service_db_and_timeout()

        target_client, target_endpoint = build_raw_target_client(target_url)
        nodes = get_enabled_source_nodes()
        routers = get_cluster_routers()
        if not routers:
            raise CommandError("No CacheRouter records found for current cluster; aborting to avoid unrouted overwrite")

        routed_node_ids = {r.node_id for r in routers if r.strategy_score > 0}
        owner_cache: dict[int, int | None] = {}

        total_matched = 0
        total_stale_skipped = 0
        total_migrated = 0
        skipped_nodes = 0

        for node in nodes:
            if node.id not in routed_node_ids:
                skipped_nodes += 1
                self.stdout.write(
                    f"node({node.id}:{getattr(node, 'node_alias', '')}) not referenced by positive CacheRouter, skipped"
                )
                continue

            node_endpoint = resolve_node_endpoint(node, db)
            if node_endpoint is not None and node_endpoint == target_endpoint:
                skipped_nodes += 1
                self.stdout.write(f"node({node.id}:{getattr(node, 'node_alias', '')}) matches target endpoint, skipped")
                continue

            source_client = build_raw_source_client(node)
            if node.cache_type == "SentinelRedisCache":
                src_host, src_port = source_client.connection_pool.get_master_address()
                if (str(src_host), int(src_port), db) == target_endpoint:
                    skipped_nodes += 1
                    self.stdout.write(
                        f"node({node.id}:{getattr(node, 'node_alias', '')}) sentinel master matches target, skipped"
                    )
                    continue

            node_matched, node_stale_skipped, node_migrated = self._migrate_node(
                node_id=node.id,
                routers=routers,
                owner_cache=owner_cache,
                source_client=source_client,
                target_client=target_client,
                pattern=pattern,
                batch_size=batch_size,
                dry_run=dry_run,
            )
            total_matched += node_matched
            total_stale_skipped += node_stale_skipped
            total_migrated += node_migrated
            self.stdout.write(
                f"node({node.id}:{getattr(node, 'node_alias', '')}) matched={node_matched} "
                f"stale_skipped={node_stale_skipped} migrated={node_migrated} dry_run={dry_run}"
            )

        self.stdout.write(
            f"summary: nodes={len(nodes)} skipped_nodes={skipped_nodes} matched={total_matched} "
            f"stale_skipped={total_stale_skipped} migrated={total_migrated} dry_run={dry_run}"
        )

    @staticmethod
    def _migrate_node(
        node_id: int,
        routers,
        owner_cache: dict[int, int | None],
        source_client,
        target_client,
        pattern: str,
        batch_size: int,
        dry_run: bool,
    ):
        cursor = 0
        matched = 0
        stale_skipped = 0
        migrated = 0

        while True:
            cursor, keys = source_client.scan(cursor=cursor, match=pattern, count=batch_size)
            if keys:
                owned_keys = []
                for k in keys:
                    sid = extract_strategy_id_from_key(k)
                    if sid is None or sid <= 0:
                        stale_skipped += 1
                        continue
                    # 仅迁移当前 CacheRouter 归属于本节点的键，跳过路由迁移后旧分片尚未过期的残留键
                    if resolve_owner_node_id(sid, routers, owner_cache) != node_id:
                        stale_skipped += 1
                        continue
                    owned_keys.append(k)

                matched += len(owned_keys)
                if not dry_run and owned_keys:
                    read_pipe = source_client.pipeline(transaction=False)
                    for k in owned_keys:
                        read_pipe.pttl(k)
                        read_pipe.dump(k)
                    raw_pairs = read_pipe.execute()

                    write_pipe = target_client.pipeline(transaction=False)
                    queued = 0
                    for idx, k in enumerate(owned_keys):
                        pttl = raw_pairs[idx * 2]
                        payload = raw_pairs[idx * 2 + 1]
                        if payload is None or pttl == -2:
                            continue
                        # Redis RESTORE 约定 ttl=0 表示永不过期（对应源端 PTTL == -1）
                        restore_ttl = 0 if pttl is None or int(pttl) < 0 else max(1, int(pttl))
                        write_pipe.restore(k, restore_ttl, payload, replace=True)
                        queued += 1
                    if queued:
                        write_pipe.execute()
                        migrated += queued

            if int(cursor) == 0:
                break

        return matched, stale_skipped, migrated
