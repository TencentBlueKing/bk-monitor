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
import sys

"""
celery api任务
"""
import datetime
import gc
import logging
import os
import time

import psutil
from django.conf import settings
from django.core.cache import caches
from django.db import close_old_connections
from gevent.monkey import saved
from six.moves import range

from alarm_backends.constants import CONST_MINUTES, CONST_ONE_HOUR
from alarm_backends.core.lock.service_lock import share_lock
from alarm_backends.management.hashring import HashRing
from api.cmdb import client
from api.cmdb.define import Host
from bkmonitor.models import StrategyModel
from bkmonitor.utils.common_utils import get_local_ip
from bkmonitor.utils.supervisor_utils import get_supervisor_client
from core.drf_resource import api

logger = logging.getLogger(__name__)

MAX_CONCURRENCE_NUMBER = 20
gevent_active = "time" in saved

IP = get_local_ip()


RING_NODE_REFRESHED = False


def active_biz_ids():
    global RING_NODE_REFRESHED
    biz_ids = StrategyModel.objects.all().values("bk_biz_id").distinct()
    biz_count = len(biz_ids)
    if biz_count > 100 and not RING_NODE_REFRESHED:
        refresh_ring_nodes(biz_count)
        RING_NODE_REFRESHED = True
    return biz_ids


def refresh_ring_nodes(count):
    global HR, RING_NODES
    RING_NODES *= len(str((count + 1) // 10))
    HR = HashRing(dict.fromkeys(list(range(RING_NODES)), 1))
    logger.info(f"[api cache] hash ring nodes: {RING_NODES}")


@share_lock()
def cache_business():
    """
        CC_CACHE_ALWAYS                 None
    api.cmdb.search_cloud_area -> client.search_cloud_area
    client.search_business
    :return:
    """
    client.search_business.request.refresh()
    api.cmdb.search_cloud_area.request.refresh()


def func_adapter_resource(func):
    setattr(func, "request", func)


def cmdb_api_list(bk_biz_id):
    """
    这里周期刷新的接口，可以设置cache_type = CacheType.CC_CACHE_ALWAYS
    client.xxx: 底层api调用，直接设置CC_CACHE_ALWAYS
        client.search_biz_inst_topo
        client.get_biz_internal_module
        client.list_service_category
    api.cmdb.xxx: 上层封装，因此具体实现逻辑中，调用的client.xxx 不需要设置CacheType
        CC_CACHE_ALWAYS                         None
        api.cmdb.get_host_dict_by_biz -> client.list_biz_hosts_topo
        api.cmdb.get_service_instance_by_biz -> client.list_service_instance_detail
    """
    # api模块下非resource对象(仅函数) 没有request 方法，需要设置一下
    func_adapter_resource(api.cmdb.get_host_dict_by_biz)
    func_adapter_resource(api.cmdb.get_service_instance_by_biz)
    cmdb_tasks = [
        {"api": client.search_biz_inst_topo, "args": (), "kwargs": {"bk_biz_id": bk_biz_id}},
        {
            "api": client.get_biz_internal_module,
            "args": (),
            "kwargs": {"bk_biz_id": bk_biz_id, "bk_supplier_account": settings.BK_SUPPLIER_ACCOUNT},
        },
        {"api": api.cmdb.get_service_instance_by_biz, "args": (bk_biz_id,), "kwargs": {}},
        {"api": client.list_service_category, "args": (), "kwargs": {"bk_biz_id": bk_biz_id}},
        {"api": api.cmdb.get_host_dict_by_biz, "args": (bk_biz_id, Host.Fields), "kwargs": {}},
    ]
    return cmdb_tasks


@share_lock(identify=IP)
def cache_cmdb_resource():
    """
    只有配置了采集任务，这个接口就会反复被调用，但是表在SaaS的库，这边全部缓存
    """
    from gevent.pool import Pool

    api_coroutines = []
    biz_result = active_biz_ids()
    pool = Pool(MAX_CONCURRENCE_NUMBER)
    minute_line = datetime.datetime.now().minute
    tobe_cached_bizs = []
    for biz in biz_result:
        bk_biz_id = biz["bk_biz_id"]
        if bk_biz_id < 0 or not biz_is_ready(bk_biz_id, minute_line):
            continue
        tobe_cached_bizs.append(bk_biz_id)
        for cmdb_task in cmdb_api_list(bk_biz_id):
            call_obj = cmdb_task["api"]
            api_coroutines.append(gevent_run(call_obj.request.refresh, pool, *cmdb_task["args"], **cmdb_task["kwargs"]))
    if gevent_active:
        for coroutine in api_coroutines:
            coroutine.join()
    logger.info(f"[api cache] run cache with {len(tobe_cached_bizs)}bizs: {tobe_cached_bizs}")
    # 执行完任务后自杀
    term_api_cron(immediately=True)


@share_lock()
def term_api_cron(immediately=False):
    if settings.IS_CONTAINER_MODE:
        self_p = psutil.Process(os.getpid())
        run_time = time.time() - self_p.create_time()
        logger.info(f"[api cache] scheduler:celery_worker_api_cron now running {run_time}s")
        if (immediately and run_time > 30 * CONST_MINUTES) or run_time > CONST_ONE_HOUR:
            logger.info("[api cache] term_api_cron now")
            # celery 自杀，通过广播shutdown信号退出码非0，会导致k8s判定为crash
            # 当前 gevent 模式，没有子进程，因此可以直接退出
            sys.exit(0)
        return

    # 二进制部署，用supervisor管理
    s_client = get_supervisor_client()
    process_info = s_client.supervisor.getProcessInfo("scheduler:celery_worker_api_cron")
    if process_info["statename"] != "RUNNING":
        return
    # 1小时一次
    run_time = process_info["now"] - process_info["start"]
    logger.info(f"[api cache] scheduler:celery_worker_api_cron now running {run_time}s")
    if (immediately and run_time > 5 * CONST_MINUTES) or run_time > CONST_ONE_HOUR:
        # 保证最少跑5分钟
        # 发送中断信号
        # signal.SIGTERM
        logger.info("[api cache] term_api_cron now")
        s_client.supervisor.signalProcess("scheduler:celery_worker_api_cron", 15)


def biz_is_ready(bk_biz_id, minute_line):
    if bk_biz_id == 0:
        return False

    client_index = HR.get_node(bk_biz_id)
    return client_index == minute_line % RING_NODES


API_CRONTAB = [
    (cache_business, "*/1 * * * *", "global"),
    (cache_cmdb_resource, "*/1 * * * *", "global"),
    (term_api_cron, "*/1 * * * *", "global"),
]


RING_NODES = os.getenv("API_CACHE_BASE_INTERVAL", "10")
try:
    RING_NODES = int(RING_NODES)
except (TypeError, ValueError):
    RING_NODES = 5


def gevnet_task_with_close_connections(run, pool, *args, **kwargs):
    """
    gevnet_task_with_close_db_connections
    """

    def task_wrapper(func):
        try:
            return func(*args, **kwargs)
        finally:
            close_old_connections()
            try:
                mem_cache = caches["locmem"]
                mem_cache.clear()
                del mem_cache
            finally:
                gc.collect()

    if gevent_active:
        return pool.spawn(task_wrapper, run)
    else:
        return task_wrapper(run)


gevent_run = gevnet_task_with_close_connections

# 初始化一个65535个虚拟节点，实际节点（0-4）的哈希环
HR = HashRing(dict.fromkeys(list(range(RING_NODES)), 1))
