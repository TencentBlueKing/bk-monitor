from types import SimpleNamespace
from unittest.mock import call

import pytest

from metadata.resources.resources import KafkaTailResource


TOPIC = "0bkmonitor_15791090"
BK_DATA_ID = 1579109


@pytest.fixture
def kafka_tail_settings(settings):
    settings.KAFKA_TAIL_API_TIMEOUT_SECONDS = 1000
    settings.KAFKA_TAIL_API_RETRY_TIMES = 3
    settings.KAFKA_TAIL_API_RETRY_INTERVAL_SECONDS = 2


@pytest.fixture
def gse_config(mocker):
    mocker.patch(
        "metadata.resources.resources.api.gse.query_route",
        return_value=[
            {
                "route": [
                    {
                        "stream_to": {
                            "stream_to_id": 1072,
                            "kafka": {"topic_name": TOPIC},
                        }
                    }
                ]
            }
        ],
    )
    mocker.patch(
        "metadata.resources.resources.api.gse.query_stream_to",
        return_value=[
            {
                "kafka": {
                    "storage_address": [{"ip": "kafka.example.com", "port": 9092}],
                    "sasl_username": "",
                    "sasl_passwd": "",
                }
            }
        ],
    )


def configure_empty_partition(consumer):
    consumer.beginning_offsets.side_effect = lambda partitions: {partitions[0]: 0}
    consumer.end_offsets.side_effect = lambda partitions: {partitions[0]: 0}


def test_gse_kafka_tail_waits_for_metadata_with_configured_timeout(mocker, kafka_tail_settings, gse_config):
    consumer = mocker.MagicMock()
    consumer.partitions_for_topic.side_effect = [None, {0}]
    configure_empty_partition(consumer)
    kafka_consumer = mocker.patch("metadata.resources.resources.KafkaConsumer", return_value=consumer)
    sleep = mocker.patch("metadata.resources.resources.time.sleep")

    result = KafkaTailResource()._consume_with_gse_config_by_bk_data_id(BK_DATA_ID, size=10)

    assert result == []
    kafka_consumer.assert_called_once_with(
        TOPIC,
        bootstrap_servers=["kafka.example.com:9092"],
        request_timeout_ms=1000,
        consumer_timeout_ms=1000,
    )
    assert consumer.poll.call_args_list == [call(timeout_ms=1000), call(timeout_ms=1000)]
    assert consumer.partitions_for_topic.call_args_list == [call(TOPIC), call(TOPIC)]
    sleep.assert_called_once_with(2)
    consumer.close.assert_called_once_with()


def test_gse_kafka_tail_closes_consumer_after_metadata_retries_exhausted(mocker, kafka_tail_settings, gse_config):
    consumer = mocker.MagicMock()
    consumer.partitions_for_topic.return_value = None
    mocker.patch("metadata.resources.resources.KafkaConsumer", return_value=consumer)
    sleep = mocker.patch("metadata.resources.resources.time.sleep")

    with pytest.raises(ValueError, match="partition获取失败"):
        KafkaTailResource()._consume_with_gse_config_by_bk_data_id(BK_DATA_ID, size=10)

    assert consumer.poll.call_args_list == [call(timeout_ms=1000)] * 3
    assert consumer.partitions_for_topic.call_args_list == [call(TOPIC)] * 3
    assert sleep.call_args_list == [call(2), call(2)]
    consumer.close.assert_called_once_with()


def test_kafka_python_tail_does_not_use_sample_size_as_poll_timeout(mocker, kafka_tail_settings):
    consumer = mocker.MagicMock()
    consumer.partitions_for_topic.return_value = {0}
    configure_empty_partition(consumer)
    kafka_consumer = mocker.patch("metadata.resources.resources.KafkaConsumer", return_value=consumer)
    mocker.patch(
        "metadata.resources.resources.models.KafkaTopicInfo.objects.get",
        return_value=SimpleNamespace(topic=TOPIC),
    )

    mq_cluster = SimpleNamespace(
        domain_name="kafka.example.com",
        port=9092,
        username="",
        password="",
    )
    datasource = SimpleNamespace(
        bk_data_id=BK_DATA_ID,
        mq_config_id=1,
        mq_cluster=mq_cluster,
    )
    mq_ins = SimpleNamespace(is_ssl_verify=False)

    result = KafkaTailResource()._consume_with_kafka_python(datasource, mq_ins, size=10)

    assert result == []
    kafka_consumer.assert_called_once_with(
        TOPIC,
        bootstrap_servers="kafka.example.com:9092",
        request_timeout_ms=1000,
        consumer_timeout_ms=1000,
    )
    consumer.poll.assert_called_once_with(timeout_ms=1000)
    consumer.close.assert_called_once_with()
