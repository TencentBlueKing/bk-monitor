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
import time
from collections import namedtuple

import mock
import pytest

from alarm_backends.service.access import AccessRealTimeDataProcess

pytestmark = pytest.mark.django_db


@pytest.fixture()
def mock_time(mocker):
    fake_time = mocker.MagicMock()
    fake_time.time = time.time
    return mocker.patch("alarm_backends.service.access.data.processor.time", fake_time)


@pytest.fixture()
def mock_kafka_consumer(mocker):
    consumer = mock.MagicMock(side_effect=lambda *args, **kwargs: FakeKafkaConsumer())
    return mocker.patch("alarm_backends.service.access.data.processor.KafkaConsumer", consumer)


class FakeKafkaConsumer(mock.MagicMock):
    def __init__(self, *args, **kwargs):
        super(FakeKafkaConsumer, self).__init__()
        self.topics = set()
        self.subscribe_call_count = 0
        self.subscription_call_count = 0

    def subscription(self):
        self.subscription_call_count += 1
        return self.topics

    def subscribe(self, topics):
        self.subscribe_call_count += 1
        self.topics = set(topics)


class TestAccessDataProcess(object):
    def test_leader(self, mock_time):
        service = mock.MagicMock()
        p = AccessRealTimeDataProcess(service)
        p.ip = "127.0.0.1"
        get_all_hosts = mock.MagicMock().side_effect = lambda _: ["127.0.0.1", "127.0.0.2"]
        AccessRealTimeDataProcess.get_all_hosts = get_all_hosts

        p.run_leader(once=True)
        assert p.cache.get("real-time-handler-leader") == p.ip

        p = AccessRealTimeDataProcess(service)
        p.ip = "127.0.0.2"
        AccessRealTimeDataProcess.get_all_hosts = get_all_hosts

        p.run_leader(once=True)
        assert p.cache.get("real-time-handler-leader") == "127.0.0.1"

    def test_consumer_manager(self, mock_time, mock_kafka_consumer):
        service = mock.MagicMock()
        p = AccessRealTimeDataProcess(service)
        p.ip = "127.0.0.1"

        p.cache.hset(
            p.topic_cache_key,
            p.ip,
            json.dumps({"kafka1.service.consul:9092|topic1": "", "kafka2.service.consul:9092|topic2": ""}),
        )
        p.run_consumer_manager(once=True)
        assert len(p.consumers) == 2
        assert mock_kafka_consumer.call_count == 2
        assert p.consumers["kafka1.service.consul:9092"].subscribe_call_count == 1
        assert p.consumers["kafka2.service.consul:9092"].subscribe_call_count == 1
        consumer2 = p.consumers["kafka2.service.consul:9092"]

        p.cache.hset(
            p.topic_cache_key,
            p.ip,
            json.dumps({"kafka1.service.consul:9092|topic1": "", "kafka3.service.consul:9092|topic3": ""}),
        )
        p.run_consumer_manager(once=True)
        assert len(p.consumers) == 2
        assert mock_kafka_consumer.call_count == 3
        assert p.consumers["kafka1.service.consul:9092"].subscribe_call_count == 1
        assert p.consumers["kafka3.service.consul:9092"].subscribe_call_count == 1
        assert consumer2.close.call_count == 1

        p.cache.hset(
            p.topic_cache_key,
            p.ip,
            json.dumps({"kafka1.service.consul:9092|topic1": "", "kafka3.service.consul:9092|topic3": ""}),
        )

        p.run_consumer_manager(once=True)
        assert len(p.consumers) == 2
        assert mock_kafka_consumer.call_count == 3
        assert p.consumers["kafka1.service.consul:9092"].subscribe_call_count == 1
        assert p.consumers["kafka3.service.consul:9092"].subscribe_call_count == 1

        p.cache.hset(
            p.topic_cache_key,
            p.ip,
            json.dumps({"kafka1.service.consul:9092|topic4": "", "kafka3.service.consul:9092|topic3": ""}),
        )

        p.run_consumer_manager(once=True)
        assert len(p.consumers) == 2
        assert mock_kafka_consumer.call_count == 3
        assert p.consumers["kafka1.service.consul:9092"].subscribe_call_count == 2
        assert p.consumers["kafka3.service.consul:9092"].subscribe_call_count == 1

    def test_poller(self, mock_kafka_consumer):
        service = mock.MagicMock()
        p = AccessRealTimeDataProcess(service)
        p.ip = "127.0.0.1"

        p.cache.hset(
            p.topic_cache_key,
            p.ip,
            json.dumps({"kafka1.service.consul:9092|topic1": "", "kafka2.service.consul:9092|topic2": ""}),
        )
        p.run_consumer_manager(once=True)
        for consumer in p.consumers.values():
            consumer.poll = lambda *args, **kwargs: {
                "record1": [
                    b'{"time":1646654276,"dimensions":{"bk_biz_id":3,"bk_cloud_id":0,"bk_cmdb_level":"null",'
                    b'"bk_supplier_id":0,"bk_target_cloud_id":"0","bk_target_ip":"127.0.0.2",'
                    b'"device_name":"cpu-total","hostname":"VM-233-232-centos","ip":"127.0.0.2"},'
                    b'"metrics":{"guest":0,"idle":0.9633778145526556,"interrupt":0,"iowait":0.00039590531917403843,'
                    b'"nice":0.0000032647704520309565,"softirq":0.001961290886801718,"stolen":null,'
                    b'"system":0.0088828947147627,"usage":5.549278091672173,"user":0.025378829756153826}}'
                ],
                "record2": [
                    b'{"time":1646654289,"dimensions":{"bk_biz_id":2,"bk_cloud_id":0,"bk_cmdb_level":"null",'
                    b'"bk_supplier_id":0,"bk_target_cloud_id":"0","bk_target_ip":"127.0.0.1",'
                    b'"device_name":"cpu-total","hostname":"VM-68-183-centos","ip":"127.0.0.1"},"metrics":'
                    b'{"guest":0,"idle":0.8892071480874113,"interrupt":0,"iowait":0.01150230305921522,'
                    b'"nice":0.000008206645092959288,"softirq":0.005655448600487947,"stolen":0,'
                    b'"system":0.024662938476193073,"usage":17.05800814878766,"user":0.06896395513159939}}'
                ],
            }
        p.run_poller(once=True)
        assert p.queue.qsize() == 4

    def test_handler(self):
        ConsumerRecord = namedtuple("ConsumerRecord", ["topic", "value"])
        service = mock.MagicMock()
        p = AccessRealTimeDataProcess(service)
        p.ip = "127.0.0.1"
        p.topics = {
            "kafka1.service.consul:9092|topic1": {"strategy_ids": [1, 2], "dimensions": ["bk_target_ip"]},
            "kafka2.service.consul:9092|topic2": {"strategy_ids": [3, 4], "dimensions": ["ip", "bk_cloud_id"]},
        }
        message = f'{{"time":{int(time.time())},"dimensions":{{"bk_biz_id":3,"bk_cloud_id":0,"bk_cmdb_level":"null",'
        p.queue.put(
            (
                "kafka1.service.consul:9092",
                [
                    ConsumerRecord(
                        "topic1",
                        message.encode() + b'"bk_supplier_id":0,"bk_target_cloud_id":"0","bk_target_ip":"127.0.0.2",'
                        b'"device_name":"cpu-total","hostname":"VM-233-232-centos","ip":"127.0.0.2"},'
                        b'"metrics":{"guest":0,"idle":0.9633778145526556,"interrupt":0,"iowait":0.00039590531917403843,'
                        b'"nice":0.0000032647704520309565,"softirq":0.001961290886801718,"stolen":null,'
                        b'"system":0.0088828947147627,"usage":5.549278091672173,"user":0.025378829756153826}}',
                    )
                ],
            )
        )
        message = f'{{"time":{int(time.time())},"dimensions":{{"bk_biz_id":2,"bk_cloud_id":0,"bk_cmdb_level":"null",'
        p.queue.put(
            (
                "kafka2.service.consul:9092",
                [
                    ConsumerRecord(
                        "topic2",
                        message.encode() + b'"bk_supplier_id":0,"bk_target_cloud_id":"0","bk_target_ip":"127.0.0.1",'
                        b'"device_name":"cpu-total","hostname":"VM-68-183-centos","ip":"127.0.0.1"},"metrics":'
                        b'{"guest":0,"idle":0.8892071480874113,"interrupt":0,"iowait":0.01150230305921522,'
                        b'"nice":0.000008206645092959288,"softirq":0.005655448600487947,"stolen":0,'
                        b'"system":0.024662938476193073,"usage":17.05800814878766,"user":0.06896395513159939}}',
                    )
                ],
            )
        )
        p.run_handler(once=True)
