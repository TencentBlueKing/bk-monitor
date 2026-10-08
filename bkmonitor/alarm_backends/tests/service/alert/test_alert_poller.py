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
import threading
import time
from collections import namedtuple

from unittest import mock
import pytest
from django.conf import settings

from alarm_backends.core.alert.alert import AlertUIDManager
from alarm_backends.core.cache.key import ALERT_DATA_POLLER_LEADER_KEY
from alarm_backends.service.alert.handler import AlertHandler
from alarm_backends.service.alert import handler
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
        super().__init__()
        self.partitions = set()
        self.assign_call_count = 0
        self.assignment_call_count = 0

    def assignment(self):
        self.assignment_call_count += 1
        return self.partitions

    def assign(self, partitions):
        self.assign_call_count += 1
        self.partitions = set(partitions)


class TestAlertPollerHandler:
    def test_leader_publishes_assignment_atomically(self, mocker, mock_alert_kafka_consumer):
        p = AlertHandler(mock.Mock())
        mock_alert_kafka_consumer.side_effect = lambda **kwargs: mock.Mock(partitions_for_topic=lambda topic: {0})
        p.redis_client.set(p.leader_key, p.ip)
        p.redis_client.hset(p.data_id_cache_key, p.ip, "[]")
        mocker.patch.object(p, "get_all_hosts", return_value=[p.ip])
        mocker.patch.object(handler, "get_cluster", return_value=mock.Mock(is_default=lambda: False, name="test"))
        mocker.patch.object(handler.time, "sleep")
        pipeline = p.redis_client.pipeline(transaction=True)
        execute = pipeline.execute
        snapshots = []

        def publish():
            # execute 前旧分配仍可读，不能暴露 DEL 与 HMSET 之间的空窗。
            snapshots.append((p.redis_client.hget(p.data_id_cache_key, p.ip), len(pipeline.command_stack)))
            return execute()

        mocker.patch.object(pipeline, "execute", side_effect=publish)
        mocker.patch.object(p.redis_client, "pipeline", return_value=pipeline)
        p.run_leader()
        assert snapshots == [("[]", 4)]
        assert json.loads(p.redis_client.hget(p.data_id_cache_key, p.ip))
        assert p.redis_client.ttl(p.data_id_cache_key) > 0

    def test_poller_owns_consumer_lifecycle(self, mocker, mock_alert_kafka_consumer):
        p = AlertHandler(mock.Mock())
        p.run_once = False
        clock = [0]
        operations = []
        consumer = FakeKafkaConsumer()
        conf = {"data_id": 0, "topic": "events", "bootstrap_server": "kafka.example:9092"}
        p.redis_client.hset(p.data_id_cache_key, p.ip, json.dumps([conf]))
        mocker.patch.object(handler.time, "monotonic", side_effect=lambda: clock[0])
        mocker.patch.object(handler.time, "sleep", side_effect=lambda _: p._stop())

        def record(operation):
            operations.append((operation, threading.get_ident()))

        def poll(*args, **kwargs):
            record("poll")
            # 拉取期间发生分配变更，应先完成本批分发，再关闭 consumer。
            p.redis_client.hset(p.data_id_cache_key, p.ip, "[]")
            clock[0] = 16
            return {"events": [b"event"]}

        mock_alert_kafka_consumer.side_effect = lambda **kwargs: record("create") or consumer
        mocker.patch.object(consumer, "assign", side_effect=lambda **kwargs: record("assign"))
        consumer.poll.side_effect = poll
        consumer.commit.side_effect = lambda: record("commit")
        consumer.close.side_effect = lambda **kwargs: record("close")
        mocker.patch.object(p, "push_handle_task", side_effect=lambda *args: record("push"))
        worker = threading.Thread(target=p.run_poller, daemon=True)
        worker.start()
        worker.join(timeout=2)
        assert not worker.is_alive()
        assert [operation for operation, _ in operations] == ["create", "assign", "poll", "push", "commit", "close"]
        assert {thread_id for _, thread_id in operations} == {worker.ident}
        assert p.consumers == {}

    @pytest.mark.parametrize("failure", ["create", "assign", "seek"])
    def test_refresh_failure_keeps_healthy_consumer(self, mocker, mock_alert_kafka_consumer, failure):
        p = AlertHandler(mock.Mock())
        healthy = FakeKafkaConsumer()
        new_consumer = FakeKafkaConsumer()
        healthy.poll.return_value = {}
        p.consumers["healthy.example:9092"] = healthy
        confs = [
            {"data_id": 1, "topic": "healthy", "bootstrap_server": "healthy.example:9092"},
            {"data_id": 2, "topic": "new", "bootstrap_server": "new.example:9092"},
        ]
        p.redis_client.hset(p.data_id_cache_key, p.ip, json.dumps(confs))
        mocker.patch.object(p, "get_kafka_redis_offset", return_value=123)
        mock_alert_kafka_consumer.side_effect = RuntimeError("unavailable") if failure == "create" else None
        mock_alert_kafka_consumer.return_value = new_consumer
        if failure != "create":
            mocker.patch.object(new_consumer, failure, side_effect=RuntimeError("unavailable"))
        p.run_poller()
        healthy.poll.assert_called_once()
        assert "new.example:9092" not in p.consumers
        if failure != "create":
            new_consumer.close.assert_called_once_with(autocommit=False)
        new_consumer.commit.assert_not_called()

        mock_alert_kafka_consumer.side_effect = None
        mock_alert_kafka_consumer.return_value = FakeKafkaConsumer()
        p.run_consumer_manager()
        assert "new.example:9092" in p.consumers

    def test_stop_closes_all_consumers_even_if_close_fails(self):
        p = AlertHandler(mock.Mock())
        consumers = [FakeKafkaConsumer(), FakeKafkaConsumer()]
        consumers[0].close.side_effect = RuntimeError("unavailable")
        p.consumers = dict(zip(["first", "second"], consumers))
        p._stop()
        p.run_poller()
        for consumer in consumers:
            consumer.poll.assert_not_called()
            consumer.commit.assert_not_called()
            consumer.close.assert_called_once_with(autocommit=False)
        assert p.consumers == {}

    def test_stop_after_dispatch_failure_does_not_commit(self, mocker):
        p = AlertHandler(mock.Mock())
        consumer = FakeKafkaConsumer()
        consumer.poll.return_value = {"events": [b"event"]}
        p.consumers["kafka.example:9092"] = consumer
        mocker.patch.object(p, "run_consumer_manager")

        def fail_dispatch(*args):
            p._stop()
            raise RuntimeError("dispatch failed")

        mocker.patch.object(p, "push_handle_task", side_effect=fail_dispatch)
        p.run_poller()
        consumer.commit.assert_not_called()
        consumer.close.assert_called_once_with(autocommit=False)

    def test_removed_consumer_is_not_reused_if_commit_fails(self, mocker):
        p = AlertHandler(mock.Mock())
        consumer = FakeKafkaConsumer()
        consumer.commit.side_effect = RuntimeError("unavailable")
        p.consumers["kafka.example:9092"] = consumer
        with pytest.raises(RuntimeError, match="unavailable"):
            p.run_consumer_manager()
        consumer.close.assert_called_once_with(autocommit=False)
        assert p.consumers == {}

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
