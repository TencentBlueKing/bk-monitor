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
import sys
import time
from io import StringIO

import requests
from django.conf import settings
from kafka import KafkaConsumer, TopicPartition

from alarm_backends.management.story.base import (
    BaseStory,
    CheckStep,
    Problem,
    StepController,
    register_step,
    register_story,
)
from bkmonitor.utils.dns_resolve import resolve_domain
from bkmonitor.utils.kafka_tools import get_kafka_clusters
from metadata.models import KafkaTopicInfo

default_group_id = "bkmonitorv3_transfer"
default_offset_delta = 1000


class TransferEntry(StepController):
    def _check(self):
        return "-transfer" in sys.argv


transfer_controller = TransferEntry()


@register_story()
class TransferStory(BaseStory):
    name = "Transfer Healthz Check"

    def __init__(self):
        # 获取全部topic
        topic_infos = KafkaTopicInfo.objects.all().values()
        self.topics = [info["topic"] for info in topic_infos]
        clusters = get_kafka_clusters()
        self.bootstrap_servers = ["{}:{}".format(clusters[idx]["domain"], clusters[idx]["port"]) for idx in clusters]
        # 从全局配置中获取transfer group id,
        self.group_id = settings.TRANSFER_CONSUMER_GROUP_ID

        # transfer和influxdb-proxy需要注意的是，每个节点的信息都不一样
        # 初始化transfer的ip地址，注：这里TRANSFER_HOST必须是域名，如果是ip，则会timeout
        transfer_host = settings.TRANSFER_HOST
        self.transfer_ips = resolve_domain(transfer_host)


@register_step(TransferStory)
class TransferOffset(CheckStep):
    name = "check transfer consumer offset"
    controller = transfer_controller

    def check(self):
        self.story.info("this step will cost a couple of seconds")
        p_list = []
        # 连接kafka获取最新的offset，consumer.tail_offset
        # 获取transfer消费到的每个分区的offset。
        allow_max_delta = settings.TRANSFER_ALLOW_MAX_OFFSET_DELTA  # 允许最大的偏移量差值，从全局配置中获取
        for topic in self.story.topics:
            consumer = KafkaConsumer(
                bootstrap_servers=self.story.bootstrap_servers,
                auto_offset_reset=False,
                group_id="{}{}".format(self.story.group_id, topic),
                enable_auto_commit=False,
            )
            # https://github.com/dpkp/kafka-python/issues/1860
            _ = consumer.topics()
            # 获取topic下所有分区
            partitions = consumer.partitions_for_topic(topic)
            tps = [TopicPartition(topic, partition) for partition in partitions]
            # 重新指定topic和partition
            consumer.unsubscribe()
            consumer.assign(tps)
            # {TopicPartition(topic='0bkmonitor_10070', partition=0): 1013236}, end_offsets实际是最新的偏移量的下一个值
            end_offsets = consumer.end_offsets(tps)
            for tp in tps:
                try:
                    position = consumer.position(tp)
                    if end_offsets[tp] - position > allow_max_delta:
                        p = TransferOffsetProblem(
                            f"[{tp}]current consumption offset:[{position}]"
                            f" is far from the latest offset:[{end_offsets[tp]-1}] ",
                            self.story,
                        )
                        p_list.append(p)
                    # self.story.info(f"[{tp}] current offset:[{position}], latest offset:[{end_offsets[tp]-1}]")
                except Exception:
                    continue
            consumer.close()

        return p_list


@register_step(TransferStory)
class TransferDropData(CheckStep):
    name = "check transfer drop data"
    controller = transfer_controller

    def check(self):
        transfer_ips = self.story.transfer_ips
        transfer_port = settings.TRANSFER_PORT
        p_list = []
        drop_maps = {}

        # 如果未感知到transfer，在自监控会发现，所以此处默认transfer_ips中有值
        for transfer_node in transfer_ips:
            url = "http://{}:{}/metrics".format(transfer_node, transfer_port)
            # 自监控没问题，默认返回状态为200。resp.status_code
            resp = requests.get(url)
            drop_maps[transfer_node] = self.parse_metrics(resp.text)

        # 睡一分钟，观察之后的再分析之后的数据
        self.story.info("please wait 1 min to calculate the diff...")
        time.sleep(60)
        for transfer_node in transfer_ips:
            url = "http://{}:{}/metrics".format(transfer_node, transfer_port)
            # 自监控没问题，默认返回状态为200。resp.status_code
            resp = requests.get(url)
            current_drop_map = self.parse_metrics(resp.text)

            # 对比新的map中相对于之前的map是否有增长
            old_drop_map = drop_maps.get(transfer_node, {})
            for name, val in current_drop_map.items():
                if old_drop_map.get(name, "0") == val:
                    continue

                if name.find("transfer_pipeline_backend_dropped_total") != -1:
                    p = TransferBackendDropDataProblem(
                        f"[{transfer_node}] backend drop data [{name} {val}]", self.story
                    )
                    p_list.append(p)
                    continue

                if name.find("transfer_pipeline_processor_dropped_total") != -1:
                    p = TransferProcessorDropDataProblem(f"[{transfer_node}] drop data [{name} {val}]", self.story)
                    p_list.append(p)
                    continue

                p = TransferFrontendDropDataProblem(f"[{transfer_node}] drop data [{name} {val}]", self.story)
                p_list.append(p)

        return p_list

    @classmethod
    def parse_metrics(cls, txt):
        # 判断含有drop，并且值不为0的记录下来
        # transfer_pipeline_backend_dropped_total
        # transfer_pipeline_processor_dropped_total
        # transfer_pipeline_frontend_dropped_total
        output = StringIO(txt)
        drop_map = {}
        line = "start"
        while line != "":
            line = output.readline()
            if line.startswith("#"):
                continue
            # {metrickey_labelname_labelvalue: metricvalue}
            if line.find("_dropped_") == -1:
                continue
            # 获取到drop指标，过滤掉drop不为零的。普罗格式被切割后会被切割成  [metric_name{labels}, metric_value]
            items = line.split()
            if len(items) < 2:
                continue
            if items[1] == "0":
                continue
            drop_map[items[0]] = items[1]
        output.close()
        return drop_map


class TransferOffsetProblem(Problem):
    def position(self):
        self.story.warning("建议：检查transfer CPU使用率是否已经过高，需要扩容transfer")


class TransferFrontendDropDataProblem(Problem):
    def position(self):
        self.story.warning("如果有增长，告警检查采集器是否版本为更新问题")


class TransferProcessorDropDataProblem(Problem):
    def position(self):
        self.story.warning("检查transfer warn级别日志，确认数据丢弃原因")


class TransferBackendDropDataProblem(Problem):
    def position(self):
        self.story.warning("建议：检查transfer日志，确认数据写入失败原因")
