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

    def test_flush_timeout_follows_message_timeout(self):
        # flush 等待窗口随生效的 message.timeout.ms 推导(+1s 余量)，不写死，
        # 否则调大 message.timeout.ms 时 flush 会提前截断、把成功投递误判为失败
        flush_calls = []

        def factory(conf):
            producer = MagicMock()
            producer.produce.side_effect = lambda topic, value, on_delivery=None: None

            def flush(timeout=None):
                flush_calls.append(timeout)
                return 0

            producer.flush.side_effect = flush
            return producer

        # 默认 3000ms -> flush 4s
        with patch(PRODUCER_PATH, side_effect=factory):
            KafKaClient(DSN).send("hello")
        self.assertEqual(flush_calls[-1], 4)

        # 显式 10000ms -> flush 11s（不会停在 5s 截断 6-10s 的成功投递）
        dsn = {"bootstrap.servers": "localhost:9092", "topic": "t", "message.timeout.ms": 10000}
        with patch(PRODUCER_PATH, side_effect=factory):
            KafKaClient(dsn).send("hello")
        self.assertEqual(flush_calls[-1], 11)

    def test_flush_timeout_tolerates_config_value_forms(self):
        # confluent_kafka 接受 int/str/float 形式的配置值；推导需兼容这几种，
        # 且 message.timeout.ms=0(librdkafka 语义的“无限”)退回默认，避免 flush 退化为 1s
        flush_calls = []

        def factory(conf):
            producer = MagicMock()
            producer.produce.side_effect = lambda topic, value, on_delivery=None: None
            producer.flush.side_effect = lambda timeout=None: (flush_calls.append(timeout), 0)[1]
            return producer

        cases = [
            ("8000", 9),  # 字符串
            (8000.0, 9),  # 浮点
            ("8000.0", 9),  # 浮点字符串（int("8000.0") 会抛错，需 int(float()) 兜底）
            (0, 4),  # 无限 -> 退回默认 3000ms
        ]
        for value, expected in cases:
            dsn = {"bootstrap.servers": "localhost:9092", "topic": "t", "message.timeout.ms": value}
            with patch(PRODUCER_PATH, side_effect=factory):
                KafKaClient(dsn).send("hello")
            self.assertEqual(flush_calls[-1], expected, f"value={value!r}")

    def test_respects_delivery_timeout_alias(self):
        # delivery.timeout.ms 是 message.timeout.ms 的 librdkafka 别名：
        # 调用方用别名指定时，不应再注入 message.timeout.ms 默认值（会冲突/静默覆盖），
        # 且 flush 应按别名的生效值推导
        seen_conf = {}
        flush_calls = []

        def factory(conf):
            seen_conf.clear()
            seen_conf.update(conf)
            producer = MagicMock()
            producer.produce.side_effect = lambda topic, value, on_delivery=None: None
            producer.flush.side_effect = lambda timeout=None: (flush_calls.append(timeout), 0)[1]
            return producer

        dsn = {"bootstrap.servers": "localhost:9092", "topic": "t", "delivery.timeout.ms": 10000}
        with patch(PRODUCER_PATH, side_effect=factory):
            KafKaClient(dsn).send("hello")
        self.assertNotIn("message.timeout.ms", seen_conf)  # 未注入默认值，避免与别名冲突
        self.assertEqual(seen_conf.get("delivery.timeout.ms"), 10000)  # 保留调用方设置
        self.assertEqual(flush_calls[-1], 11)  # flush 按别名值 10000 推导(+1s)
