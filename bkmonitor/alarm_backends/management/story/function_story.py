"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
from collections import defaultdict

from django.conf import settings
from kafka import KafkaConsumer, TopicPartition

from alarm_backends.core.cache.key import REAL_TIME_HOST_TOPIC_KEY
from alarm_backends.management.story.base import (
    BaseStory,
    CheckStep,
    Problem,
    register_step,
    register_story,
)
from metadata.models import PingServerSubscriptionConfig


@register_story()
class FunctionStory(BaseStory):
    name = "Function Healthz Check"


class TooManyPingTargetsProblem(Problem):
    def position(self):
        self.story.warning("请扩容云区域({})的proxy节点".format(self.context["bk_cloud_id"]))


@register_step(FunctionStory)
class MaxPingTargetsNumber(CheckStep):
    name = "check max ping targets number"

    def check(self):
        p_list = []
        configs = PingServerSubscriptionConfig.objects.all()
        error_clouds = defaultdict(list)
        for config in configs:
            if config.config.get("status") == "STOP" or "steps" not in config.config:
                continue

            # 判断订阅参数中下发到每台机器的Ping目标数量是否超出限制
            for ip, hosts in config.config["steps"][0]["params"]["context"]["ip_to_items"].items():
                if len(hosts) > settings.PING_SERVER_TARGET_NUMBER_LIMIT:
                    error_clouds[config.bk_cloud_id].append(config.ip)

        for bk_cloud_id, ips in error_clouds.items():
            p_list.append(
                TooManyPingTargetsProblem(
                    f"cloud({bk_cloud_id}) ip({','.join(ips)}) have too many ping targets.",
                    self.story,
                    bk_cloud_id=bk_cloud_id,
                )
            )

        if p_list:
            return p_list


class TopicCongestionProblem(Problem):
    def position(self):
        self.story.warning(self.name)


@register_step(FunctionStory)
class RealTimeTopicStatus(CheckStep):
    name = "check real time topic status"

    def check(self):
        threshold = 10000
        client = REAL_TIME_HOST_TOPIC_KEY.client
        ip_topics = client.hgetall(REAL_TIME_HOST_TOPIC_KEY.get_key())
        topics = []
        for value in ip_topics.values():
            topics.extend(json.loads(value).keys())

        # kafka集群及所属topic分组
        bootstrap_servers_topics = defaultdict(set)
        for topic in topics:
            bootstrap_servers, topic = topic.split("|")
            bootstrap_servers_topics[bootstrap_servers].add(topic)

        group_id = f"{settings.APP_CODE}.real_time_access"
        for bootstrap_servers, topics in bootstrap_servers_topics.items():
            c = KafkaConsumer(bootstrap_servers=bootstrap_servers, group_id=group_id)
            c.topics()

            congestion_topics = []
            topic_partitions = []
            for topic in topics:
                partitions = c.partitions_for_topic(topic) or {0}
                topic_partitions.extend([TopicPartition(topic=topic, partition=partition) for partition in partitions])
            end_offsets = c.end_offsets(topic_partitions)
            committed_offsets = {}
            for topic_partition in topic_partitions:
                committed_offsets[topic_partition] = c.committed(topic_partition) or 0
            c.close()

            for topic_partition in committed_offsets:
                if end_offsets[topic_partition] - committed_offsets[topic_partition] > threshold:
                    congestion_topics.append(topic_partition.topic)
                    self.story.warning(
                        f"{bootstrap_servers} {topic_partition.topic} congestion occurs, "
                        f"{end_offsets[topic_partition] - committed_offsets[topic_partition]}"
                    )
