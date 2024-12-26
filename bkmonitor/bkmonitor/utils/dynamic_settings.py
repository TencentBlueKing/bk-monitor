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


from django.conf import settings
from django.utils.functional import cached_property, empty

from bkmonitor.utils.cache import InstanceCache


class DynamicSettings(object):
    __cache_expires__ = 60
    __name_list__ = set()

    def __init__(self, wrapped, global_config_model):
        self._wrapped = wrapped
        self._global_config_model = global_config_model

        from bkmonitor.define import global_config

        self.__name_list__ = set(global_config.GLOBAL_CONFIGS)

    @cached_property
    def _cache(self):
        return InstanceCache()

    def __getattr__(self, name):
        value = getattr(self._wrapped, name)
        if name not in self.__name_list__:
            return value

        if self._cache.exists(name):
            value = self._cache.get(name)
            if value is not None:
                return value

        value = self._global_config_model.get(name, value)
        self._cache.set(name, value, self.__cache_expires__, use_round=True)
        return value

    def __setattr__(self, name, value):
        if name in self.__name_list__:
            self._global_config_model.set(name, value)
            self._cache.delete(name)
        elif name.isupper():
            setattr(self._wrapped, name, value)
        else:
            super(DynamicSettings, self).__setattr__(name, value)

    def __delattr__(self, name):
        if hasattr(self, name):
            delattr(self, name)
        self.__name_list__.remove(name)
        delattr(self._wrapped, name)

    def __dir__(self):
        return dir(self._wrapped)


def hack_settings(global_config_model, settings_=None):
    if not settings.USE_DYNAMIC_SETTINGS:
        # 不启动动态配置
        return
    from django.conf import LazySettings

    LazySettings.__getattr__ = lazy__getattr__
    settings_ = settings_ or settings
    wrapped = settings_._wrapped
    settings_._wrapped = DynamicSettings(wrapped, global_config_model)


def lazy__getattr__(self, name):
    """
    Return the value of a setting and cache it in self.__dict__.
    """
    if self._wrapped is empty:
        self._setup(name)
    val = getattr(self._wrapped, name)
    if name not in self._wrapped.__name_list__:
        self.__dict__[name] = val
    return val
