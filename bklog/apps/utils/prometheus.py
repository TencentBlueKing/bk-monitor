# -*- coding: utf-8 -*-
import copy
import os
import socket
import types

from django.conf import settings
from django_prometheus.conf import NAMESPACE
from django_prometheus.middleware import Metrics
from prometheus_client import CollectorRegistry

HOSTNAME = socket.gethostname()
STAGE = os.getenv("BKPAAS_ENVIRONMENT", "dev")


class BkLogRegistry(CollectorRegistry):
    """
    适配蓝鲸监控聚合网关的采集器
    """

    def collect(self):
        """Yields metrics from the collectors in the registry."""
        collectors = None
        ti = None
        with self._lock:
            collectors = copy.copy(self._collector_to_names)
            if self._target_info:
                ti = self._target_info_metric()
        if ti:
            yield ti
        for collector in collectors:
            for metric in collector.collect():
                yield metric

            # 由于应用部署多实例的特性，上报完成后需要清空指标数据，由上层计算去聚合，此处不做累加
            if hasattr(collector, "_lock"):
                with collector._lock:
                    collector._metrics = {}
                collector._metric_init()


REGISTRY = BkLogRegistry(auto_describe=True)


def register_metric(metric_cls, name, documentation, labelnames=(), **kwargs):
    """
    Prometheus 指标注册
    """
    labelnames = [*labelnames, "hostname", "stage", "bk_app_code"]
    metric = metric_cls(name, documentation, labelnames, namespace=NAMESPACE, registry=REGISTRY, **kwargs)

    metric._origin_labels = metric.labels

    def labels(self, *labelvalues, **labelkwargs):
        labelkwargs.update({"hostname": HOSTNAME, "stage": STAGE, "bk_app_code": settings.APP_CODE})
        return self._origin_labels(*labelvalues, **labelkwargs)

    metric.labels = types.MethodType(labels, metric)
    return metric


class BkLogMetrics(Metrics):
    def register_metric(self, metric_cls, name, documentation, labelnames=(), **kwargs):
        labelnames = [*labelnames, "hostname", "stage", "bk_app_code", "app_name", "module_name"]
        return super().register_metric(
            metric_cls, name, documentation, labelnames=labelnames, registry=REGISTRY, **kwargs
        )
