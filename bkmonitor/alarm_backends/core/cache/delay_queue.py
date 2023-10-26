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
import logging
import time

from six.moves import zip

from alarm_backends.constants import CONST_MINUTES
from alarm_backends.core.cache.key import KEY_PREFIX
from alarm_backends.core.storage.redis import CACHE_BACKEND_CONF_MAP, Cache

logger = logging.getLogger("cache.delay_queue")


class DelayQueueManager(object):
    TASK_STORAGE_QUEUE = KEY_PREFIX + "task_storage"
    TASK_DELAY_QUEUE = KEY_PREFIX + "task_delay_queue"

    @classmethod
    def refresh_single_db(cls, backend):
        redis_client = Cache(backend)

        now = int(time.time())
        task_ids = redis_client.zrangebyscore(cls.TASK_DELAY_QUEUE, 0, now)

        # use the atomicity of zrem to prevent concurrency
        pipe = redis_client.pipeline()
        for task_id in task_ids:
            pipe.zrem(cls.TASK_DELAY_QUEUE, task_id)
        result = pipe.execute()
        data_keys = [data_key for data_key, flag in zip(task_ids, result) if flag]
        if not data_keys:
            return

        # load data
        task_list = redis_client.hmget(cls.TASK_STORAGE_QUEUE, data_keys)
        task_list = [json.loads(task) for task in task_list]

        # delete string key
        redis_client.hdel(cls.TASK_STORAGE_QUEUE, *data_keys)

        # redo push
        pipe = redis_client.pipeline()
        for task in task_list:
            task_id, cmd, queue, values, scheduled = task
            getattr(pipe, cmd)(queue, *values)
        pipe.execute()

    @classmethod
    def refresh(cls):
        """
        由定时任务调度，一分钟运行一次，一次运行一分钟
        """
        now = int(time.time())
        while int(time.time()) - now < CONST_MINUTES:
            duplicate_db = set()
            for backend, redis_conf in list(CACHE_BACKEND_CONF_MAP.items()):
                db = redis_conf.get("db", 0)
                if db in duplicate_db:
                    continue
                duplicate_db.add(db)

                try:
                    cls.refresh_single_db(backend)
                except Exception as e:
                    logger.exception("redo push(backend:{}), error({})" "".format(backend, e))
            time.sleep(1)


def main():
    DelayQueueManager.refresh()
