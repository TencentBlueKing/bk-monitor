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


from abc import ABCMeta, abstractmethod

import six


class BaseHandler(six.with_metaclass(ABCMeta, object)):
    """
    Base Handler

    # handler 需要支持多种方式执行
    1. 使用多线程
    2. 使用多进程（默认）
    3. 使用celery的方式运行
    """

    def __init__(self, *args, **kwargs):
        super(BaseHandler, self).__init__()

    @abstractmethod
    def handle(self):
        raise NotImplementedError("handle must be implemented " "by BaseHandler subclasses")
