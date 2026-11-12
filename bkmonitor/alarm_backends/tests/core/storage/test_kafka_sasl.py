"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest import mock

import pytest
from confluent_kafka import KafkaException
from django.db import OperationalError
from kafka import TopicPartition
from kafka.consumer.fetcher import ConsumerRecord
from kafka.errors import KafkaTimeoutError

from alarm_backends.core.storage import kafka_sasl
from alarm_backends.core.storage.kafka_sasl import SaslKafkaConsumer, get_kafka_sasl_config
from alarm_backends.service.alert import handler
from metadata.models import ClusterInfo

SASL_CONFIG = {
    "security.protocol": "SASL_PLAINTEXT",
    "sasl.mechanisms": "SCRAM-SHA-512",
    "sasl.username": "user",
    "sasl.password": "pass",
}


@pytest.fixture(autouse=True)
def clear_sasl_config_cache():
    kafka_sasl._sasl_config_cache.clear()
    yield
    kafka_sasl._sasl_config_cache.clear()


def create_kafka_cluster(domain_name, **kwargs):
    return ClusterInfo.objects.create(
        cluster_name=domain_name,
        cluster_type=ClusterInfo.TYPE_KAFKA,
        domain_name=domain_name,
        port=9092,
        description="",
        is_default_cluster=False,
        **kwargs,
    )


@pytest.mark.django_db
class TestGetKafkaSaslConfig:
    def test_auth_cluster_returns_registered_mechanism(self):
        create_kafka_cluster(
            "auth.kafka.example",
            is_auth=True,
            username="user",
            password="pass",
            sasl_mechanisms="SCRAM-SHA-512",
            security_protocol="SASL_PLAINTEXT",
        )
        assert get_kafka_sasl_config("auth.kafka.example:9092") == SASL_CONFIG

    def test_auth_cluster_without_mechanism_uses_metadata_default(self):
        create_kafka_cluster("default.kafka.example", is_auth=True, username="user", password="pass")
        config = get_kafka_sasl_config("default.kafka.example:9092")
        assert config["sasl.mechanisms"] == kafka_sasl.metadata_config.KAFKA_SASL_MECHANISM
        assert config["security.protocol"] == kafka_sasl.metadata_config.KAFKA_SASL_PROTOCOL

    @pytest.mark.parametrize(
        "bootstrap_server, cluster_kwargs",
        [
            ("plain.kafka.example:9092", {"is_auth": False, "username": "user", "password": "pass"}),
            ("nocred.kafka.example:9092", {"is_auth": True}),
            ("unknown.kafka.example:9092", None),
            ("plain.kafka.example:9093", {"is_auth": True, "username": "user", "password": "pass"}),
            (["plain.kafka.example:9092"], None),
            ("plain.kafka.example", None),
        ],
    )
    def test_non_auth_bootstrap_returns_none(self, bootstrap_server, cluster_kwargs):
        if cluster_kwargs is not None:
            create_kafka_cluster("plain.kafka.example", **cluster_kwargs)
        assert get_kafka_sasl_config(bootstrap_server) is None

    def test_result_is_cached(self, django_assert_num_queries):
        get_kafka_sasl_config("cached.kafka.example:9092")
        with django_assert_num_queries(0):
            assert get_kafka_sasl_config("cached.kafka.example:9092") is None

    def test_duplicate_clusters_with_same_credentials(self):
        for name in ("dup-a", "dup-b"):
            ClusterInfo.objects.create(
                cluster_name=name,
                cluster_type=ClusterInfo.TYPE_KAFKA,
                domain_name="dup.kafka.example",
                port=9092,
                description="",
                is_default_cluster=False,
                is_auth=True,
                username="user",
                password="pass",
                sasl_mechanisms="SCRAM-SHA-512",
                security_protocol="SASL_PLAINTEXT",
            )
        assert get_kafka_sasl_config("dup.kafka.example:9092") == SASL_CONFIG

    def test_conflicting_credentials_raise(self):
        for name, username in (("conflict-a", "user-a"), ("conflict-b", "user-b")):
            ClusterInfo.objects.create(
                cluster_name=name,
                cluster_type=ClusterInfo.TYPE_KAFKA,
                domain_name="conflict.kafka.example",
                port=9092,
                description="",
                is_default_cluster=False,
                is_auth=True,
                username=username,
                password="pass",
            )
        with pytest.raises(ValueError):
            get_kafka_sasl_config("conflict.kafka.example:9092")

    def test_database_failure_uses_expired_cache(self, mocker):
        create_kafka_cluster("stale.kafka.example", is_auth=True, username="user", password="pass")
        clock = mocker.patch.object(kafka_sasl.time, "monotonic", return_value=0)
        cached = get_kafka_sasl_config("stale.kafka.example:9092")
        clock.return_value = kafka_sasl.SASL_CONFIG_CACHE_SECONDS + 1
        mocker.patch.object(kafka_sasl, "_query_kafka_sasl_config", side_effect=OperationalError("db down"))
        assert get_kafka_sasl_config("stale.kafka.example:9092") == cached
        with pytest.raises(OperationalError):
            get_kafka_sasl_config("uncached.kafka.example:9092")

    def test_conflict_is_not_hidden_by_expired_cache(self, mocker):
        create_kafka_cluster("stale.kafka.example", is_auth=True, username="user-a", password="pass")
        clock = mocker.patch.object(kafka_sasl.time, "monotonic", return_value=0)
        get_kafka_sasl_config("stale.kafka.example:9092")
        ClusterInfo.objects.create(
            cluster_name="stale-b",
            cluster_type=ClusterInfo.TYPE_KAFKA,
            domain_name="stale.kafka.example",
            port=9092,
            description="",
            is_default_cluster=False,
            is_auth=True,
            username="user-b",
            password="pass",
        )
        clock.return_value = kafka_sasl.SASL_CONFIG_CACHE_SECONDS + 1
        with pytest.raises(ValueError):
            get_kafka_sasl_config("stale.kafka.example:9092")

    def test_connection_is_released_outside_transaction(self, mocker):
        connection = mock.Mock(in_atomic_block=False)
        mocker.patch.object(kafka_sasl, "connections", {ClusterInfo.objects.db: connection})
        get_kafka_sasl_config("release.kafka.example:9092")
        connection.close_if_unusable_or_obsolete.assert_called_once()
        connection.close.assert_called_once()


class TestSaslKafkaConsumer:
    @pytest.fixture
    def confluent(self, mocker):
        return mocker.patch.object(kafka_sasl, "Consumer").return_value

    def test_config_maps_kafka_python_arguments(self, mocker):
        factory = mocker.patch.object(kafka_sasl, "Consumer")
        SaslKafkaConsumer(
            "auth.kafka.example:9092",
            SASL_CONFIG,
            group_id="bk_monitorv3.alert.builder",
            request_timeout_ms=30000,
            session_timeout_ms=10000,
            max_partition_fetch_bytes=5 * 1024 * 1024,
            api_version_auto_timeout_ms=2000,
        )
        conf = factory.call_args.args[0]
        assert conf["bootstrap.servers"] == "auth.kafka.example:9092"
        assert conf["group.id"] == "bk_monitorv3.alert.builder"
        assert conf["enable.auto.commit"] is False
        assert conf["session.timeout.ms"] == 10000
        assert conf["max.partition.fetch.bytes"] == 5 * 1024 * 1024
        assert conf["sasl.mechanisms"] == "SCRAM-SHA-512"

    def test_metadata_only_consumer_never_commits(self, confluent, mocker):
        mocker.patch.object(kafka_sasl.time, "monotonic", return_value=10**6)
        consumer = SaslKafkaConsumer("auth.kafka.example:9092", SASL_CONFIG)
        consumer.assign([TopicPartition("events", 0)])
        confluent.consume.return_value = []
        consumer.poll(500)
        consumer.close()
        confluent.commit.assert_not_called()
        confluent.close.assert_called_once()

    def test_partitions_for_topic(self, confluent):
        topics = {
            "events": mock.Mock(error=None, partitions={0: None, 1: None}),
            "missing": mock.Mock(error="UNKNOWN_TOPIC_OR_PART", partitions={}),
        }
        confluent.list_topics.return_value = mock.Mock(topics=topics)
        consumer = SaslKafkaConsumer("auth.kafka.example:9092", SASL_CONFIG)
        assert consumer.partitions_for_topic("events") == {0, 1}
        assert consumer.partitions_for_topic("missing") is None
        assert consumer.partitions_for_topic("absent") is None
        # 只拉一次全量 metadata，且从不按 topic 查询
        confluent.list_topics.assert_called_once_with(timeout=30)

    @staticmethod
    def _offsets(call):
        return {(tp.topic, tp.partition): tp.offset for tp in call.args[0]}

    def test_assign_only_changes_added_and_removed_partitions(self, confluent):
        confluent.consume.return_value = []
        consumer = SaslKafkaConsumer("auth.kafka.example:9092", SASL_CONFIG, group_id="group")
        consumer.assign([TopicPartition("events", 0), TopicPartition("events", 1)])
        consumer.poll(500)
        confluent.reset_mock()
        consumer.assign([TopicPartition("events", 1), TopicPartition("events", 2)])
        assert consumer.assignment() == {TopicPartition("events", 1), TopicPartition("events", 2)}
        confluent.assign.assert_not_called()
        assert set(self._offsets(confluent.incremental_unassign.call_args)) == {("events", 0)}
        assert set(self._offsets(confluent.incremental_assign.call_args)) == {("events", 2)}
        # 分区未变化时不触碰 assignment
        confluent.reset_mock()
        consumer.assign([TopicPartition("events", 2), TopicPartition("events", 1)])
        confluent.incremental_assign.assert_not_called()
        confluent.incremental_unassign.assert_not_called()

    def test_seek_before_fetching_reassigns_only_that_partition(self, confluent):
        consumer = SaslKafkaConsumer("auth.kafka.example:9092", SASL_CONFIG)
        consumer.assign([TopicPartition("events", 0), TopicPartition("events", 1)])
        confluent.reset_mock()
        consumer.seek(TopicPartition("events", 0), 123)
        assert self._offsets(confluent.incremental_unassign.call_args) == {("events", 0): mock.ANY}
        assert self._offsets(confluent.incremental_assign.call_args) == {("events", 0): 123}
        confluent.seek.assert_not_called()
        with pytest.raises(ValueError):
            consumer.seek(TopicPartition("other", 0), 1)

    def test_seek_after_fetching_uses_consumer_seek(self, confluent):
        confluent.consume.return_value = []
        consumer = SaslKafkaConsumer("auth.kafka.example:9092", SASL_CONFIG)
        consumer.assign([TopicPartition("events", 0), TopicPartition("events", 1)])
        consumer.poll(500)
        # 拉取开始后新增的分区仍未开始拉取
        consumer.assign([TopicPartition("events", 0), TopicPartition("events", 1), TopicPartition("events", 2)])
        confluent.reset_mock()
        consumer.seek(TopicPartition("events", 1), 50)
        sought = confluent.seek.call_args.args[0]
        assert (sought.topic, sought.partition, sought.offset) == ("events", 1, 50)
        confluent.incremental_assign.assert_not_called()
        consumer.seek(TopicPartition("events", 2), 7)
        confluent.seek.assert_called_once()
        assert self._offsets(confluent.incremental_assign.call_args) == {("events", 2): 7}

    def test_poll_returns_kafka_python_records_and_skips_errors(self, confluent):
        message = mock.Mock()
        message.error.return_value = None
        message.topic.return_value = "events"
        message.partition.return_value = 1
        message.offset.return_value = 7
        message.timestamp.return_value = (1, 1700000000000)
        message.key.return_value = None
        message.value.return_value = b'{"a": 1}'
        message.headers.return_value = None
        broken = mock.Mock()
        broken.error.return_value = "broker error"
        confluent.consume.return_value = [message, broken]
        consumer = SaslKafkaConsumer("auth.kafka.example:9092", SASL_CONFIG, group_id="group")
        records = consumer.poll(500, max_records=5000)
        confluent.consume.assert_called_once_with(num_messages=5000, timeout=0.5)
        [record] = records[TopicPartition("events", 1)]
        assert isinstance(record, ConsumerRecord)
        assert (record.topic, record.partition, record.offset, record.value) == ("events", 1, 7, b'{"a": 1}')
        assert (record.timestamp, record.timestamp_type) == (1700000000000, 0)

    def test_repeated_consume_error_is_rate_limited(self, confluent, mocker):
        warning = mocker.patch.object(kafka_sasl.logger, "warning")
        broken = mock.Mock()
        broken.error.return_value = "UNKNOWN_TOPIC_OR_PART"
        confluent.consume.return_value = [broken]
        consumer = SaslKafkaConsumer("auth.kafka.example:9092", SASL_CONFIG, group_id="group")
        consumer.poll(500)
        consumer.poll(500)
        warning.assert_called_once()

    def test_poll_commits_asynchronously_at_interval(self, confluent, mocker):
        clock = mocker.patch.object(kafka_sasl.time, "monotonic", return_value=0)
        confluent.consume.return_value = []
        consumer = SaslKafkaConsumer("auth.kafka.example:9092", SASL_CONFIG, group_id="group")
        consumer.assign([TopicPartition("events", 0)])
        consumer.poll(500)
        confluent.commit.assert_not_called()
        clock.return_value = kafka_sasl.AUTO_COMMIT_INTERVAL_SECONDS
        confluent.commit.side_effect = KafkaException("no offset")
        consumer.poll(500)
        confluent.commit.assert_called_once_with(asynchronous=True)

    @pytest.mark.parametrize("autocommit, commits", [(False, 0), (True, 1)])
    def test_close_respects_autocommit(self, confluent, autocommit, commits):
        consumer = SaslKafkaConsumer("auth.kafka.example:9092", SASL_CONFIG, group_id="group")
        consumer.assign([TopicPartition("events", 0)])
        consumer.close(autocommit=autocommit)
        assert confluent.commit.call_count == commits
        confluent.close.assert_called_once()

    def test_offsets_for_healthz(self, confluent):
        confluent.get_watermark_offsets.return_value = (3, 10)
        confluent.committed.side_effect = [
            [mock.Mock(offset=8, error=None)],
            [mock.Mock(offset=-1001, error=None)],
            [mock.Mock(offset=-1001, error="GROUP_AUTHORIZATION_FAILED")],
        ]
        consumer = SaslKafkaConsumer("auth.kafka.example:9092", SASL_CONFIG, group_id="group")
        tp = TopicPartition("events", 0)
        assert consumer.end_offsets([tp]) == {tp: 10}
        assert consumer.committed(tp) == 8
        assert consumer.committed(tp) is None
        with pytest.raises(KafkaException):
            consumer.committed(tp)

    def test_end_offsets_share_one_timeout(self, confluent, mocker):
        clock = mocker.patch.object(kafka_sasl.time, "monotonic", return_value=0)
        timeouts = []

        def watermark(tp, timeout):
            timeouts.append(timeout)
            clock.return_value += 20
            return (0, 1)

        confluent.get_watermark_offsets.side_effect = watermark
        consumer = SaslKafkaConsumer("auth.kafka.example:9092", SASL_CONFIG, request_timeout_ms=30000)
        with pytest.raises(KafkaTimeoutError):
            consumer.end_offsets([TopicPartition("events", partition) for partition in range(3)])
        assert timeouts == [30, 10]

    def test_end_offsets_timeout_returning_none(self, confluent):
        confluent.get_watermark_offsets.return_value = None
        consumer = SaslKafkaConsumer("auth.kafka.example:9092", SASL_CONFIG)
        with pytest.raises(KafkaTimeoutError):
            consumer.end_offsets([TopicPartition("events", 0)])


@pytest.fixture
def story_base(db):
    # 导入 story 包会注册全部健康检查并访问数据库，只能在用例内导入
    from alarm_backends.management.story import base

    return base


class TestConsumerFactories:
    def test_alert_poller_uses_sasl_consumer_for_auth_cluster(self, mocker):
        mocker.patch.object(handler, "get_kafka_sasl_config", return_value=SASL_CONFIG)
        sasl_consumer = mocker.patch.object(handler, "SaslKafkaConsumer")
        kafka_consumer = mocker.patch.object(handler, "KafkaConsumer")
        handler.create_kafka_consumer("auth.kafka.example:9092", group_id="group")
        sasl_consumer.assert_called_once_with("auth.kafka.example:9092", SASL_CONFIG, group_id="group")
        kafka_consumer.assert_not_called()

    def test_alert_poller_keeps_kafka_python_for_plain_cluster(self, mocker):
        mocker.patch.object(handler, "get_kafka_sasl_config", return_value=None)
        sasl_consumer = mocker.patch.object(handler, "SaslKafkaConsumer")
        kafka_consumer = mocker.patch.object(handler, "KafkaConsumer")
        handler.create_kafka_consumer("plain.kafka.example:9092", group_id="group")
        kafka_consumer.assert_called_once_with(bootstrap_servers="plain.kafka.example:9092", group_id="group")
        sasl_consumer.assert_not_called()

    def test_healthz_uses_sasl_consumer_for_auth_cluster(self, mocker, story_base):
        mocker.patch.object(story_base, "get_kafka_sasl_config", return_value=SASL_CONFIG)
        sasl_consumer = mocker.patch.object(story_base, "SaslKafkaConsumer")
        kafka_consumer = mocker.patch.object(story_base, "KafkaConsumer")
        story_base.create_healthz_kafka_consumer(bootstrap_servers="auth.kafka.example:9092", group_id="group")
        sasl_consumer.assert_called_once_with(
            "auth.kafka.example:9092",
            SASL_CONFIG,
            group_id="group",
            session_timeout_ms=story_base.HEALTHZ_KAFKA_SESSION_TIMEOUT_MS,
            request_timeout_ms=story_base.HEALTHZ_KAFKA_SESSION_TIMEOUT_MS + story_base.KAFKA_REQUEST_TIMEOUT_BUFFER_MS,
            api_version_auto_timeout_ms=story_base.HEALTHZ_KAFKA_TIMEOUT_MS,
        )
        kafka_consumer.assert_not_called()

    def test_healthz_keeps_kafka_python_for_topic_subscription(self, mocker, story_base):
        lookup = mocker.patch.object(story_base, "get_kafka_sasl_config", return_value=SASL_CONFIG)
        kafka_consumer = mocker.patch.object(story_base, "KafkaConsumer")
        story_base.create_healthz_kafka_consumer("events", bootstrap_servers="auth.kafka.example:9092")
        lookup.assert_not_called()
        kafka_consumer.assert_called_once()
