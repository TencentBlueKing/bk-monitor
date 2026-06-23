from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from alarm_backends.service.fta_action.message_queue.client import KafKaClient

PRODUCER_PATH = "alarm_backends.service.fta_action.message_queue.client.Producer"
DSN = "kafka://localhost:9092/test_topic"


def _fake_producer_factory(deliver_err=None, flush_remaining=0, captured_conf=None):
    """构造伪 confluent_kafka Producer 工厂。

    confluent_kafka 的 produce 仅异步入队，投递结果只通过 delivery 回调返回；
    这里在 flush 时回调 on_delivery 并返回仍未投递的消息数，模拟真实语义。
    """

    def factory(conf):
        if captured_conf is not None:
            captured_conf.update(conf)
        producer = MagicMock()
        state = {"cb": None}

        def produce(topic, value, on_delivery=None):
            state["cb"] = on_delivery

        def flush(timeout=None):
            if state["cb"] is not None:
                state["cb"](deliver_err, MagicMock())
            return flush_remaining

        producer.produce.side_effect = produce
        producer.flush.side_effect = flush
        return producer

    return factory


class KafkaClientSendTest(SimpleTestCase):
    def test_send_success(self):
        # 投递成功且队列清空，send 不应抛异常
        with patch(PRODUCER_PATH, side_effect=_fake_producer_factory()):
            KafKaClient(DSN).send("hello")

    def test_send_raises_on_delivery_error(self):
        # broker 不可达/认证失败经 delivery 回调返回错误，send 必须抛异常
        factory = _fake_producer_factory(deliver_err="Disconnected: broker requires SASL")
        with patch(PRODUCER_PATH, side_effect=factory):
            with self.assertRaises(RuntimeError):
                KafKaClient(DSN).send("hello")

    def test_send_raises_on_flush_timeout(self):
        # flush 超时仍有消息未投递（返回值大于 0），send 必须抛异常
        with patch(PRODUCER_PATH, side_effect=_fake_producer_factory(flush_remaining=1)):
            with self.assertRaises(RuntimeError):
                KafKaClient(DSN).send("hello")

    def test_send_propagates_produce_exception(self):
        # produce 本身同步抛错（如本地队列满 BufferError）也应向上传递为失败
        def factory(conf):
            producer = _fake_producer_factory()(conf)
            producer.produce.side_effect = BufferError("Local: Queue full")
            return producer

        with patch(PRODUCER_PATH, side_effect=factory):
            with self.assertRaises(BufferError):
                KafKaClient(DSN).send("hello")

    def test_message_timeout_default_applied(self):
        # 默认注入有界 message.timeout.ms，避免 broker 故障时无界阻塞
        captured = {}
        with patch(PRODUCER_PATH, side_effect=_fake_producer_factory(captured_conf=captured)):
            KafKaClient(DSN)
        self.assertEqual(captured.get("message.timeout.ms"), 3000)

    def test_message_timeout_respects_explicit_config(self):
        # 调用方在配置里显式指定时，尊重其取值
        captured = {}
        dsn = {"bootstrap.servers": "localhost:9092", "topic": "t", "message.timeout.ms": 10000}
        with patch(PRODUCER_PATH, side_effect=_fake_producer_factory(captured_conf=captured)):
            KafKaClient(dsn)
        self.assertEqual(captured.get("message.timeout.ms"), 10000)
