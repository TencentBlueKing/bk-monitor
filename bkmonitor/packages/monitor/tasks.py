# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


import functools
import logging
import random
import sys
import time

from django.core.cache import cache

from bkmonitor.utils.local import local
from common import log
from common.log import logger

if "celery" in sys.argv:
    log.logger_detail = logging.getLogger("celery")

DEFAULT_RANDOM_RANGE = 10  # 将任务随机打散在[0, RANDOM_RANGE]时间范围内
DEFAULT_TASK_INTERVAL = 120  # 两次任务之间的间隔(即缓存有效期), 以任务开始执行时计算
DEFAULT_TASK_EXPIRES = 30  # 任务执行过期时间


class task_decorator(object):
    def __init__(self, random_range=DEFAULT_RANDOM_RANGE, task_interval=DEFAULT_TASK_INTERVAL):
        self.random_range = random_range if random_range > 0 else DEFAULT_RANDOM_RANGE
        self.task_interval = task_interval if task_interval > 0 else DEFAULT_TASK_INTERVAL

    def lock_key(self, task_name, args, kwargs):
        # 注意, 参数过多会导致这个key很长, 可以转成MD5
        return "__lock__{}_cache_{}__".format(task_name, (args, kwargs))

    def __call__(self, task_func):
        @functools.wraps(task_func)
        def wrapper(*args, **kwargs):
            task_name = task_func.__name__
            lock_key = self.lock_key(task_name, args, kwargs)
            try:
                # 如果key存在, 则说明前面的任务还没有运行结束
                if cache.get(lock_key):
                    return "the prev task is running, task:(%s)" % (lock_key)
                cache.set(lock_key, time.time(), self.task_interval)

                # 打散任务,避免同时并发
                time.sleep(random.randint(0, self.random_range))

                task_func(*args, **kwargs)
            except Exception as e:
                logger.error("call {} error:{}".format(lock_key, e))
            finally:
                local.clear()
                # redis_cli.delete(lock_key)
            return "call %s success" % (lock_key)

        return wrapper
