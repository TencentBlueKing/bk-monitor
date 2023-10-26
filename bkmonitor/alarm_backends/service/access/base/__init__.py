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
from typing import Dict

logger = logging.getLogger("access")


####################################
#           Base Filter            #
####################################
class Filter(object):
    def filter(self, record):
        """
        Determine if the specified record is to be handled.
        """
        return False


class Filterer(object):
    def __init__(self):
        super(Filterer, self).__init__()
        self.filters = []

    def add_filter(self, f):
        if not (f in self.filters):
            self.filters.append(f)

    def remove_filter(self, f):
        if f in self.filters:
            self.filters.remove(f)

    def filter(self, record):
        for f in self.filters:
            if f.filter(record):
                return True
        return False


####################################
#           Base Fuller            #
####################################
class Fuller(object):
    def full(self, record):
        """
        Supplement some dimension information.
        """
        pass


class Fullerer(object):
    def __init__(self):
        super(Fullerer, self).__init__()
        self.fullers = []

    def add_fuller(self, f):
        if not (f in self.fullers):
            self.fullers.append(f)

    def remove_fuller(self, f):
        if f in self.fullers:
            self.fullers.remove(f)

    def full(self, record):
        for f in self.fullers:
            f.full(record)


####################################
#           Base Record            #
####################################
class BaseRecord(Filterer):
    """
    A Record instance represents an data record being handled.
    """

    def __init__(self, raw_data: Dict):
        super(BaseRecord, self).__init__()
        self.raw_data = raw_data
        self.data = {}

    def __str__(self):
        return json.dumps(self.__dict__)

    def to_str(self):
        return json.dumps(self.data)

    def check(self):
        """Check if origin data is valid, (default: return True)"""
        return True

    def full(self):
        """Add some other property to data, (default: do nothing)"""
        return [self]

    def clean(self):
        """Clean data according to standard format"""
        return self


####################################
#           Base Process           #
####################################
class BaseAccessProcess(Filterer, Fullerer):
    """
    Access instance pull different things(data,event,alert)

    The Base Access class. defines the BaseAccess interface.
    You should inherit this class and implement the pull/push method
    """

    def __init__(self, *args, **kwargs):
        super(BaseAccessProcess, self).__init__()

        self.record_list = []
        self.pull_duration = 0

    def __str__(self):
        return self.__class__.__name__

    def process(self):
        logger.info(f"--begin {self}")
        start = time.time()
        exc = None
        try:
            self.pull()
            self.pull_duration = time.time() - start
            self.handle()
            self.push()
        except Exception as e:
            logger.exception(e)
            exc = e
        logger.info(f"--end {self} cost: {time.time()-start}")
        return exc

    def pull(self):
        """
        Pull raw data and generate record.
        """
        raise NotImplementedError("pull must be implemented " "by BaseAccessProcess subclasses")

    def push(self):
        """
        Push record to Queue.
        """
        raise NotImplementedError("push must be implemented " "by BaseAccessProcess subclasses")

    def handle(self):
        record_list = []
        for r in self.record_list:
            # 补充维度：比如：业务、集群、模块等信息
            self.full(r)

            new_r_list = r.full()
            if not new_r_list:
                continue

            record_list.extend(new_r_list)

        output = []
        for r in record_list:
            # 过滤数据
            if self.filter(r) or r.filter(r):
                continue

            # 格式化数据
            r.clean()

            output.append(r)

        self.record_list = output
        self.post_handle()

    def post_handle(self):
        pass
