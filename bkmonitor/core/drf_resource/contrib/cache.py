"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import abc

import six

from bkmonitor.utils.cache import CacheTypeItem, using_cache
from core.drf_resource.base import Resource


class CacheResource(six.with_metaclass(abc.ABCMeta, Resource)):
    """
    支持缓存的resource
    """

    # 缓存类型
    cache_type = None
    # 后台缓存类型
    backend_cache_type = None
    # 缓存是否与用户关联
    cache_user_related = None
    # 是否使用压缩
    cache_compress = True

    def __init__(self, *args, **kwargs):
        # 若cache_type为None则视为关闭缓存功能
        if self._need_cache_wrap():
            self._wrap_request()
        super().__init__(*args, **kwargs)

    def _need_cache_wrap(self):
        need_cache = False
        if self.cache_type is not None:
            if not isinstance(self.cache_type, CacheTypeItem):
                raise TypeError("param 'cache_type' must be aninstance of <utils.cache.CacheTypeItem>")
            need_cache = True
        if self.backend_cache_type is not None:
            if not isinstance(self.backend_cache_type, CacheTypeItem):
                raise TypeError("param 'cache_type' must be aninstance of <utils.cache.CacheTypeItem>")
            need_cache = True
        return need_cache

    def _wrap_request(self):
        """
        将原有的request方法替换为支持缓存的request方法
        """

        def func_key_generator(resource):
            key = f"{resource.__self__.__class__.__module__}.{resource.__self__.__class__.__name__}"
            return key

        self._using_cache = using_cache(
            cache_type=self.cache_type,
            backend_cache_type=self.backend_cache_type,
            user_related=self.cache_user_related,
            compress=self.cache_compress,
            is_cache_func=self.cache_write_trigger,
            func_key_generator=func_key_generator,
        )
        # 保留原始 request 引用，get_cached/set_cached 据此推导与 request() 一致的缓存 key
        self._cache_target_func = self.request
        self.request = self._using_cache(self.request)

    def get_cached(self, *args, **kwargs):
        """
        仅探测缓存（与 request(*args, **kwargs) 同 key）：命中返回缓存值，
        未命中或未启用缓存返回 None，不执行 perform_request。
        """
        if getattr(self, "_using_cache", None) is None:
            return None
        return self._using_cache.get_cached(self._cache_target_func, args, kwargs)

    def set_cached(self, value, *args, **kwargs):
        """
        把外部计算好的结果按 request(*args, **kwargs) 的缓存语义（同 key/超时/写入条件）回写。
        与 get_cached 配对，供「探缓存未命中后批量计算」的调用方回填单 key 缓存。
        """
        if getattr(self, "_using_cache", None) is None:
            return
        self._using_cache.set_cached(self._cache_target_func, args, kwargs, value)

    def cache_write_trigger(self, res):
        """
        缓存写入触发条件
        """
        return True
