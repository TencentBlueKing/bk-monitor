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
import time
from collections import namedtuple

from unittest import mock
import pytest
from redis.exceptions import TimeoutError as RedisTimeoutError

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
        super().__init__()
        self.topics = set()
        self.subscribe_call_count = 0
        self.subscription_call_count = 0

    def subscription(self):
        self.subscription_call_count += 1
        return self.topics

    def subscribe(self, topics):
        self.subscribe_call_count += 1
        self.topics = set(topics)


def _patch_leader_env(p, mocker, strategies, **kafka_consumer_kwargs):
    """为 run_leader 用例装配公共 mock:当选 leader + 集群匹配 + 单 host + 策略 + 结果表(同一 bootstrap_server)。

    KafkaConsumer 的行为由 kafka_consumer_kwargs 指定(return_value 或 side_effect)。
    """
    p.ip = "127.0.0.1"
    p.cache.delete("real-time-handler-leader")  # 确保本进程当选 leader
    cluster = mock.MagicMock()
    cluster.name = "default"
    cluster.match.return_value = True
    mocker.patch("alarm_backends.service.access.data.processor.get_cluster", return_value=cluster)
    mocker.patch.object(AccessRealTimeDataProcess, "get_all_hosts", return_value=["127.0.0.1"])
    mocker.patch(
        "alarm_backends.service.access.data.processor.StrategyCacheManager.get_real_time_data_strategy_ids",
        return_value=strategies,
    )
    mocker.patch(
        "alarm_backends.service.access.data.processor.ResultTableCacheManager.get_result_table_by_id",
        return_value={
            "storage_info": {
                "cluster_config": {"domain_name": "kfk", "port": 9092},
                "storage_config": {"topic": "topic1"},
            },
            "fields": [],
        },
    )
    mocker.patch("alarm_backends.service.access.data.processor.KafkaConsumer", **kafka_consumer_kwargs)


class TestAccessDataProcess:
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

    def test_leader_closes_discovery_consumers(self, mock_time, mocker):
        # run_leader 发现阶段创建的 KafkaConsumer 必须被显式 close(原 map() 惰性从不执行 -> 资源累积)
        p = AccessRealTimeDataProcess(mock.MagicMock())
        fake_consumer = mock.MagicMock()
        fake_consumer.partitions_for_topic.return_value = {0}
        _patch_leader_env(p, mocker, {"rt1": {2: [1]}}, return_value=fake_consumer)

        p.run_leader(once=True)

        fake_consumer.close.assert_called_once()

    def test_leader_closes_consumer_when_topics_probe_fails(self, mock_time, mocker):
        # 缺口回归: consumer 创建成功但 topics() 探测抛 NoBrokersAvailable, 仍须被 close(不漏关)
        from kafka.errors import NoBrokersAvailable

        p = AccessRealTimeDataProcess(mock.MagicMock())
        bad_consumer = mock.MagicMock()
        bad_consumer.topics.side_effect = NoBrokersAvailable()
        _patch_leader_env(p, mocker, {"rt1": {2: [1]}}, return_value=bad_consumer)

        p.run_leader(once=True)

        bad_consumer.close.assert_called_once()

    def test_leader_does_not_reuse_consumer_after_probe_failure(self, mock_time, mocker):
        # 同一轮内同 bootstrap_server 的两个 rt: 探测失败的 consumer 不得被后续 rt 复用,
        # 应各自新建并各自 close(否则会跳过探测, partitions_for_topic 产生坏分配/异常)
        from kafka.errors import NoBrokersAvailable

        p = AccessRealTimeDataProcess(mock.MagicMock())
        created = []

        def make_consumer(*args, **kwargs):
            c = mock.MagicMock()
            c.topics.side_effect = NoBrokersAvailable()
            created.append(c)
            return c

        _patch_leader_env(p, mocker, {"rt1": {2: [1]}, "rt2": {2: [2]}}, side_effect=make_consumer)

        p.run_leader(once=True)

        assert len(created) == 2  # 失败 consumer 未被复用 -> 两个 rt 各自新建
        for c in created:
            c.close.assert_called_once()


class TestGuardDaemon:
    """守护线程安全网: redis 故障(连接加固后会抛 TimeoutError/ConnectionError)不得杀死线程, 应重启循环。"""

    def test_restarts_until_func_returns(self, mock_time):
        # 崩溃 2 次后第 3 次正常返回(模拟收到停止信号后 func 自行结束), 期间循环被重启而非线程死亡
        service = mock.MagicMock()
        p = AccessRealTimeDataProcess(service)
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise RedisTimeoutError("redis read timeout")

        p._guard_daemon(flaky, wait=0)
        assert calls["n"] == 3

    def test_returns_immediately_when_already_stopped(self, mock_time):
        service = mock.MagicMock()
        p = AccessRealTimeDataProcess(service)
        p._stop_signal = True
        called = []

        p._guard_daemon(lambda: called.append(1), wait=0)
        assert called == []

    def test_crash_then_stop_breaks_loop(self, mock_time):
        # 崩溃同时置停止信号 -> 不应无限重启, 下一轮检查到 _stop_signal 即退出
        service = mock.MagicMock()
        p = AccessRealTimeDataProcess(service)
        calls = {"n": 0}

        def crash_then_stop():
            calls["n"] += 1
            p._stop_signal = True
            raise RedisTimeoutError("redis read timeout")

        p._guard_daemon(crash_then_stop, wait=0)
        assert calls["n"] == 1

    def test_consumer_manager_releases_lock_on_exception(self, mock_time, mocker):
        # 持锁期间 KafkaConsumer 构造抛错, consumers_lock 必须被释放:
        # 否则 _guard_daemon 重启 run_consumer_manager 会因非可重入锁自死锁, run_poller 也被堵死。
        service = mock.MagicMock()
        p = AccessRealTimeDataProcess(service)
        p.ip = "127.0.0.1"
        p.cache.hset(p.topic_cache_key, p.ip, json.dumps({"kafka-x:9092|topic1": ""}))
        mocker.patch(
            "alarm_backends.service.access.data.processor.KafkaConsumer",
            side_effect=RuntimeError("kafka boom"),
        )

        with pytest.raises(RuntimeError):
            p.run_consumer_manager(once=True)

        acquired = p.consumers_lock.acquire(blocking=False)
        assert acquired is True  # 锁已释放, 下次进入/poller 不会被堵
        p.consumers_lock.release()

    def test_consumer_manager_closes_consumers_on_stop(self, mock_time):
        # 停机分支必须真正 close 每个 consumer(原 map() 惰性从不执行)并把 self.consumers 复位为 dict
        service = mock.MagicMock()
        p = AccessRealTimeDataProcess(service)
        p.ip = "127.0.0.1"
        c1 = FakeKafkaConsumer()
        c1.topics = {"t1"}
        c2 = FakeKafkaConsumer()
        c2.topics = {"t2"}
        p.consumers = {"kafka1.svc:9092": c1, "kafka2.svc:9092": c2}
        # topics 与现有 consumer 订阅一致 => 不进入 create/update/delete 分支, 直接走停机清理
        p.cache.hset(p.topic_cache_key, p.ip, json.dumps({"kafka1.svc:9092|t1": "", "kafka2.svc:9092|t2": ""}))
        p._stop_signal = True

        p.run_consumer_manager(once=True)

        c1.close.assert_called_once()
        c2.close.assert_called_once()
        assert p.consumers == {}  # 复位为 dict, 而非 list
