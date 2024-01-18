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


import logging
from contextlib import closing

from django.conf import settings

from alarm_backends.core.storage.kafka import KafkaQueue
from bkmonitor.utils.kafka_tools import get_kafka_clusters

from .checker import CheckerRegister
from .utils import simple_check

logger = logging.getLogger(__name__)

register = CheckerRegister.kafka


@register.cluster.count()
def cluster_count(manager, result):
    """Kafka集群数"""
    value = len(get_kafka_clusters())
    result.ok_or_fail(value > 0, value, "length is %d" % value)


@register.cluster.status()
def cluster_status(manager, result, index, timeout=1):
    """Kafka集群状态"""
    clusters = get_kafka_clusters()
    config = clusters.get(index) or clusters.get(str(index))
    if not config:
        raise result.fail("config not found", value=False)
    try:
        with closing(KafkaQueue(kfk_conf=config, timeout=timeout)):
            pass
    except Exception as err:
        raise result.fail("connect failed because of: %s" % err, value=False)

    return result.ok(value="ok")


@register.status()
def kafka_status(manager, result):
    """Kafka状态"""
    return cluster_status(manager, result, index=settings.COMMON_KAFKA_CLUSTER_INDEX)


@register.queue.size()
@simple_check
def kafka_queue_qsize(topic, group_prefix=None):
    """Kafka队列长度"""
    group_prefix = group_prefix or "healthz_"
    with closing(KafkaQueue(topic=topic, group_prefix=group_prefix)) as queue:
        consumer = queue.get_consumer()
        return consumer.queue.qsize()
