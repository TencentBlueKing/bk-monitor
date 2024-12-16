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


import time
import uuid

from django.core.cache import cache
from django.utils.translation import gettext as _

from core.errors.collecting import LockTimeout


class CacheLock(object):
    def __init__(self, module, expires=60, wait_timeout=0):
        self.cache = cache
        self.module = module
        self.expires = expires  # 函数执行超时时间
        self.wait_timeout = wait_timeout  # 拿锁等待超时时间

    def get_lock(self, lock_key):
        # 获取cache锁
        wait_timeout = self.wait_timeout
        identifier = uuid.uuid4()
        while wait_timeout >= 0:
            if self.cache.add(lock_key, identifier, self.expires):
                return identifier
            wait_timeout -= 1
            time.sleep(1)
        raise LockTimeout({"msg": _("当前有其他用户正在编辑该采集配置，请稍后重试")})

    def release_lock(self, lock_key, identifier):
        # 释放cache锁
        lock_value = self.cache.get(lock_key)
        if lock_value == identifier:
            self.cache.delete(lock_key)


def lock(cache_lock):
    def my_decorator(func):
        def wrapper(*args, **kwargs):
            collect_config = args[1]
            lock_key = "bk_monitor:lock:{}_{}".format(cache_lock.module, collect_config.id)
            identifier = cache_lock.get_lock(lock_key)
            try:
                return func(*args, **kwargs)
            finally:
                cache_lock.release_lock(lock_key, identifier)

        return wrapper

    return my_decorator
