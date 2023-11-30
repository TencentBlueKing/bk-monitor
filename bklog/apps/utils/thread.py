# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""
from concurrent.futures import ThreadPoolExecutor
from typing import List, Tuple

import pytz
from django.utils import timezone
from opentelemetry.context import attach, get_current
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.utils.function import ignored
from apps.utils.local import (
    activate_request,
    get_local_param,
    get_request,
    set_local_param,
)


class FuncThread:
    def __init__(self, func, params, result_key, results, use_request=True, multi_func_params=False):
        self.func = func
        self.params = params
        self.result_key = result_key
        self.results = results
        self.use_request = use_request
        self.requests = None
        with ignored(AttributeError, BaseException):
            self.requests = get_request()
        self.trace_context = get_current()
        self.timezone = get_local_param("time_zone")
        self.multi_func_params = multi_func_params

    def _init_context(self):
        with ignored(Exception):
            attach(self.trace_context)

            if self.timezone:
                set_local_param("time_zone", self.timezone)
                timezone.activate(pytz.timezone(self.timezone))

    def run(self, return_exception=False):
        try:
            self._init_context()
            if self.use_request and self.requests:
                activate_request(self.requests)
            if self.params:
                if not self.multi_func_params:
                    self.results[self.result_key] = self.func(self.params)
                else:
                    self.results[self.result_key] = self.func(**self.params)
            else:
                self.results[self.result_key] = self.func()

        except Exception as e:  # pylint: disable=broad-except
            if return_exception:
                self.results[self.result_key] = e


def executor_wrap(params: List[Tuple[FuncThread, bool]]):
    func_thread, return_exception = params
    func_thread.run(return_exception)


class MultiExecuteFunc(object):
    """
    基于多线程的批量并发执行函数
    """

    def __init__(self, max_workers=None):
        self.results = {}
        self.task_list = []
        self.max_workers = max_workers

    def append(self, result_key, func, params=None, use_request=True, multi_func_params=False):
        if result_key in self.results:
            raise ValueError(f"result_key: {result_key} is duplicate. Please rename it.")
        task = FuncThread(
            func=func,
            params=params,
            result_key=result_key,
            results=self.results,
            use_request=use_request,
            multi_func_params=multi_func_params,
        )
        self.task_list.append(task)

    def run(self, return_exception=False):
        params = [(task, return_exception) for task in self.task_list]
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            executor.map(executor_wrap, params)
        return self.results


def generate_request(username=""):
    """
    获取一个简单request
    """
    factory = APIRequestFactory()
    request = factory.get("/")
    r = Request(request)
    r.parsers = (FormParser(), MultiPartParser())
    if username:
        r.user.username = username
    return r
