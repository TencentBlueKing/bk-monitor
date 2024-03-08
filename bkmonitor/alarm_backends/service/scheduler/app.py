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


import os
import random

import django
import six.moves.urllib.error
import six.moves.urllib.parse
import six.moves.urllib.request
from billiard import cpu_count
from celery import Celery
from celery.signals import beat_init, setup_logging
from django.conf import settings
from django.db import close_old_connections

from alarm_backends.core.cluster import get_cluster
from bkmonitor.utils.common_utils import package_contents
from core.prometheus.tools import celery_app_timer

try:
    # 加载后台动态配置
    django.setup()
    from bkmonitor import models
    from bkmonitor.utils.dynamic_settings import hack_settings

    hack_settings(models.GlobalConfig, settings)
except Exception as e:
    import sys

    print("django setup failed: {}".format(e))
    sys.exit(-1)


def default_celery_worker_num():
    """
    core(1): 1
    core(2): 2
    core(3): 3
    core(4): 4
    core(5): 4
    core(6): 5
    core(7): 5
    core(8): 6
    core(9): 6
    core(10): 7
    core(11): 7
    core(12): 8
    core(13): 8
    core(14): 9
    core(15): 9
    core(16): 9
    core(17): 10
    core(18): 10
    core(19): 10
    core(20): 11
    core(21): 11
    core(22): 11
    core(23): 12
    core(24): 12
    core(25): 12
    core(26): 13
    core(27): 13
    core(28): 13
    core(29): 13
    core(30): 14
    core(31): 14
    core(32): 14
    core(33): 15
    core(34): 15
    core(35): 15
    core(36): 15
    core(37): 16
    core(38): 16
    core(39): 16
    core(40): 16
    core(41): 17
    core(42): 17
    core(43): 17
    core(44): 17
    core(45): 18
    core(46): 18
    core(47): 18
    core(48): 18
    """
    return int(cpu_count() ** 0.6 * 1.85)


class Conf(object):
    # worker
    CELERYD_MAX_TASKS_PER_CHILD = 1000
    CELERYD_CONCURRENCY = int(getattr(settings, "CELERY_WORKERS", 0)) or default_celery_worker_num()
    CELERY_ROUTES = {}
    CELERY_SEND_EVENTS = getattr(settings, "CELERY_SEND_EVENTS", False)
    CELERY_SEND_TASK_SENT_EVENT = getattr(settings, "CELERY_SEND_TASK_SENT_EVENT", False)
    CELERY_TRACK_STARTED = getattr(settings, "CELERY_TRACK_STARTED", False)


def redis_conf():
    """
    REDIS_CELERY_CONF = {
        "host": REDIS_HOST,
        "port": REDIS_PORT,
        "db": 9,
        "password": REDIS_PASSWD,
    }
    """
    redis_celery_conf = settings.REDIS_CELERY_CONF
    redis_host = redis_celery_conf["host"]
    redis_port = redis_celery_conf["port"]
    redis_password = redis_celery_conf["password"]
    redis_db = redis_celery_conf["db"]

    class RedisConf(Conf):
        BROKER_URL = CELERY_RESULT_BACKEND = "redis://:{}@{}:{}/{}".format(
            six.moves.urllib.parse.quote(redis_password),
            redis_host,
            redis_port,
            redis_db,
        )
        CELERYBEAT_MAX_LOOP_INTERVAL = 60
        redbeat_lock_timeout = REDBEAT_LOCK_TIMEOUT = 300

    return RedisConf


def rabbitmq_conf():
    # CELERY_RESULT_SERIALIZER = 'json'
    redis_celery_conf = settings.REDIS_CELERY_CONF
    redis_host = redis_celery_conf["host"]
    redis_port = redis_celery_conf["port"]
    redis_password = redis_celery_conf["password"]
    redis_db = redis_celery_conf["db"]

    class RabbitmqConf(Conf):
        CELERY_TASK_SERIALIZER = "pickle"
        CELERY_ACCEPT_CONTENT = ["pickle"]
        CELERY_RESULT_SERIALIZER = "pickle"

        CELERY_ACKS_LATE = True
        CELERY_DEFAULT_EXCHANGE = "monitor"
        CELERY_DEFAULT_QUEUE = "monitor"
        CELERY_DEFAULT_ROUTING_KEY = "monitor"
        BROKER_URL = "amqp://{}:{}@{}:{}/{}".format(
            six.moves.urllib.parse.quote(settings.RABBITMQ_USER),
            six.moves.urllib.parse.quote(settings.RABBITMQ_PASS),
            settings.RABBITMQ_HOST,
            settings.RABBITMQ_PORT,
            settings.RABBITMQ_VHOST,
        )
        if not get_cluster().is_default():
            BROKER_TRANSPORT_OPTIONS = {
                "queue_name_prefix": "{}-".format(get_cluster().name),
            }

        CELERYBEAT_MAX_LOOP_INTERVAL = 60
        redbeat_lock_timeout = REDBEAT_LOCK_TIMEOUT = 300

        if settings.CACHE_BACKEND_TYPE == "SentinelRedisCache":
            CELERY_RESULT_BACKEND = ";".join(
                "sentinel://:{}@{}:{}/{}".format(
                    six.moves.urllib.parse.quote(settings.REDIS_PASSWD),
                    h,
                    redis_port,
                    redis_db,
                )
                for h in redis_host.split(";")
                if h
            )
            CELERY_RESULT_BACKEND_TRANSPORT_OPTIONS = {
                "master_name": settings.REDIS_MASTER_NAME,
                "sentinel_kwargs": {"password": settings.REDIS_SENTINEL_PASS},
            }

            # celery redbeat config
            redbeat_redis_url = "redis-sentinel://redis-sentinel:26379/0"
            REDBEAT_REDIS_OPTIONS = {
                "sentinels": [(h, redis_port) for h in redis_host.split(";") if h],
                "password": redis_password,
                "service_name": getattr(settings, "REDIS_MASTER_NAME", "mymaster"),
                "socket_timeout": 10,
                "retry_period": 60,
            }
            # 随机打乱顺序，避免每次都是同一个节点
            random.shuffle(REDBEAT_REDIS_OPTIONS["sentinels"])

            if getattr(settings, "REDIS_SENTINEL_PASS", ""):
                REDBEAT_REDIS_OPTIONS["sentinel_kwargs"] = {"password": settings.REDIS_SENTINEL_PASS}
        else:
            CELERY_RESULT_BACKEND = "redis://:{}@{}:{}/{}".format(
                six.moves.urllib.parse.quote(redis_password),
                redis_host,
                redis_port,
                redis_db,
            )
            redbeat_redis_url = "redis://:{}@{}:{}/0".format(
                redis_password,
                redis_host,
                redis_port,
            )

    return RabbitmqConf


app = Celery("backend")

conf_type = getattr(settings, "CELERY_CONF_TYPE", "redis_conf")
if conf_type == "rabbitmq_conf":
    app.config_from_object(rabbitmq_conf())
else:
    app.config_from_object(redis_conf())


# 任务执行时间统计
celery_app_timer(app)


TASK_ROOT_MODULES = [
    "alarm_backends.service",
    "alarm_backends.service.alert",
    "alarm_backends.service.converge",
    "api",
    "apm",
    "apm_ebpf",
    "metadata",
    "bkmonitor",
]
DISCOVER_DIRS = []
for MODULE in TASK_ROOT_MODULES:
    for m in package_contents(MODULE):
        file_name = "{}.{}".format(MODULE, m)
        if os.path.isdir(os.path.join(settings.BASE_DIR, file_name.replace(".", os.sep))):
            DISCOVER_DIRS.append(file_name)

DISCOVER_DIRS.extend(settings.INSTALLED_APPS)
app.autodiscover_tasks(DISCOVER_DIRS)


@setup_logging.connect
def config_loggers(*args, **kwags):
    from logging.config import dictConfig

    from django.conf import settings

    dictConfig(settings.LOGGING)


@beat_init.connect
def clean_db_connections(sender, **kwargs):
    close_old_connections()
