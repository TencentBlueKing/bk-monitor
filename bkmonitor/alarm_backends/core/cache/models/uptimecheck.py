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

from bk_monitor_base.domains.uptime_check.models import UptimeCheckNodeModel, UptimeCheckTaskModel

from alarm_backends.core.cache.base import CacheManager


class UptimecheckCacheManager(CacheManager):
    """
    全局拨测配置缓存，直接读取模型，避免依赖页面接口的业务和租户上下文。
    """

    # 缓存key
    NODE_CACHE_KEY_TEMPLATE = CacheManager.CACHE_KEY_PREFIX + ".uptimecheck_node_{node_id}"
    TASK_CACHE_KEY_TEMPLATE = CacheManager.CACHE_KEY_PREFIX + ".uptimecheck_task_{task_id}"

    @classmethod
    def get_node(cls, node_id):
        """
        example
        {
            "name": "xxx"
        }
        """
        data = cls.cache.get(cls.NODE_CACHE_KEY_TEMPLATE.format(node_id=node_id))
        if not data:
            return None
        return json.loads(data)

    @classmethod
    def get_task(cls, task_id, refresh=False):
        if refresh:
            return cls.refresh_task(task_id)
        data = cls.cache.get(cls.TASK_CACHE_KEY_TEMPLATE.format(task_id=task_id))
        if not data:
            return None
        return json.loads(data)

    @classmethod
    def refresh_task(cls, task_id):
        task = UptimeCheckTaskModel.objects.filter(id=task_id, is_deleted=False).first()
        if task is None:
            return None
        data = {
            "id": task.id,
            "name": task.name,
            "bk_biz_id": task.bk_biz_id,
            "protocol": task.protocol,
            "config": task.config or {},
            "node_ids": list(task.nodes.values_list("id", flat=True)),
            "group_ids": list(task.groups.values_list("id", flat=True)),
            "status": task.status,
        }
        cls.cache.set(cls.TASK_CACHE_KEY_TEMPLATE.format(task_id=task_id), json.dumps(data), cls.CACHE_TIMEOUT)
        return data

    @classmethod
    def refresh_nodes(cls):
        pipeline = cls.cache.pipeline()

        nodes = list(
            UptimeCheckNodeModel.objects.filter(is_deleted=False).values("id", "name", "bk_biz_id", "ip", "plat_id")
        )
        for node in nodes:
            node["bk_cloud_id"] = node["plat_id"]
            pipeline.set(
                cls.NODE_CACHE_KEY_TEMPLATE.format(node_id=f"{node['bk_cloud_id']}:{node['ip']}"),
                json.dumps(node),
                cls.CACHE_TIMEOUT,
            )
            pipeline.set(cls.NODE_CACHE_KEY_TEMPLATE.format(node_id=node["id"]), json.dumps(node), cls.CACHE_TIMEOUT)

        pipeline.execute()
        cls.logger.info(f"refresh uptimecheck nodes finished, amount: {len(nodes)}")

    @classmethod
    def refresh_tasks(cls):
        pipeline = cls.cache.pipeline()
        tasks = list(UptimeCheckTaskModel.objects.filter(is_deleted=False).values("id", "name", "bk_biz_id"))
        count = len(tasks)
        for task in tasks:
            pipeline.set(cls.TASK_CACHE_KEY_TEMPLATE.format(task_id=task["id"]), json.dumps(task), cls.CACHE_TIMEOUT)

        pipeline.execute()
        all_task_id = cls.cache.get(cls.TASK_CACHE_KEY_TEMPLATE.format(task_id="__all__")) or "[]"
        old_task_list = set(json.loads(all_task_id))
        to_be_delete = old_task_list - {f["id"] for f in tasks}
        for t_id in to_be_delete:
            cls.cache.delete(cls.TASK_CACHE_KEY_TEMPLATE.format(task_id=t_id))
        cls.cache.set(
            cls.TASK_CACHE_KEY_TEMPLATE.format(task_id="__all__"),
            json.dumps([f["id"] for f in tasks]),
            cls.CACHE_TIMEOUT,
        )
        cls.logger.info(f"refresh uptimecheck task finished, amount: {count}")

    @classmethod
    def get_task_id_list(cls):
        all_task_id = cls.cache.get(cls.TASK_CACHE_KEY_TEMPLATE.format(task_id="__all__")) or "[]"
        return json.loads(all_task_id)

    @classmethod
    def refresh(cls):
        cls.refresh_nodes()
        cls.refresh_tasks()


def main():
    UptimecheckCacheManager.refresh()
