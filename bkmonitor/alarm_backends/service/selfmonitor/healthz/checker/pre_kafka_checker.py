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
"""
kafka连通性，为了避免和后台节点命名的冲突，此处称为pre_kafka
"""


import json
import logging
from contextlib import closing

import six
from django.conf import settings

from alarm_backends.core.storage.kafka import KafkaQueue
from alarm_backends.service.selfmonitor.healthz.checker.checker import CheckerRegister
from alarm_backends.service.selfmonitor.healthz.checker.utils import KAFKA_COLLECT_COUNT
from bkmonitor.utils.common_utils import get_local_ip
from bkmonitor.utils.kafka_tools import get_kafka_clusters
from core.drf_resource import api

register = CheckerRegister.pre_kafka
logger = logging.getLogger(__name__)


def pre_cluster_status(manager, result, index, timeout=1):
    """Kafka集群状态"""

    clusters = get_kafka_clusters()
    config = clusters.get(index) or clusters.get(str(index))
    if not config:
        raise result.fail("config not found", value=False)
    try:
        with closing(KafkaQueue(kfk_conf=config, timeout=timeout, group_prefix="pre_cluster_status")):
            pass
    except Exception as err:
        raise result.fail("connect failed because of: %s" % err, value=False)

    return result.ok(value="ok")


def pre_cluster_config(manager, result, timeout=1):
    """Kafka集群状态"""
    clusters = get_kafka_clusters()
    result_list = []
    if not clusters:
        raise result.fail("cluster not found", value={})
    for key, value in six.iteritems(clusters):
        try:
            # 遍历查询对应配置，看是否报错
            with closing(KafkaQueue(kfk_conf=value, timeout=timeout, group_prefix="pre_cluster_config_%s" % key)):
                pass
        except Exception as err:
            logger.exception(err)
        else:
            result_list.append(value)
    result.ok(value=result_list)


@register.status()
def pre_kafka_status(manager, result):
    """Kafka状态"""
    return pre_cluster_status(manager, result, index=settings.COMMON_KAFKA_CLUSTER_INDEX)


@register.config()
def pre_kafka_config(manager, result):
    """Kafka配置"""
    pre_cluster_config(manager, result)


@register.topic_data()
def pre_kafka_topic_data(manager, result):
    """kafka对应数据的topic"""
    try:
        local_ip = get_local_ip()
        # 蓝鲸业务的kafka
        KAFKA_QUEUE = KafkaQueue("kafka", group_prefix="%s_healthz_pre_kafka" % local_ip)
        bk_biz_id = api.cmdb.get_blueking_biz()
        bk_biz_topic = "0bkmonitor_10010".format(bk_biz_id=bk_biz_id)
        KAFKA_QUEUE.set_topic(bk_biz_topic)
        # 重置kafka
        KAFKA_QUEUE.reset_offset()
        bk_result = KAFKA_QUEUE.take(count=KAFKA_COLLECT_COUNT, timeout=0.1)
        if not bk_result:
            result.fail(message="no data in topic: %s" % bk_biz_topic)
        # 将结果拼成一个列表
        result_list = []
        for index, item in enumerate(bk_result):
            tmp = json.loads(item)
            # 给一个唯一的名称
            tmp["name"] = "pre_kafka.topic_data{}".format(index + 1)
            result_list.append(tmp)
        result.ok(value=result_list)
    except Exception as e:
        logger.exception(e)
        result.fail(message=str(e))
