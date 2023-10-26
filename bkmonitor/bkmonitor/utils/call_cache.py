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


import hashlib
import pickle
import time

from django.conf import settings


class CallCache(object):
    def __init__(self, obj, timeout=None):
        self._object = obj
        self._timeout = timeout or getattr(settings, "DEFAULT_CALL_CACHE_TIMEOUT", 60)
        self._results = {}

    def __getattr__(self, item):
        attr = self.__class__(getattr(self._object, item), self._timeout)
        setattr(self, item, attr)
        return attr

    def __call__(self, *args, **kwargs):
        key = hashlib.new(
            "md5",
            pickle.dumps(
                {
                    "args": args,
                    "kwargs": kwargs,
                }
            ),
        ).hexdigest()
        now = time.time()
        cached = self._results.get(key)
        if cached and cached["time"] + self._timeout >= now:
            return cached["result"]

        result = self._object(*args, **kwargs)
        self._results[key] = {
            "result": result,
            "time": now,
        }
        return result
