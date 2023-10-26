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


import abc
import logging

import six

from alarm_backends.constants import CONST_ONE_DAY
from alarm_backends.core.cache.key import PUBLIC_KEY_PREFIX
from alarm_backends.core.storage.redis import Cache


class CacheManager(six.with_metaclass(abc.ABCMeta, object)):
    """
    缓存管理基类
    """

    CACHE_KEY_PREFIX = PUBLIC_KEY_PREFIX + ".cache"

    CACHE_TIMEOUT = CONST_ONE_DAY

    cache = Cache("cache")
    logger = logging.getLogger("cache")

    @classmethod
    @abc.abstractmethod
    def refresh(cls):
        """
        刷新缓存
        """
        raise NotImplementedError

    @property
    def read_cache(self):
        """
        读取缓存
        """
        return self.cache.readonly_instance
