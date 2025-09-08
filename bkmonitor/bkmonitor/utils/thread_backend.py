# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
from functools import partial
from multiprocessing.pool import ThreadPool as _ThreadPool
from threading import Thread
from typing import List

from django import db
from django.utils import timezone, translation
from opentelemetry.context import attach, get_current

from bkmonitor.utils.common_utils import ignored
from bkmonitor.utils.local import local

logger = logging.getLogger(__name__)


class InheritParentThread(Thread):
    def __init__(self, *args, **kwargs):
        self.register()
        super(InheritParentThread, self).__init__(*args, **kwargs)

    def register(self):
        # sync all data in local object
        self.inherit_data = []
        for item in local:
            self.inherit_data.append(item)

        # sync timezone/lang
        self.timezone = timezone.get_current_timezone().zone
        self.language = translation.get_language()
        self.trace_context = get_current()

    def sync(self):
        for sync_item in self.inherit_data:
            setattr(local, sync_item[0], sync_item[1])
        timezone.activate(self.timezone)
        translation.activate(self.language)
        with ignored(Exception):
            attach(self.trace_context)

    def unsync(self):
        # 新的线程会往local再写一些数据
        # 线程结束的时候，需要把所有线程相关的所有变量都清空
        for item in local:
            delattr(local, item[0])

        # db._connections 也是线程变量，所以在线程结束的时候需要主动的释放
        db.connections.close_all()

    def run(self):
        self.sync()
        try:
            super(InheritParentThread, self).run()
        except Exception as e:
            logger.exception(e)

        self.unsync()


def run_threads(th_list: List[InheritParentThread]):
    [th.start() for th in th_list]
    [th.join() for th in th_list]


def run_func_with_local(items, tz, lang, func, trace_context, *args, **kwargs):
    """
    线程执行函数
    :param func: 待执行函数
    :param items: Thread Local Items
    :param tz: 时区
    :param lang: 语言
    :param args: 位置参数
    :param kwargs: 关键字参数
    :return: 函数返回值
    """
    # 同步local数据
    for item in items:
        setattr(local, item[0], item[1])

    # 设置时区及语言
    timezone.activate(tz)
    translation.activate(lang)
    with ignored(Exception):
        attach(trace_context)
    try:
        data = func(*args, **kwargs)
    except Exception as e:
        raise e
    finally:
        # 关闭db连接
        db.connections.close_all()

        # 清理local数据
        for item in local:
            delattr(local, item[0])

    return data


class ThreadPool(_ThreadPool):
    """
    线程池
    """

    @staticmethod
    def get_func_with_local(func):
        tz = timezone.get_current_timezone().zone
        lang = translation.get_language()
        trace_context = get_current()
        items = [item for item in local]
        return partial(run_func_with_local, items, tz, lang, func, trace_context)

    def map_ignore_exception(self, func, iterable, return_exception=False):
        """
        忽略错误版的map
        """
        futures = []
        for params in iterable:
            if not isinstance(params, (tuple, list)):
                params = (params,)
            futures.append(self.apply_async(func, args=params))

        results = []
        for future in futures:
            try:
                results.append(future.get())
            except Exception as e:
                if return_exception:
                    results.append(e)
                logger.exception(e)

        return results

    def map_async(self, func, iterable, chunksize=None, callback=None):
        return super(ThreadPool, self).map_async(
            self.get_func_with_local(func), iterable, chunksize=chunksize, callback=callback
        )

    def apply_async(self, func, args=(), kwds=None, callback=None):
        kwds = kwds or {}
        return super(ThreadPool, self).apply_async(
            self.get_func_with_local(func), args=args, kwds=kwds, callback=callback
        )

    def imap(self, func, iterable, chunksize=1):
        return super(ThreadPool, self).imap(self.get_func_with_local(func), iterable, chunksize)

    def imap_unordered(self, func, iterable, chunksize=1):
        return super(ThreadPool, self).imap_unordered(self.get_func_with_local(func), iterable, chunksize=chunksize)


if __name__ == "__main__":
    InheritParentThread().start()
