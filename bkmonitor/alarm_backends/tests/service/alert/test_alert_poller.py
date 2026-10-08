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
from kafka import KafkaConsumer as RealKafkaConsumer
from kafka import TopicPartition
from kafka.errors import GroupCoordinatorNotAvailableError
from kafka.future import Future

from alarm_backends.core.alert.alert import AlertUIDManager
from alarm_backends.service.alert import handler
from alarm_backends.service.alert.handler import AlertHandler
from bkmonitor.documents import AlertDocument, EventDocument

pytestmark = pytest.mark.django_db


class FakeKafkaConsumer(mock.MagicMock):
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.partitions = set()

    def assignment(self):
        return self.partitions

    def assign(self, partitions):
        self.partitions = set(partitions)


def set_assignment(p, *servers, data_id=0):
    p.redis_client.hset(
        p.data_id_cache_key,
        p.ip,
        json.dumps([{"bootstrap_server": server, "topic": "events", "data_id": data_id} for server in servers]),
    )


class TestAlertPollerHandler:
    def test_leader_publishes_assignment_atomically(self, mocker):
        p = AlertHandler(mock.Mock())
        mocker.patch.object(
            handler, "KafkaConsumer", side_effect=lambda **kwargs: mock.Mock(partitions_for_topic=lambda _: {0})
        )
        p.redis_client.set(p.leader_key, p.ip)
        p.redis_client.hset(p.data_id_cache_key, p.ip, "[]")
        mocker.patch.object(p, "get_all_hosts", return_value=[p.ip])
        mocker.patch.object(handler, "get_cluster", return_value=mock.Mock(is_default=lambda: False, name="test"))
        mocker.patch.object(handler.time, "sleep")
        pipeline = p.redis_client.pipeline(transaction=True)
        execute = pipeline.execute
        snapshots = []

        def publish():
            snapshots.append((p.redis_client.hget(p.data_id_cache_key, p.ip), len(pipeline.command_stack)))
            return execute()

        mocker.patch.object(pipeline, "execute", side_effect=publish)
        mocker.patch.object(p.redis_client, "pipeline", return_value=pipeline)
        p.run_leader()
        assert snapshots == [("[]", 4)]
        assert json.loads(p.redis_client.hget(p.data_id_cache_key, p.ip))
        assert p.redis_client.ttl(p.data_id_cache_key) > 0

    @pytest.mark.parametrize("batch_size, expected_calls", [(500, 1), (1, 2)])
    def test_worker_owns_lifecycle_and_dispatches_batches(self, mocker, batch_size, expected_calls):
        p = AlertHandler(mock.Mock())
        p.max_event_number = batch_size
        operations = []
        consumer = FakeKafkaConsumer()
        set_assignment(p, "kafka.example:9092", data_id=1)
        mocker.patch.object(p, "get_kafka_redis_offset", return_value="123")

        def record(operation):
            operations.append((operation, threading.get_ident()))

        mocker.patch.object(handler, "KafkaConsumer", side_effect=lambda **kwargs: record("create") or consumer)
        assign = consumer.assign
        mocker.patch.object(consumer, "assign", side_effect=lambda **kwargs: (record("assign"), assign(**kwargs)))
        consumer.seek.side_effect = lambda *args: record("seek")
        consumer.poll.side_effect = lambda *args, **kwargs: record("poll") or {"events": [b"one", b"two"]}
        consumer.close.side_effect = lambda **kwargs: record("close")
        send = mocker.patch.object(p, "send_handler_task", side_effect=lambda **kwargs: record("push"))
        p.run_poller()
        assert [operation for operation, _ in operations] == ["create", "assign", "seek", "poll"] + [
            "push"
        ] * expected_calls + ["close"]
        assert len({thread_id for _, thread_id in operations}) == 1
        assert operations[0][1] != threading.get_ident()
        consumer.seek.assert_called_once_with(TopicPartition("events", 0), 123)
        consumer.commit.assert_not_called()
        consumer.close.assert_called_once_with(autocommit=False)
        assert send.call_count == expected_calls

    @pytest.mark.parametrize("phase", ["create", "assign", "poll", "close"])
    def test_blocked_lifecycle_is_isolated_and_shutdown_is_bounded(self, mocker, phase):
        p = AlertHandler(mock.Mock())
        p.run_once = False
        p.MAX_POLLER_THREAD = 2
        p.THREAD_JOIN_TIMEOUT = 0.03
        entered, release, healthy_progress = threading.Event(), threading.Event(), threading.Event()
        slow, healthy = FakeKafkaConsumer(), FakeKafkaConsumer()
        healthy_count = [0]

        def block():
            entered.set()
            release.wait(3)

        def healthy_poll(*args, **kwargs):
            p._stop_event.wait(0.005)
            return {"events": [b"healthy"]}

        def healthy_send(event_kwargs):
            if event_kwargs["bootstrap_server"] != "healthy.example:9092":
                return
            healthy_count[0] += 1
            if healthy_count[0] >= 3:
                healthy_progress.set()

        healthy.poll.side_effect = healthy_poll
        slow.poll.side_effect = lambda *args, **kwargs: block() if phase == "poll" else p._stop_event.wait(0.005) or {}
        if phase == "assign":
            mocker.patch.object(slow, "assign", side_effect=lambda **kwargs: block())
        if phase == "close":
            slow.close.side_effect = lambda **kwargs: block()

        def create(bootstrap_servers, **kwargs):
            if bootstrap_servers == "slow.example:9092":
                if phase == "create":
                    block()
                return slow
            return healthy

        factory = mocker.patch.object(handler, "KafkaConsumer", side_effect=create)
        mocker.patch.object(p, "send_handler_task", side_effect=healthy_send)
        set_assignment(p, "slow.example:9092", "healthy.example:9092")
        try:
            p.run_consumer_manager()
            assert healthy_progress.wait(1), "慢集群不能阻断健康集群持续分发"
            set_assignment(p, "healthy.example:9092")
            p.run_consumer_manager()
            assert entered.wait(1)
            # 已撤销但尚未退出的 owner 必须保留；重新加入不能创建第二个实例。
            set_assignment(p, "slow.example:9092", "healthy.example:9092")
            p.run_consumer_manager()
            assert factory.call_count == 2
            set_assignment(p, "healthy.example:9092", "third.example:9092")
            p.run_consumer_manager()
            assert factory.call_count == 2
            assert len(p.consumer_workers) == 2
            start = time.monotonic()
            p._stop()
            p.join_threads([worker.thread for worker in p.consumer_workers.values()])
            assert time.monotonic() - start < 0.3
            assert p.consumer_workers["slow.example:9092"].thread.is_alive()
        finally:
            p._stop()
            release.set()
            for worker in p.consumer_workers.values():
                worker.thread.join(timeout=1)
        slow.commit.assert_not_called()
        healthy.commit.assert_not_called()

    def test_real_coordinator_retry_does_not_starve_healthy_cluster(self, mocker):
        p = AlertHandler(mock.Mock())
        p.run_once = False
        entered, release, healthy_progress = threading.Event(), threading.Event(), threading.Event()
        healthy = FakeKafkaConsumer()
        healthy_count = [0]

        def healthy_poll(*args, **kwargs):
            time.sleep(0.005)
            return {"events": [b"healthy"]}

        def healthy_send(event_kwargs):
            if event_kwargs["bootstrap_server"] != "healthy.example:9092":
                return
            healthy_count[0] += 1
            if healthy_count[0] >= 3:
                healthy_progress.set()

        healthy.poll.side_effect = healthy_poll

        def create(bootstrap_servers, **kwargs):
            if bootstrap_servers == "healthy.example:9092":
                return healthy
            # 使用实际 poll/coordinator，只在传输边界注入可重试的 broker 错误。
            consumer = RealKafkaConsumer(
                bootstrap_servers=[], api_version=(0, 10, 2), group_id="test", retry_backoff_ms=10
            )
            # 不访问网络；跳过无节点的 bootstrap 退避。
            consumer._client._bootstrap = lambda: False

            def lookup_until_released():
                entered.set()
                if release.is_set():
                    raise RuntimeError("end test coordinator retry")
                return Future().failure(GroupCoordinatorNotAvailableError())

            consumer._coordinator.lookup_coordinator = lookup_until_released
            return consumer

        mocker.patch.object(handler, "KafkaConsumer", side_effect=create)
        mocker.patch.object(p, "send_handler_task", side_effect=healthy_send)
        set_assignment(p, "slow.example:9092", "healthy.example:9092")
        controller = threading.Thread(target=p.run_poller, daemon=True)
        controller.start()
        try:
            assert entered.wait(1)
            assert healthy_progress.wait(1), "实际 poll 的 coordinator 重试不能饿死健康集群"
            time.sleep(0.55)
            assert controller.is_alive()
        finally:
            p._stop()
            release.set()
            controller.join(timeout=2)
        assert not controller.is_alive()

    def test_assignment_snapshot_is_used_for_inflight_batch(self, mocker):
        p = AlertHandler(mock.Mock())
        p.run_once = False
        entered, release, dispatched = threading.Event(), threading.Event(), threading.Event()
        consumer = FakeKafkaConsumer()
        mocker.patch.object(handler, "KafkaConsumer", return_value=consumer)

        def poll(*args, **kwargs):
            entered.set()
            release.wait(2)
            return {"events": [b"event"]}

        consumer.poll.side_effect = poll

        def send(event_kwargs):
            assert event_kwargs["topic_data_id"] == {"kafka.example:9092|events": 1}
            dispatched.set()
            p._stop()

        mocker.patch.object(p, "send_handler_task", side_effect=send)
        set_assignment(p, "kafka.example:9092", data_id=1)
        try:
            p.run_consumer_manager()
            assert entered.wait(1)
            set_assignment(p, "kafka.example:9092", data_id=2)
            p.run_consumer_manager()
            release.set()
            assert dispatched.wait(1)
        finally:
            p._stop()
            release.set()
            p.join_threads([worker.thread for worker in p.consumer_workers.values()])

    @pytest.mark.parametrize("failure", ["create", "assign", "seek", "dispatch", "close"])
    def test_failed_owner_does_not_commit_and_can_be_replaced(self, mocker, failure):
        p = AlertHandler(mock.Mock())
        consumer = FakeKafkaConsumer()
        consumer.poll.return_value = {"events": [b"event"]}
        set_assignment(p, "kafka.example:9092", data_id=1)
        mocker.patch.object(p, "get_kafka_redis_offset", return_value="123")
        factory = mocker.patch.object(handler, "KafkaConsumer", return_value=consumer)
        if failure == "create":
            factory.side_effect = RuntimeError("unavailable")
        elif failure == "dispatch":
            mocker.patch.object(p, "send_handler_task", side_effect=RuntimeError("unavailable"))
        else:
            mocker.patch.object(consumer, failure, side_effect=RuntimeError("unavailable"))
        p.run_poller()
        consumer.commit.assert_not_called()
        if failure != "create":
            consumer.close.assert_called_once_with(autocommit=False)
        first = p.consumer_workers["kafka.example:9092"]
        assert not first.thread.is_alive()
        factory.side_effect = None
        factory.return_value = FakeKafkaConsumer()
        p.run_poller()
        assert p.consumer_workers["kafka.example:9092"] is not first

    @pytest.mark.parametrize("failure, interval", [(False, 15), (True, 30)])
    def test_refresh_waits_after_completion(self, mocker, failure, interval):
        p = AlertHandler(mock.Mock())
        p.run_once = False
        operations = []

        def refresh():
            operations.append("refresh completed")
            if failure:
                raise RuntimeError("unavailable")

        def wait(seconds):
            operations.append(seconds)
            p._stop()

        mocker.patch.object(p, "run_consumer_manager", side_effect=refresh)
        mocker.patch.object(p._stop_event, "wait", side_effect=wait)
        p.run_poller()
        assert operations == ["refresh completed", interval]

    def test_partition_update_is_applied_by_existing_owner(self, mocker):
        p = AlertHandler(mock.Mock())
        p.run_once = False
        consumer = FakeKafkaConsumer()
        entered, release, updated = threading.Event(), threading.Event(), threading.Event()
        assign_threads = []
        assign = consumer.assign

        def assign_partitions(**kwargs):
            assign_threads.append(threading.get_ident())
            assign(**kwargs)

        def poll(*args, **kwargs):
            if TopicPartition("updated", 1) in consumer.partitions:
                updated.set()
                p._stop()
            else:
                entered.set()
                release.wait(2)
            return {}

        factory = mocker.patch.object(handler, "KafkaConsumer", return_value=consumer)
        mocker.patch.object(consumer, "assign", side_effect=assign_partitions)
        consumer.poll.side_effect = poll
        set_assignment(p, "kafka.example:9092")
        try:
            p.run_consumer_manager()
            assert entered.wait(1)
            p.redis_client.hset(
                p.data_id_cache_key,
                p.ip,
                json.dumps(
                    [{"bootstrap_server": "kafka.example:9092", "topic": "updated", "partition": 1, "data_id": 0}]
                ),
            )
            p.run_consumer_manager()
            release.set()
            assert updated.wait(1)
        finally:
            p._stop()
            release.set()
            p.join_threads([worker.thread for worker in p.consumer_workers.values()])
        assert factory.call_count == 1
        assert len(assign_threads) == 2
        assert len(set(assign_threads)) == 1

    def test_retired_owner_releases_capacity_only_after_exit(self, mocker):
        p = AlertHandler(mock.Mock())
        p.MAX_POLLER_THREAD = 1
        factory = mocker.patch.object(handler, "KafkaConsumerWorker")
        old = factory.return_value
        old.thread.is_alive.return_value = True
        set_assignment(p, "old.example:9092")
        p.run_consumer_manager()
        set_assignment(p, "new.example:9092")
        p.run_consumer_manager()
        old.stop_event.set.assert_called_once()
        assert factory.call_count == 1
        old.thread.is_alive.return_value = False
        factory.return_value = mock.Mock()
        p.run_consumer_manager()
        assert factory.call_count == 2
        assert list(p.consumer_workers) == ["new.example:9092"]

    def test_all_current_assignments_fit_worker_budget(self, mocker):
        p = AlertHandler(mock.Mock())
        factory = mocker.patch.object(handler, "KafkaConsumerWorker", side_effect=lambda *args: mock.Mock())
        servers = [f"kafka-{i}.example:9092" for i in range(p.MAX_POLLER_THREAD + 1)]
        set_assignment(p, *servers)
        p.run_consumer_manager()
        assert factory.call_count == len(servers)
        assert set(p.consumer_workers) == set(servers)

    def test_stop_before_initialization_does_not_create_consumer(self, mocker):
        p = AlertHandler(mock.Mock())
        factory = mocker.patch.object(handler, "KafkaConsumer")
        set_assignment(p, "kafka.example:9092")
        worker = handler.KafkaConsumerWorker(p, "kafka.example:9092", (frozenset(), {}))
        p._stop()
        worker.run()
        p.run_consumer_manager()
        factory.assert_not_called()
        assert p.consumer_workers == {}

    def test_all_threads_share_shutdown_budget(self, mocker):
        p = AlertHandler(mock.Mock())
        clock = [0]
        mocker.patch.object(handler.time, "monotonic", side_effect=lambda: clock[0])

        def join(timeout):
            clock[0] += timeout

        threads = [mock.Mock(), mock.Mock(), mock.Mock()]
        for thread in threads:
            thread.join.side_effect = join
            thread.is_alive.return_value = True
        p.join_threads(threads)
        assert clock[0] == p.THREAD_JOIN_TIMEOUT
        threads[0].join.assert_called_once_with(timeout=5)
        threads[1].join.assert_called_once_with(timeout=0)
        threads[2].join.assert_called_once_with(timeout=0)

    @pytest.mark.django_db(transaction=True)
    def test_run_alert_builder_once(self, mocker):
        now = int(time.time())
        records = []
        ConsumerRecord = namedtuple("ConsumerRecord", ["topic", "value"])
        for event_id, timestamp, device in [("2", now, "cpu0"), ("1", now - 500, "cpu1")]:
            event = {
                "bk_biz_id": 2,
                "event_id": event_id,
                "plugin_id": "fta-test",
                "alert_name": "CPU usage high",
                "time": timestamp,
                "tags": [{"key": "device", "value": device}],
                "severity": 1,
                "target": "127.0.0.1",
                "dedupe_keys": ["alert_name", "target"],
                "strategy_id": 100,
            }
            records.append(ConsumerRecord("events", json.dumps(event)))
        for doc in [AlertDocument, EventDocument]:
            ilm = doc.get_lifecycle_manager()
            ilm.es_client.indices.delete(index=doc.Index.name)
            ilm.es_client.indices.create(index=doc.Index.name)
        periodic = mocker.patch("alarm_backends.service.alert.builder.processor.send_check_task", return_value=True)
        signal = mocker.patch(
            "alarm_backends.service.alert.builder.processor.AlertBuilder.send_signal", return_value=True
        )
        p = AlertHandler(mock.Mock())
        set_assignment(p, "kafka.example:9092", data_id=1)
        consumer = FakeKafkaConsumer()
        consumer.poll.return_value = {"events": records}
        mocker.patch.object(handler, "KafkaConsumer", return_value=consumer)
        p.run_poller()
        periodic.assert_called_once()
        assert signal.call_count == 1
        event = EventDocument.get_by_event_id("1")
        assert event.target == "127.0.0.1"
        assert event.dedupe_md5 == "936eafa6dac0d420db79fcdf3bae8f15"
        alert = AlertDocument.get_by_dedupe_md5(dedupe_md5=event.dedupe_md5)
        assert alert.begin_time == now - 500
        assert alert.latest_time == now
        assert alert.severity == 1
        assert alert.status == "ABNORMAL"
        assert AlertUIDManager.parse_sequence(alert.id) == 1
