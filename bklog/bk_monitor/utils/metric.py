# -*- coding: utf-8 -*-
from functools import wraps

from django.conf import settings

from bk_monitor.constants import TimeFilterEnum

REGISTERED_METRICS = {}


def build_metric_id(data_name, namespace, prefix: str, sub_type="", **kwargs) -> str:
    metric_id = f"{data_name}##{namespace}##{prefix}"
    if sub_type:
        metric_id = f"{metric_id}##{sub_type}"
    return metric_id


def clear_registered_metrics():
    REGISTERED_METRICS.clear()


def register_metric(namespace, data_name, sub_type="", prefix="", description="", time_filter=TimeFilterEnum.MINUTE1):
    """
    注册对应metric
    """

    def wrapped_view(func):
        def _wrapped_view(*args, **kwargs):
            result = func(*args, **kwargs)
            return result

        metric_id = build_metric_id(data_name, namespace, prefix, sub_type)
        if metric_id not in REGISTERED_METRICS:
            REGISTERED_METRICS[metric_id] = {
                "namespace": namespace,
                "data_name": data_name,
                "description": description,
                "prefix": prefix,
                "sub_type": sub_type,
                "method": wraps(func)(_wrapped_view),
                "time_filter": time_filter,
            }

        return REGISTERED_METRICS[metric_id]["method"]

    return wrapped_view


class Metric(object):
    """
    指标定义
    """

    def __init__(self, metric_name, metric_value, dimensions=None, timestamp=None):
        self.metric_name = metric_name
        self.metric_value = metric_value
        self.dimensions = dimensions
        self.timestamp = timestamp

    def to_bkmonitor_report(self, prefix="", namespace=""):
        if self.dimensions:
            dimensions = {key: str(value) for key, value in self.dimensions.items()}
        else:
            dimensions = {}

        if self.timestamp:
            return {
                "metrics": {self._get_actual_metric_name(prefix, namespace): self.metric_value},
                "target": settings.APP_CODE,
                "dimension": dimensions,
                "timestamp": int(self.timestamp * 1000),
            }
        else:
            return {
                "metrics": {self._get_actual_metric_name(prefix, namespace): self.metric_value},
                "target": settings.APP_CODE,
                "dimension": dimensions,
            }

    def _get_actual_metric_name(self, prefix="", namespace=""):
        if namespace:
            self.metric_name = "{}_{}".format(namespace, self.metric_name)
        if prefix:
            self.metric_name = "{}_{}".format(prefix, self.metric_name)
        return self.metric_name
