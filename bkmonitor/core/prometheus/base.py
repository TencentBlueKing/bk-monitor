# -*- coding: utf-8 -*-

import copy
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
        由于聚合网关的特性，每次上报自上次上报以来的数据，多线程并发上报时同一份数据只会进入一个快照
        """
        with self._lock:
            collectors = copy.copy(self._collector_to_names)
        return MetricSnapshot([_take_metric(collector) for collector in collectors])


class MetricSnapshot:
    """
    一次上报取出的指标数据，可作为 registry 传给 push_to_gateway；推送成功后调用 commit，失败后调用 restore
    """

    def __init__(self, parts):
        self._parts = parts

    def collect(self):
        for part in self._parts:
            for metric in part.collect():
                if metric.samples:
                    yield metric

    def commit(self):
        for part in self._parts:
            part.commit()

    def restore(self):
        """
        把数据放回原指标，等价于本次未上报
        """
        for part in self._parts:
            part.restore()


def _take_metric(metric):
    if metric._type in ("counter", "histogram"):
        return _IncrementalPart(metric)
    if metric._type == "gauge":
        return _LatestValuePart(metric)
    return _CollectedPart(metric)


class _IncrementalPart:
    """
    聚合网关对 counter、histogram 按样本求和，上报的必须是增量：取出后清零，推送失败时加回
    """

    def __init__(self, metric):
        self.metric = metric
        self.snapshot = copy.copy(metric)
        if metric._is_parent():
            # 与原逻辑一样整体换出子指标，registry 中只留之后新建的子指标
            self.snapshot._lock = Lock()
            with metric._lock:
                self.snapshot._metrics, metric._metrics = metric._metrics, {}
            if isinstance(metric, BkIncrementalMixin):
                for labelvalues, child in self.snapshot._metrics.items():
                    child._bk_seal(metric, labelvalues)
        else:
            self.snapshot._metric_init()
            _apply(metric, lambda child: _move_values(child, self.snapshot))

    def collect(self):
        return self.snapshot.collect()

    def commit(self):
        pass

    def restore(self):
        if not self.metric._is_parent():
            _apply(self.metric, lambda child: _add_values(child, self.snapshot))
            return
        for labelvalues, snapshot_child in self.snapshot._metrics.items():
            _apply(self.metric.labels(*labelvalues), lambda child, source=snapshot_child: _add_values(child, source))


class _LatestValuePart:
    """
    Gauge 按最新值上报：推送成功后移除期间未再变化的子指标，失败时不动，随下次上报重发
    """

    def __init__(self, metric):
        self.metric = metric
        if metric._is_parent():
            with metric._lock:
                self.children = metric._metrics.copy()
            self.snapshot = copy.copy(metric)
            self.snapshot._lock = Lock()
            self.snapshot._metrics = {labelvalues: _freeze(child) for labelvalues, child in self.children.items()}
        else:
            self.snapshot = _freeze(metric)

    def collect(self):
        return self.snapshot.collect()

    def commit(self):
        if not self.metric._is_parent():
            # 与原逻辑一致，无 label 的 Gauge 上报后归零
            value, pushed = self.metric._value, self.snapshot._value.get()
            with value._lock:
                if value._value == pushed:
                    value._value = 0.0
            return
        with self.metric._lock:
            for labelvalues, child in self.children.items():
                pushed = self.snapshot._metrics[labelvalues]._value.get()
                if self.metric._metrics.get(labelvalues) is child and child._value.get() == pushed:
                    del self.metric._metrics[labelvalues]

    def restore(self):
        pass


class _CollectedPart:
    """
    其他类型与原逻辑一致：推送成功后清空
    """

    def __init__(self, metric):
        self.metric = metric
        self.metrics = list(metric.collect())

    def collect(self):
        return self.metrics

    def commit(self):
        if hasattr(self.metric, "_lock"):
            with self.metric._lock:
                self.metric._metrics = {}
        self.metric._metric_init()

    def restore(self):
        pass


def _metric_values(metric):
    if metric._type == "counter":
        return [metric._value]
    return [*metric._buckets, metric._sum]


def _take_value(value) -> float:
    # 与 inc 使用同一把锁，读取和清零之间不会有写入落空
    with value._lock:
        current, value._value = value._value, 0.0
    return current


def _move_values(source, target):
    for value, target_value in zip(_metric_values(source), _metric_values(target)):
        target_value.set(_take_value(value))


def _add_values(target, source):
    for value, source_value in zip(_metric_values(target), _metric_values(source)):
        value.inc(source_value.get())


def _apply(metric, operation):
    if isinstance(metric, BkIncrementalMixin):
        metric._bk_write(operation)
    else:
        operation(metric)


def _freeze(gauge):
    frozen = copy.copy(gauge)
    frozen._metric_init()
    frozen._value.set(gauge._value.get())
    return frozen


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


class BkIncrementalMixin:
    """
    一次写入与上报取数在子指标锁内互斥，Histogram 的 sum 与 bucket 成组转移；
    子指标被上报取走后封存，之后经已持有引用的写入转到 registry 中同 label 的子指标
    """

    def _metric_init(self):
        super()._metric_init()
        self._bk_lock = Lock()
        self._bk_parent = None
        self._bk_labelvalues = ()

    def _bk_write(self, write):
        self._raise_if_not_observable()
        with self._bk_lock:
            if self._bk_parent is None:
                write(self)
                return
        _apply(self._bk_parent.labels(*self._bk_labelvalues), write)

    def _bk_seal(self, parent, labelvalues):
        with self._bk_lock:
            self._bk_parent, self._bk_labelvalues = parent, labelvalues


# 定制化指标类，目前仅支持 Histogram, Counter, Gauge
class Histogram(LabelHandleMixin, BkIncrementalMixin, BaseHistogram):
    DEFAULT_BUCKETS = (0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 7.5, 10.0, 30.0, INF)

    def __init__(self, *args, registry=REGISTRY, buckets=DEFAULT_BUCKETS, **kwargs):
        super(Histogram, self).__init__(*args, registry=registry, buckets=buckets, **kwargs)

    def labels(self, *labelvalues, **labelkwargs) -> BaseHistogram:
        return super(Histogram, self).labels(*labelvalues, **labelkwargs)

    def observe(self, amount, exemplar=None):
        self._bk_write(lambda child: BaseHistogram.observe(child, amount, exemplar))

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


class Counter(LabelHandleMixin, BkIncrementalMixin, BaseCounter):
    def __init__(self, *args, registry=REGISTRY, **kwargs):
        super(Counter, self).__init__(*args, registry=registry, **kwargs)

    def labels(self, *labelvalues, **labelkwargs) -> BaseCounter:
        return super(Counter, self).labels(*labelvalues, **labelkwargs)

    def inc(self, amount=1, exemplar=None):
        self._bk_write(lambda child: BaseCounter.inc(child, amount, exemplar))

    def _child_samples(self):
        if not self._value.get():
            return ()
        return (("_total", {}, self._value.get(), None, None),)


class Gauge(LabelHandleMixin, BaseGauge):
    def __init__(self, *args, registry=REGISTRY, **kwargs):
        super(Gauge, self).__init__(*args, registry=registry, **kwargs)

    def labels(self, *labelvalues, **labelkwargs) -> BaseGauge:
        return super(Gauge, self).labels(*labelvalues, **labelkwargs)
