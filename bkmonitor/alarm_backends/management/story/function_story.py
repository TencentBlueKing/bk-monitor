"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from collections import defaultdict

from django.conf import settings

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
        threshold = 100000
        from alarm_backends.service.access.event.event_poller import EventPoller
        from kafka.structs import TopicPartition

        ep = EventPoller()
        consumer = ep.get_consumer()
        for topic, data_id in ep.topics_map.items():
            partitions = consumer.partitions_for_topic(topic) or {0}
            topic_partitions = [TopicPartition(topic=topic, partition=partition) for partition in partitions]
            end_offsets = consumer.end_offsets(topic_partitions)
            committed_offsets = {}
            for tp in topic_partitions:
                committed_offsets[tp] = consumer.committed(tp)
                if end_offsets[tp] - committed_offsets[tp] > threshold:
                    self.story.warning(
                        f"{consumer.config['bootstrap_servers']} {topic} congestion occurs, {end_offsets[tp] - committed_offsets[tp]}"
                    )
