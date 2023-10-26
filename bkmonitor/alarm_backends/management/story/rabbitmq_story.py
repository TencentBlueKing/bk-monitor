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
import subprocess

import requests
from django.conf import settings

from alarm_backends.core.cache.strategy import StrategyCacheManager
from alarm_backends.management.story.base import (
    BaseStory,
    CheckStep,
    Problem,
    register_step,
    register_story,
)


@register_story()
class RabbitMQStory(BaseStory):
    name = "RabbitMQ Healthz Check"


@register_step(RabbitMQStory)
class TableSpace(CheckStep):
    name = "check queue size"

    # 队列堵塞告警配置
    warning_celery_service_total = 20000
    warning_worker_total = 10000

    def check(self):
        api_port = 15672
        api_url = f"http://{settings.RABBITMQ_HOST}:{api_port}/api/queues/{settings.RABBITMQ_VHOST.replace('/', '%2f')}"
        try:
            res = requests.get(api_url, auth=(settings.RABBITMQ_USER, settings.RABBITMQ_PASS))
            if res.status_code > 300:
                return ManagementAPIError("RabbitMQ management API call failed: code[]" % res.status_code, self.story)
            queue_list = res.json()
            if "error" in queue_list:
                self.story.error("get RabbitMQ info from api {} error: {}".format(api_url, queue_list["error"]))
                return
        except Exception as e:
            self.story.error("get RabbitMQ info from api {} error: {}".format(api_url, e))
            return

        problems = []
        self.story.warning("RabbitMQ queue info:")
        strategy_len = len(StrategyCacheManager.get_strategy_ids())
        warning_water_level = {"celery_service": max(self.warning_celery_service_total, strategy_len * 5)}
        for queue in queue_list:
            if queue["name"].startswith("celeryev"):
                continue
            if settings.IS_CONTAINER_MODE and queue["name"].startswith("celery@"):
                continue
            try:
                water_level = warning_water_level.get(queue["name"], self.warning_worker_total)
                p = self._check_queue(queue, water_level)
            except Exception:
                continue
            if p:
                problems.append(p)

        return problems

    def _check_queue(self, queue, water_level):
        # Total
        messages = queue["messages"]
        # Messages consumed per sec
        messages_changes = queue["messages_details"]["rate"]
        # Ready to consumed
        messages_ready = queue["messages_ready"]
        messages_ready_changes = queue["messages_ready_details"]["rate"]
        # Messages missed
        messages_unacknowledged = queue["messages_unacknowledged"]
        messages_unacknowledged_changes = queue["messages_unacknowledged_details"]["rate"]

        messages_pubilsh_rate = queue["message_stats"]["publish_details"]["rate"]
        name = queue["name"]
        self.story.info(
            f"{name}:\ttotal[{messages}({messages_changes}/s)]"
            f"\tready[{messages_ready}({messages_ready_changes}/s)]"
            f"\tunack[{messages_unacknowledged}({messages_unacknowledged_changes}/s)]"
            f"\tpublish rate: {messages_pubilsh_rate}/s"
        )

        if messages > water_level:
            return self._alert_queue_blocking(name, messages)

    def _alert_queue_blocking(self, queue_name, message_total):
        return Blocking(
            f"queue[{queue_name}] maybe blocking: message total: {message_total}", self.story, queue_name=queue_name
        )


class ManagementAPIError(Problem):
    def position(self):
        self.story.warning("确保已启用插件[rabbitmq_management], 且插件状态正常")


class Blocking(Problem):
    solution = "建议：尝试扩容后台队列[%s],当前并发数%s, 添加-c 参数指定更大的并发数"

    def position(self):
        self.story.warning(
            self.solution % (self.context["queue_name"], get_celery_worker_num(self.context["queue_name"]))
        )


def get_celery_worker_num(queue_name):
    ps = subprocess.Popen(["ps", "-ef"], stdout=subprocess.PIPE)
    grep = subprocess.Popen(["grep", queue_name], stdin=ps.stdout, stdout=subprocess.PIPE)
    grep = subprocess.Popen(["grep", "-v", "grep"], stdin=grep.stdout, stdout=subprocess.PIPE)
    wc = subprocess.Popen(["wc", "-l"], stdin=grep.stdout, stdout=subprocess.PIPE)
    output, err = wc.communicate()
    return int(output) - 1
