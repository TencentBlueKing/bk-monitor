"""Isolated source regressions; run directly with Python, without Django services.

Only the consumer/controller classes are compiled from production source. Kafka,
Redis and parent thread context are substituted; this is not a broker integration test.
"""

import __future__
import ast
import json
import logging
import queue
import signal
import threading
import time
import unittest
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


def load_classes(relative_path, names, namespace):
    path = Path(__file__).resolve().parents[3] / relative_path
    tree = ast.parse(path.read_text())
    tree.body = [node for node in tree.body if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in names]
    exec(compile(tree, str(path), "exec", flags=__future__.annotations.compiler_flag), namespace)
    return SimpleNamespace(**namespace)


class Cache:
    def __init__(self):
        self.values = {}
        self.pipeline_calls = []

    def set(self, name, value, **kwargs):
        self.values[name] = value
        return True

    def get(self, name):
        return self.values.get(name)

    def hget(self, name, field):
        return self.values.get(name, {}).get(field)

    def delete(self, name):
        self.values.pop(name, None)

    def hmset(self, name, mapping):
        self.values.setdefault(name, {}).update(mapping)

    def expire(self, *args):
        pass

    def pipeline(self, **kwargs):
        commands = []
        pipeline = SimpleNamespace()
        for name in ("delete", "hmset", "expire"):
            setattr(pipeline, name, lambda *args, _name=name, **kw: commands.append((_name, args, kw)))

        def execute():
            self.pipeline_calls.append((kwargs, list(commands), dict(self.values)))
            for name, args, kw in commands:
                getattr(self, name)(*args, **kw)

        pipeline.execute = execute
        return pipeline


class Consumer:
    def __init__(self):
        self.subscribed = set()
        self.operations = []

    def record(self, name):
        self.operations.append((name, threading.get_ident()))

    def subscription(self):
        self.record("subscription")
        return self.subscribed

    def subscribe(self, topics):
        self.record("subscribe")
        self.subscribed = set(topics)

    def poll(self, *args, **kwargs):
        self.record("poll")
        return {"events": [b"message"]}

    def close(self, *, autocommit=True):
        assert autocommit is False
        self.record("close")


def realtime_module(cache):
    return load_classes(
        "service/access/data/processor.py",
        {"RealTimeKafkaConsumerWorker", "AccessRealTimeDataProcess"},
        {
            "BaseAccessDataProcess": object,
            "Cache": lambda *args: cache,
            "key": SimpleNamespace(REAL_TIME_HOST_TOPIC_KEY=SimpleNamespace(get_key=lambda: "routing", ttl=120)),
            "get_local_ip": lambda: "poller",
            "threading": threading,
            "time": time,
            "queue": queue,
            "signal": SimpleNamespace(SIGTERM=signal.SIGTERM, SIGINT=signal.SIGINT, signal=lambda *args: None),
            "json": json,
            "defaultdict": defaultdict,
            "settings": SimpleNamespace(APP_CODE="monitor"),
            "InheritParentThread": threading.Thread,
            "logger": logging.getLogger("isolation.real_time"),
        },
    )


class TestRealTimeIsolation(unittest.TestCase):
    def setUp(self):
        self.cache = Cache()
        self.module = realtime_module(self.cache)
        self.process = self.module.AccessRealTimeDataProcess(mock.Mock())
        self.process.THREAD_JOIN_TIMEOUT = 0.03
        self.addCleanup(self.stop)

    def stop(self):
        self.process._stop()
        for worker in list(self.process.consumer_workers.values()):
            if worker.thread.ident is not None:
                worker.thread.join(2)

    def assign(self, *servers):
        self.cache.values["routing"] = {
            "poller": json.dumps({f"{server}|events": {"strategy_ids": [], "dimensions": []} for server in servers})
        }

    def test_slow_lifecycle_does_not_block_healthy_cluster(self):
        for phase in ("create", "subscribe", "poll", "close"):
            with self.subTest(phase=phase):
                entered, release, healthy_progress, slow_polled = (threading.Event() for _ in range(4))
                slow, healthy = Consumer(), Consumer()
                healthy_count = 0

                def block(*args, **kwargs):
                    entered.set()
                    if not release.wait(2):
                        raise RuntimeError("test gate not released")
                    return {} if phase == "poll" else None

                if phase in ("subscribe", "poll", "close"):
                    setattr(slow, phase, block)
                if phase == "close":
                    slow.poll = lambda *args, **kwargs: slow_polled.set() or {}

                def poll_healthy(*args, **kwargs):
                    nonlocal healthy_count
                    healthy_count += 1
                    if healthy_count >= 3:
                        healthy_progress.set()
                    return {"events": [b"healthy"]}

                healthy.poll = poll_healthy

                def create(**kwargs):
                    if kwargs["bootstrap_servers"] == "slow":
                        if phase == "create":
                            block()
                        return slow
                    return healthy

                self.module.AccessRealTimeDataProcess.run_consumer_manager.__globals__["KafkaConsumer"] = create
                self.assign("slow", "healthy")
                self.process.run_consumer_manager()
                try:
                    if phase == "close":
                        self.assertTrue(slow_polled.wait(1))
                        self.process.consumer_workers["slow"].stop_event.set()
                    self.assertTrue(entered.wait(1))
                    self.assertTrue(healthy_progress.wait(1))
                    self.process._stop()
                    started = time.monotonic()
                    self.process.join_threads([w.thread for w in self.process.consumer_workers.values()])
                    self.assertLess(time.monotonic() - started, 0.2)
                finally:
                    release.set()
                    self.stop()
                    self.process = self.module.AccessRealTimeDataProcess(mock.Mock())
                    self.process.THREAD_JOIN_TIMEOUT = 0.03

    def test_poll_exception_retries_and_lifecycle_has_one_owner(self):
        consumer = Consumer()
        progressed = threading.Event()
        calls = 0

        def poll(*args, **kwargs):
            nonlocal calls
            consumer.record("poll")
            calls += 1
            if calls == 1:
                raise RuntimeError("transient broker error")
            progressed.set()
            return {}

        consumer.poll = poll
        worker = self.module.RealTimeKafkaConsumerWorker(self.process, "broker", {"broker|events": {}})
        wait = worker.stop_event.wait
        worker.stop_event.wait = lambda timeout: wait(min(timeout, 0.01))
        self.process.consumer_workers["broker"] = worker
        self.module.RealTimeKafkaConsumerWorker.run.__globals__["KafkaConsumer"] = lambda **kw: consumer
        worker.thread.start()
        self.assertTrue(progressed.wait(1))
        self.stop()
        self.assertEqual(consumer.operations[-1][0], "close")
        self.assertEqual(len({owner for _, owner in consumer.operations}), 1)
        self.assertNotEqual(consumer.operations[0][1], threading.get_ident())

    def test_queued_batch_keeps_routing_snapshot(self):
        old = {"broker|events": {"strategy_ids": [1], "dimensions": []}}
        new = {"broker|events": {"strategy_ids": [2], "dimensions": []}}
        consumer = Consumer()
        worker = self.module.RealTimeKafkaConsumerWorker(self.process, "broker", old, once=True)
        consumer.poll = lambda *args, **kw: setattr(worker, "topics", new) or {"events": [b"old"]}
        self.module.RealTimeKafkaConsumerWorker.run.__globals__["KafkaConsumer"] = lambda **kw: consumer
        worker.run()
        self.assertEqual(consumer.subscribed, {"events"})
        self.process.topics = new
        self.process.flat = mock.Mock(return_value=[])
        self.process.push = mock.Mock()
        self.process.run_handler(once=True)
        self.process.flat.assert_called_once_with("broker", b"old", topics=old)

    def test_retired_owner_is_not_replaced_until_it_exits(self):
        old = mock.Mock()
        old.thread.is_alive.return_value = True
        self.process.consumer_workers["broker"] = old
        self.assign()
        self.process.run_consumer_manager()
        old.stop_event.set.assert_called_once()
        self.assign("broker")
        factory = mock.Mock()
        self.module.AccessRealTimeDataProcess.run_consumer_manager.__globals__["RealTimeKafkaConsumerWorker"] = factory
        self.process.run_consumer_manager()
        factory.assert_not_called()
        old.thread.is_alive.return_value = False
        self.process.run_consumer_manager()
        factory.assert_called_once()
        self.process.consumer_workers.clear()

    def test_retired_workers_count_towards_capacity(self):
        self.process.MAX_POLLER_THREAD = 1
        old = mock.Mock()
        old.thread.is_alive.return_value = True
        self.process.consumer_workers["retired"] = old
        self.assign("new")
        factory = mock.Mock()
        self.module.AccessRealTimeDataProcess.run_consumer_manager.__globals__["RealTimeKafkaConsumerWorker"] = factory
        self.process.run_consumer_manager()
        factory.assert_not_called()
        old.stop_event.set.assert_called_once()
        old.thread.is_alive.return_value = False
        self.process.run_consumer_manager()
        factory.assert_called_once()
        self.process.consumer_workers.clear()

    def test_refresh_waits_after_completion_and_backs_off_on_failure(self):
        for failure, interval in ((False, 15), (True, 30)):
            with self.subTest(failure=failure):
                self.process._stop_signal = False
                self.process._stop_event.clear()
                calls = []

                def refresh(**kwargs):
                    calls.append("refresh_finished")
                    if failure:
                        raise RuntimeError("redis unavailable")

                def wait(timeout):
                    calls.append(timeout)
                    self.process._stop_signal = True

                self.process.run_consumer_manager = refresh
                with mock.patch.object(self.process._stop_event, "wait", side_effect=wait):
                    self.process.run_poller()
                self.assertEqual(calls, ["refresh_finished", interval])

    def test_join_threads_uses_one_total_budget(self):
        threads = [SimpleNamespace(ident=1, name=str(i), is_alive=lambda: True) for i in range(4)]
        for thread in threads:
            thread.join = lambda timeout: time.sleep(timeout)
        started = time.monotonic()
        self.process.join_threads(threads)
        self.assertLess(time.monotonic() - started, 0.08)

    def test_leader_publishes_routing_atomically(self):
        namespace = self.module.AccessRealTimeDataProcess.run_leader.__globals__
        namespace.update(
            StrategyCacheManager=SimpleNamespace(get_real_time_data_strategy_ids=lambda: {"rt": {2: [1]}}),
            ResultTableCacheManager=SimpleNamespace(
                get_result_table_by_id=lambda *args: {
                    "storage_info": {
                        "cluster_config": {"domain_name": "broker", "port": 9092},
                        "storage_config": {"topic": "events"},
                    },
                    "fields": [],
                }
            ),
            DataSourceLabel=SimpleNamespace(BK_MONITOR_COLLECTOR="monitor"),
            TargetType=SimpleNamespace(biz="biz"),
            get_cluster=lambda: SimpleNamespace(match=lambda *args: True),
            KafkaConsumer=lambda **kw: mock.Mock(partitions_for_topic=lambda topic: {0}),
            HashRing=lambda hosts: SimpleNamespace(get_node=lambda value: "poller"),
        )
        self.process.get_all_hosts = lambda: ["poller"]
        self.cache.values["routing"] = {"poller": "old"}
        self.process.run_leader(once=True)
        options, commands, before = self.cache.pipeline_calls[0]
        self.assertEqual(options, {"transaction": True})
        self.assertEqual([name for name, _, _ in commands], ["delete", "hmset", "expire"])
        self.assertEqual(before["routing"], {"poller": "old"})
        self.assertIn("broker:9092|events", json.loads(self.cache.hget("routing", "poller")))

    def test_failed_controller_unregisters_service(self):
        self.process.run_leader = lambda: self.process._stop_event.wait(2)
        self.process.run_handler = lambda: self.process._stop_event.wait(2)
        self.process.run_poller = lambda: None
        wait = self.process._stop_event.wait
        self.process._stop_event.wait = lambda timeout: wait(min(timeout, 0.01))
        with self.assertRaisesRegex(RuntimeError, "thread exited"):
            self.process.process()
        self.process.service.unregister.assert_called_once()

    def test_full_queue_does_not_prevent_bounded_shutdown(self):
        self.process.queue = queue.Queue(maxsize=1)
        self.process.queue.put(("occupied", [], {}))
        consumer = Consumer()
        polled = threading.Event()
        consumer.poll = lambda *args, **kw: polled.set() or {"events": [b"queued"]}
        self.module.AccessRealTimeDataProcess.run_consumer_manager.__globals__["KafkaConsumer"] = lambda **kw: consumer
        self.assign("broker")
        self.process.run_consumer_manager()
        self.assertTrue(polled.wait(1))
        self.process._stop()
        started = time.monotonic()
        self.process.join_threads([w.thread for w in self.process.consumer_workers.values()])
        self.assertLess(time.monotonic() - started, 0.2)


class TestEventIsolation(unittest.TestCase):
    def setUp(self):
        self.module = load_classes(
            "service/access/event/event_poller.py",
            {"EventPoller", "always_retry"},
            {
                "threading": threading,
                "time": time,
                "defaultdict": defaultdict,
                "signal": SimpleNamespace(SIGTERM=signal.SIGTERM, SIGINT=signal.SIGINT, signal=lambda *args: None),
                "socket": SimpleNamespace(gethostname=lambda: "test-poller"),
                "InheritParentThread": threading.Thread,
                "logger": logging.getLogger("isolation.event"),
            },
        )
        self.module.EventPoller.refresh = lambda self: None
        self.poller = self.module.EventPoller()
        self.poller.THREAD_JOIN_TIMEOUT = 0.03

    def test_signal_does_not_touch_consumer(self):
        consumer = mock.Mock()
        self.poller.consumer = consumer
        self.poller._stop(signal.SIGTERM, None)
        self.assertEqual(consumer.mock_calls, [])
        self.assertIs(self.poller.consumer, consumer)
        self.assertTrue(self.poller.stop_event.is_set())

    def test_kick_task_stops_without_waiting_for_redis(self):
        thread = threading.Thread(target=self.poller.kick_task, daemon=True)
        thread.start()
        self.poller._stop(signal.SIGTERM, None)
        thread.join(0.2)
        self.assertFalse(thread.is_alive())

    def test_close_disables_synchronous_commit(self):
        consumer = Consumer()
        self.poller.consumer = consumer
        self.poller.close()
        self.assertEqual([operation for operation, _ in consumer.operations], ["close"])
        self.assertIsNone(self.poller.consumer)

    def test_blocked_poll_and_close_do_not_block_shutdown(self):
        for phase in ("poll", "close"):
            with self.subTest(phase=phase):
                self.poller.should_exit = False
                self.poller.stop_event.clear()
                entered, release, closed = (threading.Event() for _ in range(3))
                owners = []
                consumer = mock.Mock()

                def poll_once():
                    self.poller.consumer = consumer
                    owners.append(threading.get_ident())
                    if phase == "poll":
                        entered.set()
                        release.wait(2)
                    else:
                        self.poller.should_exit = True
                        self.poller.stop_event.set()
                    return []

                def close(**kwargs):
                    owners.append(threading.get_ident())
                    self.assertEqual(kwargs, {"autocommit": False})
                    if phase == "close":
                        entered.set()
                        release.wait(2)
                    closed.set()

                consumer.close.side_effect = close
                self.poller.poll_once = poll_once
                controller = threading.Thread(target=self.poller.start, daemon=True)
                controller.start()
                try:
                    self.assertTrue(entered.wait(1))
                    self.poller._stop(signal.SIGTERM, None)
                    controller.join(0.2)
                    self.assertFalse(controller.is_alive())
                finally:
                    release.set()
                    self.assertTrue(closed.wait(1))
                    controller.join(1)
                self.assertEqual(len(set(owners)), 1)
                self.assertNotEqual(owners[0], threading.get_ident())


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    unittest.main()
