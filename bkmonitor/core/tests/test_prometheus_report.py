"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import re
import threading
import time
from collections import defaultdict

import pytest
from prometheus_client import generate_latest

from core.prometheus import base, metrics
from core.prometheus.base import BkCollectorRegistry, Counter, Gauge, Histogram

SAMPLE_PATTERN = re.compile(r"^(?P<name>[a-zA-Z_:][a-zA-Z0-9_:]*)(?P<labels>\{[^}]*\})? (?P<value>\S+)$")


class FakeAggGateway:
    """按聚合网关语义合并收到的数据：counter、histogram 求和，gauge 后写覆盖"""

    def __init__(self, latency: float = 0.0):
        self.latency = latency
        self.fail_calls = set()
        self.on_push = None
        self.calls = 0
        self.values = defaultdict(float)
        self._lock = threading.Lock()

    def push_to_gateway(self, gateway, job, registry, handler=None, **kwargs):
        with self._lock:
            self.calls += 1
            call = self.calls
        payload = generate_latest(registry).decode()
        if self.latency:
            time.sleep(self.latency)
        if self.on_push:
            self.on_push()
        if call in self.fail_calls:
            raise OSError("push failed")

        metric_types = {}
        with self._lock:
            for line in payload.splitlines():
                if line.startswith("# TYPE "):
                    _, _, name, metric_type = line.split(" ", 3)
                    metric_types[name] = metric_type
                    continue
                match = SAMPLE_PATTERN.match(line)
                if not match:
                    continue
                key = match.group("name") + (match.group("labels") or "")
                value = float(match.group("value"))
                family = re.sub(r"_(total|bucket|count|sum)$", "", match.group("name"))
                if metric_types.get(family) == "gauge":
                    self.values[key] = value
                else:
                    self.values[key] += value


@pytest.fixture
def gateway(monkeypatch):
    fake = FakeAggGateway()
    monkeypatch.setattr(metrics, "get_metric_agg_gateway_url", lambda *args, **kwargs: "127.0.0.1:10206")
    monkeypatch.setattr(metrics, "push_to_gateway", fake.push_to_gateway)
    return fake


class TestReportAll:
    def test_concurrent_reports_push_each_record_once(self, gateway):
        gateway.latency = 0.001
        registry = BkCollectorRegistry()
        counter = Counter("test_task_count", "", labelnames=("task",), registry=registry)
        histogram = Histogram("test_task_time", "", labelnames=("task",), registry=registry)
        thread_count, rounds = 4, 200

        def worker():
            for _ in range(rounds):
                counter.labels(task="demo").inc()
                histogram.labels(task="demo").observe(0.2)
                metrics.report_all(registry=registry)

        threads = [threading.Thread(target=worker) for _ in range(thread_count)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        metrics.report_all(registry=registry)

        expected = thread_count * rounds
        assert gateway.values['test_task_count_total{task="demo"}'] == expected
        assert gateway.values['test_task_time_count{task="demo"}'] == expected
        assert gateway.values['test_task_time_bucket{le="0.5",task="demo"}'] == expected
        assert gateway.values['test_task_time_sum{task="demo"}'] == pytest.approx(expected * 0.2)

    def test_concurrent_reports_with_failed_pushes_lose_nothing(self, gateway):
        gateway.latency = 0.001
        gateway.fail_calls = set(range(3, 1000, 3))
        registry = BkCollectorRegistry()
        counter = Counter("test_task_count", "", labelnames=("task",), registry=registry)
        thread_count, rounds = 4, 200

        def worker():
            for _ in range(rounds):
                counter.labels(task="demo").inc()
                metrics.report_all(registry=registry)

        threads = [threading.Thread(target=worker) for _ in range(thread_count)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        gateway.fail_calls = set()
        metrics.report_all(registry=registry)

        assert gateway.values['test_task_count_total{task="demo"}'] == thread_count * rounds

    def test_failed_push_keeps_data_for_next_report(self, gateway):
        registry = BkCollectorRegistry()
        counter = Counter("test_task_count", "", labelnames=("task",), registry=registry)
        counter.labels(task="demo").inc(5)

        gateway.fail_calls = {1}
        metrics.report_all(registry=registry)
        assert gateway.values['test_task_count_total{task="demo"}'] == 0

        metrics.report_all(registry=registry)
        metrics.report_all(registry=registry)
        assert gateway.values['test_task_count_total{task="demo"}'] == 5
        assert gateway.calls == 2

    def test_label_less_metrics_are_reported_once(self, gateway):
        registry = BkCollectorRegistry()
        counter = Counter("test_forbidden_count", "", registry=registry)
        histogram = Histogram("test_batch_size", "", registry=registry)
        counter.inc(3)
        histogram.observe(7)

        metrics.report_all(registry=registry)
        metrics.report_all(registry=registry)

        assert gateway.values["test_forbidden_count_total"] == 3
        assert gateway.values["test_batch_size_count"] == 1
        assert gateway.values["test_batch_size_sum"] == 7

    def test_gauge_is_cleared_after_successful_push(self, gateway):
        registry = BkCollectorRegistry()
        gauge = Gauge("test_queue_length", "", labelnames=("queue",), registry=registry)
        gauge.labels(queue="demo").set(3)

        metrics.report_all(registry=registry)
        metrics.report_all(registry=registry)

        assert gateway.values['test_queue_length{queue="demo"}'] == 3
        assert gateway.calls == 1

    def test_failed_push_keeps_newer_gauge_value(self, gateway):
        registry = BkCollectorRegistry()
        gauge = Gauge("test_queue_length", "", labelnames=("queue",), registry=registry)
        gauge.labels(queue="demo").set(3)
        gauge.labels(queue="other").set(4)

        gateway.fail_calls = {1}
        gateway.on_push = lambda: gauge.labels(queue="demo").set(9)
        metrics.report_all(registry=registry)
        gateway.on_push = None
        metrics.report_all(registry=registry)

        assert gateway.values['test_queue_length{queue="demo"}'] == 9
        assert gateway.values['test_queue_length{queue="other"}'] == 4

    def test_write_through_held_child_after_report_is_kept(self, gateway):
        registry = BkCollectorRegistry()
        counter = Counter("test_task_count", "", labelnames=("task",), registry=registry)
        held = counter.labels(task="held")
        other = counter.labels(task="other")

        held.inc()
        metrics.report_all(registry=registry)
        other.inc()
        metrics.report_all(registry=registry)
        held.inc()
        metrics.report_all(registry=registry)

        assert gateway.values['test_task_count_total{task="held"}'] == 2
        assert gateway.values['test_task_count_total{task="other"}'] == 1

    def test_idle_label_sets_are_released(self, gateway, monkeypatch):
        monkeypatch.setattr(base, "IDLE_CHILD_RELEASE_SECONDS", 0, raising=False)
        registry = BkCollectorRegistry()
        counter = Counter("test_task_count", "", labelnames=("task",), registry=registry)
        for index in range(100):
            counter.labels(task=str(index)).inc()
        metrics.report_all(registry=registry)

        for _ in range(2):
            counter.labels(task="active").inc()
            metrics.report_all(registry=registry)

        assert len(counter._metrics) <= 1
        assert gateway.values['test_task_count_total{task="0"}'] == 1
        assert gateway.values['test_task_count_total{task="active"}'] == 2
