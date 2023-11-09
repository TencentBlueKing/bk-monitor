# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

import importlib
import logging
import time

from apps.log_measure.utils.metric import build_metric_id
from bk_monitor.utils.metric import REGISTERED_METRICS

logger = logging.getLogger("bk_monitor")


class MetricCollector(object):
    """
    实际采集
    """

    def __init__(self, collector_import_paths=None):
        if collector_import_paths and not REGISTERED_METRICS:
            for key in collector_import_paths:
                importlib.reload(importlib.import_module(key))

    def collect(self, namespaces=None, data_names=None):
        """
        采集入口
        """
        metric_methods = self.metric_filter(namespaces=namespaces, data_names=data_names)
        metric_groups = []
        for metric_method in metric_methods:
            try:
                begin_time = time.time()
                metric_groups.append(
                    {
                        "prefix": metric_method["prefix"],
                        "namespace": metric_method["namespace"],
                        "description": metric_method["description"],
                        "metrics": metric_method["method"](),
                        "data_name": metric_method["data_name"],
                    }
                )
                metric_id = build_metric_id(
                    metric_method["namespace"], metric_method["data_name"], metric_method["prefix"]
                )
                logger.info(
                    "[statistics_data] collect metric->[{}] took {} ms".format(
                        metric_id, int((time.time() - begin_time) * 1000)
                    ),
                )
            except Exception as e:  # pylint: disable=broad-except
                logger.exception(
                    "[statistics_data] collect metric->[{}] failed: {}".format(metric_method["namespace"], e)
                )

        return metric_groups

    @classmethod
    def metric_filter(cls, namespaces=None, data_names=None):
        metric_methods = []
        for metric_id, metric in REGISTERED_METRICS.items():
            if data_names and metric["data_name"] not in data_names:
                continue

            if namespaces and metric["namespace"] not in namespaces:
                continue
            metric_methods.append(metric)
        return metric_methods
