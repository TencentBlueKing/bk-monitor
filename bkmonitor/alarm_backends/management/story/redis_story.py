"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import time

from alarm_backends.core.cache.key import DATA_SIGNAL_KEY
from alarm_backends.management.story.base import (
    BaseStory,
    CheckStep,
    Problem,
    register_step,
    register_story,
)
from bkmonitor.models import CacheNode


@register_story()
class RedisStory(BaseStory):
    name = "Redis Healthz Check"

    def __init__(self):
        self.client = DATA_SIGNAL_KEY.client

    def bulk_send_client(self, cmd, *args, **kwargs):
        result = {}
        for node in CacheNode.objects.filter(is_enable=True):
            real_client = self.client.get_client(node)
            command = getattr(real_client, cmd)
            result.setdefault(str(node), command(*args, **kwargs))
        return result


@register_step(RedisStory)
class RedisEvictedKeys(CheckStep):
    name = "check redis_evicted_keys"

    def check(self):
        p_list = []
        for node_name, stats_info in self.story.bulk_send_client("info", "stats").items():
            evicted_keys = stats_info.get("evicted_keys")
            if evicted_keys is None:
                self.story.warning(f"[{node_name}] redis info stats did not return evicted_keys metric")
                continue
            if evicted_keys > 0:
                time.sleep(0.5)
                if not self.story.bulk_send_client("info", "stats")[node_name].get("evicted_keys") == evicted_keys:
                    p = RedisMemoryProblem(
                        f"[{node_name}]redis memory is not enough, {evicted_keys} keys is evicted, and still growing",  # noqa
                        self.story,
                    )
                    p_list.append(p)
                    continue
            self.story.info(f"[{node_name}]redis history redis_evicted_keys: {evicted_keys}, now evicted_keys: 0")
        return p_list


@register_step(RedisStory)
class Memory(CheckStep):
    name = "check redis memory"

    def check(self):
        p_list = []
        for node_name, mem_info in self.story.bulk_send_client("info", "memory").items():
            mem_info = mem_info or {}

            max_memory = mem_info.get("maxmemory") or mem_info.get("total_system_memory")
            if not max_memory:
                self.story.warning(f"[{node_name}]can't get max mem. now used: {mem_info['used_memory_human']}")
                continue
            # memory usage:
            usage = round(mem_info["used_memory"] * 100.0 / max_memory, 2)
            if usage > 95:
                p = RedisMemoryProblem(f"[{node_name}]redis memory usage is too high: {usage}%", self.story)
                p_list.append(p)
                continue
            func = self.story.info
            if usage > 80:
                func = self.story.warning
            func(f"[{node_name}]redis memory usage: {usage}%")
            # mem_fragmentation_ratio
            mem_fragmentation_ratio = mem_info["mem_fragmentation_ratio"]
            if usage > 50 and mem_fragmentation_ratio >= 2:
                p = RedisFragmentationProblem(
                    f"[{node_name}]redis memory fragmentation ratio is too high: {mem_fragmentation_ratio}%", self.story
                )
                p_list.append(p)
                continue
            # if mem_fragmentation_ratio > 1.5:
            #     func = self.story.warning
            # func(f"[{node_name}]redis memory fragmentation ratio: {mem_fragmentation_ratio}")
        return p_list


class RedisMemoryProblem(Problem):
    def position(self):
        self.story.warning("建议：内存不够情况下：对redis进行扩容")


class RedisFragmentationProblem(Problem):
    def position(self):
        self.story.warning("建议：碎片率高的情况下，考虑持久化redis后，重新启动redis")
