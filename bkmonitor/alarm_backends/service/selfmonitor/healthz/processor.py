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
from importlib import import_module

from django.conf import settings
from django.template import Context, Template
from django.utils import timezone

from alarm_backends.core.cache import key
from alarm_backends.service.selfmonitor.healthz.checker import CheckerTask, HealthChecker
from alarm_backends.service.selfmonitor.healthz.conf import healthz_interval, healthz_list
from bkmonitor.models import HealthzMetricConfig, HealthzMetricRecord
from bkmonitor.utils.common_utils import get_local_ip

logger = logging.getLogger("self_monitor")

now = time.time()
checker = HealthChecker()
ip = get_local_ip()


def update_config_result(config, result):
    record, created = HealthzMetricRecord.objects.update_or_create(
        metric_alias=config.metric_alias,
        server_ip=ip,
        defaults={
            "result": result.as_json(),
            "last_update": timezone.now(),
        },
    )
    logger.info("metric record[%s] create: %s", record.metric_alias, created)


def load_category(category):
    import_module("alarm_backends.service.selfmonitor.healthz.checker.%s_checker" % category)


def render_collect_args(config):
    collect_args = config.collect_args
    if not collect_args:
        return {}
    template = Template(collect_args)
    return json.loads(
        template.render(
            Context(
                {
                    "key": key,
                    "settings": settings,
                    "config": config,
                    "ip": ip,
                }
            )
        )
    )


def convert_config_to_task(config):
    try:
        return CheckerTask(
            config.collect_metric,
            render_collect_args(config),
        )
    except Exception as err:
        print("create task[{}] failed: {}".format(config.collect_metric, err))


def check_tasks():
    for config in HealthzMetricConfig.objects.filter(collect_type="backend"):
        tasks = []
        if config.category in healthz_list or len(healthz_list) == 0:
            load_category(category=config.category)
            task = convert_config_to_task(config)
            if task:
                tasks.append(task)
        results = checker.check_tasks(tasks)
        for result in results:
            update_config_result(config, result)


class HealthzProcessor(object):
    """
    Healthz Processor
    """

    def process(self):
        period = 10
        if healthz_interval:
            period = healthz_interval
        try:
            check_tasks()
        except Exception as e:
            logger.exception("get exception: %s" % e)
        finally:
            time.sleep(period)
