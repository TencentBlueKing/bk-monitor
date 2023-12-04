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

from django.core.management.base import BaseCommand

from alarm_backends.core.cluster import get_cluster
from alarm_backends.core.storage.redis_cluster import get_node_by_strategy_id
from bkmonitor.models import CacheNode, CacheRouter


class Command(BaseCommand):
    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument("--strategy_id", type=int)
        parser.add_argument("--remove_node_id", type=int)
        parser.add_argument(
            "-r",
            action="store_true",
            help="add cache router",
        )
        parser.add_argument(
            "-a",
            action="store_true",
            help="add node",
        )
        parser.add_argument(
            "-l",
            action="store_true",
            help="list node",
        )

    def handle_list(self, strategy_id):
        current_node_id = 0
        if strategy_id:
            current_node_id = get_node_by_strategy_id(strategy_id=strategy_id).id
        for node in CacheNode.objects.filter(is_enable=True, cluster_name=get_cluster().name):
            print(f"- ({node.id}){node}{' <- {}'.format(strategy_id) if current_node_id == node.id else ''}")

    def remove_node(self, node_id):
        check = input(f"[!] check again: remove node id: {node_id}  [y]/[N]:\t")
        if check.lower().strip() == "y":
            CacheNode.objects.filter(id=node_id, cluster_name=get_cluster().name).delete()
            print(f"[*] remove id {node_id} success")
        else:
            print(f"[*] {check} nothing todo")

    def add_cache_router(self):
        node_id = None
        while not node_id:
            try:
                node_id = int(input("[*] node id:\t"))
                node = CacheNode.objects.get(id=node_id, cluster_name=get_cluster().name)
                print(f"[*] the node is: ({node.id}){node}")
            except CacheNode.DoesNotExist:
                print(f"[!] node id[{node_id}] not exists")
                node_id = None
        strategy_range = "-"
        while strategy_range == "-":
            try:
                strategy_range = input("[*] strategy range(500-5000 | 5000- | -5000):\t")
                s_id = strategy_range.split("-")
                start = s_id[0] or 0
                end = s_id[1] or 2**20
            except Exception:
                strategy_range = "-"
                continue
        print(f"[*] strategy_range: {start}-{end}")
        start = int(start)
        end = int(end)
        CacheRouter.add_router(node, score_floor=start, score_ceil=end)
        print(f"[*] add router done: ({node.id}){node}  -> {start}-{end}")

    def create_node(self):
        cache_type = None
        while cache_type is None:
            cache_type_map = {"1": "RedisCache", "2": "SentinelRedisCache"}
            cache_type = input("[*] cache_type: [1]RedisCache [2]SentinelRedisCache:\t")
            cache_type = cache_type_map.get(cache_type, cache_type)
            if cache_type not in cache_type_map.values():
                print(f"[!] invalid cache_type: {cache_type}")
                cache_type = None
                continue
            print(f"[*] new redis node type is {cache_type}")

        host = input("[*] input host: ")
        print(f"[*] host is {host}")
        port = input("[*] input port: ")
        print(f"[*] port is {port}")
        password = input("[*] input password: ")
        print("[*] password is ******")
        connection_kwargs = {}
        if cache_type == "SentinelRedisCache":
            master_name = input("[*] input master_name: ")
            print(f"[*] master_name is {master_name}")
            sentinel_password = input("[*] input sentinel_password: ")
            print("[*] sentinel_password is ******}")
            connection_kwargs = {
                "master_name": master_name,
                "sentinel_password": sentinel_password,
            }
        # todo test redis is available
        CacheNode.objects.create(
            cluster_name=get_cluster().name,
            cache_type=cache_type,
            host=host,
            port=port,
            password=password,
            connection_kwargs=connection_kwargs,
        )
        print("[*] creating cache node success")

    def handle(self, *args, **options):
        CacheNode.default_node()
        if options.get("l"):
            self.handle_list(0)
            return
        print("node list:")
        strategy_id = options.get("strategy_id")
        self.handle_list(strategy_id)

        if options.get("a"):
            self.create_node()
            self.handle_list(strategy_id)
            return

        remove_node_id = options.get("remove_node_id")
        if remove_node_id:
            self.remove_node(remove_node_id)
            return

        if options.get("r"):
            self.add_cache_router()
