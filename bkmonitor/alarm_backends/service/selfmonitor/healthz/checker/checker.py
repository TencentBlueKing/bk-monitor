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


import inspect
import json
import logging
from collections import namedtuple
from importlib import import_module
from multiprocessing.pool import ThreadPool

from django.core import signals
from django.db import connections
from six.moves import zip

logger = logging.getLogger("self_monitor")

CheckerTask = namedtuple("CheckerParams", ["name", "kwargs"])
CheckerItemSep = "."

CHECKERS = {}
CHECKER_OK = 0
CHECKER_WARN = 1
CHECKER_FAILED = 2
CHECKER_NOT_FOUND = 3
CHECKER_ERROR = 4


class CheckerItem(object):
    def __init__(self, name, checker, safe=False):
        self.name = name
        self.checker = checker
        self.safe = safe

    def _get_func_args_decl(self, func, skip=0):
        args = []
        kwargs = {}
        argspec = inspect.getargspec(func)
        iargs = iter(argspec.args[::-1])
        if argspec.defaults:
            defaults = argspec.defaults[::-1]
            kwargs.update((k, v) for v, k in zip(defaults, iargs))
        args.extend(iargs)
        return args[:-skip], kwargs

    def get_argspec(self):
        args_decl = []
        if inspect.isfunction(self.checker):
            args, kwargs = self._get_func_args_decl(self.checker, skip=2)
            args_decl.extend("{}={!r}".format(k, v) for k, v in list(kwargs.items()))
            args_decl.extend(args)

        return ", ".join(args_decl)

    def get_description(self):
        return {
            "doc": inspect.getdoc(self.checker),
            "name": self.name,
            "args": self.get_argspec(),
        }

    def __call__(self, manager, **kwargs):
        result = CheckerResult(self.name, status=CHECKER_OK if self.safe else CHECKER_FAILED)
        try:
            result = self.checker(manager, result, **kwargs) or result
        except CheckerResult as result:
            if result.status is None:
                result.status = CHECKER_FAILED
        except Exception as err:
            logger.exception("%s check error: %s", self.name, err)
            result.update(message=str(err), status=CHECKER_ERROR)
        return result


class CheckerResult(Exception):
    __slots__ = ("name", "value", "status", "message")

    def __init__(self, name, value=None, status=None, message=""):
        self.name = name
        self.value = value
        self.status = status
        self.message = message
        super(CheckerResult, self).__init__()

    def update(self, value=None, message="", status=CHECKER_WARN):
        self.value = value
        self.message = message
        self.status = status

    def ok(self, value, message=""):
        self.update(value, message, CHECKER_OK)
        return self

    def fail(self, message, value=None):
        self.update(value, message, CHECKER_FAILED)
        return self

    def ok_or_fail(self, condition, value, fail_message):
        if condition:
            return self.ok(value, "")
        else:
            return self.fail(fail_message, value)

    def as_json(self):
        return json.dumps({k: getattr(self, k) for k in self.__slots__})


class CheckerRegisterManager(object):
    def __init__(self, path=()):
        self._path = path

    def __getattr__(self, name):
        item = CheckerRegisterManager(self._path + (name,))
        setattr(self, name, item)
        return item

    def __call__(self, name="", safe=False, disable=False):
        path = self._path
        if name:
            path = path + (name,)
        name = CheckerItemSep.join(path)

        def register(obj):
            if disable:
                return obj
            CHECKERS[name] = CheckerItem(
                name=name,
                checker=obj,
                safe=safe,
            )

            return obj

        return register


CheckerRegister = CheckerRegisterManager()


def close_local_connections(**kwargs):
    connections.close_all()


class HealthChecker(object):
    def __init__(self, checkers=None):
        self.pool = ThreadPool()
        self.checkers = checkers or CHECKERS

    def checker(self, name):
        return self.checkers.get(name)

    def check(self, checker_name, **kwargs):
        checker = self.checker(checker_name)
        if not checker:
            logger.warning("checker: %s not exist", checker_name)
        return checker(self, **kwargs)

    def check_task(self, task):
        signals.request_finished.connect(close_local_connections)
        kwargs = {}
        if task.kwargs:
            kwargs.update(task.kwargs)
        try:
            return self.check(task.name, **kwargs)
        except Exception as e:
            raise e
        finally:
            signals.request_finished.send(sender=self.__class__)

    def check_tasks(self, tasks):
        proxies = [self.pool.apply_async(self.check_task, args=(i,)) for i in tasks]
        results = []
        for i in proxies:
            try:
                results.append(i.get())
            except CheckerResult as err:
                results.append(err)
            except Exception as err:
                logger.exception(err)
        return results

    def get_checker_descriptions(self):
        return {c.name: c.get_description() for c in list(self.checkers.values())}

    def load_checker(self, category):
        try:
            import_module("kernel.health.checker.%s_checker" % category)
            return True
        except Exception as err:
            logger.exception(err)
            return False
