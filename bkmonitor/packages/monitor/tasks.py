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


import functools
import logging
import random
import sys
import time

from celery import task
from common import log
from common.context_processors import Platform
from common.log import logger
from django.core.cache import cache
from django.db import close_old_connections
from utils import business

from bkmonitor.utils.local import local
from core.drf_resource import resource

if "celery" in sys.argv:
    log.logger_detail = logging.getLogger("celery")

DEFAULT_RANDOM_RANGE = 10  # 将任务随机打散在[0, RANDOM_RANGE]时间范围内
DEFAULT_TASK_INTERVAL = 120  # 两次任务之间的间隔(即缓存有效期), 以任务开始执行时计算
DEFAULT_TASK_EXPIRES = 30  # 任务执行过期时间


class task_decorator(object):
    def __init__(self, random_range=DEFAULT_RANDOM_RANGE, task_interval=DEFAULT_TASK_INTERVAL):
        self.random_range = random_range if random_range > 0 else DEFAULT_RANDOM_RANGE
        self.task_interval = task_interval if task_interval > 0 else DEFAULT_TASK_INTERVAL

    def lock_key(self, task_name, args, kwargs):
        # 注意, 参数过多会导致这个key很长, 可以转成MD5
        return "__lock__{}_cache_{}__".format(task_name, (args, kwargs))

    def __call__(self, task_func):
        @functools.wraps(task_func)
        def wrapper(*args, **kwargs):
            task_name = task_func.__name__
            lock_key = self.lock_key(task_name, args, kwargs)
            try:
                # 如果key存在, 则说明前面的任务还没有运行结束
                if cache.get(lock_key):
                    return "the prev task is running, task:(%s)" % (lock_key)
                cache.set(lock_key, time.time(), self.task_interval)

                # 打散任务,避免同时并发
                time.sleep(random.randint(0, self.random_range))

                task_func(*args, **kwargs)
            except Exception as e:
                logger.error("call {} error:{}".format(lock_key, e))
            finally:
                local.clear()
                # redis_cli.delete(lock_key)
            return "call %s success" % (lock_key)

        return wrapper


def set_client_user(username):
    local.username = username


@task(ignore_result=True)
def get_application_task(use_cache=False):
    pass


@task(ignore_result=True)
def setup_userenv(username, use_cache=True):
    pass


@task(ignore_result=True)
@task_decorator(random_range=5, task_interval=30)
def refresh_host_status_cache_by_biz_id(cc_biz_id):
    """定时任务缓存主机性能数据接口"""
    set_client_user(business.maintainer(cc_biz_id))
    resource.performance.host_performance(bk_biz_id=cc_biz_id, enforce_refresh=True)


@task(ignore_resule=True)
@task_decorator(random_range=5, task_interval=30)
def refresh_cc_set_module_by_biz_id(cc_biz_id):
    """
    定时缓存CC集群和模块信息
    """
    set_client_user(business.maintainer(cc_biz_id))
    resource.cc.topo_tree(cc_biz_id)


@task(ignore_resule=True)
def refresh_host_status_cache(biz_id=None):
    close_old_connections()

    if Platform.te:
        refresh_all_biz_info_cache.apply_async(expires=DEFAULT_TASK_EXPIRES)

    biz_id_set = {biz_id} if biz_id else business.get_all_activate_business()
    for biz_id in biz_id_set:
        refresh_host_status_cache_by_biz_id.apply_async(args=(biz_id,), expires=DEFAULT_TASK_EXPIRES)
        refresh_cc_set_module_by_biz_id.apply_async(args=(biz_id,), expires=DEFAULT_TASK_EXPIRES)


@task(ignored_result=True)
@task_decorator(random_range=5, task_interval=300)
def refresh_all_biz_info_cache():
    """
    定时缓存所有业务信息，缓存5分钟
    """
    resource.cc.get_biz_map(use_cache=False)


@task(ignore_result=True)
def async_execute_deposit_task(deposit_task):
    set_client_user(deposit_task.update_user)
    deposit_task.execute()


@task()
def test_celery(number):
    """
    用于测试celery是否阻塞
    :param number: 随机的数字
    :return:
    """
    return number
