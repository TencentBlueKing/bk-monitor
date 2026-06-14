"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
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
from celery import Celery, Task
from celery.schedules import maybe_schedule
from celery.signals import beat_init, setup_logging
from kombu import Exchange, Queue
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

    print(f"django setup failed: {e}")
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


def rabbitmq_conf():
    redis_celery_conf = settings.REDIS_CELERY_CONF
    redis_host = redis_celery_conf["host"]
    redis_port = redis_celery_conf["port"]
    redis_password = redis_celery_conf["password"]
    redis_db = redis_celery_conf["db"]

    class RabbitmqConf:
        # 子进程最大任务数
        worker_max_tasks_per_child = 1000

        # worker并发数
        worker_concurrency = int(getattr(settings, "CELERY_WORKERS", 0)) or default_celery_worker_num()

        # 使用pickle序列化任务
        task_serializer = "pickle"
        accept_content = ["pickle"]
        result_serializer = "pickle"

        task_acks_late = True
        task_default_exchange = "monitor"
        task_default_queue = "monitor"
        task_default_routing_key = "monitor"
        # 显式声明队列：仅 celery_llm_task 需要 broker 端参数——TTL 自蒸发 + 长度上限，
        # 兜底"无消费者静默积压"（LLM 标题生成是体验增强，10 分钟未消费即无价值）。
        # 注意：RabbitMQ 队列参数必须首次声明就带上，已存在队列改参数会 PRECONDITION_FAILED。
        # 设置 task_queues 后裸 worker（不带 -Q）只消费此列表，故显式补回默认队列；
        # 生产全部 worker 均通过 -Q 指定消费队列，行为不受影响。
        # 其余既有队列名仍由 task_create_missing_queues（默认 True）按需自动创建。
        task_queues = [
            Queue("monitor", Exchange("monitor"), routing_key="monitor"),
            Queue(
                "celery_llm_task",
                Exchange("monitor"),
                routing_key="celery_llm_task",
                queue_arguments={"x-message-ttl": 600000, "x-max-length": 1000},
            ),
        ]
        broker_url = f"amqp://{six.moves.urllib.parse.quote(settings.RABBITMQ_USER)}:{six.moves.urllib.parse.quote(settings.RABBITMQ_PASS)}@{settings.RABBITMQ_HOST}:{settings.RABBITMQ_PORT}/{settings.RABBITMQ_VHOST}"
        if not get_cluster().is_default():
            broker_transport_options = {
                "queue_name_prefix": f"{get_cluster().name}-",
            }

        beat_max_loop_interval = 60
        redbeat_lock_timeout = 300

        if settings.CACHE_BACKEND_TYPE == "SentinelRedisCache":
            result_backend = ";".join(
                f"sentinel://:{six.moves.urllib.parse.quote(settings.REDIS_PASSWD)}@{h}:{redis_port}/{redis_db}"
                for h in redis_host.split(";")
                if h
            )
            result_backend_transport_options = {
                "master_name": settings.REDIS_MASTER_NAME,
                "sentinel_kwargs": {"password": settings.REDIS_SENTINEL_PASS},
            }

            # celery redbeat config
            redbeat_redis_url = "redis-sentinel://redis-sentinel:26379/0"
            redbeat_redis_options = {
                "sentinels": [(h, redis_port) for h in redis_host.split(";") if h],
                "password": redis_password,
                "service_name": getattr(settings, "REDIS_MASTER_NAME", "mymaster"),
                "socket_timeout": 10,
                "retry_period": 60,
            }
            # 随机打乱顺序，避免每次都是同一个节点
            random.shuffle(redbeat_redis_options["sentinels"])

            if getattr(settings, "REDIS_SENTINEL_PASS", ""):
                redbeat_redis_options["sentinel_kwargs"] = {"password": settings.REDIS_SENTINEL_PASS}
        else:
            result_backend = (
                f"redis://:{six.moves.urllib.parse.quote(redis_password)}@{redis_host}:{redis_port}/{redis_db}"
            )
            redbeat_redis_url = f"redis://:{redis_password}@{redis_host}:{redis_port}/0"

    return RabbitmqConf


app = Celery("backend")
app.config_from_object(rabbitmq_conf())


# 任务执行时间统计
celery_app_timer(app)


TASK_ROOT_MODULES = [
    "alarm_backends.service",
    "alarm_backends.service.alert",
    "alarm_backends.service.converge",
    "alarm_backends.core",
    "api",
    "apm",
    "apm_ebpf",
    "metadata",
    "bkmonitor",
]
DISCOVER_DIRS = []
for MODULE in TASK_ROOT_MODULES:
    for m in package_contents(MODULE):
        file_name = f"{MODULE}.{m}"
        if os.path.isdir(os.path.join(settings.BASE_DIR, file_name.replace(".", os.sep))):
            DISCOVER_DIRS.append(file_name)

DISCOVER_DIRS.extend(settings.INSTALLED_APPS)
app.autodiscover_tasks(DISCOVER_DIRS)


@setup_logging.connect
def config_loggers(*args, **kwargs):
    from logging.config import dictConfig

    from django.conf import settings

    dictConfig(settings.LOGGING)


@beat_init.connect
def clean_db_connections(sender, **kwargs):
    close_old_connections()


class PeriodicTask(Task):
    """A task that adds itself to the :setting:`beat_schedule` setting. 兼容celery5"""

    abstract = True
    ignore_result = True
    relative = False
    options = None
    compat = True

    def __init__(self):
        if not hasattr(self, "run_every"):
            raise NotImplementedError("Periodic tasks must have a run_every attribute")
        self.run_every = maybe_schedule(self.run_every, self.relative)
        super().__init__()

    @classmethod
    def on_bound(cls, _app):
        _app.conf.beat_schedule[cls.name] = {
            "task": cls.name,
            "schedule": cls.run_every,
            "args": (),
            "kwargs": {},
            "options": cls.options or {},
            "relative": cls.relative,
        }


def periodic_task(*args, **options):
    """Deprecated decorator, please use :setting:`beat_schedule`."""
    return app.task(**dict({"base": PeriodicTask}, **options))
