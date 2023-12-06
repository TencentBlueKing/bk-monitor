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


import json

from alarm_backends.core.cache.base import CacheManager
from core.drf_resource import api


class UptimecheckCacheManager(CacheManager):
    """
    采集配置缓存
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
    def get_task(cls, task_id):
        """
        example
        {
            "name": "yyy"
        }
        """
        data = cls.cache.get(cls.TASK_CACHE_KEY_TEMPLATE.format(task_id=task_id))
        if not data:
            return None
        return json.loads(data)

    @classmethod
    def refresh_nodes(cls):
        pipeline = cls.cache.pipeline()

        nodes = api.monitor.uptime_check_node_list()
        for node in nodes:
            pipeline.set(
                cls.NODE_CACHE_KEY_TEMPLATE.format(node_id=f"{node['bk_cloud_id']}:{node['ip']}"),
                json.dumps(node),
                cls.CACHE_TIMEOUT,
            )
            pipeline.set(cls.NODE_CACHE_KEY_TEMPLATE.format(node_id=node["id"]), json.dumps(node), cls.CACHE_TIMEOUT)

        pipeline.execute()
        cls.logger.info("refresh uptimecheck nodes finished, amount: {}".format(len(nodes)))

    @classmethod
    def refresh_tasks(cls):
        pipeline = cls.cache.pipeline()
        tasks = api.monitor.uptime_check_task_list(plain=True)
        count = len(tasks)
        for task in tasks:
            pipeline.set(cls.TASK_CACHE_KEY_TEMPLATE.format(task_id=task["id"]), json.dumps(task), cls.CACHE_TIMEOUT)

        pipeline.execute()

        cls.logger.info("refresh uptimecheck task finished, amount: {}".format(count))

    @classmethod
    def refresh(cls):
        cls.refresh_nodes()
        cls.refresh_tasks()


def main():
    UptimecheckCacheManager.refresh()
