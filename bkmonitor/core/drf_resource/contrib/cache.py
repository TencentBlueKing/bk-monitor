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

import six

from bkmonitor.utils.cache import CacheTypeItem, using_cache
from bkmonitor.utils.request import get_request
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
        super(CacheResource, self).__init__(*args, **kwargs)

    def _need_cache_wrap(self):
        need_cache = False
        if self.cache_type is not None:
            if not isinstance(self.cache_type, CacheTypeItem):
                raise TypeError("param 'cache_type' must be an" "instance of <utils.cache.CacheTypeItem>")
            need_cache = True
        if self.backend_cache_type is not None:
            if not isinstance(self.backend_cache_type, CacheTypeItem):
                raise TypeError("param 'cache_type' must be an" "instance of <utils.cache.CacheTypeItem>")
            need_cache = True
        return need_cache

    def _wrap_request(self):
        """
        将原有的request方法替换为支持缓存的request方法
        """

        def func_key_generator(resource):
            key = "{}.{}".format(resource.__self__.__class__.__module__, resource.__self__.__class__.__name__)
            return key

        self.request = using_cache(
            cache_type=self.cache_type,
            backend_cache_type=self.backend_cache_type,
            user_related=self.cache_user_related,
            compress=self.cache_compress,
            is_cache_func=self.cache_write_trigger,
            func_key_generator=func_key_generator,
        )(self.request)

    def cache_write_trigger(self, res):
        """
        缓存写入触发条件
        """
        return True


class TimedCacheResource(CacheResource):
    def round_to_five_minutes(self, timestamps):
        """将时间戳按5分钟取整"""
        if timestamps is None:
            return None
        period = 5 * 60  # 5分钟秒数
        return int(timestamps // period) * period

    def _wrap_request(self):
        """
        将原有的request方法替换为支持缓存的request方法
        """

        def func_key_generator(resource):
            request = get_request()
            try:
                # 合并获取参数逻辑，增加类型安全校验
                start_time = request.GET.get('start_time') or request.POST.get('start_time')
                end_time = request.GET.get('end_time') or request.POST.get('end_time')

                start = self.round_to_five_minutes(int(start_time)) if start_time else 0
                end = self.round_to_five_minutes(int(end_time)) if end_time else 0
            except (ValueError, TypeError):
                start = end = 0

            # 使用更高效的f-string格式化
            key = f"{resource.__self__.__class__.__module__}.{resource.__self__.__class__.__name__}"

            # 优化条件判断逻辑
            if all((start, end)):
                return f"{key}.{start}_{end}"
            return key

        self.request = using_cache(
            cache_type=self.cache_type,
            backend_cache_type=self.backend_cache_type,
            user_related=self.cache_user_related,
            compress=self.cache_compress,
            is_cache_func=self.cache_write_trigger,
            func_key_generator=func_key_generator,
        )(self.request)
