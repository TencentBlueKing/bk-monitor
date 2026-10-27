# -*- coding: utf-8 -*-

import copy
import time
from threading import Lock

from prometheus_client import CollectorRegistry
from prometheus_client import Counter as BaseCounter
from prometheus_client import Gauge as BaseGauge
from prometheus_client import Histogram as BaseHistogram
from prometheus_client import Metric
from prometheus_client.utils import INF, floatToGoString

CollectorRegistry.is_empty = lambda self: False


class BkCollectorRegistry(CollectorRegistry):
    """
    适配蓝鲸监控聚合网关的采集器
    """

    def is_empty(self):
        empty = True
        for collector in self._collector_to_names:
            if any(collector._samples()):
                return False
        return empty

    def collect(self):
        """Yields metrics from the collectors in the registry."""
        with self._lock:
            collectors = copy.copy(self._collector_to_names)
        for collector in collectors:
            for metric in collector.collect():
                samples = [s for s in metric.samples]
                if samples:
                    m = Metric(metric.name, metric.documentation, metric.type)
                    m.samples = samples
                    yield m

    def take_snapshot(self) -> "MetricSnapshot":
        """
        由于聚合网关的特性，上报的是自上次上报以来的数据：取出后重置，多线程并发上报时同一份数据只会进入一个快照
        """
        with self._lock:
            collectors = copy.copy(self._collector_to_names)
        return MetricSnapshot([(collector, _take_metric(collector)) for collector in collectors])


class MetricSnapshot:
    """
    一次上报取出的指标数据，可作为 registry 传给 push_to_gateway
    """

    def __init__(self, pairs):
        self._pairs = [(metric, snapshot) for metric, snapshot in pairs if snapshot is not None]

    def collect(self):
        for _, snapshot in self._pairs:
            for metric in snapshot.collect():
                if metric.samples:
                    yield metric

    def restore(self):
        """
        上报失败时把数据放回原指标，等价于本次未上报
        """
        for metric, snapshot in self._pairs:
            _restore_metric(metric, snapshot)


# 聚合网关对这两类指标按样本求和，上报的必须是增量
INCREMENTAL_METRIC_TYPES = ("counter", "histogram")
# 子指标连续无写入超过该时长才释放。持有子指标引用跨越释放时（如该 label 无其他写入，
# time() 计时块长于该时长且期间有两次上报），之后经该引用的写入会丢失
IDLE_CHILD_RELEASE_SECONDS = 10


def _metric_values(metric):
    if metric._type == "counter":
        return [metric._value]
    return [*metric._buckets, metric._sum]


def _take_value(value) -> float:
    # 与 inc 使用同一把锁，读取和清零之间不会有写入落空
    with value._lock:
        current, value._value = value._value, 0.0
    return current


def _take_child(metric):
    amounts = [_take_value(value) for value in _metric_values(metric)]
    if not any(amounts):
        return None
    snapshot = copy.copy(metric)
    snapshot._metric_init()
    for value, amount in zip(_metric_values(snapshot), amounts):
        value.set(amount)
    return snapshot


def _take_metric(metric):
    if metric._type not in INCREMENTAL_METRIC_TYPES:
        # Gauge 等按最新值上报：整体取出子指标，推送后不再重复上报
        snapshot = copy.copy(metric)
        if metric._is_parent():
            snapshot._lock = Lock()
            with metric._lock:
                snapshot._metrics, metric._metrics = metric._metrics, {}
        else:
            metric._metric_init()
        return snapshot

    if not metric._is_parent():
        return _take_child(metric)

    with metric._lock:
        children = metric._metrics.copy()
    snapshot = copy.copy(metric)
    snapshot._lock = Lock()
    snapshot._metrics = {}
    now = time.monotonic()
    idle_labelvalues = []
    for labelvalues, child in children.items():
        child_snapshot = _take_child(child)
        if child_snapshot is not None:
            child._bk_idle_since = None
            snapshot._metrics[labelvalues] = child_snapshot
        elif getattr(child, "_bk_idle_since", None) is None:
            child._bk_idle_since = now
        elif now - child._bk_idle_since >= IDLE_CHILD_RELEASE_SECONDS:
            idle_labelvalues.append(labelvalues)

    # 释放长时间无写入的子指标，避免 label 组合只增不减
    with metric._lock:
        for labelvalues in idle_labelvalues:
            child = children[labelvalues]
            if metric._metrics.get(labelvalues) is child and not any(v.get() for v in _metric_values(child)):
                del metric._metrics[labelvalues]
    return snapshot


def _restore_metric(metric, snapshot):
    if metric._type not in INCREMENTAL_METRIC_TYPES:
        # 期间已被重新写入的子指标保留新值
        if metric._is_parent():
            with metric._lock:
                for labelvalues, child in snapshot._metrics.items():
                    metric._metrics.setdefault(labelvalues, child)
        return

    if metric._is_parent():
        for labelvalues, child in snapshot._metrics.items():
            _restore_metric(metric.labels(*labelvalues), child)
        return

    for value, snapshot_value in zip(_metric_values(metric), _metric_values(snapshot)):
        value.inc(snapshot_value.get())


# SLI Registry
REGISTRY = BkCollectorRegistry()
# 运营数据 Registry
# Q: 为什么不考虑和 REGISTRY 合并？
# A: 由于指标拉取端需要将运营数据和 SLI 通过不同的 label:job 打到不同的 dataID 中，
# 所以需要在 Registry 侧分开。后续 dataID 合并后即可合并 Registry
OPERATION_REGISTRY = BkCollectorRegistry()


class LabelHandleMixin:
    def labels(self, *labelvalues, **labelkwargs):
        labelvalues = [type(value).__name__ if isinstance(value, Exception) else value for value in labelvalues]
        labelkwargs = {
            key: type(value).__name__ if isinstance(value, Exception) else value for key, value in labelkwargs.items()
        }
        return super(LabelHandleMixin, self).labels(*labelvalues, **labelkwargs)


# 定制化指标类，目前仅支持 Histogram, Counter, Gauge
class Histogram(LabelHandleMixin, BaseHistogram):
    DEFAULT_BUCKETS = (0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 7.5, 10.0, 30.0, INF)

    def __init__(self, *args, registry=REGISTRY, buckets=DEFAULT_BUCKETS, **kwargs):
        super(Histogram, self).__init__(*args, registry=registry, buckets=buckets, **kwargs)

    def labels(self, *labelvalues, **labelkwargs) -> BaseHistogram:
        return super(Histogram, self).labels(*labelvalues, **labelkwargs)

    def _child_samples(self):
        samples = []
        acc = 0
        tobe_sampled = False
        for i, bound in enumerate(self._upper_bounds):
            if not tobe_sampled and self._buckets[i].get():
                tobe_sampled = True
            acc += self._buckets[i].get()
            samples.append(("_bucket", {"le": floatToGoString(bound)}, acc, None, None))
        if tobe_sampled:
            samples.append(("_count", {}, acc, None, None))
            samples.append(("_sum", {}, self._sum.get(), None, None))
        return tuple(samples) if tobe_sampled else ()


class Counter(LabelHandleMixin, BaseCounter):
    def __init__(self, *args, registry=REGISTRY, **kwargs):
        super(Counter, self).__init__(*args, registry=registry, **kwargs)

    def labels(self, *labelvalues, **labelkwargs) -> BaseCounter:
        return super(Counter, self).labels(*labelvalues, **labelkwargs)

    def _child_samples(self):
        if not self._value.get():
            return ()
        return (("_total", {}, self._value.get(), None, None),)


class Gauge(LabelHandleMixin, BaseGauge):
    def __init__(self, *args, registry=REGISTRY, **kwargs):
        super(Gauge, self).__init__(*args, registry=registry, **kwargs)

    def labels(self, *labelvalues, **labelkwargs) -> BaseGauge:
        return super(Gauge, self).labels(*labelvalues, **labelkwargs)
