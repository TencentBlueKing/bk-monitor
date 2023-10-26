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


class TimeStats(object):
    """
    时间诊断
    """

    auto_start = True

    def __init__(self, bucket=""):
        self._bucket = bucket
        self.info = []
        self._slug = []
        if self.auto_start:
            self.start()

    def start(self):
        self._start = time.time()
        self._split = [
            self._start,
        ]

    def stop(self):
        self._end = time.time()
        if self._slug:
            self.info.append("{}.{}: {}".format(self._bucket, self._slug[-1], (self._end - self._split[-1])))
        self.info.insert(0, "{}.total: {}".format(self._bucket, (self._end - self._start)))
        self._split.append(self._end)

    def split(self, slug):
        _timing = time.time()
        if slug == "stop":
            return self.stop()
        if self._slug:
            self.info.append("{}.{}: {}".format(self._bucket, self._slug[-1], (_timing - self._split[-1])))
        self._slug.append(slug)
        self._split.append(_timing)

    def display(self):
        return "*** time stats ***\n" + "\n".join(self.info)
