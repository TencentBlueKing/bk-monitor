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
from django.conf import settings

from alarm_backends.core.alert.alert import AlertUIDManager
from alarm_backends.core.cache.key import ALERT_DATA_POLLER_LEADER_KEY
from alarm_backends.service.alert.handler import AlertHandler
from bkmonitor.documents import AlertDocument, EventDocument

leader_key = ALERT_DATA_POLLER_LEADER_KEY.get_key()

pytestmark = pytest.mark.django_db


@pytest.fixture()
def mock_alert_kafka_consumer(mocker):
    consumer = mock.MagicMock(side_effect=lambda *args, **kwargs: FakeKafkaConsumer())
    return mocker.patch("alarm_backends.service.alert.handler.KafkaConsumer", consumer)


@pytest.fixture()
def mock_run_alert_builder(mocker):
    mock_run = mocker.MagicMock(return_value=True)
    return mocker.patch("alarm_backends.service.alert.handler.run_alert_builder", mock_run)


@pytest.fixture()
def mock_send_periodic_check(mocker):
    ret = mocker.MagicMock(return_value=True)
    return mocker.patch("alarm_backends.service.alert.builder.processor.send_check_task", ret)


@pytest.fixture()
def mock_send_signal(mocker):
    delay_task = mocker.MagicMock(return_value=True)
    return mocker.patch("alarm_backends.service.alert.builder.processor.AlertBuilder.send_signal", delay_task)


@pytest.fixture()
def clear_index():
    for doc in [AlertDocument, EventDocument]:
        ilm = doc.get_lifecycle_manager()
        ilm.es_client.indices.delete(index=doc.Index.name)
        ilm.es_client.indices.create(index=doc.Index.name)


class FakeKafkaConsumer(mock.MagicMock):
    def __init__(self, *args, **kwargs):
        super(FakeKafkaConsumer, self).__init__()
        self.partitions = set()
        self.assign_call_count = 0
        self.assignment_call_count = 0

    def assignment(self):
        self.assignment_call_count += 1
        return self.partitions

    def assign(self, partitions):
        self.assign_call_count += 1
        self.partitions = set(partitions)


class TestAlertPollerHandler(object):
    def test_leader(self):
        service = mock.Mock()
        p = AlertHandler(service)
        p.ip = "127.0.0.1"
        get_all_hosts = mock.MagicMock().side_effect = lambda _: ["127.0.0.1", "127.0.0.2"]
        AlertHandler.get_all_hosts = get_all_hosts

        p.run_leader()
        assert p.redis_client.get(p.leader_key) == p.ip

        p = AlertHandler(service)
        p.ip = "127.0.0.2"
        AlertHandler.get_all_hosts = get_all_hosts

        p.run_leader()
        assert p.redis_client.get(p.leader_key) == "127.0.0.1"

    def test_consumer_manager(self, mock_alert_kafka_consumer):
        service = mock.Mock()
        p = AlertHandler(service)
        p.ip = "127.0.0.1"

        p.redis_client.hset(
            p.data_id_cache_key,
            p.ip,
            json.dumps(
                [
                    {
                        "data_id": 1,
                        "partition": 0,
                        "topic": "topic1",
                        "bootstrap_server": "kafka1.service.consul:9092",
                    },
                    {
                        "data_id": 2,
                        "partition": 0,
                        "topic": "topic2",
                        "bootstrap_server": "kafka2.service.consul:9092",
                    },
                ]
            ),
        )
        p.run_consumer_manager()
        assert mock_alert_kafka_consumer.call_count == 2
        assert p.consumers["kafka1.service.consul:9092"].assign_call_count == 1
        assert p.consumers["kafka2.service.consul:9092"].assign_call_count == 1
        consumer2 = p.consumers["kafka2.service.consul:9092"]

        p.redis_client.hset(
            p.data_id_cache_key,
            p.ip,
            json.dumps(
                [
                    {
                        "data_id": 1,
                        "topic": "topic1",
                        "partition": 0,
                        "bootstrap_server": "kafka1.service.consul:9092",
                    },
                    {
                        "data_id": 3,
                        "topic": "topic3",
                        "partition": 0,
                        "bootstrap_server": "kafka3.service.consul:9092",
                    },
                ]
            ),
        )
        p.run_consumer_manager()
        assert len(p.consumers) == 2
        assert mock_alert_kafka_consumer.call_count == 3
        assert p.consumers["kafka1.service.consul:9092"].assign_call_count == 1
        assert p.consumers["kafka3.service.consul:9092"].assign_call_count == 1
        assert consumer2.close.call_count == 1
        assert consumer2.seek.call_count == 0

        p.redis_client.hset(
            p.data_id_cache_key,
            p.ip,
            json.dumps(
                [
                    {
                        "data_id": 1,
                        "topic": "topic1",
                        "partition": 0,
                        "bootstrap_server": "kafka1.service.consul:9092",
                    },
                    {
                        "data_id": 3,
                        "topic": "topic3",
                        "partition": 0,
                        "bootstrap_server": "kafka3.service.consul:9092",
                    },
                ]
            ),
        )

        p.run_consumer_manager()
        assert len(p.consumers) == 2
        assert mock_alert_kafka_consumer.call_count == 3
        assert p.consumers["kafka1.service.consul:9092"].assign_call_count == 1
        assert p.consumers["kafka3.service.consul:9092"].assign_call_count == 1

        p.redis_client.hset(
            p.data_id_cache_key,
            p.ip,
            json.dumps(
                [
                    {
                        "data_id": 4,
                        "topic": "topic4",
                        "partition": 0,
                        "bootstrap_server": "kafka4.service.consul:9092",
                    },
                    {
                        "data_id": 3,
                        "topic": "topic3",
                        "partition": 0,
                        "bootstrap_server": "kafka3.service.consul:9092",
                    },
                ]
            ),
        )

        p.run_consumer_manager()
        assert len(p.consumers) == 2
        assert mock_alert_kafka_consumer.call_count == 4
        assert p.consumers["kafka4.service.consul:9092"].assign_call_count == 1
        assert p.consumers["kafka3.service.consul:9092"].assign_call_count == 1

    def test_poller(self, mock_alert_kafka_consumer, mock_run_alert_builder):
        service = mock.Mock()
        p = AlertHandler(service)
        p.ip = "127.0.0.1"

        p.redis_client.hset(
            p.data_id_cache_key,
            p.ip,
            json.dumps(
                [
                    {
                        "data_id": 1,
                        "topic": "topic1",
                        "partition": 0,
                        "bootstrap_server": "kafka1.service.consul:9092",
                    },
                    {
                        "data_id": 2,
                        "topic": "topic2",
                        "partition": 0,
                        "bootstrap_server": "kafka2.service.consul:9092",
                    },
                ]
            ),
        )
        p.run_consumer_manager()
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
        p.run_poller()

        assert mock_run_alert_builder.call_count == 2

    def test_poller_send_one_event(self, mock_alert_kafka_consumer, mock_run_alert_builder):
        service = mock.Mock()
        settings.MAX_BUILD_EVENT_NUMBER = 1
        p = AlertHandler(service)
        p.ip = "127.0.0.1"
        p.redis_client.hset(
            p.data_id_cache_key,
            p.ip,
            json.dumps(
                [
                    {
                        "data_id": 1,
                        "topic": "topic1",
                        "partition": 0,
                        "bootstrap_server": "kafka1.service.consul:9092",
                    },
                    {
                        "data_id": 2,
                        "topic": "topic2",
                        "partition": 0,
                        "bootstrap_server": "kafka2.service.consul:9092",
                    },
                ]
            ),
        )
        p.run_consumer_manager()
        for consumer in p.consumers.values():
            consumer.poll = lambda *args, **kwargs: {
                "record1": [
                    b'{"time":1646654276,"dimensions":{"bk_biz_id":3,"bk_cloud_id":0,"bk_cmdb_level":"null",'
                    b'"bk_supplier_id":0,"bk_target_cloud_id":"0","bk_target_ip":"127.0.0.2",'
                    b'"device_name":"cpu-total","hostname":"VM-233-232-centos","ip":"127.0.0.2"},'
                    b'"metrics":{"guest":0,"idle":0.9633778145526556,"interrupt":0,"iowait":0.00039590531917403843,'
                    b'"nice":0.0000032647704520309565,"softirq":0.001961290886801718,"stolen":null,'
                    b'"system":0.0088828947147627,"usage":5.549278091672173,"user":0.025378829756153826}}',
                    b'{"time":1646654289,"dimensions":{"bk_biz_id":2,"bk_cloud_id":0,"bk_cmdb_level":"null",'
                    b'"bk_supplier_id":0,"bk_target_cloud_id":"0","bk_target_ip":"127.0.0.1",'
                    b'"device_name":"cpu-total","hostname":"VM-68-183-centos","ip":"127.0.0.1"},"metrics":'
                    b'{"guest":0,"idle":0.8892071480874113,"interrupt":0,"iowait":0.01150230305921522,'
                    b'"nice":0.000008206645092959288,"softirq":0.005655448600487947,"stolen":0,'
                    b'"system":0.024662938476193073,"usage":17.05800814878766,"user":0.06896395513159939}}',
                ],
            }
        p.run_poller()
        assert mock_run_alert_builder.call_count == 4
        settings.MAX_BUILD_EVENT_NUMBER = 0

    def test_run_alert_builder_once(
        self, mock_alert_kafka_consumer, mock_send_periodic_check, mock_send_signal, clear_index
    ):
        time1 = int(time.time())
        time2 = time1 - 500
        ConsumerRecord = namedtuple("ConsumerRecord", ["topic", "value"])
        service = mock.Mock()
        p = AlertHandler(service)
        p.ip = "127.0.0.1"

        p.redis_client.hset(
            p.data_id_cache_key,
            p.ip,
            json.dumps(
                [
                    {
                        "data_id": 1,
                        "topic": "topic1",
                        "partition": 0,
                        "bootstrap_server": "kafka1.service.consul:9092",
                    }
                ]
            ),
        )

        events = [
            {
                "bk_biz_id": 2,
                "event_id": "2",
                "plugin_id": "fta-test",
                "alert_name": "CPU usage high",
                "time": time1,
                "tags": [{"key": "device", "value": "cpu0"}],
                "severity": 1,
                "target": "127.0.0.1",
                "dedupe_keys": ["alert_name", "target"],
                "strategy_id": 100,
            },
            {
                "bk_biz_id": 2,
                "event_id": "1",
                "plugin_id": "fta-test",
                "alert_name": "CPU usage high",
                "time": time2,
                "tags": [{"key": "device", "value": "cpu1"}],
                "target": "127.0.0.1",
                "severity": 1,
                "dedupe_keys": ["alert_name", "target"],
                "strategy_id": 100,
            },
        ]

        records = [ConsumerRecord("topic1", json.dumps(event)) for event in events]
        p.run_consumer_manager()
        assert len(p.consumers.values()) == 1
        consumer = p.consumers["kafka1.service.consul:9092"]
        consumer.poll = lambda *args, **kwargs: {
            "topic1": records,
        }
        p.run_poller()
        mock_send_periodic_check.assert_called_once()
        assert mock_send_signal.call_count == 1
        event1 = EventDocument.get_by_event_id("1")
        assert event1.target == "127.0.0.1"
        assert "936eafa6dac0d420db79fcdf3bae8f15" == event1.dedupe_md5

        alert = AlertDocument.get_by_dedupe_md5(dedupe_md5="936eafa6dac0d420db79fcdf3bae8f15")
        assert time2 == alert.begin_time
        assert time1 == alert.latest_time
        assert 1 == alert.severity
        assert "ABNORMAL" == alert.status
        assert 1 == AlertUIDManager.parse_sequence(alert.id)
