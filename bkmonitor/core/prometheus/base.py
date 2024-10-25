# -*- coding: utf-8 -*-

import copy

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

    def clear_data(self):
        """
        由于聚合网关的特性，上报完成后需要清空指标数据
        """
        with self._lock:
            collectors = copy.copy(self._collector_to_names)
        for collector in collectors:
            if hasattr(collector, "_lock"):
                with collector._lock:
                    collector._metrics = {}
            collector._metric_init()


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
