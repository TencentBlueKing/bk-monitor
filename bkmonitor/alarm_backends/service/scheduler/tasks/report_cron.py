"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
import json
import logging
import urllib.parse

from celery.schedules import crontab
from django.conf import settings
import requests

from alarm_backends.core.cache.base import CacheManager
from alarm_backends.core.cluster import get_cluster
from alarm_backends.core.lock.service_lock import share_lock
from alarm_backends.service.new_report.tasks import new_report_detect
from alarm_backends.service.report.tasks import (
    collect_redis_metric,
    operation_data_custom_report_v2,
    report_mail_detect,
)
from alarm_backends.service.scheduler.app import periodic_task
from alarm_backends.service.scheduler.tasks.cron import task_duration
from bkmonitor.utils.custom_report_aggate import register_report_task
from constants.common import DEFAULT_TENANT_ID
from core.drf_resource import api


logger = logging.getLogger("bkmonitor.cron_report")


@share_lock()
def register_report_task_cron():
    """注册聚合网关上报任务"""
    register_report_task()


@share_lock()
def register_alarm_cache_bmw_task():
    """
    注册bk-monitor-worker告警缓存刷新任务
    """
    # 获取已注册的告警缓存刷新任务
    bmw_api_url = settings.BMW_API_URL
    if not bmw_api_url:
        return

    # 获取 redis 配置
    cache_redis_conf = settings.REDIS_CACHE_CONF
    redis_options = {
        "addrs": [f"{cache_redis_conf['host']}:{cache_redis_conf['port']}"],
        "db": cache_redis_conf["db"],
        "master_name": cache_redis_conf.get("master_name"),
        "mode": "standalone" if settings.CACHE_BACKEND_TYPE == "RedisCache" else "sentinel",
        "password": cache_redis_conf.get("password"),
        "sentinel_password": cache_redis_conf.get("sentinel_password"),
    }

    # 参数准备
    task_kind_params: dict[str, dict[str, dict]] = {
        "daemon:alarm:cmdb_resource_watch": {
            "kind": "daemon:alarm:cmdb_resource_watch",
            "payload": {
                "prefix": CacheManager.CACHE_KEY_PREFIX,
                "redis": redis_options,
            },
            "options": {"queue": "alarm"},
        },
        "daemon:alarm:cmdb_cache_refresh": {
            "kind": "daemon:alarm:cmdb_cache_refresh",
            "payload": {
                "prefix": CacheManager.CACHE_KEY_PREFIX,
                "redis": redis_options,
                "full_refresh_intervals": {
                    "host_topo": 3600,
                    "business": 3600,
                    "module": 3600,
                    "set": 3600,
                    "service_instance": 600,
                    "dynamic_group": 3600,
                },
                "biz_concurrent": 5,
                "event_handle_interval": 120,
            },
            "options": {"queue": "alarm"},
        },
    }

    # 获取已注册的告警缓存刷新任务
    url = urllib.parse.urljoin(bmw_api_url, "bmw/task/")
    r = requests.get(url=url, params={"task_type": "daemon"}, timeout=10)
    if r.status_code != 200:
        logger.error(f"获取已注册的告警缓存刷新任务失败: {r.text}")
    try:
        result: list[dict] = r.json()["data"]
    except requests.JSONDecodeError:
        logger.error(f"获取已注册的告警缓存刷新任务失败: {r.text}")
        return

    need_delete_task_ids: list[str] = []
    tasks: dict[tuple[str, str], dict] = {}
    for task in result:
        # 过滤掉非告警缓存刷新任务
        if task["kind"] not in task_kind_params:
            continue

        bk_tenant_id = task["payload"].get("bk_tenant_id") or DEFAULT_TENANT_ID
        key = (bk_tenant_id, task["kind"])

        # 如果存在重复任务，则删除旧任务
        if key in tasks:
            need_delete_task_ids.append(task["uni_id"])
            continue
        tasks[key] = task

    # 新旧任务对比，判断是否需要注册或删除
    bk_tenant_ids = {tenant["id"] for tenant in api.bk_login.list_tenant()}
    for bk_tenant_id in bk_tenant_ids:
        for task_kind, params in task_kind_params.items():
            key = (bk_tenant_id, task_kind)
            params = copy.deepcopy(params)
            params["payload"].update({"bk_tenant_id": bk_tenant_id})

            # 如果任务不存在，或者任务参数不一致，则注册新任务
            if key not in tasks or json.dumps(tasks[key]["payload"], sort_keys=True) != json.dumps(
                params["payload"], sort_keys=True
            ):
                r = requests.post(url=url, json=params)
                if r.status_code != 200:
                    logger.error(
                        f"注册告警缓存刷新任务失败: task_name={task_kind} bk_tenant_id={bk_tenant_id} status_code={r.status_code} content={r.content}"
                    )

                # 如果发生了更新，则删除旧任务
                if key in tasks:
                    need_delete_task_ids.append(tasks[key]["uni_id"])

    # 删除租户不存在的任务
    for key, task in tasks.items():
        if key[0] not in bk_tenant_ids:
            need_delete_task_ids.append(task["uni_id"])

    # 执行删除
    if need_delete_task_ids:
        for task_uni_id in need_delete_task_ids:
            r = requests.delete(url=url, json={"task_uni_id": task_uni_id, "task_type": "daemon"})
            if r.status_code != 200:
                logger.error(
                    f"删除告警缓存刷新任务失败: task_uni_id={task_uni_id} status_code={r.status_code} content={r.content}"
                )


REPORT_CRONTAB = [
    # 运营数据上报
    (operation_data_custom_report_v2, "*/5 * * * *", "global"),
    # SLI指标周期上报(注册推送任务至agg网关)
    (register_report_task_cron, "* * * * *", "cluster"),
    # redis 指标采集
    (collect_redis_metric, "* * * * *", "cluster"),
    # 注册告警缓存刷新任务
    (register_alarm_cache_bmw_task, "* * * * *", "global"),
]

if int(settings.MAIL_REPORT_BIZ):
    # 如果配置了订阅报表默认业务
    # 订阅报表定时任务 REPORT_CRONTAB
    REPORT_CRONTAB.extend([(report_mail_detect, "*/1 * * * *", "global"), (new_report_detect, "*/1 * * * *", "global")])

for func, cron_expr, run_type in REPORT_CRONTAB:
    # 全局任务在非默认集群不执行
    if run_type == "global" and not get_cluster().is_default():
        continue

    queue = "celery_report_cron"
    cron_list = cron_expr.split()
    new_func = task_duration(func.__name__, queue_name=queue)(func)
    locals()[new_func.__name__] = periodic_task(
        run_every=crontab(*cron_list),
        ignore_result=True,
        queue=queue,
        expires=300,  # The task will not be executed after the expiration time.
    )(new_func)
